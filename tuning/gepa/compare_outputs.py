"""Run optimized program on all 28 seeds, produce a markdown comparison doc.

Each section: context summary (form_state keys filled + last assistant turn),
user message, gold answer, predicted answer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO_ROOT / "tuning" / "dspy"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

import dspy  # noqa: E402

from optimize_prompt import FormAssistant  # noqa: E402
from optimize import case_to_example  # noqa: E402
from tuning.harness.pipeline import configure_lm, DEFAULT_LM_MODEL  # noqa: E402
from tuning.harness.preflight import assert_anchor_match, DEFAULT_ANCHOR, SCHEMA_PATH  # noqa: E402

SEEDS_PATH = Path(__file__).parent / "seeds.jsonl"
FLAG_NAMES = ["has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit"]


def fmt_flags(d: dict) -> str:
    fired = [f for f in FLAG_NAMES if d.get(f)]
    return ", ".join(fired) if fired else "(none)"


def context_summary(case: dict) -> str:
    fs = case["input"].get("form_state", {})
    history = case["input"].get("conversation_history", [])

    fs_keys = sorted(k for k, v in fs.items() if v not in (None, "", False))
    parts = []
    if fs_keys:
        parts.append(f"**form_state filled** ({len(fs_keys)} keys): `{', '.join(fs_keys[:8])}`"
                     + (f" + {len(fs_keys)-8} more" if len(fs_keys) > 8 else ""))
    else:
        parts.append("**form_state**: empty")

    if history:
        parts.append(f"**history**: {len(history)} turns")
        # Show last turn (usually assistant's question that led to user_message)
        last = history[-1]
        role = last.get("role", "?")
        content = last.get("content", "")[:200]
        parts.append(f"- last [{role}]: {content}")
    else:
        parts.append("**history**: empty (turn 1)")
    return "\n".join(parts)


def fmt_answer(a: dict) -> str:
    """Format an answer dict (gold or predicted) as markdown."""
    lines = [f"- **flags**: {fmt_flags(a.get('flags', {}))}"]
    rt = a.get("response_text", "")
    if rt:
        lines.append(f"- **response_text**: {rt}")
    if a.get("field_ids"):
        ids = a["field_ids"]
        vals = a.get("field_values", [])
        pairs = list(zip(ids, vals))
        lines.append(f"- **field updates** ({len(pairs)}):")
        for fid, val in pairs:
            lines.append(f"  - `{fid}` = `{val!r}`")
    if a.get("question"):
        opts = a.get("options", [])
        lines.append(f"- **question**: {a['question']}")
        lines.append(f"  - options: {opts}")
    if a.get("summary_title") or a.get("summary_content"):
        lines.append(f"- **review**: '{a.get('summary_title', '')}' — {a.get('summary_content', '')}")
    return "\n".join(lines)


def pred_to_dict(pred) -> dict:
    return {
        "flags": {f: bool(getattr(pred, f, False)) for f in FLAG_NAMES},
        "response_text": getattr(pred, "response_text", "") or "",
        "field_ids": list(getattr(pred, "field_ids", []) or []),
        "field_values": list(getattr(pred, "field_values", []) or []),
        "question": getattr(pred, "question", "") or "",
        "options": list(getattr(pred, "options", []) or []),
        "summary_title": getattr(pred, "summary_title", "") or "",
        "summary_content": getattr(pred, "summary_content", "") or "",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", required=True)
    ap.add_argument("--student-port", type=int, default=8100)
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL)
    ap.add_argument("--anchor", default=str(DEFAULT_ANCHOR))
    ap.add_argument("--out", default="/tmp/seed_comparison.md")
    ap.add_argument("--skip-preflight", action="store_true")
    args = ap.parse_args()

    configure_lm(
        api_base=f"http://localhost:{args.student_port}/v1",
        model=args.student_model,
    )
    if not args.skip_preflight:
        assert_anchor_match(args.anchor)

    print(f"Loading optimized program: {args.program}")
    optimized = FormAssistant()
    optimized.load(args.program)

    print("Building baseline (un-optimized) program — same signatures, no GEPA tuning")
    baseline = FormAssistant()

    seeds = [json.loads(l) for l in open(SEEDS_PATH)]
    form_schema = json.loads(Path(SCHEMA_PATH).read_text())
    examples = [case_to_example(c, form_schema) for c in seeds]

    out_lines: list[str] = []
    out_lines.append("# Seed comparison: gold (authored) vs baseline (pre-GEPA) vs optimized (post-GEPA)")
    out_lines.append("")
    out_lines.append(f"Optimized program: `{args.program}`")
    out_lines.append("")
    out_lines.append(f"28 seeds, base SFT model on port {args.student_port}.")
    out_lines.append("")

    for ex in examples:
        case = ex.case
        cannots = ", ".join(case["cannot_targets"]) or "(legacy)"
        gold = case["correct_answer"]
        out_lines.append("---")
        out_lines.append("")
        out_lines.append(f"## `{case['test_id']}`  —  {cannots}")
        out_lines.append("")
        out_lines.append("### Context")
        out_lines.append(context_summary(case))
        out_lines.append("")
        out_lines.append("### User message")
        out_lines.append(f"> {case['input']['user_message'].replace(chr(10), ' ')[:500]}")
        out_lines.append("")

        out_lines.append("### Gold answer (authored reference)")
        out_lines.append(fmt_answer(gold))
        out_lines.append("")

        out_lines.append("### Old answer (baseline FormAssistant, pre-GEPA)")
        try:
            pred_old = baseline(context=ex.context, user_message=ex.user_message)
            out_lines.append(fmt_answer(pred_to_dict(pred_old)))
        except Exception as e:
            out_lines.append(f"**ERROR**: {type(e).__name__}: {str(e)[:200]}")
        out_lines.append("")

        out_lines.append("### New answer (optimized GEPA program)")
        try:
            pred_new = optimized(context=ex.context, user_message=ex.user_message)
            out_lines.append(fmt_answer(pred_to_dict(pred_new)))
        except Exception as e:
            out_lines.append(f"**ERROR**: {type(e).__name__}: {str(e)[:200]}")
        out_lines.append("")
        print(f"  done: {case['test_id']}")

    Path(args.out).write_text("\n".join(out_lines))
    print(f"\nWrote {args.out} ({len(out_lines)} lines)")


if __name__ == "__main__":
    main()
