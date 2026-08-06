"""Steps 3-5 — Compose responsive actions, update state, run the agenda (doc-18.1).

`compose()` is the deterministic turn assembler: given the pre-step result and
the validated outcomes, it produces the merged action list + directives and
mutates `state`. The two model calls (extractor before, responder after) live in
program.py; this module is pure code and fully unit-testable.
"""
from __future__ import annotations
import json

from .state import TurnState, Pending, CONFIRM_SUBMIT, queue, is_active
from .schema import Field
from .validator import Outcome, VALID_SET, CORRECTION, CHOICE_NEEDED, CLARIFY


# ---- action builders -----------------------------------------------------

def _opt_label(f: Field, value) -> str:
    for val, label in f.options:
        if val == value:
            return label
    return str(value)


def _display(f: Field, value) -> str:
    if f.is_multi and isinstance(value, list):
        return ", ".join(_opt_label(f, v) for v in value)
    if f.is_choice:
        return _opt_label(f, value)
    return str(value)


def _ask_choice(f: Field, options) -> dict:
    return {
        "type": "ask_choice",
        "question": f"{f.label}?",
        "options": [{"label": label, "value": val} for val, label in options],
    }


def _show_button(kind: str) -> dict:
    return {"type": "show_button", "button": kind}


def _show_preview(state: TurnState) -> dict:
    secs: dict[str, list] = {}
    order: list[str] = []
    for f in state.schema.fields:
        if not state.is_filled(f.field_id):
            continue
        if f.section_id not in secs:
            secs[f.section_id] = []
            order.append(f.section_id)
        secs[f.section_id].append({"label": f.label, "value": _display(f, state.form_state[f.field_id])})
    return {
        "type": "show_preview",
        "title": "Application Summary",
        "sections": [{"title": sid, "fields": secs[sid]} for sid in order],
    }


# ---- compose (steps 3-5) -------------------------------------------------

def compose(state: TurnState, prestep, outcomes: list[Outcome]):
    """Returns (actions, directives). Mutates `state` (form_state + pending)."""
    actions: list[dict] = []
    directives: list = list(prestep.directives)
    it = prestep.intents

    # validation-error re-pend + hold
    if prestep.repend is not None:
        state.pending = Pending(prestep.repend, held=True)

    # --- step 3a + step 4: collect & apply sets (early so completeness/agenda see them) ---
    sets = [(o.field_id, o.value) for o in prestep.set_outcomes]
    sets += [(o.field_id, o.value) for o in outcomes if o.kind in (VALID_SET, CORRECTION)]
    if sets:
        for fid, val in sets:
            state.form_state[fid] = val
        actions.append({"type": "set_fields",
                        "fields": [{"field_id": fid, "value": val} for fid, val in sets]})
        # doc-22 dormant-set transparency: a value recorded onto a field whose schema
        # condition is NOT currently satisfied is DORMANT storage (by design, user ruling
        # 2026-08-05). Flag it so the reply can note it's recorded-but-not-required.
        # Directives only — placement/actions unchanged. One per dormant field, in order.
        seen_dormant = set()
        for fid, _ in sets:
            f = state.schema.field(fid)
            if f is not None and not is_active(f, state.form_state) and fid not in seen_dormant:
                seen_dormant.add(fid)
                directives.append(("dormant_set", fid))
    # clear pending if its field just got filled (held pending is never auto-cleared)
    p = state.pending
    if p and not p.held and p.target != CONFIRM_SUBMIT and state.is_filled(p.target):
        state.pending = None

    # --- step 3b: responsive choice (<=1 per turn) ---
    responsive_choice = False
    choices = [o for o in outcomes if o.kind == CHOICE_NEEDED]
    if choices:
        c = choices[0]
        actions.append(_ask_choice(state.schema.field(c.field_id), c.options))
        state.pending = Pending(c.field_id)
        responsive_choice = True
    clarified = any(o.kind == CLARIFY for o in outcomes)
    for o in outcomes:
        if o.kind == CLARIFY:
            directives.append(("clarify", o))

    # --- step 3c: review / save / submit intents ---
    if it.get("wants_review"):
        actions.append(_show_preview(state))
    if it.get("wants_save"):
        actions.append(_show_button("save_draft"))
    if it.get("wants_submit"):
        if not queue(state):
            if not any(a["type"] == "show_preview" for a in actions):
                actions.append(_show_preview(state))
            actions.append(_show_button("submit"))
            state.pending = Pending(CONFIRM_SUBMIT)
        else:
            # can't submit yet — offer a graceful save-or-continue, don't push the next field
            if not any(a["type"] == "show_button" for a in actions):
                actions.append(_show_button("save_draft"))
            directives.append(("submit_blocked", [f.field_id for f in queue(state)]))

    # --- step 5: agenda (proactive) ---
    a_actions, a_dirs = _agenda(state, prestep, responsive_choice, it, clarified)
    actions += a_actions
    directives += a_dirs
    return actions, directives


def _agenda(state: TurnState, prestep, responsive_choice: bool, it: dict, clarified: bool):
    # guards — don't push the next field when the user is pausing (save) or just
    # tried to submit (we offer save-or-continue instead of nagging the next field)
    # clarified: a CLARIFY answer is a competing thread, same as responsive_choice —
    # stand down; pending stays pending so the reask fires next quiet turn
    if prestep.hold or responsive_choice or clarified or it.get("wants_save") or it.get("wants_submit"):
        return [], []
    p = state.pending
    if p and p.target == CONFIRM_SUBMIT:
        return [], []
    if p and not state.is_filled(p.target):           # still open/unanswered
        return [], [("reask_pending", p.target)]       # re-assert in text only

    q = queue(state)
    if not q:                                          # terminal
        state.pending = Pending(CONFIRM_SUBMIT)
        return [_show_preview(state), _show_button("submit")], [("terminal", None)]

    nxt = q[0]
    state.pending = Pending(nxt.field_id)
    if nxt.button_choice:
        return [_ask_choice(nxt, nxt.options)], [("ask_target", nxt.field_id)]
    return [], [("ask_target", nxt.field_id)]           # free field / large select -> text ask


# ---- output serialization ------------------------------------------------

def serialize(text: str, actions: list[dict]) -> str:
    if not actions:
        return text
    return f"{text}\n\n---actions---\n```json\n{json.dumps(actions, indent=2)}\n```"
