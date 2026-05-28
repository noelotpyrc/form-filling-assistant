"""OpenRouter judge — same prompt design as judge_claude_headless, different transport.

Mirrors judge_claude_headless.py:
  - Uniform system prompt
  - User prompt = case_id + verbatim MODEL INPUT (build_context output) + GOLD + PREDICTED + numbered rubric
  - One judge call per case
  - N parallel threaded calls → element-wise averaged confidence scores in [0, 1]
  - Stateless (each call is independent)

Differences:
  - Transport: openai.OpenAI client pointed at OpenRouter
  - No subprocess; uses the same dependency stack as the existing openai-backend judge

Env knobs:
  JUDGE_OPENROUTER_MODEL   — model id (default: moonshotai/kimi-k2.6)
  JUDGE_OPENROUTER_BASE_URL — API base URL (default: https://openrouter.ai/api/v1)
  JUDGE_OPENROUTER_N       — ensemble size per decision (default: 3)
  JUDGE_OPENROUTER_TIMEOUT — per-call timeout in seconds (default: 120)
  OPENROUTER_API_KEY       — credential
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))

# Reuse the exact same prompt structure as the claude_headless judge so a
# variance / lift comparison between backends is apples-to-apples.
from judge_claude_headless import SYSTEM_PROMPT, build_user_prompt, _parse_floats  # noqa: E402

MODEL = os.getenv("JUDGE_OPENROUTER_MODEL", "moonshotai/kimi-k2.6")
BASE_URL = os.getenv("JUDGE_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
N_ENSEMBLE = int(os.getenv("JUDGE_OPENROUTER_N", "3"))
TIMEOUT_SEC = int(os.getenv("JUDGE_OPENROUTER_TIMEOUT", "120"))
# Temperature override. Some models (e.g. gpt-5) only accept the default
# value (1.0) and reject explicit overrides. Set to empty string to omit
# the parameter entirely; numeric value to send explicitly. Default 0 for
# near-deterministic judging.
_TEMP_ENV = os.getenv("JUDGE_OPENROUTER_TEMPERATURE", "0")
TEMPERATURE: float | None = None if _TEMP_ENV == "" else float(_TEMP_ENV)


_CLIENT = None


def _client():
    global _CLIENT
    if _CLIENT is None:
        import openai
        # Pick the right credential for the configured endpoint.
        if "openrouter" in BASE_URL:
            api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENROUTER_API_KEY not set")
        else:
            # OpenAI-compatible endpoint (api.openai.com or other) — use OpenAI key.
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY not set")
        _CLIENT = openai.OpenAI(api_key=api_key, base_url=BASE_URL, timeout=TIMEOUT_SEC)
    return _CLIENT


def _one_call(user_prompt: str, expected_n: int, model: str) -> list[float]:
    client = _client()
    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    if TEMPERATURE is not None:
        kwargs["temperature"] = TEMPERATURE
    resp = client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    return _parse_floats(text, expected_n)


def judge_case(case: dict, predicted: dict, rubric_items: list[dict],
               model: str | None = None) -> list[float]:
    """Score a case — N parallel calls, element-wise average over the calls
    that succeed.

    Tolerates partial-ensemble failures: if some calls fail (e.g., DeepSeek
    returns malformed JSON), we average over the successful ones. Only raise
    when ALL N calls fail — at which point the outer retry policy in
    judge.judge_case kicks in.
    """
    if not rubric_items:
        return []
    user_prompt = build_user_prompt(case, predicted, rubric_items)
    m = model or MODEL
    n = N_ENSEMBLE
    results: list[list[float] | None] = [None] * n
    errors: list[BaseException | None] = [None] * n

    def _worker(i: int):
        try:
            results[i] = _one_call(user_prompt, len(rubric_items), m)
        except BaseException as e:  # noqa: BLE001
            errors[i] = e

    threads = [threading.Thread(target=_worker, args=(i,), daemon=True) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    valid = [r for r in results if r is not None]
    if not valid:
        # All N calls failed — surface the first error so the outer retry
        # logic in judge.judge_case can retry the whole judge_case.
        raise next(e for e in errors if e is not None)

    if len(valid) < n:
        n_failed = n - len(valid)
        first_err = next((e for e in errors if e is not None), None)
        sys.stderr.write(
            f"[judge_openrouter] partial ensemble: {n_failed}/{n} calls failed, "
            f"averaging over {len(valid)} successes. First error: "
            f"{type(first_err).__name__}: {str(first_err)[:120]}\n"
        )
        sys.stderr.flush()

    item_count = len(rubric_items)
    return [sum(r[i] for r in valid) / len(valid) for i in range(item_count)]


# CLI smoke
if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    load_dotenv(REPO / ".env")
    from rubrics import get_rubric_for_case

    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="seed-P3-ex3")
    args = ap.parse_args()

    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    case = next(s for s in seeds if s["test_id"] == args.seed)
    rubric = get_rubric_for_case(case)
    predicted = dict(case["correct_answer"])
    print(f"Seed: {args.seed}  N={N_ENSEMBLE}  model={MODEL}  base_url={BASE_URL}")
    scores = judge_case(case, predicted, rubric)
    print(f"Scores: {[round(s, 3) for s in scores]}")
    for it, s in zip(rubric, scores):
        mark = "✓" if s >= 0.999 else ("✗" if s <= 0.001 else f"~{s:.2f}")
        print(f"  {mark} [{it['weight']}] {it['id']}")
