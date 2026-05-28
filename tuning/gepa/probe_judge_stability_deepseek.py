"""Probe: OpenRouter DeepSeek judge with temperature=0 — does temperature=0
produce stable scores across independent identical calls?

Mirrors probe_judge_stability.py but routes through the existing OpenAI/
OpenRouter HTTP path in judge.py instead of Claude Code CLI.

Sets:
  JUDGE_BACKEND=openai  (default)
  JUDGE_BASE_URL=https://openrouter.ai/api/v1
  JUDGE_MODEL=deepseek/deepseek-v4-flash
  JUDGE_TEMPERATURE=0

Run from repo root:
  python tuning/gepa/probe_judge_stability_deepseek.py
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / ".env")

# Force OpenRouter DeepSeek with temp=0 for this probe.
os.environ["JUDGE_BACKEND"] = "openai"
os.environ["JUDGE_BASE_URL"] = "https://openrouter.ai/api/v1"
os.environ["JUDGE_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["JUDGE_TEMPERATURE"] = "0"

from rubrics import get_rubric_for_case  # noqa: E402
from judge import judge_case  # noqa: E402
from probe_judge_stability import fabricated_pred, weighted_score  # noqa: E402

RUNS_PER_CASE = 5
LEGACY_TAG = "(legacy)"


def run_case(label: str, case: dict, mode: str):
    rubric = get_rubric_for_case(case)
    if mode == "gold":
        predicted = dict(case["correct_answer"])
    else:
        predicted = fabricated_pred()
    tags = case.get("cannot_targets") or []
    print(f"\n━━━ {label} — case={case['test_id']}  mode={mode}  "
          f"tags={tags or [LEGACY_TAG]}  items={len(rubric)} ━━━")
    rows: list[list[bool]] = []
    scores: list[float] = []
    for r in range(RUNS_PER_CASE):
        try:
            answers = judge_case(case, predicted, rubric)
        except Exception as e:
            print(f"  run {r+1}: ERROR {type(e).__name__}: {e}")
            continue
        bools = [bool(a) for a in answers]
        score = weighted_score(rubric, bools)
        rows.append(bools)
        scores.append(score)
        joined = "".join("Y" if a else "n" for a in bools)
        print(f"  run {r+1}: [{joined}] score={score:.3f}")
    if not rows:
        print("  ** all runs failed")
        return
    flips = []
    for i in range(len(rubric)):
        col = [r[i] for r in rows]
        unanimous = all(col) or not any(col)
        flips.append(0 if unanimous else sum(1 for v in col if v != col[0]))
    flip_total = sum(1 for f in flips if f > 0)
    print(f"  per-item flips: {flips}  ({flip_total}/{len(flips)} items disagreed)")
    if len(scores) > 1:
        print(f"  score: mean={statistics.mean(scores):.3f}  "
              f"stdev={statistics.stdev(scores):.4f}  "
              f"range=[{min(scores):.3f}, {max(scores):.3f}]")


def main():
    print(f"Config: model={os.environ['JUDGE_MODEL']}, "
          f"temperature={os.environ['JUDGE_TEMPERATURE']}, "
          f"runs/case={RUNS_PER_CASE}")
    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    eval_cases = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]
    by_id = {s["test_id"]: s for s in seeds}
    eval_by_id = {c["test_id"]: c for c in eval_cases}

    plan = [
        ("single-tag GOLD",       "seed-P3-ex3", by_id,      "gold"),
        ("single-tag FABRICATED", "seed-P3-ex3", by_id,      "fabricated"),
        ("multi-tag FABRICATED",  "seed-P1-ex1", by_id,      "fabricated"),
    ]
    legacy_ids = [c["test_id"] for c in eval_cases
                  if c["test_id"].startswith("legacy-") and not (c.get("cannot_targets") or [])]
    if legacy_ids:
        plan.append(("legacy GOLD", legacy_ids[0], eval_by_id, "gold"))

    for label, tid, src, mode in plan:
        case = src.get(tid)
        if not case:
            print(f"\n** SKIP — {tid} not found")
            continue
        run_case(label, case, mode)

    print("\nDone.")


if __name__ == "__main__":
    main()
