"""Run a saved GEPA program against each seed and print the prediction.

Shows side-by-side: gold (correct_answer) vs predicted, per case.
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
    return " ".join(f"{f[:4]}={int(bool(d.get(f, False)))}" for f in FLAG_NAMES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", required=True)
    ap.add_argument("--student-port", type=int, default=8100)
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL)
    ap.add_argument("--anchor", default=str(DEFAULT_ANCHOR))
    ap.add_argument("--seed-id", default=None,
                    help="If set, only run this single seed (e.g., seed-P3-ex3)")
    ap.add_argument("--skip-preflight", action="store_true")
    args = ap.parse_args()

    configure_lm(
        api_base=f"http://localhost:{args.student_port}/v1",
        model=args.student_model,
    )
    if not args.skip_preflight:
        assert_anchor_match(args.anchor)

    print(f"Loading: {args.program}")
    program = FormAssistant()
    program.load(args.program)

    seeds = [json.loads(l) for l in open(SEEDS_PATH)]
    if args.seed_id:
        seeds = [s for s in seeds if s["test_id"] == args.seed_id]
        if not seeds:
            sys.exit(f"No seed with test_id={args.seed_id}")

    form_schema = json.loads(Path(SCHEMA_PATH).read_text())
    examples = [case_to_example(c, form_schema) for c in seeds]

    for ex in examples:
        case = ex.case
        gold = case["correct_answer"]
        cannots = ", ".join(case["cannot_targets"])
        print(f"\n{'═' * 90}")
        print(f"{case['test_id']}   [{cannots}]")
        print(f"{'═' * 90}")
        print(f"USER MESSAGE:")
        print(f"  {case['input']['user_message'][:200]}")
        print()
        print(f"GOLD:")
        print(f"  flags:   {fmt_flags(gold['flags'])}")
        print(f"  resp:    {gold['response_text'][:160]}")
        if gold["field_ids"]:
            print(f"  fields:  {list(zip(gold['field_ids'], gold['field_values']))[:6]}")
        if gold["question"]:
            print(f"  ask:     {gold['question'][:80]}  options={gold['options']}")
        if gold["summary_title"]:
            print(f"  review:  '{gold['summary_title']}' — {gold['summary_content'][:120]}")

        print(f"\nPREDICTED:")
        try:
            pred = program(context=ex.context, user_message=ex.user_message)
            pred_flags = {f: getattr(pred, f, False) for f in FLAG_NAMES}
            print(f"  flags:   {fmt_flags(pred_flags)}")
            print(f"  resp:    {(pred.response_text or '')[:160]}")
            fids = list(getattr(pred, "field_ids", []) or [])
            fvals = list(getattr(pred, "field_values", []) or [])
            if fids:
                print(f"  fields:  {list(zip(fids, fvals))[:6]}")
            if getattr(pred, "question", ""):
                print(f"  ask:     {pred.question[:80]}  options={list(pred.options)[:6]}")
            if getattr(pred, "summary_title", ""):
                print(f"  review:  '{pred.summary_title}' — {(pred.summary_content or '')[:120]}")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {str(e)[:120]}")


if __name__ == "__main__":
    main()
