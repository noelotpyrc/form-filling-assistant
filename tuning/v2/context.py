"""Context rendering — the strings the extractor and responder see (doc-18.1).

Pure stdlib, no DSPy. Produces the model-input fields:
  - form_schema      : the form structure (sections, fields, options)
  - filled_fields    : the durable "memory" — accumulated form_state as a
                       humanized list (R11: humanized beats a JSON dump)
  - recent_history   : capped conversation transcript (short-term, coreference)

`pending` is deliberately NOT rendered (doc-18.1: harness-only state; the last
asked question is already the most-recent history entry).
"""
from __future__ import annotations

from .schema import Schema, Field

HISTORY_TURNS = 6        # last N messages kept (tunable)
HISTORY_CHARS = 600      # per-message cap (file uploads handled later, v2.5)


def render_schema(schema: Schema) -> str:
    lines = [f"Form: {schema.name}", ""]
    section = None
    for f in schema.fields:
        if f.section_id != section:
            section = f.section_id
            lines.append(f"[{section}]")
        req = " (required)" if f.required else ""
        if f.is_choice:
            opts = ", ".join(str(label) for _val, label in f.options)
            lines.append(f"  {f.field_id} ({f.type}: {opts}){req}")
        else:
            lines.append(f"  {f.field_id} ({f.type}){req}")
    return "\n".join(lines)


def _display(schema: Schema, fid: str, value) -> str:
    f = schema.field(fid)
    if f is None:
        return str(value)
    if f.is_multi and isinstance(value, list):
        return ", ".join(_opt_label(f, v) for v in value)
    if f.is_choice:
        return _opt_label(f, value)
    return str(value)


def _opt_label(f: Field, value) -> str:
    for val, label in f.options:
        if val == value:
            return str(label)
    return str(value)


def render_filled(schema: Schema, form_state: dict) -> str:
    items = [f for f in schema.fields if f.field_id in form_state
             and form_state[f.field_id] not in (None, "", [])]
    if not items:
        return "(nothing filled yet)"
    return "\n".join(f"  {f.label}: {_display(schema, f.field_id, form_state[f.field_id])}"
                     for f in items)


def render_history(history: list[dict], turns: int = HISTORY_TURNS) -> str:
    if not history:
        return "(conversation just started)"
    out = []
    for m in history[-turns:]:
        role = "User" if m.get("role") == "user" else "Assistant"
        content = str(m.get("content", "")).strip()
        if len(content) > HISTORY_CHARS:
            content = content[:HISTORY_CHARS] + "…"
        out.append(f"{role}: {content}")
    return "\n".join(out)
