"""Probe: Claude headless judge — confidence scores + N=3 ensemble AVERAGE.

Per "judge decision":
  N=3 parallel stateless claude -p calls, each returning a JSON array of
  floats in [0,1]. Element-wise AVERAGE → final per-item scores.

5 trials per case to measure cross-trial stability of the averaged output.

Locks: model=claude-opus-4-7, effort=medium, confidence-score output, N=3.

Run from repo root:
  python tuning/gepa/probe_judge_stability_confidence_n3.py
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / ".env")

from rubrics import get_rubric_for_case  # noqa: E402
from judge_claude_headless import LEGACY_TAG  # noqa: E402
from probe_judge_stability import fabricated_pred  # noqa: E402
from probe_judge_stability_confidence import (  # noqa: E402
    stateless_judge_confidence, weighted_score_float,
)

N_ENSEMBLE = 3
TRIALS_PER_CASE = 5


def ensembled_confidence(case: dict, predicted: dict, rubric_items: list[dict],
                         tag: str, n: int = N_ENSEMBLE):
    """N parallel stateless calls + element-wise AVERAGE of confidence scores.

    Returns (avg_scores, per_call_scores, per_call_durs).
    """
    results: list[list[float] | None] = [None] * n
    durs: list[float] = [0.0] * n
    errors: list[BaseException | None] = [None] * n

    def _worker(i: int):
        try:
            results[i], data = stateless_judge_confidence(case, predicted, rubric_items, tag)
            durs[i] = data.get("duration_ms", 0) / 1000
        except BaseException as e:  # noqa: BLE001
            errors[i] = e

    threads = [threading.Thread(target=_worker, args=(i,), daemon=True) for i in range(n)]
    for t in threads: t.start()
    for t in threads: t.join()
    if any(e is not None for e in errors):
        raise next(e for e in errors if e is not None)
    valid = [r for r in results if r is not None]
    item_count = len(rubric_items)
    avg = [sum(r[i] for r in valid) / len(valid) for i in range(item_count)]
    return avg, [r or [] for r in results], durs


def run_case(label: str, case: dict, mode: str, tag: str):
    rubric = get_rubric_for_case(case)
    predicted = dict(case["correct_answer"]) if mode == "gold" else fabricated_pred()
    print(f"\n━━━ {label} — case={case['test_id']}  mode={mode}  tag={tag}  items={len(rubric)} ━━━")

    trial_avgs: list[list[float]] = []
    trial_scores: list[float] = []
    trial_durs: list[float] = []
    within_trial_max_spread: list[float] = []

    for t in range(TRIALS_PER_CASE):
        try:
            avg, per_call, durs = ensembled_confidence(case, predicted, rubric, tag)
        except Exception as e:
            print(f"  trial {t+1}: ERROR {type(e).__name__}: {str(e)[:120]}")
            continue
        ws = weighted_score_float(rubric, avg)
        trial_avgs.append(avg)
        trial_scores.append(ws)
        trial_durs.append(max(durs))
        # Within-trial spread: how much do the N=3 sample scores disagree per item?
        spreads = [max(r[i] for r in per_call) - min(r[i] for r in per_call) for i in range(len(rubric))]
        within_trial_max_spread.append(max(spreads))
        compact = "[" + ",".join(f"{s:.2f}" for s in avg) + "]"
        print(f"  trial {t+1}: avg={compact}  ws={ws:.3f}  "
              f"par_dur={trial_durs[-1]:.1f}s  max_within_spread={max(spreads):.2f}")

    if not trial_avgs:
        print("  ** all trials failed")
        return

    item_stdevs = []
    for i in range(len(rubric)):
        col = [r[i] for r in trial_avgs]
        item_stdevs.append(statistics.stdev(col) if len(col) > 1 else 0.0)
    print(f"  per-item σ across trials: [{', '.join(f'{s:.3f}' for s in item_stdevs)}]")
    print(f"  max per-item σ: {max(item_stdevs):.3f}   "
          f"mean per-item σ: {statistics.mean(item_stdevs):.3f}")
    print(f"  mean within-trial max-spread: {statistics.mean(within_trial_max_spread):.3f}")
    if len(trial_scores) > 1:
        print(f"  weighted score: mean={statistics.mean(trial_scores):.3f}  "
              f"stdev={statistics.stdev(trial_scores):.4f}  "
              f"range=[{min(trial_scores):.3f}, {max(trial_scores):.3f}]")


def main():
    print(f"Config: model=claude-opus-4-7, effort=medium, N={N_ENSEMBLE} confidence-avg, "
          f"trials/case={TRIALS_PER_CASE}")
    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    eval_cases = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]
    by_id = {s["test_id"]: s for s in seeds}
    eval_by_id = {c["test_id"]: c for c in eval_cases}

    plan = [
        ("single-tag GOLD",       "seed-P3-ex3", by_id,      "gold",        "#4_commits_regardless"),
        ("single-tag FABRICATED", "seed-P3-ex3", by_id,      "fabricated",  "#4_commits_regardless"),
        ("multi-tag #4 side",     "seed-P1-ex1", by_id,      "fabricated",  "#4_commits_regardless"),
        ("multi-tag #8 side",     "seed-P1-ex1", by_id,      "fabricated",  "#8_training_data_hallucination"),
    ]
    legacy_ids = [c["test_id"] for c in eval_cases
                  if c["test_id"].startswith("legacy-") and not (c.get("cannot_targets") or [])]
    if legacy_ids:
        plan.append(("legacy GOLD", legacy_ids[0], eval_by_id, "gold", LEGACY_TAG))

    for label, tid, src, mode, tag in plan:
        case = src.get(tid)
        if not case:
            print(f"\n** SKIP — {tid} not found")
            continue
        run_case(label, case, mode, tag)

    print("\nDone.")


if __name__ == "__main__":
    main()
