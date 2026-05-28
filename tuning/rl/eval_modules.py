#!/usr/bin/env python3
"""
eval_modules.py — Evaluate a model across all 5 DSPy modules in two modes.

Two-mode design (replaces the earlier single-routing pick_modules approach,
which undercounted text_responder and mismatched production gating):

  Mode A — ISOLATION (per-module competence, gold-gated)
    Tests "given correct inputs, can the model emit correct format+content
    per module?" Each module whose gate fires on GOLD intent is called
    independently with gold inputs (text_responder gets gold intent as its
    `intent` input). Coverage matches what forward() would run if the
    intent decider were perfect:
      intent_decider  — every case (300)
      text_responder  — every case (300)        # runs unconditionally in forward()
      data_extractor  — gold intent ∈ {gather, close}
      choice_builder  — gold intent ∈ {gather, clarify}
      review_builder  — gold intent ∈ {review, close}

  Mode B — CASCADE (production SLO, model-gated)
    Tests "in production, what fraction of turns produce a fully valid
    output?" Runs intent_decider first, then gates downstream modules on
    the MODEL'S PREDICTED intent — mirroring FormAssistant.forward(). The
    `intent` fed to text_responder is the prediction, not the gold. Turns
    are scored as `turn_format_ok` = AND of format_ok across every module
    that fired.

Per-module format_ok definitions (unchanged):
    intent_decider  — [[ ## completed ## ]] + intent marker + token in vocab
    text_responder  — [[ ## completed ## ]] + [[ ## response_text ## ]]
    data_extractor  — [[ ## completed ## ]] + field_ids + field_values + equal length
    choice_builder  — [[ ## completed ## ]] + question + options (parseable list)
    review_builder  — [[ ## completed ## ]] + summary_title + summary_content

Output (per mode):
    preds_modules_{name}_{mode}.jsonl
    summary_modules_{name}_{mode}.json

Usage:
    # Start the target model first:
    cd python && uv run python -m mlx_vlm.server \\
      --model ~/work/models/qwen35-08b-dspy-format-mlx --port 8084 &

    # Run both modes (default):
    uv run python tuning/rl/eval_modules.py \\
      --url http://localhost:8084/v1/chat/completions \\
      --model-path ~/work/models/qwen35-08b-dspy-format-mlx \\
      --checkpoint-name sft \\
      --output tuning/rl/eval_results/

    # One mode only:
    uv run python tuning/rl/eval_modules.py ... --mode isolation
    uv run python tuning/rl/eval_modules.py ... --mode cascade

    # Smoke test:
    uv run python tuning/rl/eval_modules.py ... --num 30
"""

import argparse
import ast
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

import requests

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dspy
from dspy.adapters.chat_adapter import ChatAdapter

# ══════════════════════════════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════════════════════════════

FORM_SCHEMA_PATH = PROJECT_ROOT / "packages/web-app/public/forms/masters-northfield.json"
TEST_CASES_PATH = PROJECT_ROOT / "tuning/data/test-cases.jsonl"
MAX_TOKENS = 512

INTENT_VOCAB = {"gather", "converse", "clarify", "close", "review"}


# ══════════════════════════════════════════════════════════════════════
# DSPy signatures — MUST match tuning/dspy/optimize_prompt.py exactly
# ══════════════════════════════════════════════════════════════════════

class IntentDeciderSignature(dspy.Signature):
    """Decide the assistant's intent for this turn of a form-filling conversation.

    - gather: User provided information — extract it into form fields, optionally ask next question
    - converse: No form action needed — just respond conversationally (greetings, questions, acknowledgments)
    - clarify: Need more info from the user — present choices or ask a specific question
    - close: Form is nearly complete — offer to save draft or submit
    - review: Show the user a summary of what's been filled so far"""

    context: str = dspy.InputField(desc="Form fields and current state")
    user_message: str = dspy.InputField(desc="Current user message")
    intent: Literal["gather", "converse", "clarify", "close", "review"] = dspy.OutputField(
        desc="The assistant's intent for this turn"
    )


class TextResponderSignature(dspy.Signature):
    """Generate a conversational response for a form-filling assistant.
    Keep it natural, helpful, and concise. Acknowledge what the user said
    and guide them through the form."""

    context: str = dspy.InputField(desc="Form fields and current state")
    user_message: str = dspy.InputField(desc="Current user message")
    intent: str = dspy.InputField(desc="Decided intent: gather/converse/clarify/close/review")
    response_text: str = dspy.OutputField(desc="Conversational response to the user")


class DataExtractorSignature(dspy.Signature):
    """Extract form field values from the user's message. Only extract data
    that the user explicitly provided. Map to the exact field_ids from the
    form schema. Return empty lists if no extractable data."""

    context: str = dspy.InputField(desc="Form fields and current state")
    user_message: str = dspy.InputField(desc="User message containing form data")
    field_ids: list[str] = dspy.OutputField(desc="List of field_ids to set, e.g. ['full_name', 'email']")
    field_values: list[str] = dspy.OutputField(desc="Corresponding values, e.g. ['Jane Smith', 'jane@email.com']")


class ChoiceBuilderSignature(dspy.Signature):
    """Build a multiple-choice question to present to the user.
    The question should guide them to the next piece of needed information.
    Options should be concrete and drawn from the form schema where applicable."""

    context: str = dspy.InputField(desc="Form fields and current state")
    user_message: str = dspy.InputField(desc="Current user message")
    question: str = dspy.OutputField(desc="The question to ask the user")
    options: list[str] = dspy.OutputField(desc="List of choice options, e.g. ['Full-time', 'Part-time']")


class ReviewBuilderSignature(dspy.Signature):
    """Build a summary of the form progress to show the user.
    Include what's been filled and what's still needed."""

    context: str = dspy.InputField(desc="Form fields and current state")
    user_message: str = dspy.InputField(desc="Current user message")
    summary_title: str = dspy.OutputField(desc="Title for the summary, e.g. 'Application Progress'")
    summary_content: str = dspy.OutputField(desc="Summary of filled fields and remaining items")


SIGNATURES = {
    "intent_decider":  IntentDeciderSignature,
    "text_responder":  TextResponderSignature,
    "data_extractor":  DataExtractorSignature,
    "choice_builder":  ChoiceBuilderSignature,
    "review_builder":  ReviewBuilderSignature,
}

ALL_MODULES = list(SIGNATURES.keys())

adapter = ChatAdapter()


# ══════════════════════════════════════════════════════════════════════
# Context builder (matches optimize_prompt.py / gen_format_data.py)
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
    form = json.load(open(FORM_SCHEMA_PATH))
    ids = set()
    for section in form["schema"]["sections"]:
        for f in section["fields"]:
            fid = f["field_id"]
            ids.add(fid)
            if f.get("type") == "group":
                for sub in f.get("fields", []):
                    sub_id = sub["field_id"]
                    ids.add(f"{fid}.*.{sub_id}")
                    ids.add(sub_id)
    return ids


# ══════════════════════════════════════════════════════════════════════
# Intent inference + module gating
# ══════════════════════════════════════════════════════════════════════

def infer_intent(case: dict) -> str:
    """Gold intent derived from expected_action_types. Mirrors
    optimize_prompt.infer_intent() so training labels and eval gold match."""
    acts = set(case.get("expected_action_types", case.get("action_types", [])))
    if "show_button" in acts:
        return "close"
    if ("show_preview" in acts or "show_fields" in acts) and "set_fields" not in acts and "ask_choice" not in acts:
        return "review"
    if "set_fields" in acts:
        return "gather"
    if "ask_choice" in acts:
        return "clarify"
    return "converse"


def modules_for_intent(intent: str) -> list[str]:
    """Which modules fire in FormAssistant.forward() for a given intent.

    intent_decider + text_responder run unconditionally on every turn;
    the other three are gated on intent. This is the single source of
    truth for both isolation (gold intent) and cascade (predicted intent)
    gating — same logic as FormAssistant.forward().
    """
    mods = ["intent_decider", "text_responder"]
    if intent in ("gather", "close"):   mods.append("data_extractor")
    if intent in ("gather", "clarify"): mods.append("choice_builder")
    if intent in ("review", "close"):   mods.append("review_builder")
    return mods


# ══════════════════════════════════════════════════════════════════════
# Ground truth extraction
# ══════════════════════════════════════════════════════════════════════

def parse_gt_values(case: dict) -> dict[str, str]:
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
                fid, val = f.get("field_id"), f.get("value")
                if fid is not None and val is not None:
                    values[fid] = val
    return values


# ══════════════════════════════════════════════════════════════════════
# Marker parsing
# ══════════════════════════════════════════════════════════════════════

MARKER_RE = re.compile(r"\[\[\s*##\s*(\w+)\s*##\s*\]\]")


def parse_markers(text: str) -> dict[str, str]:
    """Extract {field_name: value} for every [[ ## name ## ]] marker."""
    result = {}
    positions = [(m.start(), m.end(), m.group(1)) for m in MARKER_RE.finditer(text)]
    for i, (s, e, name) in enumerate(positions):
        next_s = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        result[name] = text[e:next_s].strip()
    return result


def parse_list(text: str) -> list:
    text = text.strip()
    if not text:
        return []
    try:
        r = json.loads(text)
        return r if isinstance(r, list) else []
    except json.JSONDecodeError:
        pass
    try:
        r = ast.literal_eval(text)
        return r if isinstance(r, list) else []
    except (ValueError, SyntaxError):
        return []


# ══════════════════════════════════════════════════════════════════════
# Per-module scorers
# ══════════════════════════════════════════════════════════════════════

def score_intent(markers: dict, case: dict) -> dict:
    has_completed = "completed" in markers
    intent_val = markers.get("intent", "").strip().lower()
    intent_val = intent_val.strip('"').strip("'").strip()
    in_vocab = intent_val in INTENT_VOCAB
    format_ok = has_completed and "intent" in markers and in_vocab
    gold = infer_intent(case)
    content_ok = in_vocab and intent_val == gold
    return {
        "format_ok": format_ok,
        "has_completed": has_completed,
        "pred_intent": intent_val,
        "gold_intent": gold,
        "intent_correct": content_ok,
    }


def score_text(markers: dict, case: dict) -> dict:
    has_completed = "completed" in markers
    text = markers.get("response_text", "").strip()
    has_marker = "response_text" in markers
    format_ok = has_completed and has_marker
    content_ok = len(text) > 20
    return {
        "format_ok": format_ok,
        "has_completed": has_completed,
        "response_length": len(text),
        "content_ok": content_ok,
    }


def score_extractor(markers: dict, case: dict, valid_schema_ids: set[str]) -> dict:
    has_completed = "completed" in markers
    has_ids_marker = "field_ids" in markers
    has_vals_marker = "field_values" in markers

    pred_ids = parse_list(markers.get("field_ids", "")) if has_ids_marker else []
    pred_vals = parse_list(markers.get("field_values", "")) if has_vals_marker else []
    format_ok = has_completed and has_ids_marker and has_vals_marker and len(pred_ids) == len(pred_vals)
    format_ok_loose = has_completed and has_ids_marker and has_vals_marker

    gt_ids = case.get("expected_fields_set", []) if "set_fields" in case.get("expected_action_types", []) else []
    gt_vals = parse_gt_values(case) if gt_ids else {}
    gt_set = set(gt_ids)
    pred_set = set(pred_ids)
    pred_map = dict(zip(pred_ids, pred_vals))

    tp = len(gt_set & pred_set)
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

    def id_in_schema(fid: str) -> bool:
        if fid in valid_schema_ids:
            return True
        pattern = re.sub(r"\.\d+\.", ".*.", fid)
        return pattern in valid_schema_ids
    hallucinated = [fid for fid in pred_ids if not id_in_schema(fid)]

    empty_expected = not gt_set
    empty_correct = empty_expected and (not pred_set)
    content_ok = (
        format_ok
        and (empty_correct if empty_expected else (f1 >= 0.5))
    )

    return {
        "format_ok": format_ok,
        "format_ok_loose": format_ok_loose,
        "has_completed": has_completed,
        "content_ok": content_ok,
        "gt_count": len(gt_set),
        "pred_count": len(pred_set),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "value_matches": value_matches,
        "value_considered": value_considered,
        "value_match_rate_of_gt": value_match_rate_of_gt,
        "hallucination_count": len(hallucinated),
        "hallucination_rate": len(hallucinated) / len(pred_ids) if pred_ids else 0.0,
        "empty_expected": empty_expected,
        "empty_correct": empty_correct,
        "pred_ids": pred_ids,
        "pred_vals": pred_vals,
    }


def score_choice(markers: dict, case: dict) -> dict:
    has_completed = "completed" in markers
    has_q = "question" in markers
    has_opts = "options" in markers
    question = markers.get("question", "").strip()
    options = parse_list(markers.get("options", "")) if has_opts else []
    format_ok = has_completed and has_q and has_opts and isinstance(options, list)
    content_ok = format_ok and len(question) > 5 and len(options) >= 2
    return {
        "format_ok": format_ok,
        "has_completed": has_completed,
        "question_length": len(question),
        "options_count": len(options),
        "content_ok": content_ok,
    }


def score_review(markers: dict, case: dict) -> dict:
    has_completed = "completed" in markers
    has_title = "summary_title" in markers
    has_content = "summary_content" in markers
    title = markers.get("summary_title", "").strip()
    content = markers.get("summary_content", "").strip()
    format_ok = has_completed and has_title and has_content
    content_ok = format_ok and len(title) > 3 and len(content) > 20
    return {
        "format_ok": format_ok,
        "has_completed": has_completed,
        "title_length": len(title),
        "content_length": len(content),
        "content_ok": content_ok,
    }


SCORERS = {
    "intent_decider": lambda m, c, _: score_intent(m, c),
    "text_responder": lambda m, c, _: score_text(m, c),
    "data_extractor": lambda m, c, ids: score_extractor(m, c, ids),
    "choice_builder": lambda m, c, _: score_choice(m, c),
    "review_builder": lambda m, c, _: score_review(m, c),
}


# ══════════════════════════════════════════════════════════════════════
# Model calling + one module call
# ══════════════════════════════════════════════════════════════════════

def call_model(url: str, model: str, messages: list[dict]) -> tuple[str, float, str | None]:
    payload = {"model": model, "messages": messages, "max_tokens": MAX_TOKENS, "temperature": 0.0}
    t0 = time.time()
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"], time.time() - t0, None
    except Exception as e:
        return "", time.time() - t0, str(e)


def call_module(
    url: str,
    model_path: str,
    module: str,
    case: dict,
    ctx: str,
    intent_for_text: str | None,
    valid_schema_ids: set[str],
) -> dict:
    """Run one module on one case and return {module, raw_output, latency, error, metrics}.

    For text_responder, `intent_for_text` is the value fed into the `intent` input
    field (gold in isolation mode, predicted in cascade mode).
    """
    sig = SIGNATURES[module]
    inputs = {"context": ctx, "user_message": case["user_message"]}
    if module == "text_responder":
        assert intent_for_text is not None, "text_responder requires an intent input"
        inputs["intent"] = intent_for_text

    messages = adapter.format(signature=sig, demos=[], inputs=inputs)
    raw, dur, err = call_model(url, model_path, messages)
    if err:
        return {
            "module": module,
            "raw_output": "",
            "latency_s": dur,
            "error": err,
            "metrics": None,
        }
    markers = parse_markers(raw)
    metrics = SCORERS[module](markers, case, valid_schema_ids)
    return {
        "module": module,
        "raw_output": raw,
        "latency_s": dur,
        "error": None,
        "metrics": metrics,
    }


# ══════════════════════════════════════════════════════════════════════
# Mode A — ISOLATION
# ══════════════════════════════════════════════════════════════════════

def run_isolation(args, cases: list[dict], form_context: str, valid_schema_ids: set[str]) -> dict:
    """Gate on GOLD intent. Each module called independently with gold inputs."""
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    preds_path = out_dir / f"preds_modules_{args.checkpoint_name}_isolation.jsonl"
    summary_path = out_dir / f"summary_modules_{args.checkpoint_name}_isolation.json"

    per_example: list[dict] = []
    errors = 0
    latencies: list[float] = []

    # Count calls up front
    planned: list[tuple[int, dict, str]] = []
    for idx, c in enumerate(cases):
        gold = infer_intent(c)
        for m in modules_for_intent(gold):
            planned.append((idx, c, m))

    per_module_planned = Counter(m for _, _, m in planned)
    print(f"[ISOLATION]  {len(cases)} cases → {len(planned)} module calls")
    print(f"  per-module planned: {dict(per_module_planned)}")

    for i, (case_idx, case, module) in enumerate(planned):
        ctx = build_context(case, form_context)
        gold = infer_intent(case)
        intent_for_text = gold if module == "text_responder" else None
        result = call_module(
            args.url, args.model_path, module, case, ctx, intent_for_text, valid_schema_ids
        )
        result.update({
            "mode": "isolation",
            "case_idx": case_idx,
            "test_id": case.get("test_id"),
            "category": case.get("category"),
            "gold_intent": gold,
            "user_message": case["user_message"][:200],
        })
        latencies.append(result["latency_s"])
        if result["error"]:
            errors += 1
        per_example.append(result)

        if (i + 1) % 20 == 0:
            avg_lat = sum(latencies) / len(latencies)
            print(f"  {i + 1}/{len(planned)}  errors={errors}  avg_latency={avg_lat:.2f}s")

    with open(preds_path, "w") as f:
        for r in per_example:
            f.write(json.dumps(r) + "\n")
    print(f"[ISOLATION] Wrote per-example → {preds_path}")

    summary = aggregate_per_module(per_example, cases, errors, latencies, mode="isolation")
    summary["checkpoint"] = args.checkpoint_name
    summary["model_path"] = args.model_path
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print_isolation_summary(args.checkpoint_name, summary)
    print(f"[ISOLATION] Wrote summary → {summary_path}")
    return summary


def aggregate_per_module(
    per_example: list[dict], cases: list[dict], errors: int, latencies: list[float], mode: str
) -> dict:
    by_module: dict[str, list] = defaultdict(list)
    for r in per_example:
        if r["metrics"] is not None:
            by_module[r["module"]].append(r)

    per_module_summary = {}
    for module, rows in by_module.items():
        n = len(rows)
        def rate(key):
            return sum(1 for r in rows if r["metrics"].get(key)) / n if n else 0.0
        def avg(key, subset=None):
            src = subset if subset is not None else rows
            vals = [r["metrics"].get(key, 0) for r in src if r["metrics"].get(key) is not None]
            return sum(vals) / len(vals) if vals else 0.0

        s = {
            "n": n,
            "format_ok_rate": rate("format_ok"),
            "has_completed_rate": rate("has_completed"),
        }

        if module == "intent_decider":
            s["intent_accuracy"] = rate("intent_correct")
            per_intent_n = Counter(r["metrics"]["gold_intent"] for r in rows)
            per_intent_correct = Counter(
                r["metrics"]["gold_intent"] for r in rows if r["metrics"].get("intent_correct")
            )
            s["per_gold_intent_accuracy"] = {
                g: (per_intent_correct[g] / per_intent_n[g] if per_intent_n[g] else 0.0)
                for g in sorted(per_intent_n)
            }
            s["per_gold_intent_n"] = dict(per_intent_n)
        elif module == "text_responder":
            s["content_ok_rate"] = rate("content_ok")
            s["avg_response_length"] = avg("response_length")
        elif module == "data_extractor":
            s["content_ok_rate"] = rate("content_ok")
            s["format_ok_loose_rate"] = rate("format_ok_loose")
            positive = [r for r in rows if r["metrics"]["gt_count"] > 0]
            negative = [r for r in rows if r["metrics"]["gt_count"] == 0]
            s["num_positive"] = len(positive)
            s["num_negative"] = len(negative)
            s["positive_precision"] = avg("precision", positive)
            s["positive_recall"] = avg("recall", positive)
            s["positive_f1"] = avg("f1", positive)
            s["positive_value_match_rate"] = avg("value_match_rate_of_gt", positive)
            s["positive_hallucination_rate"] = avg("hallucination_rate", positive)
            s["negative_empty_correct_rate"] = (
                sum(1 for r in negative if r["metrics"]["empty_correct"]) / len(negative)
                if negative else 0.0
            )
            s["negative_avg_pred_count"] = avg("pred_count", negative)
        elif module == "choice_builder":
            s["content_ok_rate"] = rate("content_ok")
            s["avg_options_count"] = avg("options_count")
        elif module == "review_builder":
            s["content_ok_rate"] = rate("content_ok")
            s["avg_content_length"] = avg("content_length")

        per_module_summary[module] = s

    return {
        "mode": mode,
        "num_cases": len(cases),
        "num_module_calls": len(per_example),
        "num_errors": errors,
        "avg_latency_s": sum(latencies) / len(latencies) if latencies else 0.0,
        "per_module": per_module_summary,
    }


def print_isolation_summary(name: str, summary: dict) -> None:
    print("\n" + "=" * 72)
    print(f"ISOLATION SUMMARY — {name}")
    print("=" * 72)
    print(f"  Cases: {summary['num_cases']}  |  Calls: {summary['num_module_calls']}  |  Errors: {summary['num_errors']}")
    print(f"  Avg latency: {summary['avg_latency_s']:.2f}s")
    print()
    print(f"  {'Module':<18} {'n':>4}  {'format_ok':>10}  {'content':>10}  notes")
    print(f"  {'-'*18} {'-'*4}  {'-'*10}  {'-'*10}  {'-'*40}")
    for module in ALL_MODULES:
        s = summary["per_module"].get(module)
        if not s:
            continue
        fmt = f"{s['format_ok_rate']*100:.1f}%"
        notes = ""
        if module == "intent_decider":
            content = f"{s.get('intent_accuracy', 0)*100:.1f}%"
            per_g = s.get("per_gold_intent_accuracy", {})
            notes = " ".join(f"{g}={per_g[g]*100:.0f}%" for g in sorted(per_g))
        elif module == "text_responder":
            content = f"{s.get('content_ok_rate', 0)*100:.1f}%"
            notes = f"avg_len={s.get('avg_response_length', 0):.0f}"
        elif module == "data_extractor":
            content = f"{s.get('content_ok_rate', 0)*100:.1f}%"
            notes = (f"loose_fmt={s.get('format_ok_loose_rate', 0)*100:.1f}%  "
                     f"pos_f1={s.get('positive_f1', 0)*100:.1f}%  "
                     f"neg_empty={s.get('negative_empty_correct_rate', 0)*100:.1f}%")
        elif module == "choice_builder":
            content = f"{s.get('content_ok_rate', 0)*100:.1f}%"
            notes = f"avg_opts={s.get('avg_options_count', 0):.1f}"
        elif module == "review_builder":
            content = f"{s.get('content_ok_rate', 0)*100:.1f}%"
            notes = f"avg_content_len={s.get('avg_content_length', 0):.0f}"
        print(f"  {module:<18} {s['n']:>4}  {fmt:>10}  {content:>10}  {notes}")


# ══════════════════════════════════════════════════════════════════════
# Mode B — CASCADE
# ══════════════════════════════════════════════════════════════════════

def run_cascade(args, cases: list[dict], form_context: str, valid_schema_ids: set[str]) -> dict:
    """Production pipeline: intent_decider first, then gate downstream on
    the PREDICTED intent (same logic as FormAssistant.forward)."""
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    preds_path = out_dir / f"preds_modules_{args.checkpoint_name}_cascade.jsonl"
    summary_path = out_dir / f"summary_modules_{args.checkpoint_name}_cascade.json"

    per_turn: list[dict] = []
    errors = 0
    latencies: list[float] = []

    print(f"[CASCADE]  {len(cases)} cases  (intent-gated downstream, predicted intent)")

    for i, case in enumerate(cases):
        ctx = build_context(case, form_context)
        gold_intent = infer_intent(case)

        # Step 1: intent_decider
        intent_res = call_module(
            args.url, args.model_path, "intent_decider", case, ctx, None, valid_schema_ids
        )
        latencies.append(intent_res["latency_s"])
        if intent_res["error"]:
            errors += 1

        intent_metrics = intent_res["metrics"]
        predicted_intent = intent_metrics["pred_intent"] if intent_metrics else ""
        intent_format_ok = bool(intent_metrics and intent_metrics["format_ok"])

        # Step 2: gate downstream on predicted intent (only if it's in vocab)
        fired_modules = ["intent_decider"]
        module_results: dict[str, dict] = {"intent_decider": intent_res}

        if predicted_intent in INTENT_VOCAB:
            downstream = [m for m in modules_for_intent(predicted_intent) if m != "intent_decider"]
        else:
            # Invalid intent → cannot safely gate downstream. Mark turn as
            # format-broken but still run text_responder on the raw string
            # (production would fail earlier via AdapterParseError, but we
            # want a diagnostic signal, not a silent skip).
            downstream = ["text_responder"]

        for module in downstream:
            intent_for_text = predicted_intent if module == "text_responder" else None
            r = call_module(
                args.url, args.model_path, module, case, ctx, intent_for_text, valid_schema_ids
            )
            latencies.append(r["latency_s"])
            if r["error"]:
                errors += 1
            fired_modules.append(module)
            module_results[module] = r

        # Turn-level format_ok = AND of format_ok across every fired module
        per_module_format = {
            m: (res["metrics"]["format_ok"] if res["metrics"] else False)
            for m, res in module_results.items()
        }
        turn_format_ok = all(per_module_format.values()) and predicted_intent in INTENT_VOCAB

        # Turn-level content_ok: requires intent correct AND content_ok on all
        # other fired modules that have a content_ok metric.
        intent_correct = bool(intent_metrics and intent_metrics["intent_correct"])
        other_content_ok = all(
            res["metrics"].get("content_ok", False)
            for m, res in module_results.items()
            if m != "intent_decider" and res["metrics"] is not None
        )
        turn_content_ok = turn_format_ok and intent_correct and other_content_ok

        per_turn.append({
            "mode": "cascade",
            "case_idx": i,
            "test_id": case.get("test_id"),
            "category": case.get("category"),
            "user_message": case["user_message"][:200],
            "gold_intent": gold_intent,
            "predicted_intent": predicted_intent,
            "intent_correct": intent_correct,
            "intent_format_ok": intent_format_ok,
            "fired_modules": fired_modules,
            "per_module_format_ok": per_module_format,
            "turn_format_ok": turn_format_ok,
            "turn_content_ok": turn_content_ok,
            "module_results": {
                m: {
                    "raw_output": res["raw_output"],
                    "latency_s": res["latency_s"],
                    "error": res["error"],
                    "metrics": res["metrics"],
                }
                for m, res in module_results.items()
            },
        })

        if (i + 1) % 20 == 0:
            avg_lat = sum(latencies) / len(latencies)
            fmt_rate = sum(1 for t in per_turn if t["turn_format_ok"]) / len(per_turn)
            print(f"  {i + 1}/{len(cases)}  turn_format_ok={fmt_rate*100:.1f}%  "
                  f"errors={errors}  avg_latency={avg_lat:.2f}s")

    with open(preds_path, "w") as f:
        for r in per_turn:
            f.write(json.dumps(r) + "\n")
    print(f"[CASCADE] Wrote per-turn → {preds_path}")

    summary = aggregate_cascade(per_turn, errors, latencies)
    summary["checkpoint"] = args.checkpoint_name
    summary["model_path"] = args.model_path
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print_cascade_summary(args.checkpoint_name, summary)
    print(f"[CASCADE] Wrote summary → {summary_path}")
    return summary


def aggregate_cascade(per_turn: list[dict], errors: int, latencies: list[float]) -> dict:
    n = len(per_turn)
    if n == 0:
        return {"mode": "cascade", "num_turns": 0}

    def rate(key):
        return sum(1 for t in per_turn if t.get(key)) / n

    # Per-fired-module format_ok rates (conditional on that module firing)
    per_module_rows: dict[str, list] = defaultdict(list)
    for t in per_turn:
        for m, res in t["module_results"].items():
            per_module_rows[m].append(res)

    per_module_summary = {}
    for module, rows in per_module_rows.items():
        rn = len(rows)
        fok = sum(1 for r in rows if r["metrics"] and r["metrics"].get("format_ok")) / rn if rn else 0.0
        cok = sum(1 for r in rows if r["metrics"] and r["metrics"].get("content_ok")) / rn if rn else 0.0
        per_module_summary[module] = {
            "n_fired": rn,
            "format_ok_rate": fok,
            "content_ok_rate": cok,
        }

    # Confusion: gold intent → predicted intent
    confusion: dict[str, Counter] = defaultdict(Counter)
    for t in per_turn:
        confusion[t["gold_intent"]][t["predicted_intent"]] += 1

    return {
        "mode": "cascade",
        "num_turns": n,
        "num_errors": errors,
        "avg_latency_s": sum(latencies) / len(latencies) if latencies else 0.0,
        "intent_accuracy": rate("intent_correct"),
        "intent_format_ok_rate": rate("intent_format_ok"),
        "turn_format_ok_rate": rate("turn_format_ok"),
        "turn_content_ok_rate": rate("turn_content_ok"),
        "per_module_conditional": per_module_summary,
        "intent_confusion": {g: dict(c) for g, c in confusion.items()},
    }


def print_cascade_summary(name: str, summary: dict) -> None:
    print("\n" + "=" * 72)
    print(f"CASCADE SUMMARY — {name}")
    print("=" * 72)
    print(f"  Turns: {summary['num_turns']}  |  Errors: {summary['num_errors']}")
    print(f"  Avg latency: {summary['avg_latency_s']:.2f}s")
    print()
    print(f"  Intent accuracy:       {summary['intent_accuracy']*100:.1f}%")
    print(f"  Intent format_ok:      {summary['intent_format_ok_rate']*100:.1f}%")
    print(f"  Turn format_ok (prod): {summary['turn_format_ok_rate']*100:.1f}%")
    print(f"  Turn content_ok:       {summary['turn_content_ok_rate']*100:.1f}%")
    print()
    print(f"  Per-module (conditional on firing):")
    print(f"  {'Module':<18} {'n_fired':>8}  {'format_ok':>10}  {'content_ok':>10}")
    print(f"  {'-'*18} {'-'*8}  {'-'*10}  {'-'*10}")
    for module in ALL_MODULES:
        s = summary["per_module_conditional"].get(module)
        if not s:
            continue
        print(f"  {module:<18} {s['n_fired']:>8}  "
              f"{s['format_ok_rate']*100:>9.1f}%  {s['content_ok_rate']*100:>9.1f}%")
    print()
    print(f"  Intent confusion (gold → predicted):")
    for gold in sorted(summary["intent_confusion"]):
        counts = summary["intent_confusion"][gold]
        total = sum(counts.values())
        pairs = ", ".join(f"{p}={counts[p]}" for p in sorted(counts, key=lambda k: -counts[k]))
        print(f"    {gold:<8} (n={total}): {pairs}")


# ══════════════════════════════════════════════════════════════════════
# Driver
# ══════════════════════════════════════════════════════════════════════

def run_eval(args):
    form_context = load_form_context()
    valid_schema_ids = load_valid_schema_ids()
    cases = [json.loads(l) for l in open(TEST_CASES_PATH) if l.strip()]
    if args.num:
        cases = cases[: args.num]

    print(f"Model:      {args.checkpoint_name}")
    print(f"URL:        {args.url}")
    print(f"Cases:      {len(cases)}")
    print(f"Mode:       {args.mode}")
    print("=" * 72)

    if args.mode in ("isolation", "both"):
        run_isolation(args, cases, form_context, valid_schema_ids)
    if args.mode in ("cascade", "both"):
        run_cascade(args, cases, form_context, valid_schema_ids)


def main():
    parser = argparse.ArgumentParser(description="Evaluate a model across all 5 DSPy modules (two-mode)")
    parser.add_argument("--url", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--checkpoint-name", required=True)
    parser.add_argument("--output", default="tuning/rl/eval_results/")
    parser.add_argument("--num", type=int, default=None)
    parser.add_argument(
        "--mode",
        choices=["isolation", "cascade", "both"],
        default="both",
        help="isolation = per-module competence (gold-gated); cascade = production SLO (model-gated).",
    )
    args = parser.parse_args()
    run_eval(args)


if __name__ == "__main__":
    main()
