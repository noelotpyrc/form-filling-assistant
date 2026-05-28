#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "torch>=2.5",
#     "transformers>=4.50",
#     "trl>=0.23",
#     "peft>=0.15",
#     "datasets>=4.0",
#     "accelerate>=1.0",
# ]
# ///
"""
debug_grpo_cpu.py — Local CPU test for GRPO training flow.

No Unsloth dependency. Uses vanilla HuggingFace + TRL to validate:
1. Model loads (tiny model or Qwen3.5-0.8B if available)
2. Reward functions parse DSPy format correctly
3. GRPOTrainer can do 1 training step on CPU
4. Confirms the training loop works before going to Colab

Usage:
    cd form-filling-assistant/tuning/rl
    uv run debug_grpo_cpu.py                  # tiny model (fast, ~2 min)
    uv run debug_grpo_cpu.py --qwen           # real Qwen3.5-0.8B (~10 min, needs ~4GB RAM)
    uv run debug_grpo_cpu.py --skip-training  # only test reward functions + data loading
"""

import argparse
import json
import os
import sys
import ast
import time

os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch
torch._dynamo.config.disable = True

from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
from trl import GRPOTrainer, GRPOConfig
from datasets import Dataset


# ─── Reward functions (same as Colab notebook) ───────────────────────

def parse_list(s):
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    try:
        r = ast.literal_eval(s)
        return r if isinstance(r, list) else []
    except Exception:
        return []


def parse_dspy(text):
    try:
        if "[[ ## field_ids ## ]]" not in text:
            return [], []
        ids = text.split("[[ ## field_ids ## ]]")[1].split("[[ ## field_values ## ]]")[0].strip()
        vals = text.split("[[ ## field_values ## ]]")[1]
        if "[[ ## completed ## ]]" in vals:
            vals = vals.split("[[ ## completed ## ]]")[0].strip()
        else:
            vals = vals.strip()
        return parse_list(ids), parse_list(vals)
    except Exception:
        return [], []


def get_text(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list) and c:
        msg = c[0]
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(x.get("text", "") for x in content if isinstance(x, dict))
    return str(c)


def format_reward(completions, **kw):
    """Reward for correct DSPy output format."""
    scores = []
    for c in completions:
        t = get_text(c)
        ids, vals = parse_dspy(t)
        s = 0.0
        markers = ["[[ ## field_ids ## ]]", "[[ ## field_values ## ]]", "[[ ## completed ## ]]"]
        if all(m in t for m in markers):
            s += 1.0
            if ids and len(ids) == len(vals):
                s += 1.0
        scores.append(s)
    return scores


def accuracy_reward(completions, ground_truth_ids, ground_truth_values, **kw):
    """Reward for correct field extraction (F1 + exact match)."""
    scores = []
    for c, gt_i, gt_v in zip(completions, ground_truth_ids, ground_truth_values):
        t = get_text(c)
        gt_ids, gt_vals = json.loads(gt_i), json.loads(gt_v)
        pred_ids, pred_vals = parse_dspy(t)

        if not gt_ids:
            scores.append(1.5 if not pred_ids else 0.0)
            continue
        if not pred_ids:
            scores.append(0.0)
            continue

        gt_s, pred_s = set(gt_ids), set(pred_ids)
        tp = len(gt_s & pred_s)
        p = tp / len(pred_s) if pred_s else 0
        r = tp / len(gt_s) if gt_s else 0
        f1 = 2 * p * r / (p + r) if p + r else 0
        gt_map = dict(zip(gt_ids, gt_vals))
        pred_map = dict(zip(pred_ids, pred_vals))
        cv = sum(1 for fid in gt_s & pred_s if str(pred_map.get(fid, "")).strip() == str(gt_map[fid]).strip())
        scores.append(f1 * 1.5 + (cv / len(gt_s)) * 1.5)
    return scores


# ─── Test reward functions first ─────────────────────────────────────

def test_reward_functions():
    """Verify reward functions work correctly before training."""
    print("\n" + "=" * 60)
    print("TEST: Reward functions")
    print("=" * 60)

    good = '[[ ## field_ids ## ]]\n["name", "amount"]\n\n[[ ## field_values ## ]]\n["John", "$12.50"]\n\n[[ ## completed ## ]]'
    bad = "I found the name John and amount $12.50"
    partial = '[[ ## field_ids ## ]]\n["name"]\n\n[[ ## field_values ## ]]\n["John"]\n\n[[ ## completed ## ]]'

    gt_ids = json.dumps(["name", "amount"])
    gt_vals = json.dumps(["John", "$12.50"])

    # Format reward
    fmt = format_reward([good, bad, partial])
    print(f"  Format: good={fmt[0]}, bad={fmt[1]}, partial={fmt[2]}")
    assert fmt[0] == 2.0, f"Good format should be 2.0, got {fmt[0]}"
    assert fmt[1] == 0.0, f"Bad format should be 0.0, got {fmt[1]}"
    assert fmt[2] == 2.0, f"Partial format should be 2.0, got {fmt[2]}"

    # Accuracy reward
    acc = accuracy_reward(
        [good, bad, partial],
        [gt_ids] * 3,
        [gt_vals] * 3,
    )
    print(f"  Accuracy: good={acc[0]:.2f}, bad={acc[1]:.2f}, partial={acc[2]:.2f}")
    assert acc[0] == 3.0, f"Good accuracy should be 3.0, got {acc[0]}"
    assert acc[1] == 0.0, f"Bad accuracy should be 0.0, got {acc[1]}"
    assert acc[2] > 0 and acc[2] < 3.0, f"Partial should be between 0 and 3, got {acc[2]}"

    # Test with single-quoted lists (Python format)
    single_quote = "[[ ## field_ids ## ]]\n['name', 'amount']\n\n[[ ## field_values ## ]]\n['John', '$12.50']\n\n[[ ## completed ## ]]"
    ids, vals = parse_dspy(single_quote)
    print(f"  Single-quote parse: ids={ids}, vals={vals}")
    assert ids == ["name", "amount"], f"Single-quote ids failed: {ids}"

    print("  ✓ All reward function tests passed\n")


# ─── Test GRPO training ─────────────────────────────────────────────

def test_grpo_training(use_qwen=False):
    """Test GRPO training loop on CPU with a tiny model."""
    print("=" * 60)
    if use_qwen:
        print("TEST: GRPO training with Qwen3.5-0.8B on CPU")
        model_name = "Qwen/Qwen3.5-0.8B"
    else:
        print("TEST: GRPO training with tiny model on CPU")
        model_name = "HuggingFaceTB/SmolLM2-135M-Instruct"
    print("=" * 60)

    print(f"\n  Loading {model_name}...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float32,  # CPU needs float32
        device_map="cpu",
        trust_remote_code=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"  Loaded in {time.time() - t0:.1f}s")
    print(f"  Params: {sum(p.numel() for p in model.parameters()):,}")

    # Add LoRA
    print("  Adding LoRA...")
    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Trainable params: {trainable:,}")

    # Create test dataset — use real data format
    print("  Creating test dataset...")
    data_path = os.path.join(os.path.dirname(__file__), "grpo_extractor_mutated.jsonl")
    if os.path.exists(data_path):
        with open(data_path) as f:
            raw = [json.loads(line) for i, line in enumerate(f) if i < 8]
        test_data = []
        for r in raw:
            test_data.append({
                "prompt": r["prompt"],  # list of message dicts
                "ground_truth_ids": json.dumps(r["ground_truth_ids"]),
                "ground_truth_values": json.dumps(r["ground_truth_values"]),
            })
        print(f"  Using {len(test_data)} real examples from grpo_extractor_mutated.jsonl")
    else:
        print("  grpo_extractor_mutated.jsonl not found, using synthetic data")
        test_data = [
            {
                "prompt": [
                    {"role": "system", "content": "Extract form fields from the text."},
                    {"role": "user", "content": "Form has: Name: John Smith, Amount: $12.50"},
                ],
                "ground_truth_ids": json.dumps(["name", "amount"]),
                "ground_truth_values": json.dumps(["John Smith", "$12.50"]),
            }
        ] * 8

    dataset = Dataset.from_list(test_data)

    # Create trainer
    print("  Creating GRPOTrainer...")
    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[format_reward, accuracy_reward],
        args=GRPOConfig(
            output_dir="/tmp/grpo_cpu_test",
            max_steps=1,
            num_generations=2,           # Small for CPU
            per_device_train_batch_size=1,
            gradient_accumulation_steps=2,
            max_completion_length=64,    # Short for CPU speed
            learning_rate=5e-6,
            report_to="none",
            bf16=False,                  # CPU doesn't support bf16
            fp16=False,
        ),
        train_dataset=dataset,
    )
    print("  Trainer created successfully!")

    # Train 1 step
    print("\n  Starting training (1 step on CPU, this will be slow)...")
    t0 = time.time()
    try:
        trainer.train()
        elapsed = time.time() - t0
        print(f"\n  ✓ Training completed in {elapsed:.1f}s")
        print("  ✓ GRPO training loop works on CPU!")
        return True
    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n  ✗ Training failed after {elapsed:.1f}s")
        print(f"  Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


# ─── Test with real data loading ─────────────────────────────────────

def test_data_loading():
    """Test that the GRPO data loads and parses correctly."""
    print("\n" + "=" * 60)
    print("TEST: Data loading")
    print("=" * 60)

    data_path = os.path.join(os.path.dirname(__file__), "grpo_extractor_mutated.jsonl")
    if not os.path.exists(data_path):
        print(f"  ⚠ {data_path} not found, skipping")
        return

    with open(data_path) as f:
        lines = f.readlines()
    print(f"  Total examples: {len(lines):,}")

    # Parse first few
    for i in range(min(3, len(lines))):
        r = json.loads(lines[i])
        prompt = r["prompt"]
        gt_ids = r["ground_truth_ids"]
        gt_vals = r["ground_truth_values"]
        print(f"\n  Example {i}:")
        print(f"    Prompt roles: {[m['role'] for m in prompt]}")
        print(f"    System msg length: {len(prompt[0]['content'])}")
        print(f"    User msg length: {len(prompt[1]['content'])}")
        print(f"    GT IDs: {gt_ids[:3]}{'...' if len(gt_ids) > 3 else ''}")
        print(f"    GT vals: {[str(v)[:30] for v in gt_vals[:3]]}{'...' if len(gt_vals) > 3 else ''}")

    print(f"\n  ✓ Data loading works\n")


# ─── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Debug GRPO training on CPU")
    parser.add_argument("--qwen", action="store_true", help="Use Qwen3.5-0.8B instead of tiny model")
    parser.add_argument("--skip-training", action="store_true", help="Only test reward functions and data loading")
    args = parser.parse_args()

    print("GRPO CPU Debug Script")
    print(f"  torch: {torch.__version__}")
    print(f"  Device: CPU (MPS available: {torch.backends.mps.is_available()})")
    print(f"  Python: {sys.version.split()[0]}")

    # Test 1: Reward functions (fast, no model needed)
    test_reward_functions()

    # Test 2: Data loading
    test_data_loading()

    if args.skip_training:
        print("\nSkipping training test (--skip-training)")
        sys.exit(0)

    # Test 3: GRPO training
    success = test_grpo_training(use_qwen=args.qwen)

    print("\n" + "=" * 60)
    if success:
        print("ALL TESTS PASSED — GRPO flow works on CPU")
        print("Next: run on Colab with GPU + Unsloth for actual training")
    else:
        print("TRAINING TEST FAILED — debug the error above")
    print("=" * 60)
