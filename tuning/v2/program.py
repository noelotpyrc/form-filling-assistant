"""FormAssistant — the DSPy program (doc-18.1). Two learned calls (extract,
respond) wrapped around the deterministic core (prestep -> validate -> compose).

The LM is configured externally (`dspy.configure(lm=ClaudeLM(...))` for the
teacher, or the SFT student later) — this module is LM-agnostic.

Verified on DSPy 3.3.0b1 (typed list[Extraction] output parses; the teacher
produces the {field, ""} / {field, partial} / [] conventions reliably).
"""
from __future__ import annotations
from typing import Optional
import re

import dspy
from dspy.utils.exceptions import AdapterParseError
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
    - A value you can confidently attribute to a field (named or implied by the
      user's words, matching a field's option labels, or of a format that only
      one field could take) -> {field_id, that value}. For a partial or
      category term pointing at a select field (e.g. "a science program"), use
      the partial text as the value (e.g. {"program", "science"}) so the
      options can be narrowed.
    - A value you recognize but cannot place on a specific field ->
      {field_id: null, value}. A bare value whose type fits several fields
      (e.g. a lone date — date of birth? a test date?) with no words tying it
      to one of them is unplaceable: emit {field_id: null, value}; never pick
      the field from its type alone.
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
    state. Keep it brief and warm.

    When actions say choice buttons are shown, ask the question but do not list
    the options in prose — the buttons already show them. If the user asks about
    anything the form doesn't cover, say you don't know rather than guessing;
    never invent policies or facts."""
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
        elif kind == "submit_blocked":
            n = len(payload)
            out.append(
                f"The user wants to submit, but {n} required field(s) are still "
                f"missing, so it can't be submitted yet. Reassure them warmly, then "
                f"offer a gentle choice: keep going now, or save a draft and come "
                f"back later (a Save Draft button is shown). Don't pressure or list "
                f"every missing field."
            )
        elif kind == "ask_target":
            f = schema.field(payload)
            if f is not None and f.button_choice:
                out.append(f"Ask the user for: {f.label}. The options are shown as "
                           f"buttons — don't list them in your reply.")
            else:
                out.append(f"Ask the user for: {_label(schema, payload)}.")
        elif kind == "reask_pending":
            out.append(f"Gently re-ask about: {_label(schema, payload)}.")
        elif kind == "clarify":
            tgt = _label(schema, payload.field_id) if payload.field_id else "the value just given"
            out.append(f"Ask the user to clarify {tgt}.")
        elif kind == "terminal":
            out.append("All required fields are complete — invite the user to review the summary and submit. "
                       "The summary card is already shown — don't repeat its contents in your reply.")
    return " ".join(out) if out else "Respond naturally."


# The teacher sometimes emits a malformed DSPy end-marker (e.g. "[[ ## completed ]]",
# missing the trailing ##), which the adapter fails to strip and which then leaks
# into the user-facing reply. Belt-and-suspenders: remove any [[ ## ... ]] marker.
_MARKER = re.compile(r"\[\[\s*##.*?\]\]")


def strip_markers(text: str) -> str:
    return _MARKER.sub("", text).strip()


def _last_raw_completion() -> str:
    """Raw text of the most recent LM call (the call is recorded in history
    before the adapter parses it, so this survives an AdapterParseError)."""
    h = getattr(dspy.settings.lm, "history", [])
    if h and h[-1].get("outputs"):
        out = h[-1]["outputs"][0]
        return out if isinstance(out, str) else ""
    return ""


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

def build_extract_demos(schema: Schema) -> list:
    """ONE hand demo teaching the compound convention: a pending-answer plus a
    volunteered extra in a single message must yield BOTH pairs, not just the
    pending one (nemotron baseline missed the extra: compound 0/3, while bulk
    without a pending is 100%). The assistant's last turn asked for the date of
    birth, so binding the leading date to `dob` is a cued, confident attribution
    (not a bare-value guess — the message carries other words, so the runtime
    bare-value guard does not fire). The trailing phone is the volunteered extra.

    Instance is eval-disjoint (NOT the March-3rd-1995 / (415) 555-0132 eval compound
    case, nor any _BARE_DATES instance in datagen)."""
    return [
        dspy.Example(
            form_schema=context.render_schema(schema),
            filled_fields=context.render_filled(schema, {}),
            recent_history=context.render_history(
                [{"role": "assistant", "content": "Thanks! What's your date of birth?"}]),
            user_message="June 4, 1991 — oh, and my phone is (312) 555-0148.",
            extractions=[Extraction(field_id="dob", value="1991-06-04"),
                         Extraction(field_id="phone", value="(312) 555-0148")],
        ).with_inputs("form_schema", "filled_fields", "recent_history", "user_message")
    ]


def build_teacher(schema: Schema) -> "FormAssistant":
    """The canonical teacher — FormAssistant() with ONE extract demo (the compound
    convention, `build_extract_demos`).

    Demos are BACK for the API-native teacher (2026-07-14): OpenRouterLM passes the
    DSPy messages array through NATIVELY, so a demo renders as real user/assistant
    turns and lifts compound extraction without hurting marker compliance. Note the
    earlier 2026-07-13 retirement was CLI-specific: ClaudeLM._split flattens the demo
    into one user string, which broke ChatAdapter markers (~85-90% malformed extract,
    M4_PLAN Pilot1) — so `--backend claude` is legacy / demo-incompatible; use
    `--backend openrouter` for the demo-carrying teacher. (The bare-date restraint the
    old demo also taught is now enforced deterministically in the validator, doc-18.1
    "code owns placement", so this demo carries only the compound lesson.)

    Kept as the factory seam: a future MIPRO/GEPA compiled artifact would slot a
    `.load(...)` here without touching callers (eval, data-gen)."""
    program = FormAssistant()
    program.extract.demos = build_extract_demos(schema)
    return program


def assign_lms(program: "FormAssistant", extract_lm=None, respond_lm=None) -> "FormAssistant":
    """Assign per-predictor LMs (M4_PLAN P4): the extract and respond calls are
    fully decoupled through the deterministic core, so the two-artifact hypothesis
    is to run a different model per predictor (e.g. slice-1 = student-extractor +
    nemotron-responder). Setting `predictor.lm` overrides the global `settings.lm`
    at call time (dspy 3.3.0b1 predict.py:149 `lm = kwargs.pop("lm", self.lm) or
    settings.lm`); None leaves that predictor inheriting the global."""
    if extract_lm is not None:
        program.extract.lm = extract_lm
    if respond_lm is not None:
        program.respond.lm = respond_lm
    return program


class FormAssistant(dspy.Module):
    def __init__(self):
        super().__init__()
        self.extract = dspy.Predict(Extract)
        self.respond = dspy.Predict(Respond)

    def forward(self, state: TurnState, user_message: str, history: list[dict],
                with_response: bool = True):
        schema = state.schema
        schema_str = context.render_schema(schema)
        hist_str = context.render_history(history)

        ps = prestep.run(user_message, state)
        if ps.handled:
            outcomes = []
        else:
            try:
                pred = self.extract(
                    form_schema=schema_str,
                    filled_fields=context.render_filled(schema, state.form_state),
                    recent_history=hist_str,
                    user_message=user_message,
                )
                pairs = [{"field_id": e.field_id, "value": e.value} for e in pred.extractions]
            except AdapterParseError:
                pairs = []   # teacher format slip -> extract nothing this turn (safe)
            outcomes = validate(pairs, state, user_message)

        actions, directives = compose(state, ps, outcomes)

        # The responder is a second LM call; Tier-1 extractor scoring doesn't need
        # it, so eval can skip it (with_response=False) to halve teacher cost. The
        # extract -> validate -> compose path above is identical either way.
        text = None
        if with_response:
            try:
                rpred = self.respond(
                    form_schema=schema_str,
                    filled_fields=context.render_filled(schema, state.form_state),  # post-update
                    recent_history=hist_str,
                    user_message=user_message,
                    actions_taken=summarize_actions(schema, actions),
                    guidance=render_guidance(schema, directives),
                )
                text = strip_markers(rpred.response_text)
            except AdapterParseError:
                # teacher omitted the response_text marker — recover the prose it wrote
                text = strip_markers(_last_raw_completion())
        full = serialize(text, actions) if text is not None else None
        return dspy.Prediction(text=text, actions=actions, full=full)
