"""FormAssistant — the DSPy program (doc-18.1). Two learned calls (extract,
respond) wrapped around the deterministic core (prestep -> validate -> compose).

The LM is configured externally (`dspy.configure(lm=ClaudeLM(...))` for the
teacher, or the SFT student later) — this module is LM-agnostic.

Verified on DSPy 3.3.0b1 (typed list[Extraction] output parses; the teacher
produces the {field, ""} / {field, partial} / [] conventions reliably).
"""
from __future__ import annotations
from typing import Optional

import dspy
from pydantic import BaseModel

from .schema import Schema
from .state import TurnState, CONFIRM_SUBMIT
from . import prestep, context
from .validator import validate
from .composer import compose, serialize


# ---- learned-call signatures --------------------------------------------

class Extraction(BaseModel):
    """One extracted pair. field_id=None means 'a value I can't place' — the
    harness binding cascade resolves it (doc-18.1). value="" means the field was
    engaged with no usable value."""
    field_id: Optional[str]
    value: str


class Extract(dspy.Signature):
    """Extract what the user's latest message implies about the form fields.

    Emit a list of {field_id, value} pairs, one per case below:
    - A value you can confidently attribute to a field (by format, or by the
      field's option labels) -> {field_id, that value}. For a partial or
      category term pointing at a select field (e.g. "a science program"), use
      the partial text as the value (e.g. {"program", "science"}) so the
      options can be narrowed.
    - A value you recognize but cannot place on a specific field ->
      {field_id: null, value}.
    - The user asking which options exist / what to put for a SPECIFIC field,
      giving no value (e.g. "what programs do you offer?") -> {that field_id,
      ""} (empty value), to surface that field's choices.
    - Nothing about any field (greetings, small talk, questions not tied to a
      field) -> an empty list [].
    Never invent values."""
    form_schema: str = dspy.InputField()
    filled_fields: str = dspy.InputField(desc="already-filled fields (the durable state)")
    recent_history: str = dspy.InputField()
    user_message: str = dspy.InputField()
    extractions: list[Extraction] = dspy.OutputField()


class Respond(dspy.Signature):
    """Write the assistant's conversational reply for this turn.

    The actions for this turn have ALREADY been decided (shown in
    actions_taken). Your job is only to verbalize them naturally and follow the
    guidance. Do not announce actions that aren't listed, and don't invent form
    state. Keep it brief and warm."""
    form_schema: str = dspy.InputField()
    filled_fields: str = dspy.InputField()
    recent_history: str = dspy.InputField()
    user_message: str = dspy.InputField()
    actions_taken: str = dspy.InputField(desc="what the harness is doing this turn")
    guidance: str = dspy.InputField(desc="directives to follow in the reply")
    response_text: str = dspy.OutputField()


# ---- directive / action summaries for the responder ---------------------

def _label(schema: Schema, fid: str) -> str:
    f = schema.field(fid)
    return f.label if f else fid


def render_guidance(schema: Schema, directives: list) -> str:
    out = []
    for kind, payload in directives:
        if kind == "ack":
            out.append(f"Acknowledge that the user just did: {payload}.")
        elif kind == "fix":
            out.append(f"A validation error occurred ({payload}). Apologize briefly and ask for a corrected value.")
        elif kind == "missing_fields":
            labels = ", ".join(_label(schema, f) for f in payload)
            out.append(f"Still required before submitting: {labels}. Ask for the first one.")
        elif kind == "ask_target":
            out.append(f"Ask the user for: {_label(schema, payload)}.")
        elif kind == "reask_pending":
            out.append(f"Gently re-ask about: {_label(schema, payload)}.")
        elif kind == "clarify":
            tgt = _label(schema, payload.field_id) if payload.field_id else "the value just given"
            out.append(f"Ask the user to clarify {tgt}.")
        elif kind == "terminal":
            out.append("All required fields are complete — invite the user to review the summary and submit.")
    return " ".join(out) if out else "Respond naturally."


def summarize_actions(schema: Schema, actions: list[dict]) -> str:
    parts = []
    for a in actions:
        t = a["type"]
        if t == "set_fields":
            parts.append("Recorded: " + ", ".join(_label(schema, f["field_id"]) for f in a["fields"]))
        elif t == "ask_choice":
            parts.append(f"Showing choice buttons: {a['question']}")
        elif t == "show_preview":
            parts.append("Showing a summary card.")
        elif t == "show_button":
            parts.append(f"Showing the {a['button']} button.")
        elif t == "show_fields":
            parts.append("Focusing a form section.")
    return " ".join(parts) if parts else "(no actions this turn)"


# ---- the program ---------------------------------------------------------

class FormAssistant(dspy.Module):
    def __init__(self):
        super().__init__()
        self.extract = dspy.Predict(Extract)
        self.respond = dspy.Predict(Respond)

    def forward(self, state: TurnState, user_message: str, history: list[dict]):
        schema = state.schema
        schema_str = context.render_schema(schema)
        hist_str = context.render_history(history)

        ps = prestep.run(user_message, state)
        if ps.handled:
            outcomes = []
        else:
            pred = self.extract(
                form_schema=schema_str,
                filled_fields=context.render_filled(schema, state.form_state),
                recent_history=hist_str,
                user_message=user_message,
            )
            pairs = [{"field_id": e.field_id, "value": e.value} for e in pred.extractions]
            outcomes = validate(pairs, state)

        actions, directives = compose(state, ps, outcomes)

        rpred = self.respond(
            form_schema=schema_str,
            filled_fields=context.render_filled(schema, state.form_state),  # post-update
            recent_history=hist_str,
            user_message=user_message,
            actions_taken=summarize_actions(schema, actions),
            guidance=render_guidance(schema, directives),
        )
        text = rpred.response_text.strip()
        return dspy.Prediction(text=text, actions=actions, full=serialize(text, actions))
