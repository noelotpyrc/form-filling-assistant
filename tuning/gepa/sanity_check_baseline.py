"""Sanity check: re-infer baseline on a few val cases, byte-compare to stored
`generated_best_outputs_valset/task_*/iter_0_prog_0.json`.

If everything is deterministic, every check should pass. If any case fails,
our "student is deterministic across runs" assumption is wrong and we have
to revisit before trusting the candidate-2 comparison.

Run from repo root:
  python -u tuning/gepa/sanity_check_baseline.py \\
    --state tuning/gepa/results/run_full_claude_judge_20260514_1617/gepa_state.bin \\
    --n 5
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO / "tuning" / "dspy"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / ".env")

from optimize_prompt import FormAssistant  # noqa: E402
from optimize import load_examples, stratified_sample  # noqa: E402
from tuning.harness.pipeline import configure_lm, DEFAULT_LM_MODEL  # noqa: E402
from tuning.harness.preflight import SCHEMA_PATH  # noqa: E402


def flat_pred(p) -> dict:
    """Match the schema in iter_0_prog_0.json (flat, not nested under 'flags')."""
    return {
        "response_text": p.response_text or "",
        "has_new_data": bool(getattr(p, "has_new_data", False)),
        "needs_choice": bool(getattr(p, "needs_choice", False)),
        "wants_review": bool(getattr(p, "wants_review", False)),
        "wants_save": bool(getattr(p, "wants_save", False)),
        "wants_submit": bool(getattr(p, "wants_submit", False)),
        "field_ids": list(getattr(p, "field_ids", []) or []),
        "field_values": list(getattr(p, "field_values", []) or []),
        "question": getattr(p, "question", "") or "",
        "options": list(getattr(p, "options", []) or []),
        "summary_title": getattr(p, "summary_title", "") or "",
        "summary_content": getattr(p, "summary_content", "") or "",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", required=True)
    ap.add_argument("--stored-dir", default=None,
                    help="Folder with task_*/iter_0_prog_0.json. Defaults to next to state.")
    ap.add_argument("--student-port", type=int, default=8100)
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL)
    ap.add_argument("--train-size", type=int, default=486)
    ap.add_argument("--val-size", type=int, default=122)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n", type=int, default=5, help="How many random val cases to check")
    ap.add_argument("--sample-seed", type=int, default=7, help="Seed for picking which cases to check")
    args = ap.parse_args()

    stored_dir = Path(args.stored_dir) if args.stored_dir else \
        Path(args.state).parent / "generated_best_outputs_valset"
    if not stored_dir.exists():
        sys.exit(f"Stored preds dir not found: {stored_dir}")

    configure_lm(api_base=f"http://localhost:{args.student_port}/v1", model=args.student_model)

    form_schema = json.loads(Path(SCHEMA_PATH).read_text())
    examples = load_examples(form_schema)
    rng = random.Random(args.seed)
    rng.shuffle(examples)
    train_set = stratified_sample(examples, args.train_size, seed=args.seed)
    train_ids = {id(ex) for ex in train_set}
    remaining = [ex for ex in examples if id(ex) not in train_ids]
    val_set = stratified_sample(remaining, args.val_size, seed=args.seed + 1)
    print(f"val_set: {len(val_set)}")

    # Random subset to check
    rng2 = random.Random(args.sample_seed)
    indices = rng2.sample(range(len(val_set)), min(args.n, len(val_set)))
    print(f"Checking indices: {sorted(indices)}\n")

    program = FormAssistant()
    matches = 0
    mismatches = []
    for idx in sorted(indices):
        ex = val_set[idx]
        tid = ex.case["test_id"]
        stored_path = stored_dir / f"task_{idx}" / "iter_0_prog_0.json"
        if not stored_path.exists():
            print(f"[{idx:3d}] {tid:38s} STORED MISSING: {stored_path}")
            mismatches.append((idx, tid, "stored_missing"))
            continue
        stored = json.loads(stored_path.read_text())
        pred = program(context=ex.context, user_message=ex.user_message)
        fresh = flat_pred(pred)
        identical = stored == fresh
        if identical:
            matches += 1
            print(f"[{idx:3d}] {tid:38s} MATCH ✓")
        else:
            mismatches.append((idx, tid, "diff"))
            diffs = {k: (stored.get(k), fresh.get(k)) for k in set(stored) | set(fresh) if stored.get(k) != fresh.get(k)}
            print(f"[{idx:3d}] {tid:38s} DIFFER ✗")
            for k, (s, f) in diffs.items():
                sr = repr(s)[:80]; fr = repr(f)[:80]
                print(f"        {k}:")
                print(f"          stored: {sr}")
                print(f"          fresh : {fr}")

    print(f"\n── Result ──")
    print(f"  matches:    {matches} / {len(indices)}")
    print(f"  mismatches: {len(mismatches)}")
    if mismatches:
        print(f"  → student is NOT bit-reproducible across runs. Investigate before trusting cand2 preds.")
        sys.exit(1)
    else:
        print(f"  → student is bit-reproducible. Stored baseline preds can be trusted.")


if __name__ == "__main__":
    main()
