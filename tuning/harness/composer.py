"""composer.py — turn a 5-module DSPy Prediction into the legacy
text + ---actions--- + JSON format the web app's action-parser.js expects.

The composition rules mirror the SFT training data format produced by
`tuning/sft/gen_format_data.py` and the live system-prompt the production
agent uses (packages/web-app/public/js/system-prompt.js).

Output shape:

    {response_text}

    ---actions---
    ```json
    [{...}, {...}, ...]
    ```

Action emission rules (gated by route flags):

    has_new_data + non-empty field_ids/field_values  →  set_fields
    needs_choice + non-empty question                →  ask_choice
    wants_review + (summary_title or summary_content) →  show_preview
    wants_save                                       →  show_button save_draft
    wants_submit                                     →  show_button submit
"""

from __future__ import annotations

import json
from typing import Any

from tuning.harness.state_check import validate_against_schema


# ══════════════════════════════════════════════════════════════════════
# Action builders — small, explicit, easy to extend.
# ══════════════════════════════════════════════════════════════════════


def _build_set_fields(
    field_ids: list[str],
    field_values: list[str],
    schema: dict | None = None,
) -> tuple[dict | None, list[dict]]:
    """Build a set_fields action from parallel ID/value lists.

    When a schema is provided, each (field_id, value) pair is validated against
    it (CANNOT #6 + #7 fixes):
      - Drop fields whose field_id isn't in the schema
      - Drop select/multi_select values not reconcilable to a schema enum
      - Coerce string-encoded booleans / numbers / lists to their proper types
      - Snap select labels to canonical values ("Computer Science (MS)" → "cs")

    Returns (action, dropped) where dropped is a list of `{field_id, value, reason}`
    entries the caller can log for debugging the model's bad outputs.
    """
    if not field_ids:
        return None, []
    fields = []
    dropped: list[dict] = []
    for i, fid in enumerate(field_ids):
        if not fid:
            continue
        v = field_values[i] if i < len(field_values) else ""
        if schema is not None:
            ok, corrected, reason = validate_against_schema(schema, fid, v)
            if not ok:
                dropped.append({"field_id": fid, "value": v, "reason": reason})
                continue
            fields.append({"field_id": fid, "value": corrected})
        else:
            fields.append({"field_id": fid, "value": v})
    if not fields:
        return None, dropped
    return {"type": "set_fields", "fields": fields}, dropped


def _build_ask_choice(question: str, options: list[str]) -> dict | None:
    """Build an ask_choice action. Empty question → no action.

    The web app's renderAskChoice expects each option as `{label, value}`
    (see packages/web-app/public/index.html). The SFT model emits a plain
    list[str], so we wrap each into a {label, value} dict here. Without
    this, the click handler reads opt.label as undefined and the user
    selection becomes the literal string "undefined" — which then lands
    back in the conversation as a useless [system] event.
    """
    if not (question or "").strip():
        return None
    wrapped = []
    for o in (options or []):
        if not o:
            continue
        if isinstance(o, dict):
            wrapped.append({
                "label": str(o.get("label") or o.get("value") or "").strip(),
                "value": str(o.get("value") or o.get("label") or "").strip(),
            })
        else:
            s = str(o).strip()
            wrapped.append({"label": s, "value": s})
    return {
        "type": "ask_choice",
        "question": question.strip(),
        "options": wrapped,
    }


def _build_show_preview(title: str, summary: str) -> dict | None:
    """Build a show_preview action. Empty title AND summary → no action."""
    title = (title or "").strip()
    summary = (summary or "").strip()
    if not title and not summary:
        return None
    return {
        "type": "show_preview",
        "title": title or "Application Progress",
        "summary": summary,
    }


def _build_show_button(button: str) -> dict:
    return {"type": "show_button", "button": button}


# ══════════════════════════════════════════════════════════════════════
# Top-level composer.
# ══════════════════════════════════════════════════════════════════════


def compose_actions(prediction: Any, schema: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Build the ordered action list from a 5-module DSPy Prediction.

    Order matches what the web app expects: data mutations first, then UI
    affordances. Each builder returns None when the flag is on but the
    payload is empty (a graceful degradation; the model occasionally fires
    a flag without producing usable content).

    When `schema` is provided, set_fields entries are coerced (#6) and
    validated against the schema (#7) before emitting; bad entries are
    dropped and returned in the second tuple slot so callers can log them.
    """
    actions: list[dict] = []
    dropped: list[dict] = []

    if bool(getattr(prediction, "has_new_data", False)):
        a, drops = _build_set_fields(
            list(getattr(prediction, "field_ids", []) or []),
            list(getattr(prediction, "field_values", []) or []),
            schema=schema,
        )
        dropped.extend(drops)
        if a is not None:
            actions.append(a)

    if bool(getattr(prediction, "needs_choice", False)):
        a = _build_ask_choice(
            getattr(prediction, "question", "") or "",
            list(getattr(prediction, "options", []) or []),
        )
        if a is not None:
            actions.append(a)

    if bool(getattr(prediction, "wants_review", False)):
        a = _build_show_preview(
            getattr(prediction, "summary_title", "") or "",
            getattr(prediction, "summary_content", "") or "",
        )
        if a is not None:
            actions.append(a)

    if bool(getattr(prediction, "wants_save", False)):
        actions.append(_build_show_button("save_draft"))

    if bool(getattr(prediction, "wants_submit", False)):
        # Note: model has zero training supervision on this flag (see doc-12
        # Experiment 9 audit). Honor it if it fires; in practice it rarely will.
        actions.append(_build_show_button("submit"))

    return actions, dropped


def compose_text(prediction: Any) -> str:
    """Pull the conversational reply (before the actions delimiter)."""
    return (getattr(prediction, "response_text", "") or "").strip()


def compose(prediction: Any, schema: dict | None = None) -> tuple[str, list[dict], str, list[dict]]:
    """Compose a Prediction into (response_text, actions, full_response, dropped).

    full_response is the legacy concatenated form the web app's
    action-parser.js expects:

        {response_text}\\n\\n---actions---\\n```json\\n[...]\\n```

    If there are no actions, the delimiter and JSON block are omitted.

    `dropped` lists set_fields entries that were rejected by schema
    validation (unknown field_id, value not in enum, etc.) — surfaced so
    serve.py can log them for debugging without confusing the user.
    """
    text = compose_text(prediction)
    actions, dropped = compose_actions(prediction, schema=schema)

    if actions:
        full = (
            f"{text}\n\n"
            f"---actions---\n"
            f"```json\n"
            f"{json.dumps(actions, indent=2)}\n"
            f"```"
        )
    else:
        full = text

    return text, actions, full, dropped


# ══════════════════════════════════════════════════════════════════════
# Smoke test — `uv run python tuning/harness/composer.py`
# ══════════════════════════════════════════════════════════════════════


def _smoke() -> None:
    """Test composition on a fake Prediction object."""

    class FakePred:
        response_text = "Got it! I've added your name and email."
        has_new_data = True
        needs_choice = False
        wants_review = False
        wants_save = False
        wants_submit = False
        field_ids = ["full_name", "email"]
        field_values = ["Jane Smith", "jane@example.com"]
        question = ""
        options = []
        summary_title = ""
        summary_content = ""

    text, actions, full = compose(FakePred())
    print("=== text ===")
    print(text)
    print("\n=== actions ===")
    print(json.dumps(actions, indent=2))
    print("\n=== full response ===")
    print(full)


if __name__ == "__main__":
    _smoke()
