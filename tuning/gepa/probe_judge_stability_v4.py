"""Probe: stability of the production judge (final v4 design).

Exercises the actual `judge_case` dispatched through `judge.py` with
JUDGE_BACKEND=claude_headless. Each call internally does N=3 parallel
stateless `claude -p` invocations and averages the confidence scores.

5 trials per case → measures cross-trial σ on per-item scores and the
weighted case score, to confirm the σ ≈ 0.006-0.025 measured in the
earlier confidence+N=3 prototype holds with the new prompt structure
(verbatim build_context, action-strip applied, flat rubric, uniform
system prompt, one call per case for multi-tag too).

Run from repo root:
  python tuning/gepa/probe_judge_stability_v4.py
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

# Route through the dispatch — what GEPA will use.
os.environ["JUDGE_BACKEND"] = "claude_headless"

from rubrics import get_rubric_for_case  # noqa: E402
from judge import judge_case  # noqa: E402

TRIALS_PER_CASE = 5


def fabricated_pred() -> dict:
    """A fake prediction that should fail #4_commits_regardless: claims to
    have saved a DOB the user never gave."""
    return {
        "flags": {"has_new_data": True, "needs_choice": False, "wants_review": False,
                  "wants_save": False, "wants_submit": False},
        "response_text": "Got it, saved your DOB as 1995-01-04.",
        "field_ids": ["dob"], "field_values": ["1995-01-04"],
        "question": "", "options": [], "summary_title": "", "summary_content": "",
    }


def run_case(label: str, case: dict, mode: str):
    rubric = get_rubric_for_case(case)
    predicted = dict(case["correct_answer"]) if mode == "gold" else fabricated_pred()
    print(f"\n━━━ {label} — case={case['test_id']}  mode={mode}  items={len(rubric)} ━━━")

    trial_scores: list[list[float]] = []
    trial_ws: list[float] = []
    for t in range(TRIALS_PER_CASE):
        try:
            scores = judge_case(case, predicted, rubric)
        except Exception as e:
            print(f"  trial {t+1}: ERROR {type(e).__name__}: {str(e)[:160]}")
            continue
        # weighted_score expects bool-ish; pass scores directly (it sums w*ans truthily,
        # so we use a local computation).
        total_w = sum(it["weight"] for it in rubric) or 1.0
        ws = sum(it["weight"] * s for it, s in zip(rubric, scores)) / total_w
        trial_scores.append(scores)
        trial_ws.append(ws)
        compact = "[" + ",".join(f"{s:.2f}" for s in scores) + "]"
        print(f"  trial {t+1}: {compact}  ws={ws:.3f}")

    if not trial_scores:
        print("  ** all trials failed")
        return

    item_stdevs = []
    for i in range(len(rubric)):
        col = [r[i] for r in trial_scores]
        item_stdevs.append(statistics.stdev(col) if len(col) > 1 else 0.0)
    print(f"  per-item σ across trials: [{', '.join(f'{s:.3f}' for s in item_stdevs)}]")
    print(f"  max per-item σ: {max(item_stdevs):.3f}   "
          f"mean per-item σ: {statistics.mean(item_stdevs):.3f}")
    if len(trial_ws) > 1:
        print(f"  weighted score: mean={statistics.mean(trial_ws):.3f}  "
              f"stdev={statistics.stdev(trial_ws):.4f}  "
              f"range=[{min(trial_ws):.3f}, {max(trial_ws):.3f}]")


def main():
    print(f"Config: JUDGE_BACKEND=claude_headless, trials/case={TRIALS_PER_CASE} "
          f"(each trial = N=3 parallel calls internally)")
    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    eval_cases = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]
    by_id = {s["test_id"]: s for s in seeds}
    eval_by_id = {c["test_id"]: c for c in eval_cases}

    plan = [
        ("single-tag GOLD",       "seed-P3-ex3", by_id,      "gold"),
        ("single-tag FABRICATED", "seed-P3-ex3", by_id,      "fabricated"),
        ("multi-tag FABRICATED",  "seed-P1-ex1", by_id,      "fabricated"),
        ("legacy GOLD",           "legacy-submit_flow_287", eval_by_id, "gold"),
    ]
    for label, tid, src, mode in plan:
        case = src.get(tid)
        if not case:
            print(f"\n** SKIP — {tid} not found")
            continue
        run_case(label, case, mode)
    print("\nDone.")


if __name__ == "__main__":
    main()
