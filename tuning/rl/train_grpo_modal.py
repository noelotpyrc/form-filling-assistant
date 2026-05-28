"""
train_grpo_modal.py — GRPO training on Modal with remote GPU.

Usage:
    modal run tuning/rl/train_grpo_modal.py                        # full 300-step training
    modal run tuning/rl/train_grpo_modal.py --max-steps 5          # quick test
    modal run tuning/rl/train_grpo_modal.py --max-steps 600 --resume           # resume from HF checkpoint
    modal run tuning/rl/train_grpo_modal.py --max-steps 300 --use-grpo-lora   # continue from previous GRPO LoRA
    modal run tuning/rl/train_grpo_modal.py --gpu T4               # cheaper GPU

Monitors in real-time. Ctrl-C detaches (training continues).
Reattach via: modal app logs

Artifacts saved to Modal Volume "grpo-checkpoints" and downloaded locally after training.
"""

import modal
import os
from pathlib import Path

# ─── Modal Setup ────────────────────────────────────────────────────

app = modal.App("grpo-extractor-qwen35-08b")

# Local paths for data that gets added to the image
LOCAL_SFT_LORA = Path.home() / "work/models/qwen35-08b-dspy-format-lora"
LOCAL_DATA = (
    Path.home()
    / "work/form-filling-assistant/tuning/rl/grpo_extractor_mutated.jsonl"
)

# Training image with pinned versions (same as notebook + local CPU test)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch>=2.5",
        "transformers==5.5.4",
        "trl==1.1.0",
        "peft==0.19.0",
        "datasets>=4.0",
        "accelerate==1.13.0",
        "bitsandbytes>=0.45",
        "safetensors",
        "numpy",
    )
    .add_local_dir(str(LOCAL_SFT_LORA), remote_path="/data/sft-lora")
    .add_local_file(str(LOCAL_DATA), remote_path="/data/grpo_extractor_mutated.jsonl")
)

# Persistent volume for checkpoints + output
# Mounted at /vol inside the container. Browsable via `modal volume ls grpo-checkpoints`.
#
# Volume layout (all written during/after training):
#   grpo_outputs/              — HF Trainer auto-checkpoints (saved every save_steps during training)
#     checkpoint-100/            adapter weights + optimizer + scheduler + trainer state
#     checkpoint-200/            (used by --resume to continue from exact training state)
#     checkpoint-300/
#   grpo-extractor-lora/       — Clean LoRA adapter (saved after training completes)
#                                Just adapter_model.safetensors + tokenizer. No optimizer baggage.
#                                Use with: PeftModel.from_pretrained(base_model, path)
#   log_history.json           — Training metrics per step (reward, loss, etc.)
#
# Merged standalone models are produced by merge_checkpoints_modal.py (separate
# script) using an fp16 base, NOT here — merging with the 4-bit training base
# introduces rounding errors. Merged models live under `merged/checkpoint-{N}/`.
#
# Note: The SFT LoRA (starting point) is NOT on this volume — it's baked into the
# container image at /data/sft-lora via image.add_local_dir() above.
volume = modal.Volume.from_name("grpo-checkpoints", create_if_missing=True)
VOLUME_PATH = Path("/vol")
OUTPUT_DIR = VOLUME_PATH / "grpo_outputs"

# ─── Reward Functions ───────────────────────────────────────────────
# Defined at module level so Modal can serialize them.

import json
import ast
import re


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
                return " ".join(
                    c.get("text", "") for c in content if isinstance(c, dict)
                )
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
                    parts.append(
                        " ".join(
                            c.get("text", "")
                            for c in content
                            if isinstance(c, dict)
                        )
                    )
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
        if (
            "[[ ## field_ids ## ]]" not in completion
            or "[[ ## field_values ## ]]" not in completion
        ):
            return [], []
        ids_part = (
            completion.split("[[ ## field_ids ## ]]")[1]
            .split("[[ ## field_values ## ]]")[0]
            .strip()
        )
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


def accuracy_reward_func(
    completions, ground_truth_ids, ground_truth_values, **kwargs
) -> list[float]:
    scores = []
    for completion, gt_ids_json, gt_vals_json in zip(
        completions, ground_truth_ids, ground_truth_values
    ):
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
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0
        )
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
        print(f"--- GT: {gt} | Pred: {pred} | Score: {scores[0]:.2f}")
    return scores


def hallucination_penalty_func(prompts, completions, **kwargs) -> list[float]:
    scores = []
    for prompt, completion in zip(prompts, completions):
        text = extract_completion_text(completion)
        prompt_text = extract_prompt_text(prompt)
        valid_ids = set(
            re.findall(
                r"^\s+(\w+)\s+\((?:text|date|select|email|tel|number|textarea|checkbox|radio|file)",
                prompt_text,
                re.MULTILINE,
            )
        )
        pred_ids, _ = parse_dspy_output(text)
        if not valid_ids or not pred_ids:
            scores.append(0.0)
            continue
        hallucinated = [fid for fid in pred_ids if fid not in valid_ids]
        penalty = min(len(hallucinated) * 0.5, 2.0)
        scores.append(-penalty)
    return scores


# ─── Training Function ─────────────────────────────────────────────


@app.function(
    image=image,
    gpu="L4",  # 24GB VRAM, good balance of price + headroom
    timeout=6 * 60 * 60,  # 6 hours max
    volumes={str(VOLUME_PATH): volume},
)
def train(max_steps: int = 300, resume: bool = False, use_grpo_lora: bool = False, gpu_type: str = ""):
    import torch
    import numpy as np
    from transformers import AutoTokenizer, BitsAndBytesConfig
    from transformers.models.qwen3_5.modeling_qwen3_5 import (
        Qwen3_5ForConditionalGeneration,
    )
    from peft import PeftModel
    from trl import GRPOConfig, GRPOTrainer
    from datasets import Dataset
    from collections import Counter

    print("=" * 60)
    print("GRPO Training — Modal")
    print("=" * 60)
    print(f"torch:        {torch.__version__}")
    print(f"CUDA:         {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU:          {torch.cuda.get_device_name(0)}")
        mem_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"VRAM:         {mem_gb:.1f} GB")
    print(f"max_steps:    {max_steps}")
    print(f"resume:       {resume}")
    print(f"use_grpo_lora: {use_grpo_lora}")

    # ─── Load Base Model + SFT LoRA ────────────────────────────────
    print("\n--- Loading base model ---")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    BASE_MODEL = "Qwen/Qwen3.5-0.8B"
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )

    # Choose LoRA: either previous GRPO output (continue training) or original SFT
    GRPO_LORA_PATH = str(VOLUME_PATH / "grpo-extractor-lora")
    SFT_LORA_PATH = "/data/sft-lora"

    import os
    if use_grpo_lora and os.path.exists(GRPO_LORA_PATH):
        lora_path = GRPO_LORA_PATH
        print(f"Loading GRPO LoRA (continuing from previous run): {lora_path}")
    else:
        lora_path = SFT_LORA_PATH
        if use_grpo_lora:
            print(f"GRPO LoRA not found on volume, falling back to SFT LoRA")
        print(f"Loading SFT LoRA: {lora_path}")

    tokenizer = AutoTokenizer.from_pretrained(lora_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = PeftModel.from_pretrained(model, lora_path, is_trainable=True)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(
        f"Model: {total:,} total, {trainable:,} trainable ({trainable/total*100:.1f}%)"
    )

    # Verify LoRA loaded (not random) and measure weight stats
    lora_stds = []
    for name, param in model.named_parameters():
        if "lora_B" in name and param.requires_grad:
            lora_stds.append(param.data.std().item())
    avg_std = np.mean(lora_stds) if lora_stds else 0
    print(f"LoRA B avg std: {avg_std:.6f}")
    assert avg_std > 0.0001, f"LoRA weights appear to be zeros! avg_std={avg_std}"
    print("✓ LoRA weights verified (non-zero)")

    # If continuing from GRPO LoRA, measure drift from SFT baseline
    if use_grpo_lora and os.path.exists(SFT_LORA_PATH):
        from safetensors import safe_open
        sft_weights = {}
        for sf in [f for f in os.listdir(SFT_LORA_PATH) if f.endswith(".safetensors")]:
            with safe_open(os.path.join(SFT_LORA_PATH, sf), framework="pt") as st:
                for key in st.keys():
                    sft_weights[key] = st.get_tensor(key)

        l2_dists = []
        rel_changes = []
        cos_sims = []
        for name, param in model.named_parameters():
            # Strip PEFT wrapper prefix to match safetensor keys
            key = name.replace(".default", "")
            if key in sft_weights:
                sft_w = sft_weights[key].float()
                cur_w = param.data.float().cpu()
                diff = cur_w - sft_w
                l2 = diff.norm().item()
                sft_norm = sft_w.norm().item()
                rel = l2 / sft_norm if sft_norm > 0 else 0
                cos = torch.nn.functional.cosine_similarity(
                    cur_w.flatten().unsqueeze(0),
                    sft_w.flatten().unsqueeze(0),
                ).item()
                l2_dists.append(l2)
                rel_changes.append(rel)
                cos_sims.append(cos)

        if l2_dists:
            print(f"\n  Weight drift from SFT baseline ({len(l2_dists)} params):")
            print(f"    L2 distance:     mean={np.mean(l2_dists):.6f}, max={np.max(l2_dists):.6f}")
            print(f"    Relative change: mean={np.mean(rel_changes):.4%}, max={np.max(rel_changes):.4%}")
            print(f"    Cosine sim:      mean={np.mean(cos_sims):.6f}, min={np.min(cos_sims):.6f}")
            print(f"    (cosine=1.0 means no change, <1.0 means weights have shifted)")
        else:
            print("  Warning: could not compare weights (key mismatch)")

    # ─── Load Training Data ────────────────────────────────────────
    print("\n--- Loading training data ---")
    DATA_PATH = "/data/grpo_extractor_mutated.jsonl"
    with open(DATA_PATH) as f:
        raw_data = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(raw_data)} examples")
    print(f"Source distribution: {Counter(r['source'] for r in raw_data)}")

    train_data = []
    for r in raw_data:
        train_data.append(
            {
                "prompt": r["prompt"],
                "ground_truth_ids": json.dumps(r["ground_truth_ids"]),
                "ground_truth_values": json.dumps(r["ground_truth_values"]),
            }
        )
    train_dataset = Dataset.from_list(train_data)
    print(f"Dataset: {len(train_dataset)} examples")

    # ─── GRPO Training ─────────────────────────────────────────────
    print("\n--- Creating GRPOTrainer ---")
    output_dir = str(OUTPUT_DIR)

    training_args = GRPOConfig(
        output_dir=output_dir,
        max_steps=max_steps,
        save_steps=100,
        logging_steps=1,
        num_generations=4,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        max_completion_length=512,
        learning_rate=5e-6,
        adam_beta1=0.9,
        adam_beta2=0.99,
        weight_decay=0.1,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        optim="adamw_8bit",
        max_grad_norm=0.1,
        bf16=True,
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

    # GPU memory before training
    if torch.cuda.is_available():
        start_mem = torch.cuda.max_memory_reserved() / 1024**3
        print(f"GPU memory reserved before training: {start_mem:.1f} GB")

    # Commit volume after each checkpoint save
    from transformers import TrainerCallback

    class VolumeCommitCallback(TrainerCallback):
        def on_save(self, args, state, control, **kwargs):
            volume.commit()
            print(f"  Volume committed at step {state.global_step}")

    trainer.add_callback(VolumeCommitCallback())

    # Train! Resume from latest checkpoint if requested.
    checkpoint_path = None
    if resume:
        import glob
        checkpoints = sorted(
            glob.glob(str(OUTPUT_DIR / "checkpoint-*")),
            key=lambda x: int(x.split("-")[-1]),
        )
        if checkpoints:
            checkpoint_path = checkpoints[-1]
            print(f"\n--- Resuming from {checkpoint_path} (→ {max_steps} total steps) ---")
        else:
            print("\n--- No checkpoint found, starting fresh ---")
    else:
        print(f"\n--- Training ({max_steps} steps) ---")

    trainer.train(resume_from_checkpoint=checkpoint_path)

    if torch.cuda.is_available():
        peak_mem = torch.cuda.max_memory_reserved() / 1024**3
        print(f"Peak GPU memory: {peak_mem:.1f} GB")

    # ─── Save Training Log History ─────────────────────────────────
    log_path = str(VOLUME_PATH / "log_history.json")
    with open(log_path, "w") as f:
        json.dump(trainer.state.log_history, f, indent=2)
    print(f"Saved log history: {log_path} ({len(trainer.state.log_history)} entries)")

    # ─── Save LoRA ─────────────────────────────────────────────────
    # Save clean LoRA adapter from the live model in memory (after all training steps).
    # This may differ from the last auto-checkpoint if training didn't end on a save_steps boundary.
    # E.g. 350 steps with save_steps=100 → last checkpoint is step 300, but this saves step 350.
    print("\n--- Saving LoRA adapter ---")
    lora_path = str(VOLUME_PATH / "grpo-extractor-lora")
    model.save_pretrained(lora_path)
    tokenizer.save_pretrained(lora_path)

    from safetensors import safe_open
    import glob

    for f in glob.glob(f"{lora_path}/*.safetensors"):
        with safe_open(f, framework="pt") as st:
            for key in list(st.keys())[:3]:
                tensor = st.get_tensor(key)
                print(
                    f"  {key}: shape={tensor.shape}, std={tensor.std():.6f}"
                )

    # Note: We do NOT merge LoRA into the base model here. The base is loaded
    # at 4-bit (QLoRA), so merging causes rounding-error degradation (PEFT warns
    # about this). For eval or deployment, run `merge_checkpoints_modal.py`
    # separately — it loads an fp16 base and produces a clean merged model.
    # See tuning/rl/EVAL_PLAN.md §5 for details.

    volume.commit()

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print(f"LoRA adapter:  {lora_path}")
    print("To produce a deployable merged model, run:")
    print("  modal run tuning/rl/merge_checkpoints_modal.py")
    print("=" * 60)

    return {"lora_path": lora_path}


# ─── Local Entrypoint ──────────────────────────────────────────────


@app.local_entrypoint()
def main(max_steps: int = 300, resume: bool = False, use_grpo_lora: bool = False, gpu: str = "L4"):
    print(f"Launching GRPO training on Modal ({gpu}, {max_steps} steps, resume={resume}, use_grpo_lora={use_grpo_lora})")
    print(f"SFT LoRA: {LOCAL_SFT_LORA}")
    print(f"Data: {LOCAL_DATA}")

    # Verify local files exist before uploading
    assert LOCAL_SFT_LORA.exists(), f"SFT LoRA not found: {LOCAL_SFT_LORA}"
    assert LOCAL_DATA.exists(), f"Training data not found: {LOCAL_DATA}"

    result = train.remote(max_steps=max_steps, resume=resume, use_grpo_lora=use_grpo_lora, gpu_type=gpu)
    print(f"\nDone! Results: {result}")
    print("\nTo download artifacts:")
    print("  modal volume get grpo-checkpoints grpo-extractor-lora ./grpo-extractor-lora")
    print("  modal volume get grpo-checkpoints grpo-extractor-merged ./grpo-extractor-merged")
