"""Independent full-val eval of a single candidate from gepa_state.bin.

Loads candidate N's per-module instructions, applies them to a FormAssistant,
runs through the same val_set used by precalc_baseline / GEPA, and reports
the avg score under the current judge. Used to verify GEPA's reported val
score in clean conditions (e.g., after a rate-limit window has reset).

Run from repo root:
  JUDGE_BACKEND=claude_headless python -u tuning/gepa/eval_candidate.py \\
    --state tuning/gepa/results/run_full_claude_judge_20260514_1617/gepa_state.bin \\
    --candidate 2 \\
    --out tuning/gepa/results/eval_candidate2_fresh.json
"""

from __future__ import annotations

import argparse
import json
import os
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
from optimize import load_examples, stratified_sample, make_metric  # noqa: E402
import metric as gepa_metric  # noqa: E402
from tuning.harness.pipeline import configure_lm, DEFAULT_LM_MODEL  # noqa: E402
from tuning.harness.preflight import assert_anchors_match, SCHEMA_PATH  # noqa: E402


def apply_candidate(program: FormAssistant, prompts: dict) -> FormAssistant:
    """Overwrite each module's signature.instructions with the candidate's text."""
    for module_name, instructions in prompts.items():
        module = getattr(program, module_name)
        module.signature = module.signature.with_instructions(instructions)
    return program


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", required=True, help="Path to gepa_state.bin")
    ap.add_argument("--candidate", type=int, required=True,
                    help="Candidate index (0 = baseline, 1+ = GEPA candidates)")
    ap.add_argument("--student-port", type=int, default=8100)
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL)
    ap.add_argument("--judge", action="store_true", default=True)
    ap.add_argument("--train-size", type=int, default=486)
    ap.add_argument("--val-size", type=int, default=122)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-preflight", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY not set")

    configure_lm(
        api_base=f"http://localhost:{args.student_port}/v1",
        model=args.student_model,
    )

    if not args.skip_preflight:
        assert_anchors_match()

    # Load state + extract candidate prompts
    state = pickle.load(open(args.state, "rb"))
    candidates = state["program_candidates"]
    val_subscores = state["prog_candidate_val_subscores"]
    parents = state.get("parent_program_for_candidate", [])
    if args.candidate < 0 or args.candidate >= len(candidates):
        sys.exit(f"--candidate {args.candidate} out of range [0, {len(candidates)-1}]")
    cand_prompts = candidates[args.candidate]
    cand_gepa_avg = sum(val_subscores[args.candidate].values()) / len(val_subscores[args.candidate])
    cand_parent = parents[args.candidate] if args.candidate < len(parents) else None

    print(f"Loaded candidate {args.candidate} from {args.state}")
    print(f"  GEPA's reported val avg: {cand_gepa_avg:.4f}")
    print(f"  Parent(s): {cand_parent}")
    base = candidates[0]
    mutated = [m for m in cand_prompts if cand_prompts[m] != base[m]]
    print(f"  Modules mutated vs baseline: {mutated}")

    # Same val split as precalc_baseline / optimize
    form_schema = json.loads(Path(SCHEMA_PATH).read_text())
    print("\nLoading eval cases…")
    examples = load_examples(form_schema)
    print(f"  Total: {len(examples)} cases")
    rng = random.Random(args.seed)
    rng.shuffle(examples)
    train_set = stratified_sample(examples, args.train_size, seed=args.seed)
    train_ids = {id(ex) for ex in train_set}
    remaining = [ex for ex in examples if id(ex) not in train_ids]
    val_set = stratified_sample(remaining, args.val_size, seed=args.seed + 1)
    print(f"  Train: {len(train_set)}  Val: {len(val_set)}")

    metric = make_metric(use_judge=args.judge)
    judge_label = os.getenv("JUDGE_BACKEND", "openai")
    print(f"  Judge backend: {judge_label}")

    # Build candidate program
    program = FormAssistant()
    apply_candidate(program, cand_prompts)

    print(f"\n── Fresh full-val eval of candidate {args.candidate} ──")
    rows: list[dict] = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def write_partial():
        partial = {
            "schema_version": "2",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "state_file": args.state,
            "candidate_index": args.candidate,
            "parent_candidates": cand_parent,
            "modules_mutated": mutated,
            "gepa_reported_avg": cand_gepa_avg,
            "fresh_full_val_avg": (sum(r["score"] for r in rows) / len(rows)) if rows else 0.0,
            "judge_backend": judge_label,
            "env": gepa_metric.capture_judge_env(),
            "config": {
                "student_port": args.student_port,
                "student_model": args.student_model,
                "seed": args.seed,
                "train_size": args.train_size,
                "val_size": args.val_size,
                "judge_enabled": args.judge,
            },
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
            # Persist progress (with the failed-case pred captured) before re-raising
            rows.append({"val_idx": i, "test_id": tid, "score": None,
                         "error": "judge_failed_after_retries — see stderr",
                         "pred": pred_flat})
            write_partial()
            raise
        rows.append({"val_idx": i, "test_id": tid, "score": score,
                     "error": None, "pred": pred_flat})
        print(f"  [{i:3d}] {tid:35s} score={score:.3f}")
        # Incremental save every 10 cases so a crash leaves us with progress
        if (i + 1) % 10 == 0 or i + 1 == len(val_set):
            write_partial()

    fresh_avg = sum(r["score"] for r in rows) / len(rows) if rows else 0.0
    print(f"\n  Fresh full-val avg: {fresh_avg:.4f}")
    print(f"  GEPA-reported avg:  {cand_gepa_avg:.4f}")
    print(f"  Δ:                  {fresh_avg - cand_gepa_avg:+.4f}")

    out = {
        "schema_version": "2",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "state_file": args.state,
        "candidate_index": args.candidate,
        "parent_candidates": cand_parent,
        "modules_mutated": mutated,
        "gepa_reported_avg": cand_gepa_avg,
        "fresh_full_val_avg": fresh_avg,
        "delta": fresh_avg - cand_gepa_avg,
        "judge_backend": judge_label,
        "env": gepa_metric.capture_judge_env(),
        "config": {
            "student_port": args.student_port,
            "student_model": args.student_model,
            "seed": args.seed,
            "train_size": args.train_size,
            "val_size": args.val_size,
            "judge_enabled": args.judge,
        },
        "n_completed": len(rows),
        "scores": rows,
    }
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
