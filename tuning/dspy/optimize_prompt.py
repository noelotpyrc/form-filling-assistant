#!/usr/bin/env python3
"""
DSPy GEPA prompt optimization for form-filling assistant.

Decomposes the form-filling task into 5 modules matching how a human
customer service rep thinks:

  1. IntentDecider  — What phase are we in? (gather/converse/clarify/close/review)
  2. TextResponder  — What do I say to the user?
  3. DataExtractor  — Did the user provide form data? Extract it.
  4. ChoiceBuilder  — Do we need to present options?
  5. ReviewBuilder  — Should we show a summary?

GEPA optimizes each module's instructions independently using GPT-5
as the reflection LM, while the student model (Qwen via MLX) runs
the actual predictions.

⚠️  IMPORTANT — for new entry points that run the SFT model, do NOT copy
the LM-config or `load_form_context` from this file. They are known to
diverge from the production harness (missing max_tokens=512 / cache=False,
[:5] options truncation). The canonical setup lives in
`tuning/harness/pipeline.py::configure_lm` and `build_context`. New scripts
must call those plus `tuning/harness/preflight.py::assert_anchor_match`
before any costly run. See CLAUDE.md > Experiment hygiene.

The current canonical GEPA driver is `tuning/gepa/optimize.py`, not this
file. The `main()` here is preserved for historical reference only and
will print a deprecation banner if invoked.

Usage (canonical):
    python/.venv/bin/python tuning/gepa/optimize.py --budget light
"""

import json
import os
import re
import sys
import argparse
from typing import List, Literal
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import dspy
import mlflow
import mlflow.dspy

FORM_SCHEMA_PATH = PROJECT_ROOT / "packages/web-app/public/forms/masters-northfield.json"


# ══════════════════════════════════════════════════════════════════════
# Signatures — one per module, typed outputs DSPy can parse
# ══════════════════════════════════════════════════════════════════════

class ActionRouterSignature(dspy.Signature):
    """Decide which assistant actions this turn should produce.

    Each flag is INDEPENDENT — a turn may set zero, one, or several. This
    replaces a single categorical `intent` with per-action booleans so
    multi-action turns are represented losslessly.

    - has_new_data: user's message contains new form field values to extract
      (triggers data_extractor → set_fields action)
    - needs_choice: assistant should present multiple-choice buttons to guide
      the user (triggers choice_builder → ask_choice action)
    - wants_review: assistant should show a progress summary card
      (triggers review_builder → show_preview action)
    - wants_save: assistant should offer a Save Draft button
      (emits show_button with button=save_draft)
    - wants_submit: assistant should offer a Submit Application button
      (emits show_button with button=submit)
    """

    context: str = dspy.InputField(desc="Form fields and current state")
    user_message: str = dspy.InputField(desc="Current user message")
    has_new_data: bool = dspy.OutputField(desc="True if user provided new field values to extract")
    needs_choice: bool = dspy.OutputField(desc="True if a multiple-choice question should be presented")
    wants_review: bool = dspy.OutputField(desc="True if a progress-summary card should be shown")
    wants_save: bool = dspy.OutputField(desc="True if a Save Draft button should be offered")
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
    field_ids: list = dspy.OutputField(desc="List of field_ids to set, e.g. ['full_name', 'email']")
    field_values: list = dspy.OutputField(desc="Corresponding values (strings, numbers, or booleans depending on the field type)")


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


# ══════════════════════════════════════════════════════════════════════
# Module — routes through sub-modules based on intent
# ══════════════════════════════════════════════════════════════════════

class FormAssistant(dspy.Module):
    def __init__(self):
        self.action_router = dspy.Predict(ActionRouterSignature)
        self.text_responder = dspy.Predict(TextResponderSignature)
        self.data_extractor = dspy.Predict(DataExtractorSignature)
        self.choice_builder = dspy.Predict(ChoiceBuilderSignature)
        self.review_builder = dspy.Predict(ReviewBuilderSignature)

    def forward(self, context, user_message):
        # No try/except — let AdapterParseError propagate so DSPy's
        # bootstrap_trace_data can catch it, record FailedPrediction in the
        # trace, and feed it to GEPA's reflection system.

        # Step 1: Route actions — 5 independent booleans
        route = self.action_router(context=context, user_message=user_message)
        has_new_data = bool(route.has_new_data)
        needs_choice = bool(route.needs_choice)
        wants_review = bool(route.wants_review)
        wants_save = bool(route.wants_save)
        wants_submit = bool(route.wants_submit)

        # Step 2: Generate text response (independent of route flags)
        text_result = self.text_responder(context=context, user_message=user_message)

        # Step 3: Conditionally run sub-modules based on route flags
        field_ids: list[str] = []
        field_values: list[str] = []
        question = ""
        options: list[str] = []
        summary_title = ""
        summary_content = ""

        if has_new_data:
            extract = self.data_extractor(context=context, user_message=user_message)
            field_ids = extract.field_ids
            field_values = extract.field_values

        if needs_choice:
            choice = self.choice_builder(context=context, user_message=user_message)
            question = choice.question
            options = choice.options

        if wants_review:
            review = self.review_builder(context=context, user_message=user_message)
            summary_title = review.summary_title
            summary_content = review.summary_content

        return dspy.Prediction(
            response_text=text_result.response_text,
            # Route flags (new)
            has_new_data=has_new_data,
            needs_choice=needs_choice,
            wants_review=wants_review,
            wants_save=wants_save,
            wants_submit=wants_submit,
            # Sub-module outputs
            field_ids=field_ids,
            field_values=field_values,
            question=question,
            options=options,
            summary_title=summary_title,
            summary_content=summary_content,
        )


# ══════════════════════════════════════════════════════════════════════
# Metric + per-module feedback
# ══════════════════════════════════════════════════════════════════════

ROUTE_FLAGS = ("has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit")


def feedback_route(gold_route: dict, pred_route: dict):
    """Score and feedback for ActionRouter.

    Score = fraction of flags predicted correctly (0.0 to 1.0).
    Feedback lists per-flag errors so GEPA reflection can target specifics.
    """
    correct = 0
    errors = []
    for flag in ROUTE_FLAGS:
        g = bool(gold_route.get(flag, False))
        p = bool(pred_route.get(flag, False))
        if g == p:
            correct += 1
        else:
            errors.append(f"{flag}: predicted {p}, expected {g}")
    score = correct / len(ROUTE_FLAGS)
    if not errors:
        return f"Correct route: all {len(ROUTE_FLAGS)} flags match.", 1.0
    return "Route errors — " + "; ".join(errors), score


def feedback_text(pred_text):
    """Score and feedback for TextResponder."""
    text = pred_text.strip() if pred_text else ""
    if len(text) > 20:
        return "Good: produced meaningful conversational text.", 1.0
    elif len(text) > 0:
        return f"Too short ({len(text)} chars). Need a helpful conversational response.", 0.3
    else:
        return "Empty response. Must always produce conversational text.", 0.0


def feedback_fields(gold_field_ids, pred_field_ids, pred_field_values):
    """Score and feedback for DataExtractor."""
    gold_set = set(gold_field_ids) if gold_field_ids else set()
    pred_set = set(pred_field_ids) if pred_field_ids else set()

    if not gold_set and not pred_set:
        return "Correct: no fields to extract.", 1.0
    if not gold_set and pred_set:
        return (
            f"WRONG: Extracted {len(pred_set)} fields when none were provided in the user message. "
            f"Do NOT extract fields from the conversation history or form context — only from the CURRENT user message. "
            f"Hallucinated fields: {sorted(pred_set)}"
        ), 0.0

    intersection = gold_set & pred_set
    recall = len(intersection) / len(gold_set) if gold_set else 0
    precision = len(intersection) / len(pred_set) if pred_set else 0
    f1 = 2 * recall * precision / (recall + precision) if (recall + precision) > 0 else 0

    parts = []
    missing = gold_set - pred_set
    extra = pred_set - gold_set
    if missing:
        parts.append(f"Missing fields: {sorted(missing)}")
    if extra:
        over_ratio = len(extra) / max(len(gold_set), 1)
        if over_ratio > 2:
            parts.append(
                f"OVER-EXTRACTION: Extracted {len(pred_set)} fields but user only provided {len(gold_set)}. "
                f"Only extract data explicitly stated in the CURRENT user message, not from context or history. "
                f"Extra fields: {sorted(extra)}"
            )
        else:
            parts.append(f"Extra fields (not in user message): {sorted(extra)}")
    if not parts:
        parts.append(f"All {len(gold_set)} fields correctly extracted.")

    # Check field_ids/values alignment
    if pred_field_ids and pred_field_values and len(pred_field_ids) != len(pred_field_values):
        parts.append(f"field_ids and field_values length mismatch ({len(pred_field_ids)} vs {len(pred_field_values)})")

    return " | ".join(parts), f1


def feedback_choice(gold_has_choice, pred_has_choice, pred_question, pred_options):
    """Score and feedback for ChoiceBuilder."""
    if not gold_has_choice and not pred_has_choice:
        return "Correct: no choice needed.", 1.0
    if not gold_has_choice and pred_has_choice:
        return "Incorrectly produced a choice when none was expected.", 0.0
    if gold_has_choice and not pred_has_choice:
        return "Missing choice — should have presented options to the user.", 0.0

    # Both have choice — check quality
    score = 0.5  # base for having a choice at all
    parts = []
    if pred_question and len(pred_question) > 5:
        score += 0.25
    else:
        parts.append("Question is missing or too short.")
    if pred_options and len(pred_options) >= 2:
        score += 0.25
    else:
        parts.append(f"Need at least 2 options, got {len(pred_options) if pred_options else 0}.")

    if not parts:
        parts.append(f"Good choice with {len(pred_options)} options.")
    return " | ".join(parts), score


def feedback_review(gold_has_review, pred_summary_title, pred_summary_content):
    """Score and feedback for ReviewBuilder."""
    has_review = bool(pred_summary_title and pred_summary_content)
    if not gold_has_review and not has_review:
        return "Correct: no review needed.", 1.0
    if not gold_has_review and has_review:
        return "Produced a review summary when none was expected.", 0.3  # mild penalty
    if gold_has_review and not has_review:
        return "Missing review — should have shown a summary.", 0.0

    score = 0.5
    parts = []
    if len(pred_summary_title) > 3:
        score += 0.25
    else:
        parts.append("Summary title too short.")
    if len(pred_summary_content) > 20:
        score += 0.25
    else:
        parts.append("Summary content too short.")

    if not parts:
        parts.append("Good review summary.")
    return " | ".join(parts), score


def form_filling_metric(example, prediction, trace=None, pred_name=None, pred_trace=None):
    """
    Combined metric with per-module feedback for GEPA.

    When pred_name is None: returns a float (module-level score).
    When pred_name is set: returns dspy.Prediction(score=..., feedback=...)
    for the specific predictor GEPA is optimizing.
    """
    # Gold route flags
    gold_route = {flag: example.get(f"gold_{flag}", False) for flag in ROUTE_FLAGS}
    gold_field_ids = example.get("expected_fields_set", [])

    # Predicted route flags
    pred_route = {flag: getattr(prediction, flag, False) for flag in ROUTE_FLAGS}
    pred_text = getattr(prediction, "response_text", "")
    pred_field_ids = getattr(prediction, "field_ids", [])
    pred_field_values = getattr(prediction, "field_values", [])
    pred_question = getattr(prediction, "question", "")
    pred_options = getattr(prediction, "options", [])
    pred_summary_title = getattr(prediction, "summary_title", "")
    pred_summary_content = getattr(prediction, "summary_content", "")

    # Score each module.
    # Note: parse failures are handled by DSPy's FailedPrediction mechanism.
    # GEPA catches AdapterParseError, records it in the trace, and feeds format
    # failure feedback to the reflection LM when add_format_failure_as_feedback=True.
    fb_route, score_route = feedback_route(gold_route, pred_route)
    fb_text, score_text = feedback_text(pred_text)
    fb_fields, score_fields = feedback_fields(gold_field_ids, pred_field_ids, pred_field_values)
    fb_choice, score_choice = feedback_choice(
        gold_route["needs_choice"],
        pred_route["needs_choice"],
        pred_question,
        pred_options,
    )
    fb_review, score_review = feedback_review(
        gold_route["wants_review"],
        pred_summary_title,
        pred_summary_content,
    )

    # Weighted total — router and fields matter most
    total = (
        0.30 * score_route
        + 0.15 * score_text
        + 0.25 * score_fields
        + 0.15 * score_choice
        + 0.15 * score_review
    )

    # Per-predictor feedback for GEPA reflection
    if pred_name is not None:
        feedback_map = {
            "action_router": fb_route,
            "text_responder": fb_text,
            "data_extractor": fb_fields,
            "choice_builder": fb_choice,
            "review_builder": fb_review,
        }
        # Match pred_name (DSPy uses "module_name.predict" format)
        feedback = None
        for key, fb in feedback_map.items():
            if key in pred_name:
                feedback = fb
                break
        if feedback is None:
            feedback = f"Route: {fb_route} | Text: {fb_text} | Fields: {fb_fields}"

        return dspy.Prediction(score=total, feedback=feedback)

    return total


# ══════════════════════════════════════════════════════════════════════
# Data Loading
# ══════════════════════════════════════════════════════════════════════

def infer_route(turn: dict) -> dict:
    """Infer route flags (5 booleans) from a turn's action types + parsed_actions.

    Each flag is set independently based on what actions the turn actually
    contains — no priority cascade, no single-label squashing.
    """
    acts = set(turn.get("expected_action_types", turn.get("action_types", [])))
    parsed = turn.get("parsed_actions", [])
    buttons = {
        a.get("button") for a in parsed if a.get("type") == "show_button"
    }
    return {
        "has_new_data": "set_fields" in acts,
        "needs_choice": "ask_choice" in acts,
        "wants_review": "show_preview" in acts or "show_fields" in acts,
        "wants_save": "save_draft" in buttons,
        "wants_submit": "submit" in buttons,
    }


def load_form_context() -> str:
    """⚠️  DEPRECATED: do not use for new code.

    This builds the form-context string with a known bug: select fields are
    truncated to the first 5 options (so `Mechanical Engineering (MS)` is
    invisible to the model). Production uses
    `tuning/harness/pipeline.py::build_context` which shows all options.
    Keeping this around only because some legacy SFT-training data was
    generated under this format and needs reproducible re-runs.
    """
    import warnings
    warnings.warn(
        "load_form_context() is deprecated; use tuning.harness.pipeline.build_context",
        DeprecationWarning, stacklevel=2,
    )
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


def load_test_cases(path: str) -> list:
    """Load test cases and convert to DSPy examples with intent labels."""
    cases = [json.loads(l) for l in open(path) if l.strip()]
    form_context = load_form_context()

    examples = []
    for case in cases:
        # Build context with state + recent history
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

        # Infer gold labels — 5 independent route flags
        gold_route = infer_route(case)

        ex = dspy.Example(
            context=ctx,
            user_message=case["user_message"],
            # Gold labels for scoring — one per route flag, prefixed "gold_"
            gold_has_new_data=gold_route["has_new_data"],
            gold_needs_choice=gold_route["needs_choice"],
            gold_wants_review=gold_route["wants_review"],
            gold_wants_save=gold_route["wants_save"],
            gold_wants_submit=gold_route["wants_submit"],
            expected_fields_set=case.get("expected_fields_set", case.get("fields_set", [])),
            category=case.get("category", "other"),
        ).with_inputs("context", "user_message")

        examples.append(ex)

    return examples


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════

def main():
    print(
        "\n⚠️  DEPRECATED: tuning/dspy/optimize_prompt.py main() is the legacy GEPA "
        "driver and has known config bugs (no max_tokens=512, no cache=False, [:5] "
        "options truncation, wrong default --student-model).\n\n"
        "    Use the canonical driver instead:\n"
        "        python/.venv/bin/python tuning/gepa/optimize.py --judge --budget light\n\n"
        "    See CLAUDE.md > Experiment hygiene.\n",
        file=sys.stderr,
    )
    parser = argparse.ArgumentParser(description="[DEPRECATED] DSPy GEPA prompt optimization")
    parser.add_argument("--student-port", type=int, default=8082, help="MLX server port")
    parser.add_argument("--student-model", default="mlx-community/Qwen3.5-0.8B-4bit", help="Student model")
    parser.add_argument("--reflection-model", default="gpt-5", help="OpenAI reflection model")
    parser.add_argument("--test-cases", default=str(PROJECT_ROOT / "tuning/data/test-cases.jsonl"))
    parser.add_argument("--budget", default="light", choices=["light", "medium", "heavy"])
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "tuning/dspy/results"))
    parser.add_argument("--max-tokens", type=int, default=None, help="Max tokens for student (None = model default)")
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--i-know-this-is-deprecated", action="store_true",
                        help="Required: confirms you've read the deprecation note above")
    args = parser.parse_args()
    if not args.i_know_this_is_deprecated:
        sys.exit("Refusing to run deprecated driver without --i-know-this-is-deprecated.")

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set. Set in .env or environment.")
        sys.exit(1)

    # Configure LMs
    student_lm = dspy.LM(
        f"openai/{args.student_model}",
        api_base=f"http://localhost:{args.student_port}/v1",
        api_key="",
        model_type="chat",
        temperature=0.0,
    )

    reflection_lm = dspy.LM(
        f"openai/{args.reflection_model}",
        temperature=1.0,
        max_tokens=32000,
    )

    dspy.configure(lm=student_lm)

    # Load data
    print(f"Loading test cases from {args.test_cases}...")
    examples = load_test_cases(args.test_cases)
    print(f"  Loaded {len(examples)} examples")

    # Show route-flag distribution
    from collections import Counter
    flag_counts = {flag: sum(1 for ex in examples if ex.get(f"gold_{flag}")) for flag in ROUTE_FLAGS}
    print(f"  Route flag True counts: {flag_counts}")

    # Split
    split = int(len(examples) * args.train_ratio)
    train_set = examples[:split]
    val_set = examples[split:]
    print(f"  Train: {len(train_set)}, Val: {len(val_set)}")

    # Baseline eval
    print("\n── Baseline evaluation ──")
    program = FormAssistant()
    baseline_scores = []
    for i, ex in enumerate(val_set[:10]):
        try:
            pred = program(context=ex.context, user_message=ex.user_message)
            score = form_filling_metric(ex, pred)
            baseline_scores.append(score)
            pred_flags = {f: getattr(pred, f, False) for f in ROUTE_FLAGS}
            true_flags = [f for f, v in pred_flags.items() if v]
            print(f"  [{i}] flags={true_flags} score={score:.2f} | user: {ex.user_message[:60]}")
        except Exception as e:
            baseline_scores.append(0.0)
            err_name = type(e).__name__
            print(f"  [{i}] FAIL({err_name}) | user: {ex.user_message[:60]}")
            # Show last LM raw output for debugging
            if student_lm.history:
                last_out = student_lm.history[-1].get("outputs", [{}])
                if last_out:
                    raw = str(last_out[0])[:150]
                    print(f"       raw: {raw}")
    baseline_avg = sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0
    print(f"  Baseline avg: {baseline_avg:.3f}")

    # MLflow tracking
    mlflow_db = PROJECT_ROOT / "tuning" / "mlflow.db"
    mlflow.set_tracking_uri(f"sqlite:///{mlflow_db}")
    mlflow.set_experiment("gepa-form-assistant")
    mlflow.dspy.autolog(
        log_compiles=True,
        log_evals=True,
        log_traces=False,  # disabled — causes NonRecordingSpan errors with GEPA
    )

    # Run GEPA
    print(f"\n── GEPA optimization (budget={args.budget}) ──")
    print(f"  Student: {args.student_model} @ localhost:{args.student_port}")
    print(f"  Reflection: {args.reflection_model}")
    print(f"  MLflow UI: cd tuning && mlflow ui")

    optimizer = dspy.GEPA(
        metric=form_filling_metric,
        reflection_lm=reflection_lm,
        auto=args.budget,
        track_stats=True,
        add_format_failure_as_feedback=True,
        failure_score=0.0,
        reflection_minibatch_size=10,  # default 3 is too small for 5 conditional modules
    )

    # ── Debug: monkey-patch make_reflective_dataset for trace visibility ──
    from dspy.teleprompt.bootstrap_trace import FailedPrediction as _FP
    from dspy.teleprompt.gepa.gepa_utils import DspyAdapter
    import types

    _orig_make_rd = DspyAdapter.make_reflective_dataset

    def _debug_make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        program = self.build_program(candidate)
        trajs = eval_batch.trajectories or []
        print(f"\n  [DEBUG reflect] components={components_to_update}, trajectories={len(trajs)}")
        for i, data in enumerate(trajs):
            trace = data["trace"]
            prediction = data["prediction"]
            is_failed = isinstance(prediction, _FP)
            sigs_in_trace = []
            for t in trace:
                pred_obj, inputs, output = t
                sig_name = type(pred_obj.signature).__name__ if hasattr(pred_obj, 'signature') else '?'
                is_fp = isinstance(output, _FP)
                sigs_in_trace.append(f"{sig_name}({'FAIL' if is_fp else 'ok'})")
            print(f"    traj[{i}]: pred_failed={is_failed}, trace=[{', '.join(sigs_in_trace)}]")

        # Check signature matching for each component
        for pred_name in components_to_update:
            module = None
            for name, m in program.named_predictors():
                if name == pred_name:
                    module = m
                    break
            if module is None:
                print(f"    [DEBUG] predictor '{pred_name}' not found in program!")
                continue
            mod_sig = module.signature
            for i, data in enumerate(trajs):
                trace = data["trace"]
                matches = [t for t in trace if t[0].signature.equals(mod_sig)]
                if not matches:
                    mod_instr = mod_sig.instructions[:60] if mod_sig.instructions else 'None'
                    mod_fields = sorted(mod_sig.fields.keys())
                    for ti, t in enumerate(trace):
                        t_sig = t[0].signature
                        t_instr = t_sig.instructions[:60] if t_sig.instructions else 'None'
                        t_fields = sorted(t_sig.fields.keys())
                        instr_match = t_sig.instructions == mod_sig.instructions
                        fields_match = mod_fields == t_fields
                        print(f"    [DEBUG] traj[{i}] trace[{ti}]: instr_match={instr_match} fields_match={fields_match}")
                        if not instr_match:
                            print(f"      module: {mod_instr}")
                            print(f"      trace:  {t_instr}")
                        if not fields_match:
                            print(f"      module fields: {mod_fields}")
                            print(f"      trace fields:  {t_fields}")

        return _orig_make_rd(self, candidate, eval_batch, components_to_update)

    DspyAdapter.make_reflective_dataset = _debug_make_reflective_dataset

    optimized_program = optimizer.compile(
        program,
        trainset=train_set,
        valset=val_set,
    )

    # Post-optimization eval
    print("\n── Post-optimization evaluation ──")
    opt_scores = []
    for i, ex in enumerate(val_set[:10]):
        try:
            pred = optimized_program(context=ex.context, user_message=ex.user_message)
            score = form_filling_metric(ex, pred)
            opt_scores.append(score)
            print(f"  [{i}] intent={pred.intent} score={score:.2f}")
        except Exception as e:
            opt_scores.append(0.0)
            print(f"  [{i}] ERROR: {type(e).__name__}: {str(e)[:80]}")
    opt_avg = sum(opt_scores) / len(opt_scores) if opt_scores else 0
    print(f"  Optimized avg: {opt_avg:.3f}")
    print(f"  Improvement: {opt_avg - baseline_avg:+.3f}")

    # Save
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    model_label = args.student_model.split("/")[-1]

    program_path = os.path.join(args.output_dir, f"gepa-{model_label}-{timestamp}.json")
    optimized_program.save(program_path)
    print(f"\n  Saved program: {program_path}")

    summary = {
        "timestamp": timestamp,
        "student_model": args.student_model,
        "reflection_model": args.reflection_model,
        "budget": args.budget,
        "train_size": len(train_set),
        "val_size": len(val_set),
        "baseline_avg": baseline_avg,
        "optimized_avg": opt_avg,
        "improvement": opt_avg - baseline_avg,
    }
    summary_path = os.path.join(args.output_dir, f"gepa-{model_label}-{timestamp}-summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Saved summary: {summary_path}")

    # Print optimized instructions
    print("\n── Optimized instructions ──")
    for name, param in optimized_program.named_parameters():
        if hasattr(param, "instructions") and param.instructions:
            print(f"\n  [{name}]:")
            print(f"  {param.instructions[:500]}")


if __name__ == "__main__":
    main()
