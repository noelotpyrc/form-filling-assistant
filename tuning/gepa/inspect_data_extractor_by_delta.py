"""Side-by-side comparison picked by score Δ: biggest boosts + biggest regressions.

Uses the precomputed baseline (`baseline_sft_v2_claude_conf_n3.json`) and the
fresh candidate-2 eval (`eval_candidate2_fresh.json`) to find data-extractor
cases where candidate 2 helped most and hurt most. Runs inference on those
cases and dumps both predictions plus the score deltas.

Run from repo root:
  python -u tuning/gepa/inspect_data_extractor_by_delta.py \\
    --boosts 5 --regressions 5 \\
    --out /tmp/data_extractor_compare_by_delta.md
"""

from __future__ import annotations

import argparse
import json
import pickle
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


def apply_candidate(program, prompts):
    for module_name, instructions in prompts.items():
        module = getattr(program, module_name)
        module.signature = module.signature.with_instructions(instructions)
    return program


def fmt_pred(p):
    flags = {f: getattr(p, f, False) for f in
             ["has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit"]}
    flag_str = " ".join(f"{k}={bool(v)}" for k, v in flags.items())
    fids = list(p.field_ids or [])
    fvals = list(p.field_values or [])
    lines = [f"flags:    {flag_str}",
             f"response_text: {p.response_text!r}",
             f"field updates ({len(fids)}):"]
    if fids:
        lines += [f"  {fid} = {fv!r}" for fid, fv in zip(fids, fvals)]
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def fmt_gold(gold):
    flags = gold.get("flags", {})
    flag_str = " ".join(f"{k}={bool(v)}" for k, v in flags.items())
    fids = gold.get("field_ids", []) or []
    fvals = gold.get("field_values", []) or []
    lines = [f"flags:    {flag_str}",
             f"response_text: {gold.get('response_text', '')!r}",
             f"field updates ({len(fids)}):"]
    if fids:
        lines += [f"  {fid} = {fv!r}" for fid, fv in zip(fids, fvals)]
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="tuning/gepa/results/run_full_claude_judge_20260514_1617/gepa_state.bin")
    ap.add_argument("--candidate", type=int, default=2)
    ap.add_argument("--baseline-scores", default="tuning/gepa/results/baseline_sft_v2_claude_conf_n3.json")
    ap.add_argument("--cand-scores",      default="tuning/gepa/results/eval_candidate2_fresh.json")
    ap.add_argument("--boosts", type=int, default=5, help="Top N cases where cand beat baseline")
    ap.add_argument("--regressions", type=int, default=5, help="Top N cases where cand lost to baseline")
    ap.add_argument("--student-port", type=int, default=8100)
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    base_scores = {r["test_id"]: r["score"] for r in json.load(open(args.baseline_scores))["scores"]}
    cand_scores = {r["test_id"]: r["score"] for r in json.load(open(args.cand_scores))["scores"]}
    common = sorted(set(base_scores) & set(cand_scores))

    # Load all eval cases by id
    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    ec = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]
    case_by_id = {c["test_id"]: c for c in seeds + ec}

    # Filter to data-extractor-active cases (gold has_new_data=True with non-empty fields)
    def is_data(c):
        ca = c["correct_answer"]
        return ca["flags"].get("has_new_data") and (ca.get("field_ids") or [])

    eligible = [tid for tid in common if tid in case_by_id and is_data(case_by_id[tid])]
    print(f"data-extractor-active cases in val set: {len(eligible)}")

    deltas = [(tid, cand_scores[tid] - base_scores[tid]) for tid in eligible]
    deltas.sort(key=lambda x: x[1])
    regressions = deltas[:args.regressions]            # most negative first
    boosts = list(reversed(deltas[-args.boosts:]))     # most positive first

    picks: list[tuple[str, str, float]] = []
    for tid, d in boosts:
        picks.append(("BOOST", tid, d))
    for tid, d in regressions:
        picks.append(("REGRESSION", tid, d))

    print(f"Picked: {len(boosts)} boosts, {len(regressions)} regressions")
    for k, tid, d in picks:
        print(f"  {k:11s} {tid:35s} Δ={d:+.3f}  base={base_scores[tid]:.3f}  cand={cand_scores[tid]:.3f}")

    # Configure LM + build both programs
    configure_lm(api_base=f"http://localhost:{args.student_port}/v1", model=args.student_model)
    state = pickle.load(open(args.state, "rb"))
    baseline_prog = FormAssistant()
    cand_prog = FormAssistant()
    apply_candidate(cand_prog, state["program_candidates"][args.candidate])

    schema = json.loads(Path(SCHEMA_PATH).read_text())

    md = ["# data_extractor inference: baseline vs candidate 2 (picked by score Δ)", "",
          f"Top {args.boosts} cases where candidate 2 **improved** vs baseline, then top {args.regressions} **regressions**. "
          "Both scored under the same judge framework (Claude headless N=3 confidence).",
          ""]

    for kind, tid, d in picks:
        c = case_by_id[tid]
        inp = c["input"]
        ctx = build_context(schema, inp.get("form_state", {}), inp.get("conversation_history", []))
        try:
            bp = baseline_prog(context=ctx, user_message=inp["user_message"])
            base_pred = fmt_pred(bp)
        except Exception as e:
            base_pred = f"ERROR {type(e).__name__}: {e}"
        try:
            cp = cand_prog(context=ctx, user_message=inp["user_message"])
            cand_pred = fmt_pred(cp)
        except Exception as e:
            cand_pred = f"ERROR {type(e).__name__}: {e}"

        md += [
            "---",
            f"## {kind} — `{tid}` (Δ={d:+.3f})",
            "",
            f"- source: `{c.get('source','?')}`",
            f"- tags: `{c.get('cannot_targets') or []}`",
            f"- baseline score: {base_scores[tid]:.3f}",
            f"- candidate 2 score: {cand_scores[tid]:.3f}",
            "",
            "**user_message**",
            "```",
            inp["user_message"],
            "```",
            "",
            "**GOLD**",
            "```",
            fmt_gold(c["correct_answer"]),
            "```",
            "",
            "**BASELINE**",
            "```",
            base_pred,
            "```",
            "",
            "**CANDIDATE 2**",
            "```",
            cand_pred,
            "```",
            "",
        ]
        print(f"  inferred: {tid}")

    Path(args.out).write_text("\n".join(md))
    print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
