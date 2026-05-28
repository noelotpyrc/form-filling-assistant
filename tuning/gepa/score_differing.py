"""Score only the rows where baseline_pred != cand_pred (byte-diff).

Input:  paired_preds_cand{N}.json (from gen_cand_preds.py)
Output: scored_paired_preds_cand{N}.json (adds baseline_score, cand_score, delta)

For identical pairs, score is set to None (would be same modulo judge noise —
no signal). For differing pairs, both preds are scored with the composite
metric (judge ON by default).

Run from repo root:
  JUDGE_BACKEND=claude_headless python/.venv/bin/python -u \\
    tuning/gepa/score_differing.py \\
    --paired tuning/gepa/results/paired_preds_cand2.json \\
    --out    tuning/gepa/results/scored_paired_preds_cand2.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
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
    """Convert flat schema (used in iter_0_prog_0.json and gen_cand_preds.py
    output) into the nested dict score_case expects."""
    if flat is None:
        return None
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


def load_case_by_id() -> dict:
    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    ec = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]
    return {c["test_id"]: c for c in seeds + ec}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paired", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-judge", action="store_true",
                    help="Score with programmatic checks only (deterministic, fast)")
    args = ap.parse_args()

    use_judge = not args.no_judge
    payload = json.load(open(args.paired))
    rows = payload["rows"]
    case_by_id = load_case_by_id()
    judge_label = os.getenv("JUDGE_BACKEND", "openai")

    print(f"Loaded {len(rows)} rows from {args.paired}")
    print(f"  use_judge={use_judge}  judge_backend={judge_label}")

    n_diff = sum(1 for r in rows if not r["identical"])
    print(f"  identical pairs: {sum(1 for r in rows if r['identical'])}")
    print(f"  differing pairs: {n_diff}  (these will be scored)\n")

    new_rows: list[dict] = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    scored = 0
    for r in rows:
        tid = r["test_id"]
        case = case_by_id.get(tid)
        if not case:
            print(f"  [{r['val_idx']:3d}] {tid:38s} CASE NOT FOUND")
            continue

        nr = dict(r)
        if r["identical"]:
            nr["baseline_score"] = None
            nr["cand_score"] = None
            nr["delta"] = None
            new_rows.append(nr)
            continue

        # Score both preds with composite metric
        base_dict = to_nested(r["baseline_pred"])
        cand_dict = to_nested(r["cand_pred"])
        try:
            br = gepa_metric.score_case(case, base_dict, use_judge=use_judge)
            bs = float(br["score"])
        except Exception as e:
            bs = None
            print(f"  [{r['val_idx']:3d}] {tid:38s} BASELINE SCORE ERROR: {e}")
        try:
            cr = gepa_metric.score_case(case, cand_dict, use_judge=use_judge)
            cs = float(cr["score"])
        except Exception as e:
            cs = None
            print(f"  [{r['val_idx']:3d}] {tid:38s} CAND SCORE ERROR: {e}")
        delta = (cs - bs) if (bs is not None and cs is not None) else None
        nr["baseline_score"] = bs
        nr["cand_score"] = cs
        nr["delta"] = delta
        new_rows.append(nr)
        scored += 1
        d_str = f"Δ={delta:+.3f}" if delta is not None else "Δ=ERR"
        print(f"  [{r['val_idx']:3d}] {tid:38s} base={bs:.3f}  cand={cs:.3f}  {d_str}")

        # Incremental save
        if scored % 3 == 0 or scored == n_diff:
            out_payload = {
                **{k: v for k, v in payload.items() if k != "rows"},
                "scored_at": datetime.now().isoformat(timespec="seconds"),
                "judge_backend_used": judge_label,
                "use_judge": use_judge,
                "n_differing_scored": scored,
                "rows": new_rows + [r for r in rows[len(new_rows):]],
            }
            out_path.write_text(json.dumps(out_payload, indent=2))

    # Final save with all rows
    out_payload = {
        **{k: v for k, v in payload.items() if k != "rows"},
        "scored_at": datetime.now().isoformat(timespec="seconds"),
        "judge_backend_used": judge_label,
        "use_judge": use_judge,
        "n_differing_scored": scored,
        "rows": new_rows,
    }
    out_path.write_text(json.dumps(out_payload, indent=2))

    diff_rows = [r for r in new_rows if r["delta"] is not None]
    if diff_rows:
        avg_delta = sum(r["delta"] for r in diff_rows) / len(diff_rows)
        boosts = sum(1 for r in diff_rows if r["delta"] > 0)
        regressions = sum(1 for r in diff_rows if r["delta"] < 0)
        ties = sum(1 for r in diff_rows if abs(r["delta"]) < 1e-9)
        print(f"\n── Summary across {len(diff_rows)} differing-pair scores ──")
        print(f"  cand better than baseline: {boosts}")
        print(f"  cand worse than baseline:  {regressions}")
        print(f"  ties:                      {ties}")
        print(f"  mean Δ (cand - base):      {avg_delta:+.4f}")
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
