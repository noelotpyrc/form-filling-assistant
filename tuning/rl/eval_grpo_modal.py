"""
eval_grpo_modal.py — Run the DataExtractor eval sweep on Modal.

One Modal function per model checkpoint: loads the fp16 merged model, runs
all 300 test cases from tuning/data/test-cases.jsonl, computes the same
metrics as tuning/rl/eval_grpo.py, and returns per-example + summary results.

Why Modal: local MLX servers crashed on sequential model swaps on M1 Pro 16GB.
L4 has 24GB VRAM, handles each model load cleanly, and runs transformers in fp16.

Models on the volume under `merged/`:
    merged/sft/                — (if produced via merge_checkpoints_modal.py --include-sft)
    merged/checkpoint-300/
    merged/checkpoint-900/
    merged/checkpoint-1500/
    merged/checkpoint-1800/

Base model `unsloth/Qwen3.5-0.8B` is pulled from HF (fp16 load).

Usage:
    # Full sweep (base + sft + 4 grpo)
    modal run tuning/rl/eval_grpo_modal.py

    # Specific checkpoints only
    modal run tuning/rl/eval_grpo_modal.py --checkpoints base,grpo-1500

    # Quick sanity: 30 cases only
    modal run tuning/rl/eval_grpo_modal.py --num 30

Outputs (downloaded locally after run):
    tuning/rl/eval_results/preds_{name}.jsonl
    tuning/rl/eval_results/summary_{name}.json
"""

import modal
import json
import sys
from pathlib import Path

app = modal.App("grpo-eval")

PROJECT_ROOT = Path(__file__).parent.parent.parent
LOCAL_TEST_CASES = PROJECT_ROOT / "tuning/data/test-cases.jsonl"
LOCAL_FORM_SCHEMA = PROJECT_ROOT / "packages/web-app/public/forms/masters-northfield.json"
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
        "dspy-ai>=2.6",
    )
    .add_local_file(str(LOCAL_TEST_CASES), remote_path="/data/test-cases.jsonl")
    .add_local_file(str(LOCAL_FORM_SCHEMA), remote_path="/data/form-schema.json")
    .add_local_dir(str(LOCAL_SFT_LORA), remote_path="/data/sft-lora")
)

volume = modal.Volume.from_name("grpo-checkpoints", create_if_missing=False)
VOLUME_PATH = "/vol"


# ─── Remote function ────────────────────────────────────────────────

@app.function(
    image=image,
    gpu="L4",
    timeout=3600,
    volumes={VOLUME_PATH: volume},
)
def evaluate(
    checkpoint_name: str,
    model_spec: dict,  # {"type": "hf_base"|"merged"|"base_plus_lora", "path": ..., "lora": ...}
    num_cases: int | None = None,
) -> dict:
    """Load one model, run 300 (or num_cases) test cases, return results.

    model_spec forms:
      {"type": "hf_base",       "hf_id": "unsloth/Qwen3.5-0.8B"}
      {"type": "merged",        "path": "/vol/merged/checkpoint-1500"}
      {"type": "base_plus_lora","hf_id": "unsloth/Qwen3.5-0.8B", "lora": "/data/sft-lora"}
    """
    import re
    import time
    import torch
    from transformers import AutoTokenizer
    from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5ForConditionalGeneration

    print("=" * 72)
    print(f"Evaluating: {checkpoint_name}")
    print(f"Model spec: {model_spec}")
    print("=" * 72)

    # ─── Load model ─────────────────────────────────────────────
    t0 = time.time()
    mtype = model_spec["type"]
    if mtype == "hf_base":
        hf_id = model_spec["hf_id"]
        print(f"Loading fp16 base from HF: {hf_id}")
        tokenizer = AutoTokenizer.from_pretrained(hf_id, trust_remote_code=True)
        model = Qwen3_5ForConditionalGeneration.from_pretrained(
            hf_id, torch_dtype=torch.float16, device_map="cuda", trust_remote_code=True,
        )
    elif mtype == "merged":
        path = model_spec["path"]
        print(f"Loading merged model from volume: {path}")
        tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
        model = Qwen3_5ForConditionalGeneration.from_pretrained(
            path, torch_dtype=torch.float16, device_map="cuda", trust_remote_code=True,
        )
    elif mtype == "base_plus_lora":
        from peft import PeftModel
        hf_id = model_spec["hf_id"]
        lora_path = model_spec["lora"]
        print(f"Loading {hf_id} + LoRA {lora_path}")
        tokenizer = AutoTokenizer.from_pretrained(lora_path, trust_remote_code=True)
        base = Qwen3_5ForConditionalGeneration.from_pretrained(
            hf_id, torch_dtype=torch.float16, device_map="cuda", trust_remote_code=True,
        )
        model = PeftModel.from_pretrained(base, lora_path)
        model = model.merge_and_unload()  # merge once for inference speed
    else:
        raise ValueError(f"Unknown model type: {mtype}")

    model.eval()
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    load_time = time.time() - t0
    print(f"Model loaded in {load_time:.1f}s")

    # ─── Load data ──────────────────────────────────────────────
    cases = [json.loads(l) for l in open("/data/test-cases.jsonl") if l.strip()]
    if num_cases:
        cases = cases[:num_cases]
    print(f"Test cases: {len(cases)}")

    form = json.load(open("/data/form-schema.json"))

    # ─── Schema IDs for hallucination check ─────────────────────
    valid_schema_ids = set()
    for section in form["schema"]["sections"]:
        for f in section["fields"]:
            fid = f["field_id"]
            valid_schema_ids.add(fid)
            if f.get("type") == "group":
                for sub in f.get("fields", []):
                    sub_id = sub["field_id"]
                    valid_schema_ids.add(f"{fid}.*.{sub_id}")
                    valid_schema_ids.add(sub_id)
    print(f"Valid schema IDs: {len(valid_schema_ids)}")

    # ─── Build form context (same as eval_grpo.py) ──────────────
    parts = [f"Form: {form['name']}", ""]
    for section in form["schema"]["sections"]:
        fd = []
        for f in section["fields"]:
            req = " (required)" if f.get("required") else ""
            ftype = f["type"]
            if ftype == "group":
                subs = [sf["field_id"] for sf in f.get("fields", [])]
                fd.append(f"  {f['field_id']} (group: {', '.join(subs)}){req}")
            elif ftype == "select" and f.get("options"):
                opts = [
                    o.get("label", o.get("value", "")) if isinstance(o, dict) else str(o)
                    for o in f["options"][:5]
                ]
                fd.append(f"  {f['field_id']} (select: {', '.join(opts)}){req}")
            else:
                fd.append(f"  {f['field_id']} ({ftype}){req}")
        parts.append(f"{section['title']}:")
        parts.extend(fd)
    form_context = "\n".join(parts)

    # ─── DSPy prompt building ──────────────────────────────────
    # Build messages using the same ChatAdapter signature as training/local eval.
    import dspy
    from dspy.adapters.chat_adapter import ChatAdapter

    class DataExtractorSignature(dspy.Signature):
        """Extract form field values from the user's message. Only extract data
        that the user explicitly provided. Map to the exact field_ids from the
        form schema. Return empty lists if no extractable data."""
        context: str = dspy.InputField(desc="Form fields and current state")
        user_message: str = dspy.InputField(desc="User message containing form data")
        field_ids: list[str] = dspy.OutputField(desc="List of field_ids to set, e.g. ['full_name', 'email']")
        field_values: list[str] = dspy.OutputField(desc="Corresponding values, e.g. ['Jane Smith', 'jane@email.com']")

    adapter = ChatAdapter()

    def build_context(case):
        ctx = form_context
        fs = case.get("form_state_before", {})
        if fs:
            ctx += f"\n\nFilled fields: {json.dumps(fs)}"
        h = case.get("conversation_history", [])
        if h:
            recent = h[-6:]
            ctx += "\n\nRecent conversation:\n"
            ctx += "\n".join(
                f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:300]}"
                for m in recent
            )
        return ctx

    # ─── Parsing + scoring (same logic as eval_grpo.py) ────────
    FIELD_IDS_MARKER = "[[ ## field_ids ## ]]"
    FIELD_VALUES_MARKER = "[[ ## field_values ## ]]"
    COMPLETED_MARKER = "[[ ## completed ## ]]"

    def parse_list(text):
        text = text.strip()
        if not text:
            return []
        try:
            r = json.loads(text)
            return r if isinstance(r, list) else []
        except json.JSONDecodeError:
            pass
        try:
            import ast
            r = ast.literal_eval(text)
            return r if isinstance(r, list) else []
        except (ValueError, SyntaxError):
            return []

    def parse_output(text):
        has_ids = FIELD_IDS_MARKER in text
        has_vals = FIELD_VALUES_MARKER in text
        has_done = COMPLETED_MARKER in text
        if not (has_ids and has_vals):
            return [], [], has_done
        try:
            ids_part = text.split(FIELD_IDS_MARKER)[1].split(FIELD_VALUES_MARKER)[0].strip()
            vals_raw = text.split(FIELD_VALUES_MARKER)[1]
            if COMPLETED_MARKER in vals_raw:
                vals_part = vals_raw.split(COMPLETED_MARKER)[0].strip()
            else:
                vals_part = vals_raw.strip()
            return parse_list(ids_part), parse_list(vals_part), has_done
        except (IndexError, ValueError):
            return [], [], has_done

    def parse_gt_values(case):
        output = case.get("expected_output", "")
        m = re.search(r"---actions---\s*```json\s*(\[.*?\])\s*```", output, re.DOTALL)
        if not m:
            return {}
        try:
            actions = json.loads(m.group(1))
        except json.JSONDecodeError:
            return {}
        values = {}
        for action in actions:
            if action.get("type") == "set_fields":
                for f in action.get("fields", []):
                    fid = f.get("field_id")
                    val = f.get("value")
                    if fid is not None and val is not None:
                        values[fid] = val
        return values

    def score_one(gt_ids, gt_vals, pred_ids, pred_vals, has_completed):
        gt_set = set(gt_ids)
        pred_set = set(pred_ids)
        pred_map = dict(zip(pred_ids, pred_vals))

        format_ok = has_completed and len(pred_ids) == len(pred_vals)

        tp = len(gt_set & pred_set)
        fp = len(pred_set - gt_set)
        fn = len(gt_set - pred_set)
        precision = tp / len(pred_set) if pred_set else (1.0 if not gt_set else 0.0)
        recall = tp / len(gt_set) if gt_set else (1.0 if not pred_set else 0.0)
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        value_matches = 0
        value_considered = 0
        for fid in gt_set & pred_set:
            if fid in gt_vals:
                value_considered += 1
                if str(pred_map.get(fid, "")).strip() == str(gt_vals[fid]).strip():
                    value_matches += 1
        value_match_rate_of_gt = value_matches / len(gt_set) if gt_set else (1.0 if not pred_set else 0.0)

        def id_in_schema(fid):
            if fid in valid_schema_ids:
                return True
            pattern = re.sub(r"\.\d+\.", ".*.", fid)
            return pattern in valid_schema_ids
        hallucinated = [fid for fid in pred_ids if not id_in_schema(fid)]
        hallucination_rate = len(hallucinated) / len(pred_ids) if pred_ids else 0.0

        return {
            "format_ok": format_ok, "has_completed": has_completed,
            "gt_count": len(gt_set), "pred_count": len(pred_set),
            "tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1,
            "value_matches": value_matches, "value_considered": value_considered,
            "value_match_rate_of_gt": value_match_rate_of_gt,
            "hallucinated_ids": hallucinated,
            "hallucination_count": len(hallucinated),
            "hallucination_rate": hallucination_rate,
            "empty_expected": not gt_set,
            "empty_correct": (not gt_set) and (not pred_set),
        }

    # ─── Generation ────────────────────────────────────────────
    per_example = []
    latencies = []
    completion_lengths = []

    for i, case in enumerate(cases):
        ctx = build_context(case)
        messages = adapter.format(
            signature=DataExtractorSignature,
            demos=[],
            inputs={"context": ctx, "user_message": case["user_message"]},
        )

        prompt_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt_text, return_tensors="pt", truncation=True, max_length=8192).to("cuda")

        t0 = time.time()
        with torch.no_grad():
            out_ids = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
        elapsed = time.time() - t0
        latencies.append(elapsed)

        completion = tokenizer.decode(
            out_ids[0][inputs.input_ids.shape[1]:], skip_special_tokens=True
        )
        completion_lengths.append(len(completion))

        gt_ids = case.get("expected_fields_set", []) if "set_fields" in case.get("expected_action_types", []) else []
        gt_vals = parse_gt_values(case) if gt_ids else {}

        pred_ids, pred_vals, has_done = parse_output(completion)
        metrics = score_one(gt_ids, gt_vals, pred_ids, pred_vals, has_done)

        per_example.append({
            "test_id": case.get("test_id"),
            "category": case.get("category"),
            "action_types": case.get("expected_action_types", []),
            "user_message": case["user_message"][:200],
            "gt_ids": gt_ids, "gt_vals": gt_vals,
            "pred_ids": pred_ids, "pred_vals": pred_vals,
            "raw_output": completion,
            "latency_s": elapsed,
            "metrics": metrics,
        })

        if (i + 1) % 25 == 0:
            avg = sum(latencies) / len(latencies)
            print(f"  {i+1}/{len(cases)}  avg_latency={avg:.2f}s")

    # ─── Aggregate ─────────────────────────────────────────────
    n = len(per_example)
    positive = [r for r in per_example if r["metrics"]["gt_count"] > 0]
    negative = [r for r in per_example if r["metrics"]["gt_count"] == 0]

    def avg(key, results=per_example):
        vals = [r["metrics"][key] for r in results]
        return sum(vals) / len(vals) if vals else 0.0

    def rate(key, results=per_example):
        return sum(1 for r in results if r["metrics"][key]) / len(results) if results else 0.0

    summary = {
        "checkpoint": checkpoint_name,
        "model_spec": model_spec,
        "num_cases": n,
        "num_positive": len(positive),
        "num_negative": len(negative),
        "avg_latency_s": sum(latencies) / len(latencies),
        "avg_completion_chars": sum(completion_lengths) / len(completion_lengths),
        "format_ok_rate": rate("format_ok"),
        "has_completed_rate": rate("has_completed"),
        "positive_precision": avg("precision", positive),
        "positive_recall": avg("recall", positive),
        "positive_f1": avg("f1", positive),
        "positive_value_match_rate": avg("value_match_rate_of_gt", positive),
        "positive_hallucination_rate": avg("hallucination_rate", positive),
        "negative_empty_correct_rate": rate("empty_correct", negative),
        "negative_avg_pred_count": avg("pred_count", negative),
        "overall_hallucination_rate": avg("hallucination_rate"),
        "load_time_s": load_time,
    }

    print("\n" + "=" * 72)
    print(f"SUMMARY — {checkpoint_name}")
    print(f"  Format OK:        {summary['format_ok_rate']*100:.1f}%")
    print(f"  Positive F1:      {summary['positive_f1']*100:.1f}%")
    print(f"  Value match:      {summary['positive_value_match_rate']*100:.1f}%")
    print(f"  Halluc rate:      {summary['positive_hallucination_rate']*100:.1f}% pos / {summary['overall_hallucination_rate']*100:.1f}% overall")
    print(f"  Empty correct:    {summary['negative_empty_correct_rate']*100:.1f}% on {len(negative)} negatives")
    print(f"  Avg latency:      {summary['avg_latency_s']:.2f}s")
    print("=" * 72)

    return {"summary": summary, "per_example": per_example}


# ─── Local entrypoint ──────────────────────────────────────────────

@app.local_entrypoint()
def main(
    checkpoints: str = "base,sft,grpo-300,grpo-900,grpo-1500,grpo-1800",
    num: int = 0,  # 0 = all 300
):
    """Run the eval sweep across selected checkpoints."""
    out_dir = PROJECT_ROOT / "tuning/rl/eval_results"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build the model spec table
    specs = {
        "base": {"type": "hf_base", "hf_id": "unsloth/Qwen3.5-0.8B"},
        "sft": {"type": "base_plus_lora", "hf_id": "unsloth/Qwen3.5-0.8B", "lora": "/data/sft-lora"},
        "grpo-300": {"type": "merged", "path": f"{VOLUME_PATH}/merged/checkpoint-300"},
        "grpo-900": {"type": "merged", "path": f"{VOLUME_PATH}/merged/checkpoint-900"},
        "grpo-1500": {"type": "merged", "path": f"{VOLUME_PATH}/merged/checkpoint-1500"},
        "grpo-1800": {"type": "merged", "path": f"{VOLUME_PATH}/merged/checkpoint-1800"},
    }

    names = [s.strip() for s in checkpoints.split(",") if s.strip()]
    for n in names:
        if n not in specs:
            raise ValueError(f"Unknown checkpoint: {n}. Choose from {list(specs)}")

    num_cases = num if num > 0 else None

    print(f"Launching eval for {len(names)} checkpoint(s): {names}")
    if num_cases:
        print(f"Limited to {num_cases} cases")
    print()

    # Run sequentially; each function call is independent
    for name in names:
        spec = specs[name]
        print(f"\n{'#' * 72}")
        print(f"# {name}")
        print(f"{'#' * 72}")
        result = evaluate.remote(name, spec, num_cases)

        summary = result["summary"]
        per_example = result["per_example"]

        summary_path = out_dir / f"summary_{name}.json"
        preds_path = out_dir / f"preds_{name}.jsonl"

        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        with open(preds_path, "w") as f:
            for r in per_example:
                f.write(json.dumps(r, default=str) + "\n")

        print(f"\n✓ Wrote {summary_path.name} + {preds_path.name}")

    print("\n" + "=" * 72)
    print(f"SWEEP COMPLETE — {len(names)} models evaluated")
    print(f"Results: {out_dir}")
    print("=" * 72)
