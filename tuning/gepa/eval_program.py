"""Evaluate a saved GEPA program against a chosen subset of cases.

Usage:
  python/.venv/bin/python tuning/gepa/eval_program.py \
      --program tuning/gepa/results/gepa-pilot-20260510T025645.json \
      --subset seeds         # 28 base seeds only
      --judge

Subsets:
  seeds       — 28 base seeds (seeds.jsonl)
  variations  — 280 generated variations
  legacy      — 300 legacy cases
  all         — 608 cases
"""

from __future__ import annotations

import argparse
import json
import os
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
from optimize import case_to_example, make_metric  # noqa: E402
from tuning.harness.pipeline import configure_lm, DEFAULT_LM_MODEL  # noqa: E402
from tuning.harness.preflight import assert_anchor_match, DEFAULT_ANCHOR, SCHEMA_PATH  # noqa: E402

SEEDS_PATH = Path(__file__).parent / "seeds.jsonl"
EVAL_PATH = Path(__file__).parent / "eval_cases.jsonl"


def load_subset(subset: str) -> list[dict]:
    seeds = [json.loads(l) for l in open(SEEDS_PATH)]
    variations = [json.loads(l) for l in open(EVAL_PATH)
                  if not json.loads(l)["test_id"].startswith("legacy-")]
    legacy = [json.loads(l) for l in open(EVAL_PATH)
              if json.loads(l)["test_id"].startswith("legacy-")]
    if subset == "seeds":
        return seeds
    if subset == "variations":
        return variations
    if subset == "legacy":
        return legacy
    return seeds + variations + legacy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", required=True, help="Path to saved DSPy program JSON")
    ap.add_argument("--subset", default="seeds",
                    choices=["seeds", "variations", "legacy", "all"])
    ap.add_argument("--student-port", type=int, default=8100)
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL)
    ap.add_argument("--anchor", default=str(DEFAULT_ANCHOR))
    ap.add_argument("--judge", action="store_true",
                    help="Use LLM judge (GPT-5)")
    ap.add_argument("--skip-preflight", action="store_true")
    args = ap.parse_args()

    if args.judge and not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY not set; required for --judge")

    configure_lm(
        api_base=f"http://localhost:{args.student_port}/v1",
        model=args.student_model,
    )
    if not args.skip_preflight:
        assert_anchor_match(args.anchor)

    print(f"Loading program from {args.program}")
    program = FormAssistant()
    program.load(args.program)

    cases = load_subset(args.subset)
    print(f"Subset: {args.subset} → {len(cases)} cases")
    print(f"Judge: {'ON (GPT-5)' if args.judge else 'OFF (programmatic)'}")
    print()

    form_schema = json.loads(Path(SCHEMA_PATH).read_text())
    examples = [case_to_example(c, form_schema) for c in cases]
    metric = make_metric(use_judge=args.judge)

    print(f"{'test_id':<35s} {'cannot_targets':<40s} score")
    print("-" * 90)
    scores: list[tuple[str, float]] = []
    errors = 0
    for ex in examples:
        case = ex.case
        try:
            pred = program(context=ex.context, user_message=ex.user_message)
            score = metric(ex, pred)
            score = float(score)
        except Exception as e:
            score = 0.0
            errors += 1
            print(f"{case['test_id']:<35s} ERROR: {type(e).__name__}: {str(e)[:50]}")
            scores.append((case["test_id"], 0.0))
            continue
        scores.append((case["test_id"], score))
        cannots = ", ".join(case.get("cannot_targets", [])) or "(legacy)"
        print(f"{case['test_id']:<35s} {cannots:<40s} {score:.3f}")

    avg = sum(s for _, s in scores) / len(scores) if scores else 0.0
    print()
    print(f"Average: {avg:.3f}  ({len(scores)} cases, {errors} errors)")

    # Group by cannot_target for the seeds case
    if args.subset == "seeds":
        from collections import defaultdict
        by_cannot: dict[str, list[float]] = defaultdict(list)
        for tid, score in scores:
            case = next(c for c in cases if c["test_id"] == tid)
            for c in case.get("cannot_targets", []) or ["(legacy)"]:
                by_cannot[c].append(score)
        print("\nBy CANNOT target (avg):")
        for c, vals in sorted(by_cannot.items()):
            print(f"  {c:35s} {sum(vals)/len(vals):.3f}  (n={len(vals)})")


if __name__ == "__main__":
    main()
