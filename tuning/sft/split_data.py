#!/usr/bin/env python3
"""
Split format_train.jsonl into train/val sets and export in formats
suitable for Unsloth (HuggingFace datasets) and MLX LoRA.

Output formats:
  - format_train_split.jsonl / format_val_split.jsonl (JSONL with messages)
  - format_train_hf/ (HuggingFace Dataset directory for Unsloth)

Usage:
    cd python
    uv run python ../tuning/sft/split_data.py
    uv run python ../tuning/sft/split_data.py --val-ratio 0.15
"""

import json
import random
import argparse
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).parent.parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="tuning/sft/format_train.jsonl")
    parser.add_argument("--output-dir", default="tuning/sft")
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    input_path = PROJECT_ROOT / args.input
    output_dir = PROJECT_ROOT / args.output_dir

    # Load
    examples = []
    for line in open(input_path):
        line = line.strip()
        if line:
            examples.append(json.loads(line))

    print(f"Loaded {len(examples)} examples")

    # Stratified split by module
    by_module = {}
    for ex in examples:
        mod = ex["module"]
        by_module.setdefault(mod, []).append(ex)

    train_set = []
    val_set = []
    for mod, mod_examples in by_module.items():
        random.shuffle(mod_examples)
        val_n = max(1, int(len(mod_examples) * args.val_ratio))
        val_set.extend(mod_examples[:val_n])
        train_set.extend(mod_examples[val_n:])

    random.shuffle(train_set)
    random.shuffle(val_set)

    print(f"Train: {len(train_set)}, Val: {len(val_set)}")

    # Module distribution
    print("\nTrain distribution:")
    for mod, count in sorted(Counter(ex["module"] for ex in train_set).items(), key=lambda x: -x[1]):
        print(f"  {mod:20s} {count:5d}")
    print("\nVal distribution:")
    for mod, count in sorted(Counter(ex["module"] for ex in val_set).items(), key=lambda x: -x[1]):
        print(f"  {mod:20s} {count:5d}")

    # Write JSONL (messages-only format for Unsloth)
    def write_jsonl(data, path):
        with open(path, "w") as f:
            for ex in data:
                # Unsloth expects just {"messages": [...]}
                f.write(json.dumps({"messages": ex["messages"]}) + "\n")

    train_path = output_dir / "format_train_split.jsonl"
    val_path = output_dir / "format_val_split.jsonl"
    write_jsonl(train_set, train_path)
    write_jsonl(val_set, val_path)
    print(f"\nWrote {train_path} ({len(train_set)} examples)")
    print(f"Wrote {val_path} ({len(val_set)} examples)")

    # Also write a combined JSON file (some frameworks prefer this)
    combined_path = output_dir / "format_train_split.json"
    with open(combined_path, "w") as f:
        json.dump([{"messages": ex["messages"]} for ex in train_set], f, indent=2)
    print(f"Wrote {combined_path}")


if __name__ == "__main__":
    main()
