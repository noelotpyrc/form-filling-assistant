"""Generate baseline + candidate predictions and score BOTH inline.

This addresses the prediction/score mismatch that occurred when
`inspect_data_extractor_by_delta.py` paired *fresh re-inferred* predictions
with *stored old* scores from `eval_candidate2_fresh.json` /
`baseline_sft_v2_claude_conf_n3.json`. Because the student is stochastic,
those re-inferred predictions are NOT the predictions that produced the
stored scores — leading to apparent boosts/regressions that may not exist.

This script persists pred_dict + score TOGETHER per case so the prediction
shown later == the prediction scored.

Output JSON schema (per row):
  {
    "test_id": "...",
    "baseline_pred": {flags, response_text, field_ids, ...},
    "baseline_score": 0.xx,
    "baseline_error": null | "...",
    "cand_pred": {...},
    "cand_score": 0.xx,
    "cand_error": null | "...",
    "delta": cand_score - baseline_score,
  }

Run from repo root:
  JUDGE_BACKEND=claude_headless python -u tuning/gepa/gen_and_score.py \\
    --state tuning/gepa/results/run_full_claude_judge_20260514_1617/gepa_state.bin \\
    --candidate 2 \\
    --out tuning/gepa/results/gen_and_score_cand2.json
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
from optimize import load_examples, stratified_sample  # noqa: E402
from tuning.harness.pipeline import configure_lm, DEFAULT_LM_MODEL  # noqa: E402
from tuning.harness.preflight import assert_anchors_match, SCHEMA_PATH  # noqa: E402
import metric as gepa_metric  # noqa: E402


def apply_candidate(program: FormAssistant, prompts: dict) -> FormAssistant:
    for module_name, instructions in prompts.items():
        module = getattr(program, module_name)
        module.signature = module.signature.with_instructions(instructions)
    return program


def run_one(program, ex):
    """Run inference + extract pred_dict. Returns (pred_dict, error_or_None)."""
    try:
        pred = program(context=ex.context, user_message=ex.user_message)
        return gepa_metric._extract_pred(pred), None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:200]}"


def score_pred(case, pred_dict, use_judge: bool):
    """Score with the composite metric. Returns (score, error_or_None)."""
    if pred_dict is None:
        return 0.0, "no_pred"
    try:
        result = gepa_metric.score_case(case, pred_dict, use_judge=use_judge)
        return float(result["score"]), None
    except Exception as e:
        return 0.0, f"{type(e).__name__}: {str(e)[:200]}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", required=True)
    ap.add_argument("--candidate", type=int, required=True)
    ap.add_argument("--student-port", type=int, default=8100)
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL)
    ap.add_argument("--judge", action="store_true", default=True)
    ap.add_argument("--train-size", type=int, default=486)
    ap.add_argument("--val-size", type=int, default=122)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-preflight", action="store_true")
    ap.add_argument("--limit", type=int, default=None,
                    help="Optionally cap number of cases (for quick checks)")
    ap.add_argument("--only-test-ids", nargs="*", default=None,
                    help="If set, only run these specific test_ids from val set")
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

    state = pickle.load(open(args.state, "rb"))
    candidates = state["program_candidates"]
    if args.candidate < 0 or args.candidate >= len(candidates):
        sys.exit(f"--candidate {args.candidate} out of range [0, {len(candidates)-1}]")
    cand_prompts = candidates[args.candidate]
    base = candidates[0]
    mutated = [m for m in cand_prompts if cand_prompts[m] != base[m]]
    print(f"Loaded candidate {args.candidate} from {args.state}")
    print(f"  Modules mutated vs baseline: {mutated}")

    # Same val split as precalc_baseline / optimize / eval_candidate
    form_schema = json.loads(Path(SCHEMA_PATH).read_text())
    examples = load_examples(form_schema)
    print(f"Total cases: {len(examples)}")
    rng = random.Random(args.seed)
    rng.shuffle(examples)
    train_set = stratified_sample(examples, args.train_size, seed=args.seed)
    train_ids = {id(ex) for ex in train_set}
    remaining = [ex for ex in examples if id(ex) not in train_ids]
    val_set = stratified_sample(remaining, args.val_size, seed=args.seed + 1)
    print(f"  Train: {len(train_set)}  Val: {len(val_set)}")

    if args.only_test_ids:
        wanted = set(args.only_test_ids)
        val_set = [ex for ex in val_set if ex.case["test_id"] in wanted]
        print(f"  Filtered val to {len(val_set)} requested test_ids")
    if args.limit:
        val_set = val_set[:args.limit]
        print(f"  Limited to first {len(val_set)} cases")

    baseline_prog = FormAssistant()
    cand_prog = FormAssistant()
    apply_candidate(cand_prog, cand_prompts)

    judge_label = os.getenv("JUDGE_BACKEND", "openai")
    print(f"  Judge backend: {judge_label}")
    print(f"  use_judge: {args.judge}\n")

    rows: list[dict] = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    for i, ex in enumerate(val_set):
        tid = ex.case["test_id"]
        b_pred, b_err = run_one(baseline_prog, ex)
        c_pred, c_err = run_one(cand_prog, ex)
        b_score, b_serr = score_pred(ex.case, b_pred, args.judge)
        c_score, c_serr = score_pred(ex.case, c_pred, args.judge)
        delta = c_score - b_score
        row = {
            "test_id": tid,
            "source": ex.case.get("source"),
            "cannot_targets": ex.case.get("cannot_targets") or [],
            "baseline_pred": b_pred,
            "baseline_score": b_score,
            "baseline_error": b_err or b_serr,
            "cand_pred": c_pred,
            "cand_score": c_score,
            "cand_error": c_err or c_serr,
            "delta": delta,
        }
        rows.append(row)
        flag = ""
        if abs(delta) >= 0.10:
            flag = "  ★"
        print(f"  [{i:3d}] {tid:38s} base={b_score:.3f}  cand={c_score:.3f}  Δ={delta:+.3f}{flag}")

        # Incremental save every 10 cases so a crash doesn't lose work
        if (i + 1) % 10 == 0 or i + 1 == len(val_set):
            out_payload = {
                "schema_version": "1",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "state_file": args.state,
                "candidate_index": args.candidate,
                "modules_mutated": mutated,
                "judge_backend": judge_label,
                "use_judge": args.judge,
                "train_size": args.train_size,
                "val_size": args.val_size,
                "seed": args.seed,
                "n_completed": i + 1,
                "rows": rows,
            }
            out_path.write_text(json.dumps(out_payload, indent=2))

    base_avg = sum(r["baseline_score"] for r in rows) / len(rows) if rows else 0.0
    cand_avg = sum(r["cand_score"] for r in rows) / len(rows) if rows else 0.0
    print(f"\n── Summary ──")
    print(f"  Baseline avg:  {base_avg:.4f}")
    print(f"  Candidate avg: {cand_avg:.4f}")
    print(f"  Δ:             {cand_avg - base_avg:+.4f}")
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
