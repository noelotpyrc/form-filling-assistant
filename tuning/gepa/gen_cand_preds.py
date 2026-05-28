"""Generate candidate-N predictions for all 122 val cases (no judge).

Student is deterministic, so the preds produced here == preds GEPA scored
during its run. Output is flat (matches `iter_0_prog_0.json` schema) and
paired with the stored baseline pred for each test_id.

Output schema (per row, ordered by val_set index):
  {
    "val_idx": N,
    "test_id": "...",
    "source": "...",
    "cannot_targets": [...],
    "baseline_pred": {...flat...},
    "cand_pred":     {...flat...},
    "identical": bool,
  }

Run from repo root:
  python/.venv/bin/python -u tuning/gepa/gen_cand_preds.py \\
    --state tuning/gepa/results/run_full_claude_judge_20260514_1617/gepa_state.bin \\
    --candidate 2 \\
    --out tuning/gepa/results/paired_preds_cand2.json
"""

from __future__ import annotations

import argparse
import json
import pickle
import random
import sys
from datetime import datetime
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


def apply_candidate(program, prompts):
    for module_name, instructions in prompts.items():
        module = getattr(program, module_name)
        module.signature = module.signature.with_instructions(instructions)
    return program


def flat_pred(p) -> dict:
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
    ap.add_argument("--candidate", type=int, required=True)
    ap.add_argument("--baseline-dir", default=None,
                    help="Folder with task_*/iter_0_prog_0.json baseline preds. "
                         "Defaults to <state>/../generated_best_outputs_valset")
    ap.add_argument("--student-port", type=int, default=8100)
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL)
    ap.add_argument("--train-size", type=int, default=486)
    ap.add_argument("--val-size", type=int, default=122)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    baseline_dir = Path(args.baseline_dir) if args.baseline_dir else \
        Path(args.state).parent / "generated_best_outputs_valset"
    if not baseline_dir.exists():
        sys.exit(f"Baseline preds dir not found: {baseline_dir}")

    configure_lm(api_base=f"http://localhost:{args.student_port}/v1",
                 model=args.student_model)

    state = pickle.load(open(args.state, "rb"))
    candidates = state["program_candidates"]
    if args.candidate < 0 or args.candidate >= len(candidates):
        sys.exit(f"--candidate {args.candidate} out of range [0,{len(candidates)-1}]")
    cand_prompts = candidates[args.candidate]
    base = candidates[0]
    mutated = [m for m in cand_prompts if cand_prompts[m] != base[m]]
    print(f"Candidate {args.candidate}: mutated modules = {mutated}\n")

    form_schema = json.loads(Path(SCHEMA_PATH).read_text())
    examples = load_examples(form_schema)
    rng = random.Random(args.seed)
    rng.shuffle(examples)
    train_set = stratified_sample(examples, args.train_size, seed=args.seed)
    train_ids = {id(ex) for ex in train_set}
    remaining = [ex for ex in examples if id(ex) not in train_ids]
    val_set = stratified_sample(remaining, args.val_size, seed=args.seed + 1)
    print(f"val_set: {len(val_set)}")

    cand_prog = FormAssistant()
    apply_candidate(cand_prog, cand_prompts)

    rows: list[dict] = []
    n_identical = 0
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    for i, ex in enumerate(val_set):
        tid = ex.case["test_id"]
        # Load stored baseline
        bp_path = baseline_dir / f"task_{i}" / "iter_0_prog_0.json"
        if not bp_path.exists():
            print(f"[{i:3d}] {tid:38s} MISSING BASELINE — skipping")
            continue
        baseline_pred = json.loads(bp_path.read_text())

        # Generate candidate pred
        try:
            cp = cand_prog(context=ex.context, user_message=ex.user_message)
            cand_pred = flat_pred(cp)
            cand_error = None
        except Exception as e:
            cand_pred = None
            cand_error = f"{type(e).__name__}: {str(e)[:200]}"

        identical = (baseline_pred == cand_pred)
        n_identical += int(identical)
        rows.append({
            "val_idx": i,
            "test_id": tid,
            "source": ex.case.get("source"),
            "cannot_targets": ex.case.get("cannot_targets") or [],
            "baseline_pred": baseline_pred,
            "cand_pred": cand_pred,
            "cand_error": cand_error,
            "identical": identical,
        })
        flag = "=" if identical else "DIFFER"
        print(f"[{i:3d}] {tid:38s} {flag}")

        if (i + 1) % 25 == 0 or i + 1 == len(val_set):
            payload = {
                "schema_version": "1",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "state_file": args.state,
                "candidate_index": args.candidate,
                "modules_mutated": mutated,
                "n_completed": i + 1,
                "n_identical": n_identical,
                "rows": rows,
            }
            out_path.write_text(json.dumps(payload, indent=2))

    n_diff = len(rows) - n_identical
    print(f"\n── Summary ──")
    print(f"  Total cases:        {len(rows)}")
    print(f"  Identical preds:    {n_identical}  (no scoring needed)")
    print(f"  Differing preds:    {n_diff}  (these will be scored next)")
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
