#!/usr/bin/env python3
"""
Sample test cases from atomic training data for model evaluation.

Stratified sampling by category to ensure balanced coverage.
Outputs a test-cases.jsonl file for run_eval.py.

Usage:
    python tuning/scripts/sample.py                           # default: 300 cases
    python tuning/scripts/sample.py --total 50                # fewer cases
    python tuning/scripts/sample.py --input tuning/data/atomic.jsonl
    python tuning/scripts/sample.py --single-turn-only        # no conversation history
"""

import json
import argparse
import random
from collections import defaultdict
from pathlib import Path


# Target distribution by category (proportions, will be normalized)
TARGET_DISTRIBUTION = {
    "greeting": 0.10,
    "single_field": 0.15,
    "multi_field": 0.15,
    "choice_selection": 0.15,
    "ask_choice_only": 0.10,
    "question_no_actions": 0.10,
    "file_handling": 0.10,
    "submit_flow": 0.08,
    "other": 0.07,
}


def sample_test_cases(
    atomic_path: str,
    total: int = 300,
    seed: int = 42,
    single_turn_only: bool = False,
) -> list[dict]:
    """Sample stratified test cases from atomic data."""
    rng = random.Random(seed)

    # Load all turns
    turns = []
    for line in open(atomic_path):
        line = line.strip()
        if not line:
            continue
        turns.append(json.loads(line))

    if not turns:
        print("No turns found in atomic data.")
        return []

    # Group by category
    by_category: dict[str, list[dict]] = defaultdict(list)
    for t in turns:
        by_category[t.get("category", "other")].append(t)

    # Compute actual sample counts per category
    # Normalize target distribution to available categories
    available_cats = set(by_category.keys())
    norm_dist = {}
    total_weight = sum(
        TARGET_DISTRIBUTION.get(c, 0.05) for c in available_cats
    )
    for cat in available_cats:
        weight = TARGET_DISTRIBUTION.get(cat, 0.05)
        norm_dist[cat] = weight / total_weight

    # Allocate samples
    allocations = {}
    remaining = total
    for cat in sorted(norm_dist.keys()):
        target = max(1, round(norm_dist[cat] * total))
        actual = min(target, len(by_category[cat]), remaining)
        allocations[cat] = actual
        remaining -= actual

    # Distribute remaining to categories with more data
    while remaining > 0:
        for cat in sorted(allocations.keys(), key=lambda c: len(by_category[c]), reverse=True):
            if remaining <= 0:
                break
            if allocations[cat] < len(by_category[cat]):
                allocations[cat] += 1
                remaining -= 1

    # Sample from each category
    test_cases = []
    for cat, count in sorted(allocations.items()):
        pool = by_category[cat]
        sampled = rng.sample(pool, min(count, len(pool)))
        for s in sampled:
            case = {
                "test_id": f"{cat}_{len(test_cases)}",
                "category": cat,
                "session_id": s["session_id"],
                "persona": s["persona"],
                "profile": s["profile"],
                "turn": s["turn"],
                "user_message": s["user_message"],
                "expected_output": s["assistant_output"],
                "expected_action_types": s["action_types"],
                "expected_has_actions": s["has_actions"],
                "expected_has_delimiter": s["has_delimiter"],
                "expected_fields_set": s["fields_set"],
                "form_state_before": s["form_state_before"],
            }
            if not single_turn_only:
                case["conversation_history"] = s["conversation_history"]
            test_cases.append(case)

    rng.shuffle(test_cases)
    return test_cases


def main():
    parser = argparse.ArgumentParser(description="Sample test cases from atomic data")
    parser.add_argument("--input", default="tuning/data/atomic.jsonl", help="Input atomic JSONL")
    parser.add_argument("--output", default="tuning/data/test-cases.jsonl", help="Output test cases JSONL")
    parser.add_argument("--total", type=int, default=300, help="Total test cases to sample")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--single-turn-only", action="store_true", help="Exclude conversation history")
    args = parser.parse_args()

    cases = sample_test_cases(
        args.input,
        total=args.total,
        seed=args.seed,
        single_turn_only=args.single_turn_only,
    )

    if not cases:
        return

    # Print stats
    cats = defaultdict(int)
    for c in cases:
        cats[c["category"]] += 1

    print(f"Sampled {len(cases)} test cases:")
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat:25s} {n:3d}")

    has_actions = sum(1 for c in cases if c["expected_has_actions"])
    has_delim = sum(1 for c in cases if c["expected_has_delimiter"])
    print(f"\nWith actions: {has_actions}/{len(cases)} ({100*has_actions/len(cases):.0f}%)")
    print(f"With delimiter: {has_delim}/{len(cases)} ({100*has_delim/len(cases):.0f}%)")

    # Write
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        for case in cases:
            f.write(json.dumps(case) + "\n")
    print(f"\nWrote {len(cases)} cases to {args.output}")


if __name__ == "__main__":
    main()
