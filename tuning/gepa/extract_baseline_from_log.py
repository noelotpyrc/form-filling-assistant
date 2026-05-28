"""Extract a `--baseline-from`-compatible JSON from an existing run's stdout.log.

When optimize.py's pre-GEPA baseline loop has already run (printing per-case
`score=X.XXX` lines), this script scrapes those lines and writes them in the
schema precalc_baseline.py produces. Use to recover a 43-min eval whose only
output was the live stdout.

Run from repo root:
  python tuning/gepa/extract_baseline_from_log.py \\
      --log tuning/gepa/results/run_full_deepseek_20260511_1037/stdout.log \\
      --judge-model deepseek/deepseek-v4-flash \\
      --student-model ./models/qwen35-08b-dspy-format-v2-mlx \\
      --train-size 486 --val-size 122 --seed 42 \\
      --out tuning/gepa/results/baseline_sft_v2_deepseek.json
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

LINE_RE = re.compile(r"^\s*\[\s*(\d+)\]\s+(\S+)\s+score=([0-9.]+)\s*$")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", required=True, help="Path to stdout.log to scrape")
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--student-model", default=None)
    ap.add_argument("--train-size", type=int, required=True)
    ap.add_argument("--val-size", type=int, required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows: list[dict] = []
    last_idx = -1
    with open(args.log) as f:
        for line in f:
            m = LINE_RE.match(line)
            if not m:
                continue
            idx = int(m.group(1))
            # Take only the first contiguous run [0,1,2,...]; later "Post-eval"
            # blocks have the same shape but for a different program.
            if idx != last_idx + 1:
                if rows and idx == 0:
                    rows = []  # restart on a second [0]
                else:
                    break
            rows.append({
                "test_id": m.group(2),
                "score": float(m.group(3)),
                "error": None,
            })
            last_idx = idx

    if len(rows) != args.val_size:
        raise SystemExit(
            f"Extracted {len(rows)} rows but --val-size={args.val_size}. "
            "Either the log is partial or val_size doesn't match."
        )

    baseline_avg = sum(r["score"] for r in rows) / len(rows)
    out = {
        "schema_version": "1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": f"extracted from {args.log}",
        "student_model": args.student_model,
        "judge_enabled": bool(args.judge_model),
        "judge_model": args.judge_model,
        "seed": args.seed,
        "train_size": args.train_size,
        "val_size": args.val_size,
        "baseline_avg": baseline_avg,
        "scores": rows,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"Extracted {len(rows)} scores, baseline_avg={baseline_avg:.4f}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
