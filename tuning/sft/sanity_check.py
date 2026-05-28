#!/usr/bin/env python3
"""
Quick sanity check: is the SFT model producing meaningful, varied responses
or just parroting the same format with identical content?

Sends diverse prompts to the SFT model and prints raw outputs.

Usage:
    cd python
    uv run python ../tuning/sft/sanity_check.py
    uv run python ../tuning/sft/sanity_check.py --port 8082  # test original for comparison
"""

import json
import argparse
from pathlib import Path
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

SFT_URL_TEMPLATE = "http://localhost:{port}/v1/chat/completions"
MODEL_ID = str(PROJECT_ROOT / "models" / "qwen35-08b-dspy-format-mlx")

# ── Test cases: varied contexts, histories, user messages ──

ROUTE_SYSTEM = """Your input fields are:
1. `context` (str): Form fields and current state
2. `user_message` (str): Current user message
Your output fields are:
1. `has_new_data` (bool): True if user provided new field values to extract
2. `needs_choice` (bool): True if a multiple-choice question should be presented
3. `wants_review` (bool): True if a progress-summary card should be shown
4. `wants_save` (bool): True if a Save Draft button should be offered
5. `wants_submit` (bool): True if a Submit Application button should be offered
All interactions will be structured in the following way, with the appropriate values filled in.

[[ ## context ## ]]
{context}

[[ ## user_message ## ]]
{user_message}

[[ ## has_new_data ## ]]
{has_new_data}        # note: the value you produce must be True or False

[[ ## needs_choice ## ]]
{needs_choice}        # note: the value you produce must be True or False

[[ ## wants_review ## ]]
{wants_review}        # note: the value you produce must be True or False

[[ ## wants_save ## ]]
{wants_save}        # note: the value you produce must be True or False

[[ ## wants_submit ## ]]
{wants_submit}        # note: the value you produce must be True or False

[[ ## completed ## ]]
In adhering to this structure, your objective is:
        Decide which actions the assistant should take this turn by emitting five independent boolean flags."""

EXTRACTOR_SYSTEM = """Your input fields are:
1. `context` (str): Form fields and current state
2. `user_message` (str): User message containing form data
Your output fields are:
1. `field_ids` (list[str]): List of field_ids to set, e.g. ['full_name', 'email']
2. `field_values` (list[str]): Corresponding values, e.g. ['Jane Smith', 'jane@email.com']
All interactions will be structured in the following way, with the appropriate values filled in.

[[ ## context ## ]]
{context}

[[ ## user_message ## ]]
{user_message}

[[ ## field_ids ## ]]
{field_ids}        # note: the value you produce must adhere to the JSON schema: {"type": "array", "items": {"type": "string"}}

[[ ## field_values ## ]]
{field_values}        # note: the value you produce must adhere to the JSON schema: {"type": "array", "items": {"type": "string"}}

[[ ## completed ## ]]
In adhering to this structure, your objective is:
        Extract form field values from the user's message."""

TEXT_SYSTEM = """Your input fields are:
1. `context` (str): Form fields and current state
2. `user_message` (str): Current user message
Your output fields are:
1. `response_text` (str): Conversational response to the user
All interactions will be structured in the following way, with the appropriate values filled in.

[[ ## context ## ]]
{context}

[[ ## user_message ## ]]
{user_message}

[[ ## response_text ## ]]
{response_text}

[[ ## completed ## ]]
In adhering to this structure, your objective is:
        Generate a conversational response for a form-filling assistant."""

ROUTE_RESPOND_SUFFIX = (
    "Respond with the corresponding output fields, starting with the field "
    "`[[ ## has_new_data ## ]]` (must be formatted as a valid Python bool), "
    "then `[[ ## needs_choice ## ]]` (must be formatted as a valid Python bool), "
    "then `[[ ## wants_review ## ]]` (must be formatted as a valid Python bool), "
    "then `[[ ## wants_save ## ]]` (must be formatted as a valid Python bool), "
    "then `[[ ## wants_submit ## ]]` (must be formatted as a valid Python bool), "
    "and then ending with the marker for `[[ ## completed ## ]]`."
)

TESTS = [
    # ── Route: varied scenarios ──
    {
        "name": "Route: greeting, empty form",
        "system": ROUTE_SYSTEM,
        "user": "[[ ## context ## ]]\nForm: Northfield University Graduate Application\nFilled fields: (none)\n\n[[ ## user_message ## ]]\nHello! I'd like to start my application.\n\n" + ROUTE_RESPOND_SUFFIX,
    },
    {
        "name": "Route: providing data, mid-form",
        "system": ROUTE_SYSTEM,
        "user": '[[ ## context ## ]]\nForm: Northfield University Graduate Application\n\nFilled fields: {"full_name": "Alex Chen", "email": "alex@mit.edu", "program": "cs"}\n\nRecent conversation:\nUser: I want to do CS\nAssistant: Great choice! What start term?\n\n[[ ## user_message ## ]]\nFall 2026, full-time please.\n\n' + ROUTE_RESPOND_SUFFIX,
    },
    {
        "name": "Route: asking a question",
        "system": ROUTE_SYSTEM,
        "user": '[[ ## context ## ]]\nForm: Northfield University Graduate Application\n\nFilled fields: {"program": "public_health"}\n\n[[ ## user_message ## ]]\nDo I need to take the GRE for public health?\n\n' + ROUTE_RESPOND_SUFFIX,
    },
    {
        "name": "Route: form almost done",
        "system": ROUTE_SYSTEM,
        "user": '[[ ## context ## ]]\nForm: Northfield University Graduate Application\n\nFilled fields: {"full_name": "Maria Garcia", "dob": "1982-03-22", "email": "maria@email.com", "phone": "555-0789", "program": "public_health", "start_term": "fall_2026", "enrollment_type": "full_time", "prior_application": false, "country_citizenship": "US", "country_residence": "US", "mailing_address": "789 Pine St", "has_work_experience": true, "funding_interest": true, "statement_of_purpose": "uploaded", "resume": "uploaded"}\n\nRecent conversation:\nAssistant: Everything looks great! Ready to submit?\n\n[[ ## user_message ## ]]\nYes, let\'s submit it!\n\n' + ROUTE_RESPOND_SUFFIX,
    },
    {
        "name": "Route: requesting review",
        "system": ROUTE_SYSTEM,
        "user": '[[ ## context ## ]]\nForm: Northfield University Graduate Application\n\nFilled fields: {"full_name": "Jane Smith", "program": "data_science", "email": "jane@example.com"}\n\n[[ ## user_message ## ]]\nCan you show me what I\'ve filled in so far?\n\n' + ROUTE_RESPOND_SUFFIX,
    },

    # ── Extractor: varied data ──
    {
        "name": "Extract: single field (name)",
        "system": EXTRACTOR_SYSTEM,
        "user": '[[ ## context ## ]]\nForm: Northfield University Graduate Application\nFilled fields: (none)\n\n[[ ## user_message ## ]]\nMy name is Sarah Johnson.\n\nRespond with the corresponding output fields, starting with the field `[[ ## field_ids ## ]]` (must be formatted as a valid Python list[str]), then `[[ ## field_values ## ]]` (must be formatted as a valid Python list[str]), and then ending with the marker for `[[ ## completed ## ]]`.',
    },
    {
        "name": "Extract: multiple fields at once",
        "system": EXTRACTOR_SYSTEM,
        "user": '[[ ## context ## ]]\nForm: Northfield University Graduate Application\n\nFilled fields: {"program": "cs"}\n\n[[ ## user_message ## ]]\nI\'m David Park, born March 15 1995, email david.park@gmail.com, phone 555-1234.\n\nRespond with the corresponding output fields, starting with the field `[[ ## field_ids ## ]]` (must be formatted as a valid Python list[str]), then `[[ ## field_values ## ]]` (must be formatted as a valid Python list[str]), and then ending with the marker for `[[ ## completed ## ]]`.',
    },
    {
        "name": "Extract: boolean + selection",
        "system": EXTRACTOR_SYSTEM,
        "user": '[[ ## context ## ]]\nForm: Northfield University Graduate Application\n\nFilled fields: {"full_name": "Alex Chen", "program": "cs"}\n\nRecent conversation:\nAssistant: Have you applied to Northfield before?\n\n[[ ## user_message ## ]]\nNo, this is my first time applying.\n\nRespond with the corresponding output fields, starting with the field `[[ ## field_ids ## ]]` (must be formatted as a valid Python list[str]), then `[[ ## field_values ## ]]` (must be formatted as a valid Python list[str]), and then ending with the marker for `[[ ## completed ## ]]`.',
    },
    {
        "name": "Extract: work experience",
        "system": EXTRACTOR_SYSTEM,
        "user": '[[ ## context ## ]]\nForm: Northfield University Graduate Application\n\nFilled fields: {"full_name": "Maria Garcia", "program": "mba"}\n\nRecent conversation:\nAssistant: Tell me about your work experience.\n\n[[ ## user_message ## ]]\nI worked at Google as a Product Manager from 2019 to 2023.\n\nRespond with the corresponding output fields, starting with the field `[[ ## field_ids ## ]]` (must be formatted as a valid Python list[str]), then `[[ ## field_values ## ]]` (must be formatted as a valid Python list[str]), and then ending with the marker for `[[ ## completed ## ]]`.',
    },

    # ── Text responder: varied scenarios (no intent input in new signature) ──
    {
        "name": "Text: greet new user",
        "system": TEXT_SYSTEM,
        "user": "[[ ## context ## ]]\nForm: Northfield University Graduate Application\nFilled fields: (none)\n\n[[ ## user_message ## ]]\nHi there!\n\nRespond with the corresponding output fields, starting with the field `[[ ## response_text ## ]]`, and then ending with the marker for `[[ ## completed ## ]]`.",
    },
    {
        "name": "Text: acknowledge data, ask next",
        "system": TEXT_SYSTEM,
        "user": '[[ ## context ## ]]\nForm: Northfield University Graduate Application\n\nFilled fields: {"full_name": "Alex Chen", "email": "alex@mit.edu"}\n\nRecent conversation:\nAssistant: What program are you interested in?\nUser: Computer Science, starting Fall 2026\n\n[[ ## user_message ## ]]\nComputer Science, starting Fall 2026\n\nRespond with the corresponding output fields, starting with the field `[[ ## response_text ## ]]`, and then ending with the marker for `[[ ## completed ## ]]`.',
    },
    {
        "name": "Text: answer a question",
        "system": TEXT_SYSTEM,
        "user": '[[ ## context ## ]]\nForm: Northfield University Graduate Application\n\nFilled fields: {"program": "public_health"}\n\n[[ ## user_message ## ]]\nIs the GRE required for public health?\n\nRespond with the corresponding output fields, starting with the field `[[ ## response_text ## ]]`, and then ending with the marker for `[[ ## completed ## ]]`.',
    },
]


def call_model(url: str, model_id: str, system: str, user: str) -> str:
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 512,
        "temperature": 0.0,
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8084)
    parser.add_argument("--model-id", default=MODEL_ID)
    args = parser.parse_args()

    url = SFT_URL_TEMPLATE.format(port=args.port)
    print(f"Testing model at {url} (model={args.model_id})")
    print("=" * 80)

    # Track unique outputs to detect repetition
    all_outputs = []

    for test in TESTS:
        print(f"\n{'─' * 80}")
        print(f"TEST: {test['name']}")
        print(f"{'─' * 80}")

        output = call_model(url, args.model_id, test["system"], test["user"])
        all_outputs.append(output)
        print(output)

    # Repetition check
    print("\n" + "=" * 80)
    print("REPETITION CHECK")
    print("=" * 80)
    unique = len(set(all_outputs))
    print(f"Total outputs: {len(all_outputs)}, Unique: {unique}")
    if unique < len(all_outputs):
        from collections import Counter
        dupes = [(out[:80], cnt) for out, cnt in Counter(all_outputs).items() if cnt > 1]
        for preview, cnt in dupes:
            print(f"  DUPLICATE ({cnt}x): {preview}...")
    else:
        print("  All outputs are unique — model is producing varied responses.")


if __name__ == "__main__":
    main()
