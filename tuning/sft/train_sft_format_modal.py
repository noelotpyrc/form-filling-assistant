"""
train_sft_format_modal.py — SFT training on Modal with remote GPU.

Teaches Qwen3.5-0.8B to emit DSPy ChatAdapter's `[[ ## field ## ]]` format
across the 5 sub-modules (action_router, data_extractor, choice_builder,
review_builder, text_responder).

Usage:
    modal run tuning/sft/train_sft_format_modal.py                      # full 3-epoch run
    modal run tuning/sft/train_sft_format_modal.py --max-steps 10       # quick smoke test
    modal run tuning/sft/train_sft_format_modal.py --epochs 2           # fewer epochs
    modal run tuning/sft/train_sft_format_modal.py --resume             # resume from latest checkpoint
    modal run tuning/sft/train_sft_format_modal.py --gpu A10G           # cheaper GPU

Monitors in real-time. Ctrl-C detaches (training continues).
Reattach via: modal app logs sft-format-qwen35-08b

Artifacts saved to Modal Volume "sft-format-checkpoints".
Download the trained LoRA adapter after training:
    modal volume get sft-format-checkpoints qwen35-08b-dspy-format-lora ./qwen35-08b-dspy-format-lora
"""

import modal
from pathlib import Path

# ─── Modal Setup ────────────────────────────────────────────────────

app = modal.App("sft-format-qwen35-08b")

# Local paths for data that gets baked into the image
LOCAL_TRAIN_DATA = (
    Path.home()
    / "work/form-filling-assistant/tuning/sft/format_train_split.jsonl"
)
LOCAL_VAL_DATA = (
    Path.home()
    / "work/form-filling-assistant/tuning/sft/format_val_split.jsonl"
)

# Training image — mirrors the notebook's install block, pinned.
# Qwen3.5 is a VLM arch, so we use Unsloth's FastVisionModel path even though
# the task is text-only (same approach the Colab notebook uses).
#
# CUDA devel base is required because `causal_conv1d` and `flash-linear-attention`
# compile CUDA kernels at install time and need `nvcc`. Qwen3.5's hybrid
# Mamba/linear-attention layers fall back to a ~10× slower Python path without
# these kernels (confirmed empirically vs the Colab T4 run which had them).
image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.8.1-devel-ubuntu22.04",
        add_python="3.11",
    )
    .apt_install("git")  # needed for unsloth install via git+https
    .pip_install(
        "torch==2.8.0",
        "triton>=3.3.0",
        "numpy",
        "pillow",
        "torchvision",
        "bitsandbytes",
        "xformers==0.0.32.post2",
    )
    .pip_install(
        "unsloth_zoo[base] @ git+https://github.com/unslothai/unsloth-zoo",
        "unsloth[base] @ git+https://github.com/unslothai/unsloth",
    )
    .pip_install(
        "tokenizers",
        "trl==0.22.2",
        "transformers==5.2.0",
        extra_options="--upgrade --no-deps",
    )
    # CUDA kernels for Qwen3.5's hybrid Mamba/linear-attention layers.
    # Without these, training falls back to a ~10× slower Python path.
    .pip_install(
        "flash-linear-attention",
        "causal_conv1d==1.6.0",
        extra_options="--no-build-isolation",
    )
    .add_local_file(str(LOCAL_TRAIN_DATA), remote_path="/data/format_train_split.jsonl")
    .add_local_file(str(LOCAL_VAL_DATA), remote_path="/data/format_val_split.jsonl")
)

# Persistent volume for checkpoints + output
# Mounted at /vol inside the container. Browsable via `modal volume ls sft-format-checkpoints`.
#
# Volume layout:
#   sft_outputs/                   — HF Trainer auto-checkpoints (every save_steps)
#     checkpoint-100/                adapter weights + optimizer + scheduler state
#     checkpoint-200/                (used by --resume to continue from exact state)
#     ...
#   qwen35-08b-dspy-format-lora/   — Clean LoRA adapter (saved after training completes)
#                                    adapter_model.safetensors + tokenizer.
#                                    Use with: PeftModel.from_pretrained(base_model, path)
#   log_history.json               — Training metrics per logging step (loss, eval_loss, lr)
volume = modal.Volume.from_name("sft-format-checkpoints", create_if_missing=True)
VOLUME_PATH = Path("/vol")
OUTPUT_DIR = VOLUME_PATH / "sft_outputs"


# ─── Training Function ─────────────────────────────────────────────


@app.function(
    image=image,
    gpu="L4",  # 24GB VRAM, good balance for a 0.8B model + LoRA
    timeout=10 * 60 * 60,  # 10 hours max (3 epochs ≈ 7 hours on L4)
    volumes={str(VOLUME_PATH): volume},
)
def train(
    max_steps: int = -1,
    epochs: int = 3,
    resume: bool = False,
    gpu_type: str = "",
):
    import json
    import glob
    from collections import Counter

    import torch
    from unsloth import FastVisionModel
    from unsloth.trainer import UnslothVisionDataCollator
    from trl import SFTTrainer, SFTConfig
    from transformers import TrainerCallback

    print("=" * 60)
    print("SFT Training (DSPy format) — Modal")
    print("=" * 60)
    print(f"torch:        {torch.__version__}")
    print(f"CUDA:         {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU:          {torch.cuda.get_device_name(0)}")
        mem_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"VRAM:         {mem_gb:.1f} GB")
    print(f"epochs:       {epochs}")
    print(f"max_steps:    {max_steps} (-1 = full epoch count)")
    print(f"resume:       {resume}")

    # ─── Load Base Model + Wrap with LoRA ──────────────────────────
    print("\n--- Loading base model ---")
    model, tokenizer = FastVisionModel.from_pretrained(
        "unsloth/Qwen3.5-0.8B",
        load_in_4bit=False,
        use_gradient_checkpointing=False,  # 0.8B at batch 8 fits in <8 GB, no need to trade compute for memory
    )

    model = FastVisionModel.get_peft_model(
        model,
        finetune_vision_layers=False,      # text-only task
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=16,
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        random_state=3407,
        use_rslora=False,
        loftq_config=None,
    )

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(
        f"Model: {total:,} total, {trainable:,} trainable ({trainable/total*100:.2f}%)"
    )

    # ─── Load Training Data ────────────────────────────────────────
    print("\n--- Loading training data ---")
    TRAIN_PATH = "/data/format_train_split.jsonl"
    VAL_PATH = "/data/format_val_split.jsonl"

    with open(TRAIN_PATH) as f:
        raw_train = [json.loads(line) for line in f if line.strip()]
    with open(VAL_PATH) as f:
        raw_val = [json.loads(line) for line in f if line.strip()]

    print(f"Train: {len(raw_train)} examples")
    print(f"Val:   {len(raw_val)} examples")
    # The split files drop the `module` metadata key — only print distribution if present
    if raw_train and "module" in raw_train[0]:
        print(f"Train module distribution: {Counter(r['module'] for r in raw_train)}")
        print(f"Val module distribution:   {Counter(r['module'] for r in raw_val)}")

    # Convert to FastVisionModel format: content as list of typed blocks
    def convert(rows):
        out = []
        for r in rows:
            messages = [
                {
                    "role": msg["role"],
                    "content": [{"type": "text", "text": msg["content"]}],
                }
                for msg in r["messages"]
            ]
            out.append({"messages": messages})
        return out

    train_data = convert(raw_train)
    val_data = convert(raw_val)
    print(f"Sample assistant output (first 200 chars): "
          f"{train_data[0]['messages'][-1]['content'][0]['text'][:200]}")

    # ─── SFT Training ──────────────────────────────────────────────
    print("\n--- Creating SFTTrainer ---")
    output_dir = str(OUTPUT_DIR)

    FastVisionModel.for_training(model)

    sft_args = SFTConfig(
        # Batch 8 × grad_accum 1 = effective batch 8 (same as notebook's 2×4),
        # but 4× fewer Python loop iterations per step. Peak memory at batch 2
        # was only 5.6 GB of 22 GB; batch 8 fits comfortably.
        per_device_train_batch_size=8,
        gradient_accumulation_steps=1,
        warmup_steps=10,
        num_train_epochs=epochs,
        max_steps=max_steps,  # -1 means use epochs; positive overrides
        learning_rate=2e-4,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=100,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=3407,
        output_dir=output_dir,
        report_to="none",
        remove_unused_columns=False,
        dataset_text_field="",
        dataset_kwargs={"skip_prepare_dataset": True},
        # Dataset analysis: max sample is ~2,500 tokens, p99 is ~2,320. 4096
        # gives a safety margin with no truncation; dropping from 16384 cuts
        # wasted compute on padded positions.
        max_length=4096,
        # L4 supports bf16 natively — 2-4× faster than fp32 matmuls, same
        # dynamic range (no loss scaling needed), matches what RL training uses.
        bf16=True,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        data_collator=UnslothVisionDataCollator(model, tokenizer),
        train_dataset=train_data,
        eval_dataset=val_data,
        args=sft_args,
    )
    print("SFTTrainer created")

    # GPU memory before training
    if torch.cuda.is_available():
        start_mem = torch.cuda.max_memory_reserved() / 1024**3
        print(f"GPU memory reserved before training: {start_mem:.1f} GB")

    # Commit volume after each checkpoint save so artifacts survive detach.
    class VolumeCommitCallback(TrainerCallback):
        def on_save(self, args, state, control, **kwargs):
            volume.commit()
            print(f"  Volume committed at step {state.global_step}")

    trainer.add_callback(VolumeCommitCallback())

    # Train! Resume from latest checkpoint if requested.
    checkpoint_path = None
    if resume:
        checkpoints = sorted(
            glob.glob(str(OUTPUT_DIR / "checkpoint-*")),
            key=lambda x: int(x.split("-")[-1]),
        )
        if checkpoints:
            checkpoint_path = checkpoints[-1]
            print(f"\n--- Resuming from {checkpoint_path} ---")
        else:
            print("\n--- No checkpoint found, starting fresh ---")
    else:
        print(f"\n--- Training ({epochs} epochs, max_steps={max_steps}) ---")

    trainer_stats = trainer.train(resume_from_checkpoint=checkpoint_path)

    # ─── Post-Training Stats ───────────────────────────────────────
    if torch.cuda.is_available():
        peak_mem = torch.cuda.max_memory_reserved() / 1024**3
        used_for_lora = peak_mem - start_mem
        max_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"\nPeak GPU memory:         {peak_mem:.2f} GB")
        print(f"Peak memory for training: {used_for_lora:.2f} GB")
        print(f"Peak % of max memory:     {peak_mem/max_mem*100:.1f}%")

    runtime = trainer_stats.metrics.get("train_runtime", 0)
    print(f"Train runtime:  {runtime:.0f} s  ({runtime/60:.1f} min)")

    # Final eval loss
    print("\n--- Final evaluation ---")
    eval_results = trainer.evaluate()
    print(f"Eval loss: {eval_results['eval_loss']:.4f}")

    # ─── Save Training Log History ─────────────────────────────────
    log_path = str(VOLUME_PATH / "log_history.json")
    with open(log_path, "w") as f:
        json.dump(trainer.state.log_history, f, indent=2)
    print(f"\nSaved log history: {log_path} ({len(trainer.state.log_history)} entries)")

    # ─── Save LoRA Adapter ─────────────────────────────────────────
    print("\n--- Saving LoRA adapter ---")
    lora_path = str(VOLUME_PATH / "qwen35-08b-dspy-format-lora")
    model.save_pretrained(lora_path)
    tokenizer.save_pretrained(lora_path)

    # Sanity-check: peek at a few LoRA tensors to confirm non-zero weights
    from safetensors import safe_open
    for f in glob.glob(f"{lora_path}/*.safetensors"):
        with safe_open(f, framework="pt") as st:
            for key in list(st.keys())[:3]:
                tensor = st.get_tensor(key)
                print(f"  {key}: shape={tensor.shape}, std={tensor.std():.6f}")
        break  # just the first file is enough for a sanity-peek

    volume.commit()

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print(f"LoRA adapter:  {lora_path}")
    print(f"Final eval loss: {eval_results['eval_loss']:.4f}")
    print("\nTo download locally:")
    print(f"  modal volume get sft-format-checkpoints qwen35-08b-dspy-format-lora "
          f"./qwen35-08b-dspy-format-lora")
    print("=" * 60)

    return {
        "lora_path": lora_path,
        "eval_loss": eval_results["eval_loss"],
        "train_runtime_sec": runtime,
    }


# ─── Local Entrypoint ──────────────────────────────────────────────


@app.local_entrypoint()
def main(
    max_steps: int = -1,
    epochs: int = 3,
    resume: bool = False,
    gpu: str = "L4",
):
    print(
        f"Launching SFT training on Modal "
        f"({gpu}, epochs={epochs}, max_steps={max_steps}, resume={resume})"
    )
    print(f"Train data: {LOCAL_TRAIN_DATA}")
    print(f"Val data:   {LOCAL_VAL_DATA}")

    # Verify local files exist before uploading
    assert LOCAL_TRAIN_DATA.exists(), f"Training data not found: {LOCAL_TRAIN_DATA}"
    assert LOCAL_VAL_DATA.exists(), f"Val data not found: {LOCAL_VAL_DATA}"

    result = train.remote(
        max_steps=max_steps,
        epochs=epochs,
        resume=resume,
        gpu_type=gpu,
    )
    print(f"\nDone! Results: {result}")
    print("\nTo download artifacts:")
    print("  modal volume get sft-format-checkpoints qwen35-08b-dspy-format-lora "
          "./qwen35-08b-dspy-format-lora")
