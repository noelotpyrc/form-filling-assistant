#!/usr/bin/env python3
"""
Paraphrase intent seeds with gpt-4o-mini to build the template banks.

Reads:
    tuning/rl/intent_seeds.json
        {intent: {sub_angle: [seed_strings]}, ...}

Writes:
    tuning/rl/intent_templates.json
        {intent: {sub_angle: [seed + paraphrases]}, ...}

Per-seed behavior: ask gpt-4o-mini for N paraphrases that preserve the seed's
underlying intent and keep it natural/conversational.  We keep the original
seed too, so each bucket has (seed + N paraphrases).

Usage:
    cd python
    uv run python ../tuning/rl/mutate_intent_seeds.py --paraphrases 10 --preview 3
    uv run python ../tuning/rl/mutate_intent_seeds.py --paraphrases 10

Cost estimate (gpt-4o-mini): ~258 seeds × 1 call × ~$0.0003/call ≈ $0.10.

Model is configured in call_openai below; change it there to regenerate with a
different LLM.
"""

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
SEEDS_PATH = PROJECT_ROOT / "tuning" / "rl" / "intent_seeds.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "tuning" / "rl" / "intent_templates.json"

# Load OPENAI_API_KEY from .env
from dotenv import load_dotenv  # noqa: E402
load_dotenv(PROJECT_ROOT / ".env")


# ══════════════════════════════════════════════════════════════════════
# Mutation prompt — one per intent class
# ══════════════════════════════════════════════════════════════════════

INTENT_DESCRIPTIONS = {
    "review": (
        "The user wants to see a summary of what they've filled in so far — progress, "
        "current state, or a recap.  They are NOT providing new information and NOT "
        "asking to submit."
    ),
    "close": (
        "The user wants to finalize the form — either by submitting it or by saving it "
        "as a draft to resume later.  They are signaling 'I'm done (for now)'."
    ),
    "clarify": (
        "The user gave information that is underspecified, ambiguous, or vague.  The "
        "assistant will need to ask a follow-up question before it can extract anything."
    ),
    "converse": (
        "The user is making conversation — greetings, small talk, meta-questions about "
        "the form itself, or simple acknowledgments.  They are NOT providing form data, "
        "NOT asking for a review, and NOT signaling completion."
    ),
}


SYSTEM_PROMPT = """You are a data-augmentation assistant. You generate natural, conversational paraphrases of user messages for a form-filling chatbot's training data.

Rules:
1. Preserve the underlying intent exactly — the paraphrase must unambiguously trigger the same action the original would.
2. Vary surface form aggressively: different length, tone (formal/casual/frustrated/curious), sentence structure, hedging, disfluencies ("hmm", "lol", "ugh"), multi-clause vs. terse.
3. Keep it natural — like real users typing in a web form chat, not like button labels or customer-service scripts.
4. Do not copy the original verbatim.
5. Each paraphrase must be standalone — no lead-in like "Paraphrase: …".
6. Output strict JSON only: {"paraphrases": [string, string, ...]}. No markdown fences, no commentary."""


def build_user_prompt(seed: str, intent: str, sub_angle: str, n: int) -> str:
    intent_desc = INTENT_DESCRIPTIONS[intent]
    return f"""Intent class: `{intent}` — {intent_desc}

Sub-angle: `{sub_angle}`

Original user message (the seed):
{json.dumps(seed)}

Generate {n} natural paraphrases of this seed.  Each one must still clearly express the `{intent}` intent and sit within the `{sub_angle}` sub-angle, but should sound like a different real user wrote it.  Vary length (from 3 words to 40+ words), vary formality, include realistic conversational markers where appropriate.

Return JSON only:
{{"paraphrases": ["...", "...", ...]}}"""


# ══════════════════════════════════════════════════════════════════════
# OpenAI call
# ══════════════════════════════════════════════════════════════════════

_openai_client = None

def get_openai_client():
    global _openai_client
    if _openai_client is None:
        import openai
        _openai_client = openai.AsyncOpenAI()
    return _openai_client


async def call_openai(system: str, user: str, semaphore: asyncio.Semaphore,
                     retries: int = 3) -> str | None:
    """Call gpt-4o-mini with rate limiting and retries."""
    async with semaphore:
        for attempt in range(retries):
            try:
                client = get_openai_client()
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    max_tokens=2000,
                    temperature=0.9,  # higher temp for diversity
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format={"type": "json_object"},
                )
                return response.choices[0].message.content
            except Exception as e:
                err_str = str(e)
                if "rate" in err_str.lower() or "429" in err_str:
                    wait = (attempt + 1) * 5
                    print(f"  Rate limited, waiting {wait}s "
                          f"(attempt {attempt+1}/{retries})", file=sys.stderr)
                    await asyncio.sleep(wait)
                    continue
                print(f"  OpenAI error: {err_str[:200]}", file=sys.stderr)
                return None
        return None


# ══════════════════════════════════════════════════════════════════════
# Parse / validate
# ══════════════════════════════════════════════════════════════════════

def parse_paraphrases(response_text: str, seed: str, n_expected: int) -> list[str]:
    """Parse gpt-4o-mini JSON response; return validated paraphrase list.

    Silently drops entries that are empty, too short, or duplicate the seed.
    """
    if not response_text:
        return []

    text = response_text.strip()
    # Strip markdown fences just in case
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return []

    candidates = obj.get("paraphrases", [])
    if not isinstance(candidates, list):
        return []

    seed_norm = seed.strip().lower()
    seen = {seed_norm}
    clean = []
    for c in candidates:
        if not isinstance(c, str):
            continue
        s = c.strip()
        if len(s) < 3:
            continue
        norm = s.lower()
        if norm in seen:
            continue
        seen.add(norm)
        clean.append(s)
    return clean


# ══════════════════════════════════════════════════════════════════════
# Main pipeline
# ══════════════════════════════════════════════════════════════════════

async def main_async(args):
    seeds_doc = json.load(open(SEEDS_PATH))

    # Flatten seeds into (intent, sub_angle, seed) tuples
    tasks = []
    for intent, sub_angles in seeds_doc.items():
        if intent.startswith("_"):
            continue
        if not isinstance(sub_angles, dict):
            continue
        for sub_angle, seed_list in sub_angles.items():
            if sub_angle.startswith("_"):
                continue
            if not isinstance(seed_list, list):
                continue
            for seed in seed_list:
                tasks.append((intent, sub_angle, seed))

    print(f"Loaded {len(tasks)} seeds across "
          f"{len(seeds_doc)} intent classes")
    by_intent = Counter(t[0] for t in tasks)
    for k, v in by_intent.most_common():
        print(f"  {k:>10s}: {v}")

    if args.limit and args.limit < len(tasks):
        # Sample across intents so the test run covers all classes
        by_intent_tasks: dict[str, list] = {}
        for t in tasks:
            by_intent_tasks.setdefault(t[0], []).append(t)
        # Take proportional slice from each intent, round-robin
        picked = []
        per_intent = max(1, args.limit // len(by_intent_tasks))
        for intent, its in by_intent_tasks.items():
            picked.extend(its[:per_intent])
        tasks = picked[: args.limit]
        print(f"\n[--limit {args.limit}] Running on subset of {len(tasks)} seeds")

    if args.preview:
        print(f"\n=== PREVIEW — {args.preview} prompts ===")
        for intent, sub_angle, seed in tasks[: args.preview]:
            prompt = build_user_prompt(seed, intent, sub_angle, args.paraphrases)
            print(f"\n[{intent} / {sub_angle}]")
            print(f"  seed: {seed[:100]}")
            print(f"  prompt length: {len(prompt)} chars")
        return

    # ── Async fan-out ──
    semaphore = asyncio.Semaphore(args.concurrency)
    start_time = datetime.now()
    errors = 0
    results: dict[tuple[str, str, str], list[str]] = {}

    async def process_one(intent, sub_angle, seed):
        nonlocal errors
        user_prompt = build_user_prompt(seed, intent, sub_angle, args.paraphrases)
        response = await call_openai(SYSTEM_PROMPT, user_prompt, semaphore)
        if response is None:
            errors += 1
            return (intent, sub_angle, seed, [])
        paraphrases = parse_paraphrases(response, seed, args.paraphrases)
        if not paraphrases:
            errors += 1
        return (intent, sub_angle, seed, paraphrases)

    # Process in batches for progress reporting
    batch_size = 30
    total = len(tasks)
    for batch_start in range(0, total, batch_size):
        batch = tasks[batch_start : batch_start + batch_size]
        batch_t0 = datetime.now()
        batch_results = await asyncio.gather(*[
            process_one(*t) for t in batch
        ])
        for intent, sub_angle, seed, paras in batch_results:
            results[(intent, sub_angle, seed)] = paras

        done = batch_start + len(batch)
        elapsed = (datetime.now() - start_time).total_seconds()
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        total_paras = sum(len(v) for v in results.values())
        batch_elapsed = (datetime.now() - batch_t0).total_seconds()

        print(f"  [{datetime.now():%H:%M:%S}] {done}/{total} seeds "
              f"({batch_elapsed:.1f}s/batch) | "
              f"paraphrases: {total_paras} | errors: {errors} | "
              f"ETA: {eta:.0f}s")

    # ── Assemble output ──
    # Preserve the same {intent: {sub_angle: [strings]}} structure.
    # Each sub_angle list = concat(seeds + their paraphrases), deduped.
    out_doc: dict = {}
    for intent, sub_angles in seeds_doc.items():
        if intent.startswith("_") or not isinstance(sub_angles, dict):
            continue
        out_doc[intent] = {}
        for sub_angle, seed_list in sub_angles.items():
            if sub_angle.startswith("_") or not isinstance(seed_list, list):
                continue
            entries = []
            seen = set()
            for seed in seed_list:
                # seed itself
                k = seed.strip().lower()
                if k not in seen:
                    seen.add(k)
                    entries.append(seed)
                # paraphrases
                for p in results.get((intent, sub_angle, seed), []):
                    pk = p.strip().lower()
                    if pk not in seen:
                        seen.add(pk)
                        entries.append(p)
            out_doc[intent][sub_angle] = entries

    # ── Stats ──
    print(f"\n{'='*60}")
    print(f"Done. Total elapsed: "
          f"{(datetime.now() - start_time).total_seconds():.1f}s")
    for intent, sub_angles in out_doc.items():
        total_intent = sum(len(v) for v in sub_angles.values())
        seed_count = sum(len(seeds_doc[intent][s]) for s in sub_angles)
        print(f"  {intent:>10s}: {total_intent} entries "
              f"({seed_count} seeds + {total_intent - seed_count} paraphrases)")

    out_path = Path(args.output or DEFAULT_OUTPUT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out_doc, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Paraphrase intent seeds to build template banks")
    parser.add_argument("--paraphrases", type=int, default=10,
                        help="Paraphrases requested per seed")
    parser.add_argument("--concurrency", type=int, default=20,
                        help="Max concurrent OpenAI calls")
    parser.add_argument("--output", type=str, default=None,
                        help="Output JSON path")
    parser.add_argument("--preview", type=int, default=0,
                        help="Preview N mutation prompts (dry run, no API calls)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only process first N seeds (0 = all). For test runs.")
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
