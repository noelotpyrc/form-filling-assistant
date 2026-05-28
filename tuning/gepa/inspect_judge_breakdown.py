"""For one case, re-run baseline + candidate inference, then judge BOTH
predictions with per-rubric-item score breakdown. Helps diagnose why one
prediction outscored another.

Run from repo root:
  JUDGE_BACKEND=claude_headless python -u tuning/gepa/inspect_judge_breakdown.py \\
    --test-id legacy-single_field_239 --candidate 2 --out /tmp/judge_breakdown.md
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO / "tuning" / "dspy"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / ".env")

os.environ.setdefault("JUDGE_BACKEND", "claude_headless")

from rubrics import get_rubric_for_case  # noqa: E402
from optimize_prompt import FormAssistant  # noqa: E402
from tuning.harness.pipeline import build_context, configure_lm, DEFAULT_LM_MODEL  # noqa: E402
from tuning.harness.preflight import SCHEMA_PATH  # noqa: E402
from judge_claude_headless import judge_case  # noqa: E402


def pred_dict(p):
    return {
        "flags": {f: bool(getattr(p, f, False)) for f in
                  ["has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit"]},
        "response_text": p.response_text or "",
        "field_ids": list(p.field_ids or []),
        "field_values": list(p.field_values or []),
        "question": getattr(p, "question", "") or "",
        "options": list(getattr(p, "options", []) or []),
        "summary_title": getattr(p, "summary_title", "") or "",
        "summary_content": getattr(p, "summary_content", "") or "",
    }


def apply_candidate(program, prompts):
    for module_name, instructions in prompts.items():
        module = getattr(program, module_name)
        module.signature = module.signature.with_instructions(instructions)
    return program


def fmt_pred(p):
    flags = " ".join(f"{k}={v}" for k, v in p["flags"].items())
    fids = p["field_ids"]; fvals = p["field_values"]
    lines = [f"flags:    {flags}",
             f"response_text: {p['response_text']!r}",
             f"field updates ({len(fids)}):"]
    if fids:
        lines += [f"  {fid} = {fv!r}" for fid, fv in zip(fids, fvals)]
    else:
        lines.append("  (none)")
    if p["question"] or p["options"]:
        lines.append(f"question: {p['question']!r}")
        lines.append(f"options:  {p['options']}")
    if p["summary_title"] or p["summary_content"]:
        lines.append(f"review:   '{p['summary_title']}' — {p['summary_content']!r}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="tuning/gepa/results/run_full_claude_judge_20260514_1617/gepa_state.bin")
    ap.add_argument("--candidate", type=int, default=2)
    ap.add_argument("--test-id", required=True)
    ap.add_argument("--n-judge-trials", type=int, default=3,
                    help="How many independent judge invocations per prediction (each is itself N=3 ensembled)")
    ap.add_argument("--student-port", type=int, default=8100)
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    ec = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]
    case_by_id = {c["test_id"]: c for c in seeds + ec}
    case = case_by_id.get(args.test_id)
    if not case:
        sys.exit(f"Case {args.test_id} not found")

    configure_lm(api_base=f"http://localhost:{args.student_port}/v1", model=args.student_model)
    state = pickle.load(open(args.state, "rb"))
    baseline_prog = FormAssistant()
    cand_prog = FormAssistant()
    apply_candidate(cand_prog, state["program_candidates"][args.candidate])

    schema = json.loads(Path(SCHEMA_PATH).read_text())
    inp = case["input"]
    ctx = build_context(schema, inp.get("form_state", {}), inp.get("conversation_history", []))

    base_p = pred_dict(baseline_prog(context=ctx, user_message=inp["user_message"]))
    cand_p = pred_dict(cand_prog(context=ctx, user_message=inp["user_message"]))

    rubric = get_rubric_for_case(case)
    total_w = sum(it["weight"] for it in rubric) or 1.0

    def judge_repeatedly(pred):
        runs = []
        for _ in range(args.n_judge_trials):
            scores = judge_case(case, pred, rubric)
            runs.append(scores)
        # Per-item mean across trials
        n = len(rubric)
        mean = [sum(r[i] for r in runs) / len(runs) for i in range(n)]
        return runs, mean

    print(f"Judging baseline ({args.n_judge_trials} trials × N=3 internally)...")
    base_runs, base_mean = judge_repeatedly(base_p)
    print(f"Judging candidate {args.candidate} ({args.n_judge_trials} trials × N=3 internally)...")
    cand_runs, cand_mean = judge_repeatedly(cand_p)

    def weighted(scores):
        return sum(it["weight"] * s for it, s in zip(rubric, scores)) / total_w

    md = [f"# Judge breakdown: `{args.test_id}` — baseline vs candidate {args.candidate}", ""]
    md += [f"- source: `{case.get('source','?')}`",
           f"- tags: `{case.get('cannot_targets') or []}`",
           f"- judge: claude_headless N=3 (each trial), {args.n_judge_trials} trials per prediction",
           ""]
    md += ["## user_message", "```", inp["user_message"], "```", ""]
    md += ["## GOLD", "```",
           fmt_pred({"flags": case["correct_answer"].get("flags", {}),
                     "response_text": case["correct_answer"].get("response_text",""),
                     "field_ids": case["correct_answer"].get("field_ids",[]) or [],
                     "field_values": case["correct_answer"].get("field_values",[]) or [],
                     "question": case["correct_answer"].get("question",""),
                     "options": case["correct_answer"].get("options",[]) or [],
                     "summary_title": case["correct_answer"].get("summary_title",""),
                     "summary_content": case["correct_answer"].get("summary_content","")}),
           "```", ""]
    md += ["## BASELINE prediction", "```", fmt_pred(base_p), "```", ""]
    md += ["## CANDIDATE prediction", "```", fmt_pred(cand_p), "```", ""]
    md += ["## Per-item judge scores", "",
           f"| # | item | weight | baseline | candidate | Δ | base runs | cand runs |",
           f"|---|---|---|---|---|---|---|---|"]
    for i, it in enumerate(rubric):
        b = base_mean[i]; c = cand_mean[i]
        br = ", ".join(f"{r[i]:.2f}" for r in base_runs)
        cr = ", ".join(f"{r[i]:.2f}" for r in cand_runs)
        md.append(f"| {i+1} | {it['id']} | {it['weight']} | {b:.3f} | {c:.3f} | {c-b:+.3f} | {br} | {cr} |")

    md += ["", "## Weighted totals",
           f"- BASELINE weighted: {weighted(base_mean):.4f}",
           f"- CANDIDATE weighted: {weighted(cand_mean):.4f}",
           f"- Δ: {weighted(cand_mean)-weighted(base_mean):+.4f}",
           "",
           "(Compare to eval JSON: baseline score, candidate score)"]

    Path(args.out).write_text("\n".join(md))
    print(f"\nSaved: {args.out}")
    print(f"\nBaseline weighted:  {weighted(base_mean):.4f}")
    print(f"Candidate weighted: {weighted(cand_mean):.4f}")


if __name__ == "__main__":
    main()
