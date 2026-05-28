#!/usr/bin/env python3
"""
Compare Qwen3.5-0.8B variants (base / SFT) on DSPy structured output.

Two-stage design — inference is separate from scoring/reporting so we never
re-run a model just to look at predictions a different way.

Stage 1 — `infer`: run a model against the test cases, write per-case JSONL
          (raw outputs + gold labels). The only stage that touches a server.

Stage 2 — `report`: read one or more JSONL files, recompute every metric
          from the raw outputs, print aggregate summary and (optionally) one
          failure example per metric bucket. Pure post-processing; no model
          calls. Re-running `report` is free, so iterating on metrics or
          drilling into failures requires zero extra inference.

Usage:
    cd python

    # 1. Infer — once per model (output is canonical, reusable):
    uv run python ../tuning/sft/compare_models.py infer \\
        --label v2 \\
        --url http://localhost:8100/v1/chat/completions \\
        --model ./models/qwen35-08b-dspy-format-v2-mlx \\
        --out /tmp/preds_v2.jsonl

    uv run python ../tuning/sft/compare_models.py infer \\
        --label base \\
        --url http://localhost:8082/v1/chat/completions \\
        --model mlx-community/Qwen3.5-0.8B-4bit \\
        --out /tmp/preds_base.jsonl

    # 2. Report — read predictions, score, summarize:
    uv run python ../tuning/sft/compare_models.py report \\
        --in /tmp/preds_v2.jsonl /tmp/preds_base.jsonl

    # 3. Failure examples — one per metric bucket that's not 100%:
    uv run python ../tuning/sft/compare_models.py report \\
        --in /tmp/preds_v2.jsonl --failures
"""

import json
import sys
import re
import argparse
import time
from pathlib import Path
from collections import Counter, defaultdict

import requests

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dspy
from dspy.adapters.chat_adapter import ChatAdapter

# ══════════════════════════════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════════════════════════════

ORIGINAL_URL = "http://localhost:8082/v1/chat/completions"
SFT_URL = "http://localhost:8084/v1/chat/completions"

FORM_SCHEMA_PATH = PROJECT_ROOT / "packages/web-app/public/forms/masters-northfield.json"
TEST_CASES_PATH = PROJECT_ROOT / "tuning/data/test-cases.jsonl"

MAX_TOKENS = 512

# ══════════════════════════════════════════════════════════════════════
# DSPy Signatures — must match optimize_prompt.py
# ══════════════════════════════════════════════════════════════════════

class ActionRouterSignature(dspy.Signature):
    """Decide which actions the assistant should take this turn by emitting
    five independent boolean flags. Each flag is set independently — a single
    turn can combine e.g. extraction + choice, or review + save-offer.

    - has_new_data: user provided new field values to extract
    - needs_choice: a multiple-choice question should be presented
    - wants_review: a progress-summary card should be shown
    - wants_save:   a Save Draft button should be offered
    - wants_submit: a Submit Application button should be offered"""

    context: str = dspy.InputField(desc="Form fields and current state")
    user_message: str = dspy.InputField(desc="Current user message")
    has_new_data: bool = dspy.OutputField(desc="True if user provided new field values to extract")
    needs_choice: bool = dspy.OutputField(desc="True if a multiple-choice question should be presented")
    wants_review: bool = dspy.OutputField(desc="True if a progress-summary card should be shown")
    wants_save:   bool = dspy.OutputField(desc="True if a Save Draft button should be offered")
    wants_submit: bool = dspy.OutputField(desc="True if a Submit Application button should be offered")


class TextResponderSignature(dspy.Signature):
    """Generate a conversational response for a form-filling assistant.
    Keep it natural, helpful, and concise. Acknowledge what the user said
    and guide them through the form."""

    context: str = dspy.InputField(desc="Form fields and current state")
    user_message: str = dspy.InputField(desc="Current user message")
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
    "action_router": ActionRouterSignature,
    "text_responder": TextResponderSignature,
    "data_extractor": DataExtractorSignature,
    "choice_builder": ChoiceBuilderSignature,
    "review_builder": ReviewBuilderSignature,
}

ROUTE_FLAGS = ("has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit")

MODULE_OUTPUT_FIELDS = {
    "action_router": list(ROUTE_FLAGS),
    "text_responder": ["response_text"],
    "data_extractor": ["field_ids", "field_values"],
    "choice_builder": ["question", "options"],
    "review_builder": ["summary_title", "summary_content"],
}

# ══════════════════════════════════════════════════════════════════════
# Context builder — matches optimize_prompt.py exactly
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


# ══════════════════════════════════════════════════════════════════════
# Route inference — matches optimize_prompt.py::infer_route
# ══════════════════════════════════════════════════════════════════════

def infer_route(case: dict) -> dict:
    """Infer 5 independent route flags.

    Canonical source: the JSON action block inside `expected_output`. We parse
    it directly for both action types and button names. Earlier versions read
    `parsed_actions` / `expected_action_types`, but `tuning/scripts/sample.py`
    drops `parsed_actions` when building test-cases.jsonl — which silently made
    `wants_save` / `wants_submit` always False and inflated their reported
    accuracy. See the gold-label audit for details.

    The legacy fields (`expected_action_types`, `parsed_actions`) are honored
    as a fallback for atomic-data turns that don't carry `expected_output`.
    """
    actions = _parse_actions_block(case.get("expected_output", ""))
    if actions:
        acts = {a.get("type", "") for a in actions}
        buttons = {a.get("button") for a in actions if a.get("type") == "show_button"}
    else:
        # Fallback for inputs without expected_output (e.g., raw atomic turns)
        acts = set(case.get("expected_action_types", case.get("action_types", [])) or [])
        parsed = case.get("parsed_actions") or []
        buttons = {a.get("button") for a in parsed if a.get("type") == "show_button"}
    return {
        "has_new_data": "set_fields" in acts,
        "needs_choice": "ask_choice" in acts,
        "wants_review": "show_preview" in acts or "show_fields" in acts,
        "wants_save":   "save_draft" in buttons,
        "wants_submit": "submit" in buttons,
    }


def pick_module(case: dict) -> str:
    """Pick which content sub-module to test for this case.

    Priority: has_new_data → data_extractor, needs_choice → choice_builder,
    wants_review → review_builder, else text_responder (pure-conversation
    turns, including turns that only offer save/submit buttons).

    Note: action_router is evaluated separately on ALL cases for per-flag
    routing accuracy — see run_comparison().
    """
    route = infer_route(case)
    if route["has_new_data"]:
        return "data_extractor"
    if route["needs_choice"]:
        return "choice_builder"
    if route["wants_review"]:
        return "review_builder"
    return "text_responder"


# ══════════════════════════════════════════════════════════════════════
# Gold-label parsers — pull structured truth out of case["expected_output"]
# ══════════════════════════════════════════════════════════════════════

ACTIONS_BLOCK_RE = re.compile(r"---actions---\s*```json\s*(.*?)```", re.DOTALL)


def _parse_actions_block(expected_output: str) -> list[dict]:
    m = ACTIONS_BLOCK_RE.search(expected_output or "")
    if not m:
        return []
    try:
        return json.loads(m.group(1).strip())
    except Exception:
        return []


def _normalize_field_id(fid: str) -> str:
    """Normalize dot/dash notation so `jobs.0.title` == `jobs-0-title`."""
    return fid.replace("-", ".") if isinstance(fid, str) else fid


def gold_set_fields(case: dict) -> list[tuple[str, object]]:
    """Return list of (field_id_normalized, value) from expected set_fields action."""
    pairs = []
    for action in _parse_actions_block(case.get("expected_output", "")):
        if action.get("type") == "set_fields":
            for f in action.get("fields", []):
                if "field_id" in f and "value" in f:
                    pairs.append((_normalize_field_id(f["field_id"]), f["value"]))
    return pairs


def gold_ask_choice_options(case: dict) -> list[str]:
    """Return the options list from an expected ask_choice action, or []."""
    for action in _parse_actions_block(case.get("expected_output", "")):
        if action.get("type") == "ask_choice":
            opts = action.get("options", [])
            out = []
            for o in opts:
                if isinstance(o, dict):
                    out.append(str(o.get("label") or o.get("value") or ""))
                else:
                    out.append(str(o))
            return [o for o in out if o]
    return []


# ══════════════════════════════════════════════════════════════════════
# Format analysis
# ══════════════════════════════════════════════════════════════════════

FIELD_MARKER_RE = re.compile(r'\[\[\s*##\s*(\w+)\s*##\s*\]\]')
COMPLETED_RE = re.compile(r'\[\[\s*##\s*completed\s*##\s*\]\]')


def analyze_format(output: str, expected_fields: list[str]) -> dict:
    """Analyze whether model output matches DSPy's expected format."""
    found_fields = FIELD_MARKER_RE.findall(output)
    has_completed = bool(COMPLETED_RE.search(output))

    expected_set = set(expected_fields)
    found_set = set(found_fields) - {"completed"}

    return {
        "has_completed": has_completed,
        "found_fields": found_fields,
        "expected_fields": expected_fields,
        "fields_present": expected_set.issubset(found_set),
        "extra_fields": list(found_set - expected_set),
        "missing_fields": list(expected_set - found_set),
        "format_ok": has_completed and expected_set.issubset(found_set),
    }


def extract_field_value(output: str, field_name: str) -> str | None:
    """Extract the value after a [[ ## field_name ## ]] marker."""
    pattern = rf'\[\[\s*##\s*{re.escape(field_name)}\s*##\s*\]\]\s*\n?(.*?)(?=\[\[|$)'
    m = re.search(pattern, output, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def _parse_json_list(raw: str | None) -> list | None:
    """Parse a DSPy list-typed field. DSPy ChatAdapter emits JSON arrays."""
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return []
    # Try JSON first
    try:
        val = json.loads(raw)
        if isinstance(val, list):
            return val
    except Exception:
        pass
    # Fallback: bracketed python-ish list — crude eval via split
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        # split on commas not inside quotes — good enough for string lists
        parts = re.findall(r'"([^"]*)"|\'([^\']*)\'|([^,]+)', inner)
        return [next(p for p in tup if p).strip() for tup in parts if any(tup)]
    return None


def _values_equal(a, b) -> bool:
    """Loose equality for set_fields value comparison."""
    if a is None or b is None:
        return a == b
    # Same type after normalization
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    sa, sb = str(a).strip(), str(b).strip()
    if sa.lower() == sb.lower():
        return True
    # Numbers
    try:
        return float(sa) == float(sb)
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════
# Per-module content scorers — return dicts of metrics
# ══════════════════════════════════════════════════════════════════════

def score_data_extractor(output: str, case: dict) -> dict:
    """ID precision/recall/F1 + value exact-match rate."""
    gold_pairs = gold_set_fields(case)
    gold_ids = {fid for fid, _ in gold_pairs}
    gold_map = {fid: v for fid, v in gold_pairs}

    pred_ids_raw = _parse_json_list(extract_field_value(output, "field_ids")) or []
    pred_vals_raw = _parse_json_list(extract_field_value(output, "field_values")) or []
    pred_ids = [_normalize_field_id(x) for x in pred_ids_raw if isinstance(x, str)]

    pred_set = set(pred_ids)
    tp = len(pred_set & gold_ids)
    fp = len(pred_set - gold_ids)
    fn = len(gold_ids - pred_set)
    precision = tp / (tp + fp) if (tp + fp) else (1.0 if not gold_ids else 0.0)
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    # Value match: for each gold id the model correctly predicted, is the value right?
    value_correct = 0
    value_total = 0
    pred_map = {fid: (pred_vals_raw[i] if i < len(pred_vals_raw) else None) for i, fid in enumerate(pred_ids)}
    for fid in (pred_set & gold_ids):
        value_total += 1
        if _values_equal(pred_map.get(fid), gold_map.get(fid)):
            value_correct += 1

    return {
        "n_gold": len(gold_ids),
        "n_pred": len(pred_set),
        "tp": tp, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "value_correct": value_correct, "value_total": value_total,
        "id_exact_match": pred_set == gold_ids,
    }


def score_choice_builder(output: str, case: dict) -> dict:
    """Option-set F1 + exact-match (question text skipped — paraphrasing allowed)."""
    gold_opts = [o.strip().lower() for o in gold_ask_choice_options(case)]
    pred_opts_raw = _parse_json_list(extract_field_value(output, "options")) or []
    pred_opts = [str(o).strip().lower() for o in pred_opts_raw if o]

    gold_set = set(gold_opts)
    pred_set = set(pred_opts)
    tp = len(pred_set & gold_set)
    fp = len(pred_set - gold_set)
    fn = len(gold_set - pred_set)
    precision = tp / (tp + fp) if (tp + fp) else (1.0 if not gold_set else 0.0)
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    question = extract_field_value(output, "question") or ""
    return {
        "n_gold": len(gold_set),
        "n_pred": len(pred_set),
        "precision": precision, "recall": recall, "f1": f1,
        "exact_set_match": pred_set == gold_set,
        "has_question": bool(question.strip()),
    }


def score_review_builder(output: str, case: dict) -> dict:
    """Loose presence check: does summary_content mention any expected fields?"""
    expected = [f.lower() for f in case.get("expected_fields_set", [])]
    summary = (extract_field_value(output, "summary_content") or "").lower()
    title = (extract_field_value(output, "summary_title") or "").strip()
    mentioned = sum(1 for f in expected if f.replace("_", " ") in summary or f in summary)
    return {
        "n_expected": len(expected),
        "n_mentioned": mentioned,
        "coverage": mentioned / len(expected) if expected else 1.0,
        "has_title": bool(title),
        "has_content": bool(summary),
    }


FORMAT_LEAK_RE = re.compile(r"\[\[\s*##|---actions---")


def score_text_responder(output: str, case: dict) -> dict:
    """Free-text sanity: non-empty, reasonable length, no format leakage within the reply."""
    text = extract_field_value(output, "response_text") or ""
    text = text.strip()
    n_chars = len(text)
    leak = bool(FORMAT_LEAK_RE.search(text))
    return {
        "n_chars": n_chars,
        "nonempty": n_chars > 0,
        "reasonable_length": 5 <= n_chars <= 2000,
        "no_format_leak": not leak,
        "ok": n_chars > 0 and not leak,
    }


# ══════════════════════════════════════════════════════════════════════
# Model calling
# ══════════════════════════════════════════════════════════════════════

adapter = ChatAdapter()


def call_model(url: str, messages: list[dict], model_name: str = "default") -> tuple[str, float]:
    """Call a model via OpenAI-compatible API. Returns (output_text, duration_s)."""
    payload = {
        "model": model_name,
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
        duration = time.time() - t0
        return text, duration
    except Exception as e:
        return f"ERROR: {e}", time.time() - t0


def build_messages(sig_cls, inputs: dict) -> list[dict]:
    """Use DSPy ChatAdapter to build the exact messages the model sees."""
    return adapter.format(signature=sig_cls, demos=[], inputs=inputs)


# ══════════════════════════════════════════════════════════════════════
# Main comparison
# ══════════════════════════════════════════════════════════════════════

def _run_module(url: str, model_name: str, module: str, case: dict, form_context: str) -> tuple[str, float, dict]:
    """Run one module for one case. Returns (raw_output, duration, format_analysis)."""
    sig_cls = SIGNATURES[module]
    expected_fields = MODULE_OUTPUT_FIELDS[module]
    ctx = build_context(case, form_context)
    inputs = {"context": ctx, "user_message": case["user_message"]}
    messages = build_messages(sig_cls, inputs)
    out, dur = call_model(url, messages, model_name)
    fmt = analyze_format(out, expected_fields)
    return out, dur, fmt


# ══════════════════════════════════════════════════════════════════════
# Stage 1 — Inference: run model, dump raw outputs + gold per case.
#                      No scoring here. Scoring lives in Stage 2 so it can
#                      evolve without re-running inference.
# ══════════════════════════════════════════════════════════════════════

def run_inference(args):
    form_context = load_form_context()
    cases = [json.loads(l) for l in open(TEST_CASES_PATH) if l.strip()]
    test_items = [(case, pick_module(case)) for case in cases]
    if args.num:
        test_items = test_items[:args.num]

    n = len(test_items)
    print(f"[infer] label={args.label}  url={args.url}  model={args.model}")
    print(f"[infer] cases={n}  out={args.out}")
    print("=" * 80)

    out_fp = open(args.out, "w")
    # Header line — metadata about this inference run
    out_fp.write(json.dumps({
        "_meta": True,
        "label": args.label,
        "url": args.url,
        "model": args.model,
        "n_cases": n,
        "test_cases_path": str(TEST_CASES_PATH),
        "timestamp": time.time(),
    }) + "\n")
    out_fp.flush()

    t_start = time.time()
    for i, (case, content_module) in enumerate(test_items):
        # action_router runs on every case
        ar_out, ar_dur, ar_fmt = _run_module(args.url, args.model, "action_router", case, form_context)
        # content module — picked by pick_module()
        cm_out, cm_dur, cm_fmt = _run_module(args.url, args.model, content_module, case, form_context)

        rec = {
            # Case identity & inputs
            "test_id": case.get("test_id"),
            "category": case.get("category"),
            "user_message": case.get("user_message"),
            "content_module": content_module,
            # Gold labels — derived once at infer time so report doesn't need test-cases.jsonl
            "gold": {
                "route": infer_route(case),
                "set_fields": gold_set_fields(case) if content_module == "data_extractor" else None,
                "options": gold_ask_choice_options(case) if content_module == "choice_builder" else None,
                "expected_fields_set": case.get("expected_fields_set"),
                "expected_output": case.get("expected_output"),
            },
            # Raw model outputs — recompute scores from these in Stage 2
            "pred": {
                "action_router_output": ar_out,
                "action_router_duration": ar_dur,
                "content_output": cm_out,
                "content_duration": cm_dur,
            },
        }
        out_fp.write(json.dumps(rec, default=str) + "\n")
        out_fp.flush()

        if (i + 1) % 10 == 0:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            eta = (n - i - 1) / rate if rate > 0 else 0
            print(f"  ... {i + 1}/{n} done  ({elapsed:.0f}s elapsed, ~{eta:.0f}s remaining)")

    out_fp.close()
    print(f"\n[infer] wrote {n} cases to {args.out}")


# ══════════════════════════════════════════════════════════════════════
# Stage 2 — Report: read JSONL(s), recompute every metric, summarize.
#                   No model calls. Idempotent. Iterate freely.
# ══════════════════════════════════════════════════════════════════════

# Reconstitute a "case-like" dict from a stored gold record so existing
# scorers (which expect case dicts) keep working.
def _case_from_gold(rec: dict) -> dict:
    g = rec["gold"]
    return {
        # Don't rely on the stored `gold.route` — older JSONLs were written
        # with a buggy infer_route that didn't see button names. infer_route()
        # now re-derives from expected_output, which is canonical.
        "expected_output": g.get("expected_output", ""),
        "expected_fields_set": g.get("expected_fields_set", []) or [],
    }


def _score_record(rec: dict) -> dict:
    """Recompute all scores for one record from raw outputs. Returns a dict
    with: format_ok flags, per-flag route correctness, content metric dict.

    Note: gold_route is recomputed via infer_route() on every call so that
    fixes to the gold-derivation logic apply to existing JSONLs without
    requiring re-inference.
    """
    ar_out = rec["pred"]["action_router_output"]
    cm_out = rec["pred"]["content_output"]
    cm = rec["content_module"]
    case_like = _case_from_gold(rec)

    ar_fmt = analyze_format(ar_out, list(ROUTE_FLAGS))
    cm_fmt = analyze_format(cm_out, MODULE_OUTPUT_FIELDS[cm])

    gold_route = infer_route(case_like)
    pred_flags = {}
    flag_correct = {}
    for flag in ROUTE_FLAGS:
        raw = extract_field_value(ar_out, flag)
        pred_bool = raw is not None and raw.strip().lower() in ("true", "1", "yes")
        pred_flags[flag] = pred_bool
        flag_correct[flag] = (pred_bool == gold_route[flag])

    # data_extractor / choice_builder need the gold pulled from rec, not case_like
    if cm == "data_extractor":
        # Reconstruct a synthetic case with the right `expected_output` already in case_like
        # but our scorer pulls from expected_output via gold_set_fields(). Easier: monkey-patch.
        score = score_data_extractor(cm_out, case_like)
    elif cm == "choice_builder":
        score = score_choice_builder(cm_out, case_like)
    elif cm == "review_builder":
        score = score_review_builder(cm_out, case_like)
    elif cm == "text_responder":
        score = score_text_responder(cm_out, case_like)
    else:
        score = {}

    return {
        "ar_format_ok":  ar_fmt["format_ok"],
        "ar_has_completed": ar_fmt["has_completed"],
        "cm_format_ok":  cm_fmt["format_ok"],
        "cm_has_completed": cm_fmt["has_completed"],
        "ar_error":      ar_out.startswith("ERROR:"),
        "cm_error":      cm_out.startswith("ERROR:"),
        "ar_duration":   rec["pred"].get("action_router_duration", 0.0),
        "cm_duration":   rec["pred"].get("content_duration", 0.0),
        "pred_flags":    pred_flags,
        "flag_correct":  flag_correct,
        "gold_route":    gold_route,   # recomputed; consumers should prefer this
        "content_score": score,
    }


def _load_preds(path: str) -> tuple[dict, list[dict]]:
    """Read a preds JSONL. Returns (meta_header, list_of_records)."""
    meta = {}
    records = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("_meta"):
            meta = obj
        else:
            records.append(obj)
    return meta, records


def _aggregate(records: list[dict]) -> dict:
    """Compute aggregate metrics from a list of scored records."""
    n_cases = len(records)
    n_calls = n_cases * 2  # action_router + content per case

    overall = {"format_ok": 0, "has_completed": 0, "errors": 0, "total_time": 0.0}
    module_format_ok = Counter()
    module_total     = Counter()
    flag_correct = {f: 0 for f in ROUTE_FLAGS}
    # Per-flag confusion broken out by gold polarity:
    #   tp = gold True,  pred True ; fn = gold True,  pred False
    #   tn = gold False, pred False; fp = gold False, pred True
    # n_pos / n_neg make data-coverage gaps obvious (e.g. wants_submit has 0 positives in this dataset).
    flag_conf = {f: {"tp": 0, "fn": 0, "tn": 0, "fp": 0} for f in ROUTE_FLAGS}
    content_sum  = defaultdict(lambda: defaultdict(float))
    content_n    = Counter()

    for rec in records:
        s = rec["_score"]
        cm = rec["content_module"]
        gr = s["gold_route"]
        pf = s["pred_flags"]
        # Overall
        overall["format_ok"]     += int(s["ar_format_ok"]) + int(s["cm_format_ok"])
        overall["has_completed"] += int(s["ar_has_completed"]) + int(s["cm_has_completed"])
        overall["errors"]        += int(s["ar_error"]) + int(s["cm_error"])
        overall["total_time"]    += s["ar_duration"] + s["cm_duration"]
        # Per-module format
        module_format_ok["action_router"] += int(s["ar_format_ok"])
        module_format_ok[cm]              += int(s["cm_format_ok"])
        module_total["action_router"] += 1
        module_total[cm]              += 1
        # Per-flag routing
        for flag in ROUTE_FLAGS:
            if s["flag_correct"][flag]:
                flag_correct[flag] += 1
            g, p = bool(gr[flag]), bool(pf[flag])
            if   g and     p: flag_conf[flag]["tp"] += 1
            elif g and not p: flag_conf[flag]["fn"] += 1
            elif (not g) and (not p): flag_conf[flag]["tn"] += 1
            else:                     flag_conf[flag]["fp"] += 1
        # Content metrics
        content_n[cm] += 1
        for k, v in s["content_score"].items():
            if isinstance(v, bool):
                content_sum[cm][k] += int(v)
            elif isinstance(v, (int, float)):
                content_sum[cm][k] += float(v)

    return {
        "n_cases": n_cases,
        "n_calls": n_calls,
        "overall": overall,
        "module_format_ok": dict(module_format_ok),
        "module_total":     dict(module_total),
        "flag_correct":     flag_correct,
        "flag_conf":        flag_conf,
        "content_sum":      {k: dict(v) for k, v in content_sum.items()},
        "content_n":        dict(content_n),
    }


def _print_aggregate(agg: dict, label: str):
    n = agg["n_cases"]; n_calls = agg["n_calls"]
    o = agg["overall"]
    print(f"\n[{label}]  cases={n}  module-calls={n_calls}")
    print(f"  format_ok={o['format_ok']}/{n_calls} ({o['format_ok']/n_calls*100:.1f}%)  "
          f"completed={o['has_completed']}/{n_calls} ({o['has_completed']/n_calls*100:.1f}%)  "
          f"errors={o['errors']}  avg_latency={o['total_time']/max(n_calls,1):.2f}s")


def _print_side_by_side(aggs: dict[str, dict]):
    """Print side-by-side comparison across labels."""
    labels = list(aggs)
    nlbl = len(labels)
    col_w = 14
    head = "".join(f"{l:>{col_w}s}" for l in labels)

    # Per-module format
    print(f"\nFormat compliance by module:")
    print(f"  {'module':18s}{head}")
    for mod in ["action_router", "data_extractor", "choice_builder", "review_builder", "text_responder"]:
        row = f"  {mod:18s}"
        printed = False
        for lbl in labels:
            tot = aggs[lbl]["module_total"].get(mod, 0)
            ok  = aggs[lbl]["module_format_ok"].get(mod, 0)
            if tot:
                row += f"{ok:>4d}/{tot:<3d}({ok/tot*100:4.1f}%)"
                printed = True
            else:
                row += f"{'—':>{col_w}s}"
        if printed:
            print(row)

    # Action-router per-flag accuracy + pos/neg breakdown.
    # Showing pos-recall (TP/n_pos) and neg-recall (TN/n_neg) separately makes
    # zero-positive flags (like wants_submit in the current dataset) obvious —
    # otherwise overall accuracy = neg_recall and falsely looks like 100%.
    ar_totals = {l: aggs[l]["module_total"].get("action_router", 0) for l in labels}
    if any(ar_totals.values()):
        print(f"\nAction-router per-flag accuracy:")
        print(f"  {'flag':18s}{head}")
        for flag in ROUTE_FLAGS:
            row = f"  {flag:18s}"
            for lbl in labels:
                tot = ar_totals[lbl]
                ok  = aggs[lbl]["flag_correct"][flag]
                row += f"{ok:>4d}/{tot:<3d}({ok/tot*100:4.1f}%)" if tot else f"{'—':>{col_w}s}"
            print(row)

        # Same flags, broken down by gold polarity
        print(f"\nAction-router per-flag — pos / neg recall  (n_pos = gold-True cases, n_neg = gold-False):")
        print(f"  {'flag':18s}" + "".join(f"{l:>{2*col_w}s}" for l in labels))
        for flag in ROUTE_FLAGS:
            row = f"  {flag:18s}"
            for lbl in labels:
                c = aggs[lbl]["flag_conf"][flag]
                n_pos = c["tp"] + c["fn"]
                n_neg = c["tn"] + c["fp"]
                pos_str = f"{c['tp']}/{n_pos}({c['tp']/n_pos*100:.0f}%)" if n_pos else "—/0"
                neg_str = f"{c['tn']}/{n_neg}({c['tn']/n_neg*100:.0f}%)" if n_neg else "—/0"
                cell = f"pos:{pos_str}  neg:{neg_str}"
                row += f"{cell:>{2*col_w}s}"
            print(row)

    # Content accuracy per module
    metric_specs = {
        "data_extractor": [
            ("precision",       "ID precision"),
            ("recall",          "ID recall"),
            ("f1",              "ID F1"),
            ("id_exact_match",  "ID exact-set"),
        ],
        "choice_builder": [
            ("precision",        "option precision"),
            ("recall",           "option recall"),
            ("f1",               "option F1"),
            ("exact_set_match",  "option exact-set"),
            ("has_question",     "question present"),
        ],
        "review_builder": [
            ("coverage",     "field-mention coverage"),
            ("has_title",    "title present"),
            ("has_content",  "content present"),
        ],
        "text_responder": [
            ("nonempty",           "non-empty"),
            ("reasonable_length",  "5-2000 chars"),
            ("no_format_leak",     "no format leak"),
            ("ok",                 "overall ok"),
        ],
    }
    print(f"\nContent accuracy by module:")
    for mod, specs in metric_specs.items():
        ks = {l: aggs[l]["content_n"].get(mod, 0) for l in labels}
        if not any(ks.values()):
            continue
        n_str = "/".join(f"{l}={ks[l]}" for l in labels)
        print(f"\n  {mod} (n: {n_str}):")
        print(f"    {'metric':26s}{head}")
        for key, name in specs:
            row = f"    {name:26s}"
            for lbl in labels:
                k = ks[lbl]
                v = aggs[lbl]["content_sum"].get(mod, {}).get(key, 0.0) / k if k else None
                row += f"{v:>{col_w}.3f}" if v is not None else f"{'—':>{col_w}s}"
            print(row)
        # Special: data_extractor value-match (ratio of two summed counters)
        if mod == "data_extractor":
            row = f"    {'value match (of TP ids)':26s}"
            for lbl in labels:
                vc = aggs[lbl]["content_sum"].get(mod, {}).get("value_correct", 0.0)
                vt = aggs[lbl]["content_sum"].get(mod, {}).get("value_total", 0.0)
                v = vc / vt if vt else None
                row += f"{v:>{col_w}.3f}" if v is not None else f"{'—':>{col_w}s}"
            print(row)


# ── Failure-example extraction ────────────────────────────────────────

FAILURE_BUCKETS = [
    "data_extractor_format",
    "data_extractor_id_miss",
    "data_extractor_value_mismatch",
    "review_builder_format",
    "review_builder_low_coverage",
    "choice_builder_option_mismatch",
    "text_responder_format",
    "text_responder_format_leak",
    "action_router_format",
    "action_router_has_new_data",
    "action_router_needs_choice",
    "action_router_wants_review",
    "action_router_wants_save",
    "action_router_wants_submit",
]


def _classify_failures(rec: dict) -> list[str]:
    """Return all failure-bucket labels this record falls into."""
    labels = []
    s = rec["_score"]
    cm = rec["content_module"]
    sc = s["content_score"]

    if not s["ar_format_ok"]:
        labels.append("action_router_format")
    for flag in ROUTE_FLAGS:
        if not s["flag_correct"][flag]:
            labels.append(f"action_router_{flag}")

    if cm == "data_extractor":
        if not s["cm_format_ok"]:
            labels.append("data_extractor_format")
        if s["cm_format_ok"] and sc.get("f1", 1.0) < 1.0:
            labels.append("data_extractor_id_miss")
        if sc.get("value_total", 0) > sc.get("value_correct", 0):
            labels.append("data_extractor_value_mismatch")
    elif cm == "choice_builder":
        if sc.get("exact_set_match", 1) == 0:
            labels.append("choice_builder_option_mismatch")
    elif cm == "review_builder":
        if not s["cm_format_ok"]:
            labels.append("review_builder_format")
        if sc.get("coverage", 1.0) < 0.5:
            labels.append("review_builder_low_coverage")
    elif cm == "text_responder":
        if not s["cm_format_ok"]:
            labels.append("text_responder_format")
        if not sc.get("no_format_leak", True):
            labels.append("text_responder_format_leak")

    return labels


def _print_failure_examples(records: list[dict], label: str):
    print(f"\n" + "=" * 80)
    print(f"FAILURE EXAMPLES  (label={label})  — one per bucket")
    print("=" * 80)

    first = {b: None for b in FAILURE_BUCKETS}
    for rec in records:
        for bkt in _classify_failures(rec):
            if first.get(bkt) is None:
                first[bkt] = rec

    for bkt in FAILURE_BUCKETS:
        rec = first[bkt]
        if rec is None:
            continue   # no failure of this kind
        s = rec["_score"]; sc = s["content_score"]
        gold_route = s["gold_route"]   # recomputed; may differ from stored rec["gold"]["route"]
        print(f"\n── {bkt} ──")
        print(f"  test_id     : {rec['test_id']}  ({rec.get('category','?')})")
        msg = rec["user_message"] or ""
        print(f"  user_message: {msg[:280]}{'…' if len(msg) > 280 else ''}")
        true_flags = [f for f, v in gold_route.items() if v]
        print(f"  gold_route  : {true_flags or '[none]'}")

        if bkt.startswith("action_router_") and bkt != "action_router_format":
            flag = bkt[len("action_router_"):]
            print(f"  flag        : gold={gold_route[flag]}  pred={s['pred_flags'][flag]}")
            print(f"  ar_output   : {rec['pred']['action_router_output'][:400].replace(chr(10), ' / ')}")
        elif bkt == "action_router_format":
            print(f"  ar_output   : {rec['pred']['action_router_output'][:400].replace(chr(10), ' / ')}")
        elif bkt == "data_extractor_id_miss":
            gold_ids = [p[0] for p in (rec['gold']['set_fields'] or [])]
            print(f"  gold ids    : {gold_ids}")
            print(f"  precision={sc['precision']:.3f}  recall={sc['recall']:.3f}  f1={sc['f1']:.3f}")
            print(f"  cm_output   : {rec['pred']['content_output'][:400].replace(chr(10), ' / ')}")
        elif bkt == "data_extractor_value_mismatch":
            print(f"  gold pairs  : {rec['gold']['set_fields']}")
            print(f"  value_match : {sc['value_correct']}/{sc['value_total']}")
            print(f"  cm_output   : {rec['pred']['content_output'][:400].replace(chr(10), ' / ')}")
        elif bkt == "data_extractor_format":
            print(f"  expected    : {rec['gold']['expected_fields_set']}")
            print(f"  cm_output   : {rec['pred']['content_output'][:400].replace(chr(10), ' / ')}")
        elif bkt == "choice_builder_option_mismatch":
            print(f"  gold options: {rec['gold']['options']}")
            print(f"  f1={sc['f1']:.3f}  exact_set={sc['exact_set_match']}")
            print(f"  cm_output   : {rec['pred']['content_output'][:400].replace(chr(10), ' / ')}")
        elif bkt.startswith("review_builder"):
            print(f"  expected    : {rec['gold']['expected_fields_set']}  coverage={sc.get('coverage')}")
            print(f"  cm_output   : {rec['pred']['content_output'][:400].replace(chr(10), ' / ')}")
        elif bkt.startswith("text_responder"):
            print(f"  cm_output   : {rec['pred']['content_output'][:400].replace(chr(10), ' / ')}")


def run_report(args):
    aggs = {}
    all_records = {}
    for path in args.in_paths:
        meta, records = _load_preds(path)
        label = meta.get("label") or Path(path).stem
        for rec in records:
            rec["_score"] = _score_record(rec)
        aggs[label] = _aggregate(records)
        all_records[label] = records
        _print_aggregate(aggs[label], label)

    print("\n" + "=" * 80)
    print("SIDE-BY-SIDE")
    print("=" * 80)
    _print_side_by_side(aggs)

    if args.failures:
        for label, records in all_records.items():
            _print_failure_examples(records, label)


# ══════════════════════════════════════════════════════════════════════
# Argparse
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Compare Qwen3.5-0.8B variants on DSPy structured output. "
                    "Two stages: `infer` writes raw predictions to JSONL; "
                    "`report` reads JSONL(s) and emits aggregate stats + failure examples."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_infer = sub.add_parser("infer", help="Run a model and dump raw predictions to JSONL")
    p_infer.add_argument("--label", required=True, help="Short label for this run, e.g. 'v2', 'base'")
    p_infer.add_argument("--url", required=True, help="OpenAI-compatible chat completions URL")
    p_infer.add_argument("--model", required=True, help="Model name to send in the 'model' field")
    p_infer.add_argument("--out", required=True, help="Output JSONL path")
    p_infer.add_argument("--num", type=int, default=None,
                         help="Number of test cases (default: all)")

    p_report = sub.add_parser("report", help="Read predictions JSONL(s) and print summary + failures")
    p_report.add_argument("--in", nargs="+", required=True, dest="in_paths",
                          help="One or more preds JSONL paths to score and compare")
    p_report.add_argument("--failures", action="store_true",
                          help="Also print one failure example per bucket per label")

    args = parser.parse_args()

    if args.cmd == "infer":
        run_inference(args)
    elif args.cmd == "report":
        run_report(args)


if __name__ == "__main__":
    main()
