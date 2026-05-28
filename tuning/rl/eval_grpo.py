#!/usr/bin/env python3
"""
eval_grpo.py — Evaluate a single model on the DataExtractor task.

Loads tuning/data/test-cases.jsonl (300 cases), calls the model via OpenAI-
compatible API (mlx_vlm.server), parses the DSPy ChatAdapter output, and
computes metrics per tuning/rl/EVAL_PLAN.md.

Usage:
    # Start the target model first (e.g. checkpoint-1500):
    cd python && uv run python -m mlx_vlm.server \\
      --model ~/work/models/grpo-merged/merged/checkpoint-1500 \\
      --port 8084 &

    # Then run eval:
    uv run python tuning/rl/eval_grpo.py \\
      --url http://localhost:8084/v1/chat/completions \\
      --model-path ~/work/models/grpo-merged/merged/checkpoint-1500 \\
      --checkpoint-name grpo-1500 \\
      --output tuning/rl/eval_results/

    # Quick sanity check: 10 examples only
    uv run python tuning/rl/eval_grpo.py ... --num 10
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Literal

import requests

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dspy
from dspy.adapters.chat_adapter import ChatAdapter

# ══════════════════════════════════════════════════════════════════════
# Config (matches compare_models.py for consistency)
# ══════════════════════════════════════════════════════════════════════

FORM_SCHEMA_PATH = PROJECT_ROOT / "packages/web-app/public/forms/masters-northfield.json"
TEST_CASES_PATH = PROJECT_ROOT / "tuning/data/test-cases.jsonl"
MAX_TOKENS = 512


# ══════════════════════════════════════════════════════════════════════
# DSPy signature — must match training
# ══════════════════════════════════════════════════════════════════════

class DataExtractorSignature(dspy.Signature):
    """Extract form field values from the user's message. Only extract data
    that the user explicitly provided. Map to the exact field_ids from the
    form schema. Return empty lists if no extractable data."""

    context: str = dspy.InputField(desc="Form fields and current state")
    user_message: str = dspy.InputField(desc="User message containing form data")
    field_ids: list[str] = dspy.OutputField(desc="List of field_ids to set, e.g. ['full_name', 'email']")
    field_values: list[str] = dspy.OutputField(desc="Corresponding values, e.g. ['Jane Smith', 'jane@email.com']")


adapter = ChatAdapter()


# ══════════════════════════════════════════════════════════════════════
# Context builder (copied from compare_models.py for eval consistency)
# ══════════════════════════════════════════════════════════════════════

def load_form_context() -> str:
    form = json.load(open(FORM_SCHEMA_PATH))
    parts = [f"Form: {form['name']}", ""]
    for section in form["schema"]["sections"]:
        fields_desc = []
        for f in section["fields"]:
            req = " (required)" if f.get("required") else ""
            ftype = f["type"]
            if ftype == "group":
                sub_fields = [sf["field_id"] for sf in f.get("fields", [])]
                fields_desc.append(f"  {f['field_id']} (group: {', '.join(sub_fields)}){req}")
            elif ftype == "select" and f.get("options"):
                opts = [o.get("label", o.get("value", "")) if isinstance(o, dict) else str(o) for o in f["options"][:5]]
                fields_desc.append(f"  {f['field_id']} (select: {', '.join(opts)}){req}")
            else:
                fields_desc.append(f"  {f['field_id']} ({ftype}){req}")
        parts.append(f"{section['title']}:")
        parts.extend(fields_desc)
    return "\n".join(parts)


def build_context(case: dict, form_context: str) -> str:
    ctx = form_context
    form_state = case.get("form_state_before", {})
    if form_state:
        ctx += f"\n\nFilled fields: {json.dumps(form_state)}"

    history = case.get("conversation_history", [])
    if history:
        recent = history[-6:]
        ctx += "\n\nRecent conversation:\n"
        ctx += "\n".join(
            f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content'][:300]}"
            for h in recent
        )
    return ctx


def load_valid_schema_ids() -> set[str]:
    """Build the set of valid field_ids by parsing the form JSON directly.

    Includes both top-level IDs and group-subfield paths like "jobs.0.employer"
    (matched via pattern "jobs.*.employer" for arbitrary indices).
    """
    form = json.load(open(FORM_SCHEMA_PATH))
    ids = set()
    for section in form["schema"]["sections"]:
        for f in section["fields"]:
            fid = f["field_id"]
            ids.add(fid)
            if f.get("type") == "group":
                for sub in f.get("fields", []):
                    sub_id = sub["field_id"]
                    # Add pattern form: jobs.*.employer
                    ids.add(f"{fid}.*.{sub_id}")
                    # Also add bare subfield (model might emit just "employer")
                    ids.add(sub_id)
    return ids


# ══════════════════════════════════════════════════════════════════════
# Ground truth extraction from test-cases.jsonl
# ══════════════════════════════════════════════════════════════════════

def parse_gt_values(case: dict) -> dict[str, str]:
    """Parse expected field values from the case's expected_output action JSON."""
    output = case.get("expected_output", "")
    # Find ---actions--- block
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


# ══════════════════════════════════════════════════════════════════════
# Output parsing — matches training reward functions
# ══════════════════════════════════════════════════════════════════════

FIELD_IDS_MARKER = "[[ ## field_ids ## ]]"
FIELD_VALUES_MARKER = "[[ ## field_values ## ]]"
COMPLETED_MARKER = "[[ ## completed ## ]]"


def parse_list(text: str) -> list:
    """Parse a Python-style list literal tolerantly."""
    text = text.strip()
    if not text:
        return []
    try:
        result = json.loads(text)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        pass
    # Try Python literal (single quotes)
    try:
        import ast
        result = ast.literal_eval(text)
        return result if isinstance(result, list) else []
    except (ValueError, SyntaxError):
        return []


def parse_output(text: str) -> tuple[list[str], list[str], bool]:
    """Parse model output. Returns (field_ids, field_values, has_completed_marker)."""
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


# ══════════════════════════════════════════════════════════════════════
# Metrics
# ══════════════════════════════════════════════════════════════════════

def score_one(
    gt_ids: list[str],
    gt_vals: dict[str, str],
    pred_ids: list[str],
    pred_vals: list[str],
    valid_schema_ids: set[str],
    has_completed: bool,
) -> dict:
    """Compute per-example metrics."""
    gt_set = set(gt_ids)
    pred_set = set(pred_ids)

    pred_map = dict(zip(pred_ids, pred_vals))

    # Format
    format_ok = has_completed and len(pred_ids) == len(pred_vals)

    # ID precision/recall/F1
    tp = len(gt_set & pred_set)
    fp = len(pred_set - gt_set)
    fn = len(gt_set - pred_set)
    precision = tp / len(pred_set) if pred_set else (1.0 if not gt_set else 0.0)
    recall = tp / len(gt_set) if gt_set else (1.0 if not pred_set else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Value exact match (over intersected IDs only)
    value_matches = 0
    value_considered = 0
    for fid in gt_set & pred_set:
        if fid in gt_vals:
            value_considered += 1
            pred_v = str(pred_map.get(fid, "")).strip()
            gt_v = str(gt_vals[fid]).strip()
            if pred_v == gt_v:
                value_matches += 1
    # Value match % of ground truth (how many GT values we got right)
    value_match_rate_of_gt = value_matches / len(gt_set) if gt_set else (1.0 if not pred_set else 0.0)

    # Hallucination: pred IDs not in schema
    # Schema may use foo.*.bar pattern; check both direct and pattern match
    def id_in_schema(fid: str) -> bool:
        if fid in valid_schema_ids:
            return True
        # Check pattern match: foo.0.bar → foo.*.bar
        pattern = re.sub(r"\.\d+\.", ".*.", fid)
        return pattern in valid_schema_ids
    hallucinated = [fid for fid in pred_ids if not id_in_schema(fid)]
    hallucination_count = len(hallucinated)
    hallucination_rate = hallucination_count / len(pred_ids) if pred_ids else 0.0

    # Empty-correct: when GT is empty, is pred also empty?
    empty_correct = (not gt_set) and (not pred_set)
    empty_expected = not gt_set

    return {
        "format_ok": format_ok,
        "has_completed": has_completed,
        "gt_count": len(gt_set),
        "pred_count": len(pred_set),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "value_matches": value_matches,
        "value_considered": value_considered,
        "value_match_rate_of_gt": value_match_rate_of_gt,
        "hallucinated_ids": hallucinated,
        "hallucination_count": hallucination_count,
        "hallucination_rate": hallucination_rate,
        "empty_expected": empty_expected,
        "empty_correct": empty_correct,
    }


# ══════════════════════════════════════════════════════════════════════
# Model calling
# ══════════════════════════════════════════════════════════════════════

def call_model(url: str, model: str, messages: list[dict]) -> tuple[str, float, str | None]:
    """Call model via OpenAI-compatible API. Returns (text, duration_s, error)."""
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
    }
    t0 = time.time()
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return text, time.time() - t0, None
    except Exception as e:
        return "", time.time() - t0, str(e)


# ══════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════

def run_eval(args):
    form_context = load_form_context()
    valid_schema_ids = load_valid_schema_ids()
    print(f"Valid schema IDs: {len(valid_schema_ids)}")

    cases = [json.loads(l) for l in open(TEST_CASES_PATH) if l.strip()]
    if args.num:
        cases = cases[: args.num]

    print(f"Checkpoint: {args.checkpoint_name}")
    print(f"Model URL:  {args.url}")
    print(f"Model path: {args.model_path}")
    print(f"Cases:      {len(cases)}")
    print("=" * 72)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    preds_path = out_dir / f"preds_{args.checkpoint_name}.jsonl"
    summary_path = out_dir / f"summary_{args.checkpoint_name}.json"

    per_example_results = []
    errors = 0
    latencies = []
    completion_lengths = []

    for i, case in enumerate(cases):
        ctx = build_context(case, form_context)
        messages = adapter.format(
            signature=DataExtractorSignature,
            demos=[],
            inputs={"context": ctx, "user_message": case["user_message"]},
        )

        out, dur, err = call_model(args.url, args.model_path, messages)
        latencies.append(dur)
        completion_lengths.append(len(out))

        gt_ids = case.get("expected_fields_set", []) if "set_fields" in case.get("expected_action_types", []) else []
        gt_vals = parse_gt_values(case) if gt_ids else {}

        if err:
            errors += 1
            per_example_results.append({
                "test_id": case.get("test_id"),
                "category": case.get("category"),
                "action_types": case.get("expected_action_types", []),
                "user_message": case["user_message"][:200],
                "gt_ids": gt_ids,
                "pred_ids": [],
                "pred_vals": [],
                "raw_output": "",
                "latency_s": dur,
                "error": err,
                "metrics": None,
            })
        else:
            pred_ids, pred_vals, has_done = parse_output(out)
            metrics = score_one(gt_ids, gt_vals, pred_ids, pred_vals, valid_schema_ids, has_done)
            per_example_results.append({
                "test_id": case.get("test_id"),
                "category": case.get("category"),
                "action_types": case.get("expected_action_types", []),
                "user_message": case["user_message"][:200],
                "gt_ids": gt_ids,
                "gt_vals": gt_vals,
                "pred_ids": pred_ids,
                "pred_vals": pred_vals,
                "raw_output": out,
                "latency_s": dur,
                "error": None,
                "metrics": metrics,
            })

        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(cases)}  errors={errors}  avg_latency={sum(latencies)/len(latencies):.2f}s")

    # Write per-example
    with open(preds_path, "w") as f:
        for r in per_example_results:
            f.write(json.dumps(r) + "\n")
    print(f"\nWrote per-example predictions → {preds_path}")

    # Aggregate
    valid_results = [r for r in per_example_results if r["metrics"] is not None]
    n = len(valid_results)

    def avg(key, results=valid_results):
        vals = [r["metrics"][key] for r in results]
        return sum(vals) / len(vals) if vals else 0.0

    def rate(key, results=valid_results):
        return sum(1 for r in results if r["metrics"][key]) / len(results) if results else 0.0

    positive = [r for r in valid_results if r["metrics"]["gt_count"] > 0]
    negative = [r for r in valid_results if r["metrics"]["gt_count"] == 0]

    summary = {
        "checkpoint": args.checkpoint_name,
        "model_path": args.model_path,
        "num_cases": len(cases),
        "num_valid": n,
        "num_errors": errors,
        "num_positive": len(positive),
        "num_negative": len(negative),
        "avg_latency_s": sum(latencies) / len(latencies) if latencies else 0.0,
        "avg_completion_chars": sum(completion_lengths) / len(completion_lengths) if completion_lengths else 0.0,
        "format_ok_rate": rate("format_ok"),
        "has_completed_rate": rate("has_completed"),
        # Positive (set_fields) cases
        "positive_precision": avg("precision", positive),
        "positive_recall": avg("recall", positive),
        "positive_f1": avg("f1", positive),
        "positive_value_match_rate": avg("value_match_rate_of_gt", positive),
        "positive_hallucination_rate": avg("hallucination_rate", positive),
        # Negative (expected-empty) cases
        "negative_empty_correct_rate": rate("empty_correct", negative),
        "negative_avg_pred_count": avg("pred_count", negative),
        # Overall hallucination
        "overall_hallucination_rate": avg("hallucination_rate"),
    }

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    # Print summary
    print("\n" + "=" * 72)
    print(f"SUMMARY — {args.checkpoint_name}")
    print("=" * 72)
    print(f"  Total cases:             {summary['num_cases']}  (errors: {errors})")
    print(f"  Positive (set_fields):   {summary['num_positive']}")
    print(f"  Negative (empty GT):     {summary['num_negative']}")
    print(f"  Avg latency:             {summary['avg_latency_s']:.2f}s")
    print(f"  Avg completion chars:    {summary['avg_completion_chars']:.0f}")
    print()
    print(f"  Format OK rate:          {summary['format_ok_rate']*100:.1f}%")
    print(f"  Has [[completed]] rate:  {summary['has_completed_rate']*100:.1f}%")
    print()
    print(f"  POSITIVE cases (n={summary['num_positive']}):")
    print(f"    ID precision:          {summary['positive_precision']*100:.1f}%")
    print(f"    ID recall:             {summary['positive_recall']*100:.1f}%")
    print(f"    ID F1:                 {summary['positive_f1']*100:.1f}%")
    print(f"    Value match (of GT):   {summary['positive_value_match_rate']*100:.1f}%")
    print(f"    Hallucination rate:    {summary['positive_hallucination_rate']*100:.1f}%")
    print()
    print(f"  NEGATIVE cases (n={summary['num_negative']}):")
    print(f"    Empty correct rate:    {summary['negative_empty_correct_rate']*100:.1f}%")
    print(f"    Avg pred count:        {summary['negative_avg_pred_count']:.2f}  (should be 0)")
    print()
    print(f"  Overall hallucination:   {summary['overall_hallucination_rate']*100:.1f}%")
    print(f"\nWrote summary → {summary_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate a model on the DataExtractor task")
    parser.add_argument("--url", required=True, help="Model server URL (e.g. http://localhost:8084/v1/chat/completions)")
    parser.add_argument("--model-path", required=True, help="Full model path/id as accepted by the server")
    parser.add_argument("--checkpoint-name", required=True, help="Short name for this checkpoint (e.g. grpo-1500)")
    parser.add_argument("--output", default="tuning/rl/eval_results/", help="Output directory")
    parser.add_argument("--num", type=int, default=None, help="Limit cases (for sanity checks)")
    args = parser.parse_args()

    run_eval(args)


if __name__ == "__main__":
    main()
