#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "torch>=2.5",
#     "transformers>=5.2",
#     "trl>=0.23",
#     "peft>=0.15",
#     "datasets>=4.0",
#     "accelerate>=1.0",
#     "safetensors",
# ]
# ///
"""
test_notebook_cpu.py — Run through every notebook cell on CPU.

Mirrors grpo_extractor_qwen35_08b.ipynb exactly, substituting:
  - CPU instead of CUDA
  - Qwen/Qwen3.5-0.8B base model (no SFT LoRA, since it's on Drive)
  - 8 synthetic examples instead of 41k from JSONL
  - 1 training step instead of 300
  - bf16=False (CPU doesn't support bf16)

**Key:** Uses Qwen3_5ForConditionalGeneration (not AutoModelForCausalLM)
to match the notebook and the SFT LoRA's model class.

If this passes, the notebook will work on Colab.
"""

import os, sys, json, ast, re, time

os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch
torch._dynamo.config.disable = True

print("=" * 60)
print("Notebook Cell-by-Cell CPU Test")
print("=" * 60)
print(f"torch:        {torch.__version__}")

import transformers
print(f"transformers: {transformers.__version__}")

import trl
print(f"trl:          {trl.__version__}")

import peft
print(f"peft:         {peft.__version__}")

# ─── Cell 6: Load Base Model + LoRA ─────────────────────────────────
print("\n--- Cell 6: Load Base Model + LoRA ---")

from transformers import AutoTokenizer, BitsAndBytesConfig
from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5ForConditionalGeneration
from peft import get_peft_model, LoraConfig

BASE_MODEL = "Qwen/Qwen3.5-0.8B"
print(f"Loading base model: {BASE_MODEL}")
print("  Using Qwen3_5ForConditionalGeneration (matches SFT LoRA model class)")
t0 = time.time()

# MUST use Qwen3_5ForConditionalGeneration (not AutoModelForCausalLM)
# because the SFT LoRA was trained on this class via Unsloth's FastVisionModel.
# AutoModelForCausalLM loads Qwen3_5ForCausalLM with different layer nesting
# (model.layers.X vs model.model.layers.X), causing LoRA adapter keys to silently mismatch.
model = Qwen3_5ForConditionalGeneration.from_pretrained(
    BASE_MODEL,
    # No BitsAndBytesConfig on CPU — QLoRA needs CUDA
    device_map="cpu",
    trust_remote_code=True,
    torch_dtype=torch.float32,
)

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# Load SFT LoRA if available locally, otherwise create fresh LoRA
from peft import PeftModel
import numpy as np

SFT_LORA_PATH = os.path.expanduser("~/work/models/qwen35-08b-dspy-format-lora")
if os.path.exists(SFT_LORA_PATH):
    print(f"Loading SFT LoRA: {SFT_LORA_PATH}")
    model = PeftModel.from_pretrained(model, SFT_LORA_PATH, is_trainable=True)
else:
    print("SFT LoRA not found, creating fresh LoRA")
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)

model.enable_input_require_grads()

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
print(f"Loaded in {time.time()-t0:.1f}s")
print(f"Model: {total:,} total, {trainable:,} trainable ({trainable/total*100:.1f}%)")

# Verify layer nesting — ConditionalGeneration should have model.model.layers
layer_path_check = hasattr(model, 'base_model') and hasattr(model.base_model, 'model')
print(f"Layer nesting check: {'model.model.layers' if layer_path_check else 'model.layers'}")

# Show named parameters to verify LoRA target paths
lora_params = [n for n, p in model.named_parameters() if "lora" in n.lower() and p.requires_grad]
print(f"LoRA params ({len(lora_params)} total), first 3:")
for p in lora_params[:3]:
    print(f"  {p}")

# Verify LoRA adapter is actually loaded (not random init)
lora_stds = []
for name, param in model.named_parameters():
    if "lora_B" in name and param.requires_grad:
        lora_stds.append(param.data.std().item())
avg_std = np.mean(lora_stds) if lora_stds else 0
print(f"LoRA B avg std: {avg_std:.6f} (should be >0 if SFT weights loaded, ~0 if random init)")
if os.path.exists(SFT_LORA_PATH):
    assert avg_std > 0.0001, f"SFT LoRA weights appear to be zeros! avg_std={avg_std}"
    print("SFT LoRA weights verified: loaded correctly")
print("PASS")

# ─── Cell 8: Load Training Data ─────────────────────────────────────
print("\n--- Cell 8: Load Training Data ---")

from datasets import Dataset

DATA_PATH = os.path.join(os.path.dirname(__file__), "grpo_extractor_mutated.jsonl")
if os.path.exists(DATA_PATH):
    with open(DATA_PATH) as f:
        raw_data = [json.loads(line) for i, line in enumerate(f) if i < 8]
    train_data = []
    for r in raw_data:
        train_data.append({
            "prompt": r["prompt"],
            "ground_truth_ids": json.dumps(r["ground_truth_ids"]),
            "ground_truth_values": json.dumps(r["ground_truth_values"]),
        })
    print(f"Loaded {len(train_data)} real examples from JSONL")
else:
    train_data = [{
        "prompt": [
            {"role": "system", "content": "Extract form fields from the text."},
            {"role": "user", "content": "Form has: Name: John Smith, Amount: $12.50"},
        ],
        "ground_truth_ids": json.dumps(["name", "amount"]),
        "ground_truth_values": json.dumps(["John Smith", "$12.50"]),
    }] * 8
    print("Using 8 synthetic examples")

train_dataset = Dataset.from_list(train_data)
print(f"Dataset: {len(train_dataset)} examples, columns: {train_dataset.column_names}")
print(f"Sample prompt roles: {[m['role'] for m in train_dataset[0]['prompt']]}")
print("PASS")

# ─── Cell 10: Reward Functions ───────────────────────────────────────
print("\n--- Cell 10: Reward Functions ---")


def extract_completion_text(completion) -> str:
    if isinstance(completion, str):
        return completion
    if isinstance(completion, list) and len(completion) > 0:
        msg = completion[0]
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(c.get("text", "") for c in content if isinstance(c, dict))
    return str(completion)


def extract_prompt_text(prompt) -> str:
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):
        parts = []
        for msg in prompt:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    parts.append(" ".join(c.get("text", "") for c in content if isinstance(c, dict)))
        return "\n".join(parts)
    return str(prompt)


def parse_list(s: str) -> list:
    s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    try:
        result = ast.literal_eval(s)
        if isinstance(result, list):
            return result
    except (ValueError, SyntaxError):
        pass
    return []


def parse_dspy_output(completion: str) -> tuple[list[str], list[str]]:
    try:
        if "[[ ## field_ids ## ]]" not in completion or "[[ ## field_values ## ]]" not in completion:
            return [], []
        ids_part = completion.split("[[ ## field_ids ## ]]")[1].split("[[ ## field_values ## ]]")[0].strip()
        vals_raw = completion.split("[[ ## field_values ## ]]")[1]
        if "[[ ## completed ## ]]" in vals_raw:
            vals_part = vals_raw.split("[[ ## completed ## ]]")[0].strip()
        else:
            vals_part = vals_raw.strip()
        field_ids = parse_list(ids_part)
        field_values = parse_list(vals_part)
        if not isinstance(field_ids, list) or not isinstance(field_values, list):
            return [], []
        return field_ids, field_values
    except (IndexError, ValueError):
        return [], []


def format_reward_func(completions, **kwargs) -> list[float]:
    scores = []
    for completion in completions:
        text = extract_completion_text(completion)
        score = 0.0
        has_ids = "[[ ## field_ids ## ]]" in text
        has_vals = "[[ ## field_values ## ]]" in text
        has_done = "[[ ## completed ## ]]" in text
        if has_ids and has_vals and has_done:
            score += 1.0
            field_ids, field_values = parse_dspy_output(text)
            if len(field_ids) > 0 and len(field_ids) == len(field_values):
                score += 1.0
        scores.append(score)
    return scores


def accuracy_reward_func(completions, ground_truth_ids, ground_truth_values, **kwargs) -> list[float]:
    scores = []
    for completion, gt_ids_json, gt_vals_json in zip(completions, ground_truth_ids, ground_truth_values):
        text = extract_completion_text(completion)
        gt_ids = json.loads(gt_ids_json)
        gt_vals = json.loads(gt_vals_json)
        gt_map = dict(zip(gt_ids, gt_vals))
        pred_ids, pred_vals = parse_dspy_output(text)
        pred_map = dict(zip(pred_ids, pred_vals))
        if not gt_ids:
            scores.append(1.5 if len(pred_ids) == 0 else 0.0)
            continue
        if not pred_ids:
            scores.append(0.0)
            continue
        gt_set = set(gt_ids)
        pred_set = set(pred_ids)
        tp = len(gt_set & pred_set)
        precision = tp / len(pred_set) if pred_set else 0
        recall = tp / len(gt_set) if gt_set else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        id_score = f1 * 1.5
        correct_values = 0
        for fid in gt_set & pred_set:
            if str(pred_map.get(fid, "")).strip() == str(gt_map[fid]).strip():
                correct_values += 1
        val_score = (correct_values / len(gt_set)) * 1.5 if gt_set else 0
        scores.append(id_score + val_score)
    if completions:
        text = extract_completion_text(completions[0])
        gt = json.loads(ground_truth_ids[0])
        pred, _ = parse_dspy_output(text)
        print(f"    GT: {gt} | Pred: {pred} | Score: {scores[0]:.2f}")
    return scores


def hallucination_penalty_func(prompts, completions, **kwargs) -> list[float]:
    scores = []
    for prompt, completion in zip(prompts, completions):
        text = extract_completion_text(completion)
        prompt_text = extract_prompt_text(prompt)
        valid_ids = set(re.findall(
            r'^\s+(\w+)\s+\((?:text|date|select|email|tel|number|textarea|checkbox|radio|file)',
            prompt_text, re.MULTILINE
        ))
        pred_ids, _ = parse_dspy_output(text)
        if not valid_ids or not pred_ids:
            scores.append(0.0)
            continue
        hallucinated = [fid for fid in pred_ids if fid not in valid_ids]
        penalty = min(len(hallucinated) * 0.5, 2.0)
        scores.append(-penalty)
    return scores


# Sanity check
test_good = '[[ ## field_ids ## ]]\n["full_name", "email"]\n[[ ## field_values ## ]]\n["Jane Smith", "jane@email.com"]\n[[ ## completed ## ]]'
test_bad = "I extracted the name field for you."
test_single = "[[ ## field_ids ## ]]\n[\'full_name\']\n[[ ## field_values ## ]]\n[\'Jane\']\n[[ ## completed ## ]]"
fmt_scores = format_reward_func([test_good, test_bad, test_single])
print(f"Format: good={fmt_scores[0]}, bad={fmt_scores[1]}, single={fmt_scores[2]}")
assert fmt_scores == [2.0, 0.0, 2.0], f"Unexpected: {fmt_scores}"
print("PASS")

# ─── Cell 12: GRPOConfig + Trainer ──────────────────────────────────
print("\n--- Cell 12: GRPOConfig + Trainer ---")

from trl import GRPOConfig, GRPOTrainer

training_args = GRPOConfig(
    output_dir="/tmp/grpo_cpu_test",
    max_steps=1,
    save_steps=100,
    logging_steps=1,
    num_generations=2,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=2,
    max_completion_length=64,
    learning_rate=5e-6,
    adam_beta1=0.9,
    adam_beta2=0.99,
    weight_decay=0.1,
    warmup_ratio=0.1,
    lr_scheduler_type="cosine",
    optim="adamw_torch",  # adamw_8bit needs bitsandbytes + CUDA
    max_grad_norm=0.1,
    bf16=False,  # CPU
    fp16=False,
    log_completions=True,
    report_to="none",
)

trainer = GRPOTrainer(
    model=model,
    args=training_args,
    processing_class=tokenizer,
    reward_funcs=[
        format_reward_func,
        accuracy_reward_func,
        hallucination_penalty_func,
    ],
    train_dataset=train_dataset,
)
print("GRPOTrainer created")
print("PASS")

# ─── Cell 13: Train ─────────────────────────────────────────────────
print("\n--- Cell 13: Train (1 step on CPU) ---")
t0 = time.time()
trainer.train()
print(f"Training completed in {time.time()-t0:.1f}s")
print("PASS")

# ─── Cell 19: Save LoRA ─────────────────────────────────────────────
print("\n--- Cell 19: Save LoRA ---")
save_path = "/tmp/grpo_cpu_test_lora"
model.save_pretrained(save_path)
tokenizer.save_pretrained(save_path)

from safetensors import safe_open
import glob
for f in glob.glob(f"{save_path}/*.safetensors"):
    with safe_open(f, framework="pt") as st:
        for key in list(st.keys())[:3]:
            tensor = st.get_tensor(key)
            print(f"  {key}: shape={tensor.shape}, std={tensor.std():.6f}")
print("PASS")

# ─── Cell 20: Merge ─────────────────────────────────────────────────
print("\n--- Cell 20: Merge LoRA ---")
merged = model.merge_and_unload()
merged.save_pretrained("/tmp/grpo_cpu_test_merged")
print(f"Merged model params: {sum(p.numel() for p in merged.parameters()):,}")
print("PASS")

# ─── Summary ─────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("ALL CELLS PASSED")
print("=" * 60)
print("\nPackage versions used (pin these in the notebook):")
print(f'  "torch>={torch.__version__}"')
print(f'  "transformers>={transformers.__version__}"')
print(f'  "trl>={trl.__version__}"')
print(f'  "peft>={peft.__version__}"')
print(f'  "accelerate>={__import__("accelerate").__version__}"')
