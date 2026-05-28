#!/usr/bin/env python3
"""
Generate GRPO training data for the IntentDecider module.

Why a dedicated intent dataset:
    SFT diagnosis (doc-13) showed intent routing is the dominant failure mode.
    Per-class accuracy on the 300-case test set:
        gather   86.4%  converse 87.8%
        close    51.7%  clarify  44.4%   review 4.8%
    review/clarify/close get "pulled" toward converse, which silently skips the
    downstream modules.  This script produces (prompt, gold_intent) rows for
    GRPO rewards to re-balance that bias.

Row schema (one per line, JSONL):
    {
      "prompt": [ {role: system, content: ...}, {role: user, content: ...} ],
      "gold_intent": "review",
      "module": "intent_decider",
      "source": "real_atomic" | "synthetic_review" | "synthetic_close",
      "meta": { "session_id": ..., "turn": ..., "sub_turn": ... }
    }

`prompt` is built with DSPy's ChatAdapter against IntentDeciderSignature, so the
model sees the exact format it will see at inference (same signature, same
field markers, same `[[ ## completed ## ]]` closer).

Sources:
    1. real_atomic  — every train-safe atomic turn (test-case session+turn pairs
                      excluded) produces one row labeled with infer_intent().
    2. synthetic_review / synthetic_close — programmatic turns for the two
                      weakest classes.  Bodies are drawn from template banks of
                      natural user messages ("where are we?", "submit please",
                      etc.) and dropped onto random form states sampled from
                      train-safe atomic turns, so the context is realistic
                      while the user message unambiguously signals review/close.

This script does NOT call an LLM.  A follow-up `mutate_intent_data.py` can
paraphrase weak-class rows if we want to grow them further.

Usage:
    cd python
    uv run python ../tuning/rl/gen_intent_data.py --stats
    uv run python ../tuning/rl/gen_intent_data.py --output ../tuning/rl/grpo_train_intent.jsonl
"""

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tuning" / "sft"))
sys.path.insert(0, str(PROJECT_ROOT / "tuning" / "dspy"))

import dspy
from dspy.adapters.chat_adapter import ChatAdapter

# Reuse the exact signatures + context builder SFT used.  This guarantees the
# `prompt` we emit matches what DSPy sends at inference.
from gen_format_data import (  # noqa: E402
    IntentDeciderSignature,
    build_context,
    FORM_CONTEXT,
)
from optimize_prompt import infer_intent  # noqa: E402


ATOMIC_PATH = PROJECT_ROOT / "tuning" / "data" / "atomic.jsonl"
TEST_CASES_PATH = PROJECT_ROOT / "tuning" / "data" / "test-cases.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "tuning" / "rl" / "grpo_train_intent.jsonl"

adapter = ChatAdapter()


# ══════════════════════════════════════════════════════════════════════
# Data loading
# ══════════════════════════════════════════════════════════════════════

def load_test_keys() -> set[tuple[str, int]]:
    """Return (session_id, turn) pairs that appear in the 300-case test set.

    These must be excluded from training so eval stays honest.
    """
    keys: set[tuple[str, int]] = set()
    with open(TEST_CASES_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            keys.add((r["session_id"], int(r["turn"])))
    return keys


def load_atomic_train_safe() -> list[dict]:
    """Load atomic.jsonl minus rows whose (session_id, turn) is in test-cases."""
    test_keys = load_test_keys()
    rows = []
    with open(ATOMIC_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if (r["session_id"], int(r["turn"])) in test_keys:
                continue
            rows.append(r)
    return rows


# ══════════════════════════════════════════════════════════════════════
# Row builder
# ══════════════════════════════════════════════════════════════════════

def make_row(context: str, user_message: str, gold_intent: str, source: str,
             meta: dict | None = None) -> dict:
    """Format one intent_decider training row using DSPy's ChatAdapter."""
    messages = adapter.format(
        signature=IntentDeciderSignature,
        demos=[],
        inputs={"context": context, "user_message": user_message},
    )
    return {
        "prompt": messages,          # [system, user] — matches inference
        "gold_intent": gold_intent,
        "module": "intent_decider",
        "source": source,
        "meta": meta or {},
    }


# ══════════════════════════════════════════════════════════════════════
# 1) Real-atomic baseline — one row per train-safe turn
# ══════════════════════════════════════════════════════════════════════

def gen_real_atomic_rows(atomic_rows: list[dict]) -> list[dict]:
    rows = []
    for t in atomic_rows:
        gold = infer_intent(t)
        ctx = build_context(t)
        row = make_row(
            context=ctx,
            user_message=t["user_message"],
            gold_intent=gold,
            source="real_atomic",
            meta={
                "session_id": t["session_id"],
                "turn": int(t["turn"]),
                "sub_turn": int(t.get("sub_turn", 0)),
                "category": t.get("category", ""),
            },
        )
        rows.append(row)
    return rows


# ══════════════════════════════════════════════════════════════════════
# 2) Synthetic weak-class rows — review / close
# ══════════════════════════════════════════════════════════════════════

# Natural user phrasings that should unambiguously trigger `review`.
# Sourced from patterns in the 19/21 review→converse confusions in doc-13.
REVIEW_USER_MSGS = [
    "Can you show me what we've filled in so far?",
    "What's my progress so far?",
    "Where are we in the form?",
    "Show me the current state of my application.",
    "Can I see a summary of everything so far?",
    "Recap what I've provided.",
    "Let me see what's been filled.",
    "What have we completed?",
    "Give me a review of the form so far.",
    "Show me the draft.",
    "Let's review before I continue.",
    "Display what you have on file for me.",
    "Can we look at everything together?",
    "I want to double-check what's in the form.",
    "Print out what I've entered.",
    "Recap please.",
    "Show progress.",
    "Summary so far?",
    "What's filled in?",
    "Can you list out all the fields I've answered?",
    # Draft-restore / resume-flavored prompts (these are the ones SFT missed).
    "Draft restored. 15 fields previously filled.",
    "Draft restored. Continue?",
    "Welcome back — looks like you have a saved draft.",
    "Resuming your session — here's where you left off.",
    "I notice you had a draft. Can you show me what's in it?",
    # Recommendation-letter style meta checks (also missed by SFT).
    "Recommendation letters still shows 0/4 — is that expected?",
    "Why does the progress bar show 40%?",
    "How many fields are still empty?",
    "Which sections are incomplete?",
    "What's left for me to fill in?",
]

# Natural user phrasings that should unambiguously trigger `close`.
CLOSE_USER_MSGS = [
    "I think I'm done. Can I submit?",
    "Submit please.",
    "Let's send it.",
    "I'm ready to submit the application.",
    "Submit.",
    "Save my progress as a draft.",
    "Save draft please.",
    "Save and come back later.",
    "I need to stop here — save what I have.",
    "Can we save this and I'll finish tomorrow?",
    "Everything looks good — submit it.",
    "Go ahead and submit.",
    "Finalize and send.",
    "Okay I'm finished, submit now.",
    "Save the draft and I'll return.",
    "Submit the form.",
    "Please submit it now.",
    "Ready to submit.",
    "Looks complete — send it in.",
    "I'm all set, submit.",
    "Draft, please — I'll finish later.",
    "Save as draft.",
    "Save it and I'll come back.",
    "Pause here and save.",
    "Send my application.",
]


def _pick_form_state(atomic_rows: list[dict], min_fields: int = 8) -> dict:
    """Sample a form_state_before from atomic that looks review-worthy."""
    candidates = [t for t in atomic_rows
                  if len(t.get("form_state_before", {})) >= min_fields]
    if not candidates:
        candidates = atomic_rows
    return random.choice(candidates)


def gen_synthetic_review_rows(atomic_rows: list[dict], n: int) -> list[dict]:
    """Build n synthetic review-intent rows.

    Pick a realistic form_state from atomic (≥8 filled fields makes a review
    turn plausible) and drop a review-trigger user message onto it.  History is
    taken from the sampled turn so the context hangs together.
    """
    rows = []
    for i in range(n):
        base = _pick_form_state(atomic_rows, min_fields=8)
        user_msg = random.choice(REVIEW_USER_MSGS)

        # Build a synthetic turn by reusing base's state + history
        fake_turn = {
            "form_state_before": base.get("form_state_before", {}),
            "conversation_history": base.get("conversation_history", []),
        }
        ctx = build_context(fake_turn)

        rows.append(make_row(
            context=ctx,
            user_message=user_msg,
            gold_intent="review",
            source="synthetic_review",
            meta={"template_idx": i, "base_session": base["session_id"]},
        ))
    return rows


def gen_synthetic_close_rows(atomic_rows: list[dict], n: int) -> list[dict]:
    """Build n synthetic close-intent rows.

    Close is most natural when the form is nearly complete, so we prefer base
    turns with many filled fields.
    """
    rows = []
    for i in range(n):
        base = _pick_form_state(atomic_rows, min_fields=15)
        user_msg = random.choice(CLOSE_USER_MSGS)

        fake_turn = {
            "form_state_before": base.get("form_state_before", {}),
            "conversation_history": base.get("conversation_history", []),
        }
        ctx = build_context(fake_turn)

        rows.append(make_row(
            context=ctx,
            user_message=user_msg,
            gold_intent="close",
            source="synthetic_close",
            meta={"template_idx": i, "base_session": base["session_id"]},
        ))
    return rows


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════

def summarize(rows: list[dict]) -> None:
    by_intent = Counter(r["gold_intent"] for r in rows)
    by_source = Counter(r["source"] for r in rows)
    print(f"Total rows: {len(rows)}")
    print("\nBy gold_intent:")
    for k, v in by_intent.most_common():
        pct = 100 * v / len(rows) if rows else 0.0
        print(f"  {k:>10s}: {v:>5}  ({pct:5.1f}%)")
    print("\nBy source:")
    for k, v in by_source.most_common():
        print(f"  {k:>22s}: {v}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate GRPO training data for IntentDecider")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT),
                        help="Output JSONL path")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-synthetic-review", type=int, default=400,
                        help="Synthetic review-intent rows (SFT got 4.8% here)")
    parser.add_argument("--num-synthetic-close", type=int, default=250,
                        help="Synthetic close-intent rows (SFT got 51.7% here)")
    parser.add_argument("--stats", action="store_true",
                        help="Print distribution, don't write output")
    parser.add_argument("--preview", type=int, default=0,
                        help="Print N example rows (pretty)")
    args = parser.parse_args()

    random.seed(args.seed)

    print(f"Loading atomic.jsonl (excluding test-case session+turn pairs)...")
    atomic = load_atomic_train_safe()
    print(f"  train-safe atomic turns: {len(atomic)}")

    print("\nGenerating real_atomic rows...")
    real_rows = gen_real_atomic_rows(atomic)
    print(f"  {len(real_rows)} rows")

    print(f"\nGenerating synthetic_review rows (n={args.num_synthetic_review})...")
    review_rows = gen_synthetic_review_rows(atomic, args.num_synthetic_review)

    print(f"Generating synthetic_close rows (n={args.num_synthetic_close})...")
    close_rows = gen_synthetic_close_rows(atomic, args.num_synthetic_close)

    all_rows = real_rows + review_rows + close_rows
    random.shuffle(all_rows)

    print("\n" + "=" * 60)
    summarize(all_rows)
    print("=" * 60)

    if args.preview:
        print(f"\nPreview ({args.preview} rows):")
        for r in all_rows[: args.preview]:
            print("\n" + "-" * 60)
            print(f"source={r['source']}  gold_intent={r['gold_intent']}")
            print("SYSTEM:", r["prompt"][0]["content"][:300], "...")
            print("USER:", r["prompt"][1]["content"][:300], "...")

    if args.stats:
        print("\n[--stats] Not writing output.")
        return

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(all_rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
