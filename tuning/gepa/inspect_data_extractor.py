"""Side-by-side inference comparison: baseline vs candidate-2 (data_extractor only).

Picks cases where the gold turn has `has_new_data=True` (so data_extractor
actually fires). Runs both programs on each, dumps user_message, gold
field_ids/values, baseline pred, candidate2 pred.

Run from repo root:
  python -u tuning/gepa/inspect_data_extractor.py \\
    --n 10 --out /tmp/data_extractor_compare.txt
"""

from __future__ import annotations

import argparse
import json
import pickle
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
from tuning.harness.pipeline import build_context, configure_lm, DEFAULT_LM_MODEL  # noqa: E402
from tuning.harness.preflight import SCHEMA_PATH  # noqa: E402


def apply_candidate(program: FormAssistant, prompts: dict) -> FormAssistant:
    for module_name, instructions in prompts.items():
        module = getattr(program, module_name)
        module.signature = module.signature.with_instructions(instructions)
    return program


def fmt_pred(p, label):
    flags = {f: getattr(p, f, False) for f in
             ["has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit"]}
    flag_str = " ".join(f"{k}={bool(v)}" for k, v in flags.items())
    fids = list(p.field_ids or [])
    fvals = list(p.field_values or [])
    lines = [f"{label}:",
             f"  flags:    {flag_str}",
             f"  response_text: {p.response_text!r}",
             f"  field updates ({len(fids)}):"]
    if fids:
        lines += [f"    {fid} = {fv!r}" for fid, fv in zip(fids, fvals)]
    else:
        lines.append("    (none)")
    return "\n".join(lines)


def fmt_gold(gold, label):
    flags = gold.get("flags", {})
    flag_str = " ".join(f"{k}={bool(v)}" for k, v in flags.items())
    fids = gold.get("field_ids", []) or []
    fvals = gold.get("field_values", []) or []
    lines = [f"{label}:",
             f"  flags:    {flag_str}",
             f"  response_text: {gold.get('response_text', '')!r}",
             f"  field updates ({len(fids)}):"]
    if fids:
        lines += [f"    {fid} = {fv!r}" for fid, fv in zip(fids, fvals)]
    else:
        lines.append("    (none)")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="tuning/gepa/results/run_full_claude_judge_20260514_1617/gepa_state.bin")
    ap.add_argument("--candidate", type=int, default=2)
    ap.add_argument("--n", type=int, default=10, help="Number of data_extractor cases to compare")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--student-port", type=int, default=8100)
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # Load eval cases (seeds + variations + legacy)
    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    ec = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]
    all_cases = seeds + ec

    # Filter to cases where data_extractor fires (gold has_new_data=True with non-empty field_ids)
    data_cases = [
        c for c in all_cases
        if c["correct_answer"]["flags"].get("has_new_data")
        and (c["correct_answer"].get("field_ids") or [])
    ]
    print(f"data-extractor-active cases: {len(data_cases)} / {len(all_cases)}")

    # Mix of partitions: some seeds, some variations, some legacy
    rng = random.Random(args.seed)
    rng.shuffle(data_cases)
    picked = data_cases[:args.n]

    # Configure student LM
    configure_lm(
        api_base=f"http://localhost:{args.student_port}/v1",
        model=args.student_model,
    )

    # Build both programs
    state = pickle.load(open(args.state, "rb"))
    baseline_prog = FormAssistant()
    cand_prog = FormAssistant()
    apply_candidate(cand_prog, state["program_candidates"][args.candidate])

    schema = json.loads(Path(SCHEMA_PATH).read_text())

    out_lines = []
    out_lines.append("#" * 80)
    out_lines.append(f"# data_extractor baseline vs candidate {args.candidate} — {args.n} cases")
    out_lines.append("#" * 80)
    for i, c in enumerate(picked):
        inp = c["input"]
        ctx = build_context(schema, inp.get("form_state", {}), inp.get("conversation_history", []))
        try:
            base_p = baseline_prog(context=ctx, user_message=inp["user_message"])
        except Exception as e:
            base_p = None
            base_err = f"{type(e).__name__}: {e}"
        try:
            cand_p = cand_prog(context=ctx, user_message=inp["user_message"])
        except Exception as e:
            cand_p = None
            cand_err = f"{type(e).__name__}: {e}"

        out_lines.append("")
        out_lines.append("=" * 80)
        out_lines.append(f"[{i+1}/{args.n}] test_id={c['test_id']}  source={c.get('source', '?')}  tags={c.get('cannot_targets') or []}")
        out_lines.append("=" * 80)
        out_lines.append(f"user_message: {inp['user_message']!r}")
        out_lines.append("")
        out_lines.append(fmt_gold(c["correct_answer"], "GOLD"))
        out_lines.append("")
        if base_p is not None:
            out_lines.append(fmt_pred(base_p, "BASELINE"))
        else:
            out_lines.append(f"BASELINE: ERROR {base_err}")
        out_lines.append("")
        if cand_p is not None:
            out_lines.append(fmt_pred(cand_p, f"CANDIDATE {args.candidate}"))
        else:
            out_lines.append(f"CANDIDATE {args.candidate}: ERROR {cand_err}")
        print(f"  done {i+1}/{args.n}: {c['test_id']}")

    Path(args.out).write_text("\n".join(out_lines))
    print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
