"""Measure per-case judge variance within one script run.

For each of N picked val cases, score the SAME persisted prediction M times
sequentially using the exact same judge path used by optimize.py and
eval_candidate.py: `score_case(case, pred, use_judge=True)` with
JUDGE_BACKEND=claude_headless and judge_claude_headless defaults
(N_ENSEMBLE=3, claude-opus-4-7, effort=medium).

Report all M scores + mean/σ/min/max per sample so we can compare
per-sample within-run variance against the drift we observed across runs.

Run from repo root:
  JUDGE_BACKEND=claude_headless python/.venv/bin/python -u \\
    tuning/gepa/measure_judge_variance.py \\
    --paired tuning/gepa/results/paired_preds_cand2.json \\
    --test-ids legacy-single_field_239 legacy-ask_choice_only_23 \\
               legacy-question_no_actions_227 legacy-single_field_265 \\
               legacy-choice_selection_75 \\
    --m 10
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO / "tuning" / "dspy"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / ".env")

import metric as gepa_metric  # noqa: E402

FLAG_NAMES = ["has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit"]


def to_nested(flat: dict) -> dict:
    return {
        "flags": {f: bool(flat.get(f, False)) for f in FLAG_NAMES},
        "response_text": flat.get("response_text", "") or "",
        "field_ids": list(flat.get("field_ids", []) or []),
        "field_values": list(flat.get("field_values", []) or []),
        "question": flat.get("question", "") or "",
        "options": list(flat.get("options", []) or []),
        "summary_title": flat.get("summary_title", "") or "",
        "summary_content": flat.get("summary_content", "") or "",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paired", required=True)
    ap.add_argument("--test-ids", nargs="+", required=True)
    ap.add_argument("--m", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    payload = json.load(open(args.paired))
    by_id = {r["test_id"]: r for r in payload["rows"]}

    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    ec = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]
    case_by_id = {c["test_id"]: c for c in seeds + ec}

    judge_label = os.getenv("JUDGE_BACKEND", "openai")
    print(f"Judge backend: {judge_label}")
    print(f"M trials per sample: {args.m}\n")
    print(f"Env captured: {gepa_metric.capture_judge_env()}\n")

    results: list[dict] = []
    for tid in args.test_ids:
        if tid not in by_id:
            print(f"!! {tid}: not in paired file")
            continue
        if tid not in case_by_id:
            print(f"!! {tid}: not in seeds/eval_cases")
            continue
        row = by_id[tid]
        case = case_by_id[tid]
        pred = to_nested(row["cand_pred"])
        scores: list[float] = []
        t0 = time.time()
        print(f"── {tid}  (val_idx={row['val_idx']}) ──")
        for i in range(args.m):
            r = gepa_metric.score_case(case, pred, use_judge=True)
            s = float(r["score"])
            scores.append(s)
            print(f"  trial {i+1:2d}/{args.m}  score={s:.4f}")
        dt = time.time() - t0
        mean = sum(scores) / len(scores)
        sd = statistics.pstdev(scores) if len(scores) > 1 else 0.0
        mn, mx = min(scores), max(scores)
        spread = mx - mn
        print(f"  mean={mean:.4f}  σ={sd:.4f}  min={mn:.4f}  max={mx:.4f}  spread={spread:.4f}  ({dt:.1f}s)\n")
        results.append({
            "test_id": tid,
            "val_idx": row["val_idx"],
            "scores": scores,
            "mean": mean,
            "sd": sd,
            "min": mn,
            "max": mx,
            "spread": spread,
            "duration_sec": dt,
        })

    print("══ Summary ══")
    print(f"{'test_id':<38} {'mean':>8} {'σ':>8} {'spread':>8}")
    print("-"*64)
    for r in results:
        print(f"{r['test_id']:<38} {r['mean']:>8.4f} {r['sd']:>8.4f} {r['spread']:>8.4f}")

    if args.out:
        Path(args.out).write_text(json.dumps({
            "m": args.m,
            "env": gepa_metric.capture_judge_env(),
            "results": results,
        }, indent=2))
        print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
