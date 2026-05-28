"""
merge_lora_modal.py — Merge the SFT LoRA adapter into an fp16 standalone model.

Loads an fp16 Qwen3.5-0.8B base and applies the local LoRA adapter, then saves
the merged result to a Modal Volume for bulk download. Output format matches
the existing `qwen35-08b-dspy-format-mlx/` layout (HF fp16 safetensors), which
mlx_vlm.server loads directly.

Why fp16 instead of 4-bit: the LoRA was trained on fp16 base (see
train_sft_format_modal.py — load_in_4bit=False). Merging into fp16 base is
clean; no rounding-error degradation like QLoRA merges.

Usage:
    modal run tuning/sft/merge_lora_modal.py  # merges ~/work/models/qwen35-08b-dspy-format-lora-v2

    # Override the local adapter path or output name:
    modal run tuning/sft/merge_lora_modal.py --lora-dir ~/work/models/qwen35-08b-dspy-format-lora-v2 --output-name sft-v2

After the job finishes:
    mkdir -p ~/work/models/qwen35-08b-dspy-format-v2-mlx
    modal volume get sft-format-checkpoints merged/sft-v2/ ~/work/models/qwen35-08b-dspy-format-v2-mlx/
"""

import modal
from pathlib import Path

app = modal.App("sft-merge-lora")

LOCAL_LORA = Path.home() / "work/models/qwen35-08b-dspy-format-lora-v2"

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
    .add_local_dir(str(LOCAL_LORA), remote_path="/data/sft-lora")
)

volume = modal.Volume.from_name("sft-format-checkpoints", create_if_missing=False)
VOLUME_PATH = Path("/vol")
MERGED_DIR = VOLUME_PATH / "merged"

BASE_MODEL = "unsloth/Qwen3.5-0.8B"


@app.function(
    image=image,
    gpu="L4",
    timeout=3600,
    volumes={str(VOLUME_PATH): volume},
)
def merge(output_name: str):
    import os
    import shutil
    import torch
    from transformers import AutoTokenizer
    from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5ForConditionalGeneration
    from peft import PeftModel

    print("=" * 60)
    print("SFT LoRA Merge — Modal")
    print("=" * 60)
    print(f"torch:   {torch.__version__}")
    print(f"CUDA:    {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU:     {torch.cuda.get_device_name()}")
    print(f"Base:    {BASE_MODEL}")
    print(f"Adapter: /data/sft-lora")
    print(f"Output:  merged/{output_name}")
    print()

    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = str(MERGED_DIR / output_name)

    print("Loading base model (fp16)...")
    base = Qwen3_5ForConditionalGeneration.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="cuda",
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained("/data/sft-lora", trust_remote_code=True)

    print("Applying LoRA adapter...")
    model = PeftModel.from_pretrained(base, "/data/sft-lora")

    print("Merging...")
    merged = model.merge_and_unload()

    if os.path.exists(out_path):
        shutil.rmtree(out_path)
    os.makedirs(out_path, exist_ok=True)

    merged.save_pretrained(out_path, safe_serialization=True)
    tokenizer.save_pretrained(out_path)

    total_params = sum(p.numel() for p in merged.parameters())
    size_bytes = sum(
        os.path.getsize(os.path.join(out_path, f))
        for f in os.listdir(out_path)
        if os.path.isfile(os.path.join(out_path, f))
    )
    print(f"✓ Saved: {total_params:,} params, {size_bytes / 1e9:.2f} GB")

    volume.commit()

    print("\n" + "=" * 60)
    print("MERGE COMPLETE")
    print("=" * 60)
    print(f"  {out_path}")
    print("\nTo download:")
    print(f"  mkdir -p ~/work/models/qwen35-08b-dspy-format-v2-mlx")
    print(f"  modal volume get sft-format-checkpoints merged/{output_name}/ "
          f"~/work/models/qwen35-08b-dspy-format-v2-mlx/")

    return {"merged_path": out_path}


@app.local_entrypoint()
def main(
    lora_dir: str = "",
    output_name: str = "sft-v2",
):
    """Merge an SFT LoRA adapter into an fp16 standalone model on Modal.

    Args:
        lora_dir: Local LoRA adapter directory (defaults to ~/work/models/qwen35-08b-dspy-format-lora-v2).
                  Note: if overridden, you must edit LOCAL_LORA above since the image mount is baked in.
        output_name: Subdirectory name under merged/ on the volume.
    """
    if lora_dir:
        print(f"⚠️  --lora-dir given ({lora_dir}) but script mounts LOCAL_LORA at image build time.")
        print(f"    Edit LOCAL_LORA in this file and re-run, or use the default.")

    assert LOCAL_LORA.exists(), f"SFT LoRA not found locally: {LOCAL_LORA}"

    print(f"Launching SFT LoRA merge: output_name={output_name}")
    result = merge.remote(output_name=output_name)
    print(f"\nDone. Merged model: {result['merged_path']}")
