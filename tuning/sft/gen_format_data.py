#!/usr/bin/env python3
"""
Generate SFT training data for DSPy structured output format compliance.

Uses DSPy's own ChatAdapter to generate the exact system/user/assistant messages,
guaranteeing the training data matches what the model will see at inference time.

Converts atomic.jsonl (Claude's raw outputs) into per-module training examples
that teach the model to produce DSPy's ChatAdapter format:

    [[ ## field_name ## ]]
    value

    [[ ## completed ## ]]

Each atomic turn produces 2-5 training examples depending on its route flags:
  - ActionRouter:  always (1 per turn) — outputs 5 booleans for action gating
  - TextResponder: always (1 per turn)
  - DataExtractor: only for turns with has_new_data=True  (set_fields action)
  - ChoiceBuilder: only for turns with needs_choice=True  (ask_choice action)
  - ReviewBuilder: only for turns with wants_review=True  (show_preview/show_fields action)
                   Synthetic — deterministic dump of form_state_before. Chosen
                   deliberately for easy generation + easy evaluation.

Full conversation history is preserved (no truncation) — Qwen3.5 has 262K context.
Training data naturally includes varied context lengths (early turns = short, late = long).

Output: JSONL with chat-format messages (system + user + assistant) suitable for
Unsloth/TRL SFT training.

Usage:
    cd python
    uv run python ../tuning/sft/gen_format_data.py
    uv run python ../tuning/sft/gen_format_data.py --stats  # preview only
"""

import json
import sys
import argparse
import random
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).parent.parent.parent
FORM_SCHEMA_PATH = PROJECT_ROOT / "packages/web-app/public/forms/masters-northfield.json"
sys.path.insert(0, str(PROJECT_ROOT))

import dspy
from dspy.adapters.chat_adapter import ChatAdapter
from typing import Literal


# ══════════════════════════════════════════════════════════════════════
# DSPy Signatures — must match optimize_prompt.py exactly
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


# ══════════════════════════════════════════════════════════════════════
# Context builder — full form state + full conversation history
# ══════════════════════════════════════════════════════════════════════

def load_form_context() -> str:
    """Build a compact form context string — matches optimize_prompt.py exactly."""
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


# Cache form context — same for all turns
FORM_CONTEXT = load_form_context()


def build_context(turn: dict) -> str:
    """Build context string matching optimize_prompt.py exactly:
    form schema + filled fields as JSON + recent conversation with truncation.
    """
    ctx = FORM_CONTEXT

    # Filled fields as JSON — matches optimize_prompt.py
    form_state = turn.get("form_state_before", {})
    if form_state:
        ctx += f"\n\nFilled fields: {json.dumps(form_state)}"

    # Recent conversation — last 6 messages, each truncated to 300 chars
    history = turn.get("conversation_history", [])
    if history:
        recent = history[-6:]
        ctx += "\n\nRecent conversation:\n"
        ctx += "\n".join(
            f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content'][:300]}"
            for h in recent
        )

    return ctx


# ══════════════════════════════════════════════════════════════════════
# Route-flag inference from atomic data
# ══════════════════════════════════════════════════════════════════════

ROUTE_FLAGS = ("has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit")


def infer_route(turn: dict) -> dict:
    """Derive 5 action-route booleans from a turn's parsed_actions.

    Each flag is set independently — a turn may have none, one, or several.
    Must match `infer_route()` in tuning/dspy/optimize_prompt.py exactly.
    """
    action_types = set(turn.get("action_types", []))
    parsed = turn.get("parsed_actions", [])
    buttons = {a.get("button") for a in parsed if a.get("type") == "show_button"}
    return {
        "has_new_data": "set_fields" in action_types,
        "needs_choice": "ask_choice" in action_types,
        "wants_review": "show_preview" in action_types or "show_fields" in action_types,
        "wants_save": "save_draft" in buttons,
        "wants_submit": "submit" in buttons,
    }


# ══════════════════════════════════════════════════════════════════════
# Use DSPy's own ChatAdapter to generate training messages
# ══════════════════════════════════════════════════════════════════════

adapter = ChatAdapter()


def make_training_example(signature_cls, inputs: dict, outputs: dict, module_name: str) -> dict:
    """Use DSPy's ChatAdapter to generate exact system+user messages,
    then format the expected assistant response.

    This guarantees training data matches what the model sees at inference time.
    """
    # Get the messages DSPy would send to the LM
    messages = adapter.format(
        signature=signature_cls,
        demos=[],
        inputs=inputs,
    )

    # Get the expected assistant response in DSPy format
    assistant_content = adapter.format_assistant_message_content(
        signature=signature_cls,
        outputs=outputs,
    )

    # messages = [system, user] from adapter.format()
    # Append the expected assistant response
    messages.append({"role": "assistant", "content": assistant_content})

    return {
        "module": module_name,
        "messages": messages,
    }


# ══════════════════════════════════════════════════════════════════════
# Per-module training example generators
# ══════════════════════════════════════════════════════════════════════

def gen_action_router(turn: dict, context: str, route: dict) -> dict:
    """Generate ActionRouter training example (5 booleans)."""
    return make_training_example(
        signature_cls=ActionRouterSignature,
        inputs={"context": context, "user_message": turn["user_message"]},
        outputs={flag: bool(route[flag]) for flag in ROUTE_FLAGS},
        module_name="action_router",
    )


def gen_text_responder(turn: dict, context: str) -> dict | None:
    """Generate TextResponder training example."""
    response_text = turn.get("assistant_text", "").strip()
    if not response_text:
        return None

    return make_training_example(
        signature_cls=TextResponderSignature,
        inputs={"context": context, "user_message": turn["user_message"]},
        outputs={"response_text": response_text},
        module_name="text_responder",
    )


def gen_data_extractor(turn: dict, context: str) -> dict | None:
    """Generate DataExtractor training example from set_fields actions."""
    parsed_actions = turn.get("parsed_actions", [])

    # Collect field_id → value pairs from set_fields actions
    field_ids = []
    field_values = []
    for action in parsed_actions:
        if action.get("type") == "set_fields":
            for f in action.get("fields", []):
                fid = f.get("field_id", "")
                val = f.get("value", "")
                if fid:
                    field_ids.append(fid)
                    field_values.append(str(val) if not isinstance(val, str) else val)

    if not field_ids:
        return None

    return make_training_example(
        signature_cls=DataExtractorSignature,
        inputs={"context": context, "user_message": turn["user_message"]},
        outputs={"field_ids": field_ids, "field_values": field_values},
        module_name="data_extractor",
    )


def gen_choice_builder(turn: dict, context: str) -> dict | None:
    """Generate ChoiceBuilder training example from ask_choice actions."""
    parsed_actions = turn.get("parsed_actions", [])

    for action in parsed_actions:
        if action.get("type") == "ask_choice":
            question = action.get("question", "")
            options_raw = action.get("options", [])
            # Options can be strings or {label, value} objects
            options = []
            for opt in options_raw:
                if isinstance(opt, dict):
                    options.append(opt.get("label", opt.get("value", str(opt))))
                else:
                    options.append(str(opt))

            if not question or not options:
                continue

            return make_training_example(
                signature_cls=ChoiceBuilderSignature,
                inputs={"context": context, "user_message": turn["user_message"]},
                outputs={"question": question, "options": options},
                module_name="choice_builder",
            )

    return None


def gen_review_builder(turn: dict, context: str) -> dict | None:
    """Generate ReviewBuilder training example (synthetic from form state).

    We deliberately synthesize a deterministic, uniform progress dump from
    ``form_state_before`` rather than pulling content from a real
    ``show_preview`` action. Rationale: keeps the review target easy to
    generate and easy to evaluate — every example hits the same shape, so
    format compliance is trivially checkable and content can be diff'd
    against the filled state.
    """
    state = turn.get("form_state_before", {})
    if len(state) < 3:
        return None  # Not enough filled fields for a meaningful review

    filled_items = [f"- {k}: {v}" for k, v in state.items()]
    summary_content = f"Completed {len(state)} fields:\n" + "\n".join(filled_items)

    return make_training_example(
        signature_cls=ReviewBuilderSignature,
        inputs={"context": context, "user_message": turn["user_message"]},
        outputs={"summary_title": "Application Progress", "summary_content": summary_content},
        module_name="review_builder",
    )


# ══════════════════════════════════════════════════════════════════════
# Main pipeline
# ══════════════════════════════════════════════════════════════════════

def process_turn(turn: dict) -> list[dict]:
    """Generate all applicable training examples from one atomic turn.

    Each sub-module example is gated on the corresponding route flag.
    No module runs on a turn whose flag is False — this is what makes
    the training signal clean (no "extract nothing" junk examples).
    """
    examples = []
    context = build_context(turn)
    route = infer_route(turn)

    # Always generate ActionRouter and TextResponder
    examples.append(gen_action_router(turn, context, route))

    text_ex = gen_text_responder(turn, context)
    if text_ex:
        examples.append(text_ex)

    # Sub-modules gated on route flags (each runs only when its flag is True)
    if route["has_new_data"]:
        extract_ex = gen_data_extractor(turn, context)
        if extract_ex:
            examples.append(extract_ex)

    if route["needs_choice"]:
        choice_ex = gen_choice_builder(turn, context)
        if choice_ex:
            examples.append(choice_ex)

    if route["wants_review"]:
        review_ex = gen_review_builder(turn, context)
        if review_ex:
            examples.append(review_ex)

    # Note: wants_save / wants_submit don't need a training module — the
    # show_button action has no content to generate. FormAssistant.forward()
    # emits show_button JSON directly based on the router's flag. The router
    # training on these flags is sufficient.

    return examples


def main():
    parser = argparse.ArgumentParser(description="Generate SFT training data for DSPy format compliance")
    parser.add_argument("--input", default="tuning/data/atomic.jsonl", help="Input atomic JSONL")
    parser.add_argument("--output", default="tuning/sft/format_train.jsonl", help="Output training JSONL")
    parser.add_argument("--stats", action="store_true", help="Print stats only, don't write")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--sample-review", type=int, default=None,
                        help="Optional cap on review_builder examples (default: no cap — use all real show_preview rows)")
    args = parser.parse_args()

    random.seed(args.seed)

    input_path = PROJECT_ROOT / args.input
    output_path = PROJECT_ROOT / args.output

    # Load atomic turns
    turns = []
    for line in open(input_path):
        line = line.strip()
        if line:
            turns.append(json.loads(line))

    print(f"Loaded {len(turns)} atomic turns from {input_path}")

    # Generate training examples
    all_examples = []
    module_counts = Counter()
    flag_counts = Counter()

    for turn in turns:
        examples = process_turn(turn)
        for ex in examples:
            module_counts[ex["module"]] += 1
            all_examples.append(ex)
        for flag, v in infer_route(turn).items():
            if v:
                flag_counts[flag] += 1

    # Optional cap on review_builder examples
    if args.sample_review is not None:
        review_examples = [ex for ex in all_examples if ex["module"] == "review_builder"]
        other_examples = [ex for ex in all_examples if ex["module"] != "review_builder"]
        if len(review_examples) > args.sample_review:
            random.shuffle(review_examples)
            review_examples = review_examples[:args.sample_review]
            module_counts["review_builder"] = len(review_examples)
        all_examples = other_examples + review_examples

    # Shuffle for training
    random.shuffle(all_examples)

    # Stats
    print(f"\nTotal training examples: {len(all_examples)}")
    print(f"\nBy module:")
    for mod, count in sorted(module_counts.items(), key=lambda x: -x[1]):
        print(f"  {mod:20s} {count:5d}")

    print(f"\nTurns with each route flag True:")
    for flag in ROUTE_FLAGS:
        count = flag_counts.get(flag, 0)
        print(f"  {flag:20s} {count:5d} ({100*count/len(turns):.1f}%)")

    # Token estimate (rough: ~4 chars/token)
    total_chars = sum(
        sum(len(m["content"]) for m in ex["messages"])
        for ex in all_examples
    )
    print(f"\nEstimated total tokens: ~{total_chars // 4:,} ({total_chars:,} chars)")
    avg_chars = total_chars / len(all_examples) if all_examples else 0
    print(f"Average example size: ~{avg_chars / 4:.0f} tokens ({avg_chars:.0f} chars)")

    # Context length distribution
    char_sizes = [sum(len(m["content"]) for m in ex["messages"]) for ex in all_examples]
    char_sizes.sort()
    print(f"\nExample size distribution (chars):")
    print(f"  min={char_sizes[0]}, median={char_sizes[len(char_sizes)//2]}, "
          f"p90={char_sizes[int(len(char_sizes)*0.9)]}, max={char_sizes[-1]}")

    # Show samples
    for module_name in ["action_router", "text_responder", "data_extractor", "choice_builder", "review_builder"]:
        print("\n" + "=" * 60)
        print(f"Sample training example ({module_name}):")
        print("=" * 60)
        sample = next((ex for ex in all_examples if ex["module"] == module_name), None)
        if sample:
            for msg in sample["messages"]:
                print(f"\n--- {msg['role'].upper()} ---")
                content = msg["content"]
                if len(content) > 500:
                    print(content[:500] + "\n...(truncated)")
                else:
                    print(content)

    if args.stats:
        return

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for ex in all_examples:
            f.write(json.dumps(ex) + "\n")
    print(f"\nWrote {len(all_examples)} examples to {output_path}")


if __name__ == "__main__":
    main()
