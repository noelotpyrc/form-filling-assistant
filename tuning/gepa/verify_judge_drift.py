"""Verify the judge-drift theory by scoring byte-identical baseline/candidate
pairs within the SAME script run.

If the judge is reliable within a single run, Δ on byte-identical preds
should average ≈ 0 with small per-case noise. If we observe systematic
positive Δ matching the "+0.061" lift, the theory is wrong.

Run from repo root:
  JUDGE_BACKEND=claude_headless python/.venv/bin/python -u \\
    tuning/gepa/verify_judge_drift.py \\
    --paired tuning/gepa/results/paired_preds_cand2.json \\
    --n 10 --seed 7
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
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
    ap.add_argument("--n", type=int, default=10, help="How many identical pairs to sample")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    payload = json.load(open(args.paired))
    rows = payload["rows"]
    identical_rows = [r for r in rows if r["identical"]]
    print(f"Total rows: {len(rows)}, identical: {len(identical_rows)}")

    rng = random.Random(args.seed)
    sample = rng.sample(identical_rows, min(args.n, len(identical_rows)))

    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    ec = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]
    case_by_id = {c["test_id"]: c for c in seeds + ec}

    judge_label = os.getenv("JUDGE_BACKEND", "openai")
    print(f"Judge backend: {judge_label}\n")
    print(f"{'idx':>4} {'test_id':<38} {'base':>7} {'cand':>7} {'Δ':>8}")
    print("-" * 70)

    deltas = []
    for r in sample:
        tid = r["test_id"]
        case = case_by_id.get(tid)
        if not case:
            continue
        bp = to_nested(r["baseline_pred"])
        cp = to_nested(r["cand_pred"])
        # Preds are byte-identical (verified), but we call score_case twice
        # to expose any judge variance within one script run.
        br = gepa_metric.score_case(case, bp, use_judge=True)
        cr = gepa_metric.score_case(case, cp, use_judge=True)
        bs, cs = float(br["score"]), float(cr["score"])
        d = cs - bs
        deltas.append(d)
        print(f"{r['val_idx']:>4} {tid:<38} {bs:>7.3f} {cs:>7.3f} {d:>+8.3f}")

    if deltas:
        mean = sum(deltas) / len(deltas)
        var = sum((d - mean) ** 2 for d in deltas) / len(deltas)
        sd = var ** 0.5
        amax = max(abs(d) for d in deltas)
        print(f"\nN={len(deltas)}  mean Δ={mean:+.4f}  σ={sd:.4f}  max |Δ|={amax:.3f}")
        print(f"\nInterpretation:")
        print(f"  - Byte-identical preds should give Δ≈0 if judge is reliable within a run.")
        print(f"  - Observed mean Δ = {mean:+.4f}  (compare to inter-run 'lift' = +0.061)")
        if abs(mean) < 0.02:
            print(f"  → Consistent with the drift theory: same-run judge calls cluster near 0.")
        elif mean > 0.04:
            print(f"  → Drift theory IS WRONG: systematic +Δ even within a single run.")
        else:
            print(f"  → Ambiguous — small directional bias but inconclusive at N={len(deltas)}.")


if __name__ == "__main__":
    main()
