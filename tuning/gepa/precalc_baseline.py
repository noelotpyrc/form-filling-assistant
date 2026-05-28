"""Pre-compute the baseline FormAssistant val scores once, save to JSON.

Why this exists: optimize.py runs a baseline eval of the un-mutated
FormAssistant on the val set, which costs ~1 case × (student inference +
judge call) per val example. For a 122-case val set with DeepSeek/GPT-5
judges, that's 30-45 min per run. GEPA also runs its own iter-0 full-val
eval internally, so we're paying twice. This script lets you pay once,
then pass --baseline-from <PATH> to optimize.py to skip the redundant
pre-GEPA loop.

The saved JSON captures the val_set test_ids so optimize.py can verify
the same split is in use (same seed → same shuffle → same val_set).

Run from repo root:
  python/.venv/bin/python tuning/gepa/precalc_baseline.py \\
      --judge --val-size 122 \\
      --out tuning/gepa/results/baseline_sft_v2_deepseek.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO_ROOT / "tuning" / "dspy"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

# Reuse everything from optimize.py — same load, same split, same metric.
from optimize import (  # noqa: E402
    load_examples, stratified_sample, make_metric,
)
from optimize_prompt import FormAssistant  # noqa: E402
import metric as gepa_metric  # noqa: E402

from tuning.harness.pipeline import configure_lm, DEFAULT_LM_MODEL  # noqa: E402
from tuning.harness.preflight import (  # noqa: E402
    assert_anchor_match, assert_anchors_match, SCHEMA_PATH,
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--student-port", type=int, default=8100)
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL)
    ap.add_argument("--anchor", default=None)
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--train-size", type=int, default=486,
                    help="Train-size affects val_set selection (val drawn from "
                         "the remainder). Must match optimize.py's --train-size "
                         "for the val_ids to align.")
    ap.add_argument("--val-size", type=int, default=122)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-preflight", action="store_true")
    ap.add_argument("--out", required=True,
                    help="Output JSON path. Pass this to optimize.py via "
                         "--baseline-from to skip the redundant baseline loop.")
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY not set")

    configure_lm(
        api_base=f"http://localhost:{args.student_port}/v1",
        model=args.student_model,
    )

    if not args.skip_preflight:
        if args.anchor:
            assert_anchor_match(args.anchor)
        else:
            assert_anchors_match()

    form_schema = json.loads(Path(SCHEMA_PATH).read_text())
    print("Loading eval cases...")
    examples = load_examples(form_schema)
    print(f"  Total: {len(examples)} cases")

    # Replicate optimize.py's split EXACTLY.
    rng = random.Random(args.seed)
    rng.shuffle(examples)
    train_set = stratified_sample(examples, args.train_size, seed=args.seed)
    train_ids = {id(ex) for ex in train_set}
    remaining = [ex for ex in examples if id(ex) not in train_ids]
    val_set = stratified_sample(remaining, args.val_size, seed=args.seed + 1)
    print(f"  Train: {len(train_set)}  Val: {len(val_set)}")

    metric = make_metric(use_judge=args.judge)
    judge_label = os.getenv("JUDGE_MODEL", "gpt-5") if args.judge else None
    print(f"  Judge: {'ON (' + judge_label + ')' if args.judge else 'OFF'}")

    print("\n── Baseline eval ──")
    program = FormAssistant()
    rows: list[dict] = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def write_partial():
        partial = {
            "schema_version": "2",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "student_model": args.student_model,
            "judge_enabled": args.judge,
            "judge_model": judge_label,
            "env": gepa_metric.capture_judge_env(),
            "config": {
                "student_port": args.student_port,
                "student_model": args.student_model,
                "seed": args.seed,
                "train_size": args.train_size,
                "val_size": args.val_size,
                "judge_enabled": args.judge,
            },
            "baseline_avg": (sum(r["score"] for r in rows) / len(rows)) if rows else 0.0,
            "n_completed": len(rows),
            "scores": rows,
        }
        out_path.write_text(json.dumps(partial, indent=2))

    for i, ex in enumerate(val_set):
        tid = ex.case["test_id"]
        # No row-level try/except: judge failures must halt the run so the
        # operator can address the root cause (e.g., wait for usage reset).
        # judge.judge_case already retries JUDGE_MAX_ATTEMPTS times internally.
        # See: tuning/gepa/INCIDENT_2026-05-15_judge_silent_fallback.md
        pred = program(context=ex.context, user_message=ex.user_message)
        pred_flat = gepa_metric.pred_to_flat_dict(pred)
        try:
            score = float(metric(ex, pred))
        except BaseException:
            rows.append({"val_idx": i, "test_id": tid, "score": None,
                         "error": "judge_failed_after_retries — see stderr",
                         "pred": pred_flat})
            write_partial()
            raise
        rows.append({"val_idx": i, "test_id": tid, "score": score,
                     "error": None, "pred": pred_flat})
        print(f"  [{i:3d}] {tid:35s} score={score:.3f}")
        if (i + 1) % 10 == 0 or i + 1 == len(val_set):
            write_partial()

    baseline_avg = sum(r["score"] for r in rows) / len(rows) if rows else 0.0
    print(f"\n  Baseline avg: {baseline_avg:.4f}")

    out = {
        "schema_version": "2",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "student_model": args.student_model,
        "judge_enabled": args.judge,
        "judge_model": judge_label,
        "env": gepa_metric.capture_judge_env(),
        "config": {
            "student_port": args.student_port,
            "student_model": args.student_model,
            "seed": args.seed,
            "train_size": args.train_size,
            "val_size": args.val_size,
            "judge_enabled": args.judge,
        },
        "baseline_avg": baseline_avg,
        "n_completed": len(rows),
        "scores": rows,
    }
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\n  Saved baseline: {out_path}")


if __name__ == "__main__":
    main()
