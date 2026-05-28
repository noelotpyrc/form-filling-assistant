"""
merge_checkpoints_modal.py — Merge GRPO LoRA checkpoints into fp16 standalone models.

Loads an fp16 base model (not quantized) and applies each checkpoint's LoRA
adapter, then saves the merged result to the Modal Volume.

Why fp16 instead of 4-bit: training ran QLoRA (4-bit base + fp16 LoRA). Merging
into the 4-bit base causes rounding-error degradation (PEFT warns about this).
Merging into fp16 base is clean. Output format matches the existing SFT merged
model (~1.6 GB fp16 safetensors), so it serves directly via mlx_vlm.

Usage:
    # Merge all 6 GRPO checkpoints (300, 600, 900, 1200, 1500, 1800)
    modal run tuning/rl/merge_checkpoints_modal.py

    # Merge specific checkpoints only
    modal run tuning/rl/merge_checkpoints_modal.py --checkpoints 1500,1800

    # Also include SFT baseline (re-merge it through the same pipeline for fair comparison)
    modal run tuning/rl/merge_checkpoints_modal.py --include-sft

Artifacts saved to Volume "grpo-checkpoints" under:
    merged/checkpoint-{step}/     — one per GRPO checkpoint
    merged/sft/                   — if --include-sft

Download after:
    modal volume get grpo-checkpoints merged ./grpo-merged/
"""

import modal
from pathlib import Path

app = modal.App("grpo-merge-checkpoints")

LOCAL_SFT_LORA = Path.home() / "work/models/qwen35-08b-dspy-format-lora"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch>=2.5",
        "transformers==5.5.4",
        "peft==0.19.0",
        "accelerate==1.13.0",
        "safetensors",
        "numpy",
    )
    .add_local_dir(str(LOCAL_SFT_LORA), remote_path="/data/sft-lora")
)

volume = modal.Volume.from_name("grpo-checkpoints", create_if_missing=False)
VOLUME_PATH = Path("/vol")
OUTPUT_DIR = VOLUME_PATH / "grpo_outputs"
MERGED_DIR = VOLUME_PATH / "merged"

BASE_MODEL = "unsloth/Qwen3.5-0.8B"


@app.function(
    image=image,
    gpu="L4",
    timeout=3600,
    volumes={str(VOLUME_PATH): volume},
)
def merge(checkpoints: list[int], include_sft: bool = False):
    import os
    import shutil
    import torch
    from transformers import AutoTokenizer
    from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5ForConditionalGeneration
    from peft import PeftModel

    print("=" * 60)
    print("GRPO Checkpoint Merge — Modal")
    print("=" * 60)
    print(f"torch:  {torch.__version__}")
    print(f"CUDA:   {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU:    {torch.cuda.get_device_name()}")
    print(f"Base:   {BASE_MODEL}")
    print(f"Mode:   fp16 (no quantization)")
    print(f"Checkpoints: {checkpoints}")
    print(f"Include SFT: {include_sft}")
    print()

    MERGED_DIR.mkdir(parents=True, exist_ok=True)

    # Build the list of (name, adapter_path) pairs to merge
    jobs: list[tuple[str, str]] = []
    if include_sft:
        jobs.append(("sft", "/data/sft-lora"))
    for step in checkpoints:
        ckpt_path = str(OUTPUT_DIR / f"checkpoint-{step}")
        if not os.path.exists(ckpt_path):
            print(f"⚠️  Missing: {ckpt_path} (skipping)")
            continue
        jobs.append((f"checkpoint-{step}", ckpt_path))

    if not jobs:
        print("No valid checkpoints to merge.")
        return {"merged": []}

    merged_paths = []

    for job_name, adapter_path in jobs:
        out_path = str(MERGED_DIR / job_name)
        print(f"\n{'─' * 60}")
        print(f"Merging: {job_name}")
        print(f"  Adapter: {adapter_path}")
        print(f"  Output:  {out_path}")
        print(f"{'─' * 60}")

        # ─── Fresh fp16 base each iteration ────────────────────────
        # (PEFT mutates the base during merge, so reload to avoid drift)
        print("Loading base model (fp16)...")
        base = Qwen3_5ForConditionalGeneration.from_pretrained(
            BASE_MODEL,
            torch_dtype=torch.float16,
            device_map="cuda",
            trust_remote_code=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)

        print("Applying LoRA adapter...")
        model = PeftModel.from_pretrained(base, adapter_path)

        print("Merging...")
        merged = model.merge_and_unload()

        # ─── Save ──────────────────────────────────────────────────
        if os.path.exists(out_path):
            shutil.rmtree(out_path)
        os.makedirs(out_path, exist_ok=True)

        merged.save_pretrained(out_path, safe_serialization=True)
        tokenizer.save_pretrained(out_path)

        # Log size + param count
        total_params = sum(p.numel() for p in merged.parameters())
        size_bytes = sum(
            os.path.getsize(os.path.join(out_path, f))
            for f in os.listdir(out_path)
            if os.path.isfile(os.path.join(out_path, f))
        )
        print(f"✓ Saved: {total_params:,} params, {size_bytes / 1e9:.2f} GB")
        merged_paths.append(out_path)

        # Commit after each merge so partial progress survives failures
        volume.commit()

        # Free GPU memory
        del base, model, merged
        torch.cuda.empty_cache()

    print("\n" + "=" * 60)
    print(f"MERGE COMPLETE — {len(merged_paths)} models")
    for p in merged_paths:
        print(f"  {p}")
    print("=" * 60)
    print("\nTo download all:")
    print("  modal volume get grpo-checkpoints merged ./grpo-merged/")

    return {"merged": merged_paths}


@app.local_entrypoint()
def main(
    checkpoints: str = "300,600,900,1200,1500,1800",
    include_sft: bool = False,
):
    """Merge GRPO LoRA checkpoints into fp16 standalone models.

    Args:
        checkpoints: Comma-separated list of checkpoint step numbers.
        include_sft: Also merge the SFT baseline through the same pipeline.
    """
    ckpt_list = [int(s.strip()) for s in checkpoints.split(",") if s.strip()]
    print(f"Launching merge job: checkpoints={ckpt_list}, include_sft={include_sft}")

    assert LOCAL_SFT_LORA.exists(), f"SFT LoRA not found locally: {LOCAL_SFT_LORA}"

    result = merge.remote(checkpoints=ckpt_list, include_sft=include_sft)
    print(f"\nDone. Merged models: {result['merged']}")
    print("\nTo download:")
    print("  mkdir -p ~/work/models/grpo-merged")
    print("  modal volume get grpo-checkpoints merged ~/work/models/grpo-merged/")
