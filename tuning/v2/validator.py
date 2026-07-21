"""Step 2 — Validate (doc-18.1). Turn raw extractor pairs into typed outcomes.

The extractor emits three pair forms:
  {"field_id": "email", "value": "x"}   attributed
  {"field_id": "program", "value": ""}  field engaged, no value
  {"field_id": None, "value": "1999"}   unplaced -> runs the binding cascade

All placement of unplaced values is done here, in code — `pending` never biases
the model (doc-18.1 "binding cascade").
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import re

from .schema import Field
from .state import TurnState

# Outcome kinds
VALID_SET = "VALID_SET"
CORRECTION = "CORRECTION"
CHOICE_NEEDED = "CHOICE_NEEDED"
CLARIFY = "CLARIFY"
DROPPED = "DROPPED"

_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%B %d %Y",
                 "%b %d, %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y"]


@dataclass
class Outcome:
    kind: str
    field_id: str | None = None
    value: object = None          # canonical value for SET/CORRECTION
    options: list | None = None   # [(value, label)] for CHOICE_NEEDED
    reason: str = ""              # for CLARIFY / DROPPED (logged)


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


# ---- type coercion -------------------------------------------------------

def coerce(value: str, f: Field):
    """Return (ok, canonical_value). Pure type/format check — no schema membership."""
    v = str(value).strip()
    if f.type in ("text", "textarea"):
        return (bool(v), v)
    if f.type == "email":
        return (bool(re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+$", v)), v)
    if f.type == "phone":
        digits = re.sub(r"\D", "", v)
        return (len(digits) >= 7, v)
    if f.type == "date":
        for fmt in _DATE_FORMATS:
            try:
                return (True, datetime.strptime(v, fmt).strftime("%Y-%m-%d"))
            except ValueError:
                continue
        return (False, v)
    if f.type == "number":
        try:
            n = float(v) if ("." in v) else int(v)
        except ValueError:
            return (False, v)
        if f.min is not None and n < f.min:
            return (False, v)
        if f.max is not None and n > f.max:
            return (False, v)
        return (True, n)
    return (False, v)


def match_options(value: str, f: Field) -> list[tuple]:
    """Return the option tuples a free-typed value matches (label/value, normalized,
    with substring containment for >=3-char queries). Drives the unique/ambiguous/
    no-match branches."""
    nv = _norm(value)
    if not nv:
        return []
    exact, partial = [], []
    for opt in f.options:
        val, label = opt
        nval, nlabel = _norm(val), _norm(label)
        if nv == nval or nv == nlabel:
            exact.append(opt)
        elif len(nv) >= 3 and (nv in nlabel or nlabel.startswith(nv) or nv in nval):
            partial.append(opt)
    return exact or partial


# ---- binding cascade (doc-18.1) -----------------------------------------

def _bind_unplaced(value: str, state: TurnState) -> str | None:
    """Place a {null, value} pair onto a field. Returns field_id or None (CLARIFY).
    Rule 2: pending whose type the value coerces to. Rule 3: the unique unfilled
    field of a *distinctive* type the value coerces to (text/textarea excluded —
    too permissive to disambiguate)."""
    pf = state.pending_field()
    if pf and not pf.is_choice and coerce(value, pf)[0]:
        return pf.field_id
    if pf and pf.is_choice and match_options(value, pf):
        return pf.field_id
    hits = [
        f for f in state.schema.fields
        if f.type not in ("text", "textarea")
        and not state.is_filled(f.field_id)
        and (match_options(value, f) if f.is_choice else coerce(value, f)[0])
    ]
    return hits[0].field_id if len(hits) == 1 else None


# ---- per-pair validation -------------------------------------------------

def _validate_pair(fid: str, value: str, state: TurnState) -> Outcome:
    f = state.schema.field(fid)
    if f is None:
        return Outcome(DROPPED, fid, reason="not in schema")

    set_kind = CORRECTION if state.is_filled(fid) else VALID_SET

    if str(value).strip() == "":  # field engaged, no value
        if f.button_choice:
            return Outcome(CHOICE_NEEDED, fid, options=f.options)
        if f.is_choice:               # large select -> ask them to type it
            return Outcome(CLARIFY, fid, reason="large select, ask for typed value")
        return Outcome(CLARIFY, fid, reason="empty value on free field")

    if f.is_choice:
        if f.is_multi:
            # multi_select: an EXPLICIT conjunction list (split on ',' '&' or the
            # word 'and') where EVERY part uniquely matches ONE option -> set them
            # ALL (value is a list, deduped, in order). Anything ambiguous (a part
            # with 0 or >=2 hits, e.g. a category word like "assistantship") falls
            # through to the single-select logic below, which narrows via CHOICE_NEEDED.
            parts = [p for p in re.split(r"\s*(?:,|&|\band\b)\s*", str(value)) if p.strip()]
            part_hits = [match_options(p, f) for p in parts]
            if parts and all(len(h) == 1 for h in part_hits):
                seen, vals = set(), []
                for h in part_hits:
                    v = h[0][0]
                    if v not in seen:
                        seen.add(v)
                        vals.append(v)
                return Outcome(set_kind, fid, value=vals)
        hits = match_options(value, f)
        if len(hits) == 1:
            return Outcome(set_kind, fid, value=hits[0][0])
        if len(hits) >= 2:
            return Outcome(CHOICE_NEEDED, fid, options=hits)   # small matched subset -> buttons ok
        if f.button_choice:
            return Outcome(CHOICE_NEEDED, fid, options=f.options)  # no match, small -> all buttons
        return Outcome(CLARIFY, fid, reason="no option matched (large select)")

    ok, canonical = coerce(value, f)
    if ok:
        return Outcome(set_kind, fid, value=canonical)
    return Outcome(CLARIFY, fid, reason=f"cannot coerce to {f.type}")


def _is_bare_value(user_message: str) -> bool:
    """True when the message is ONLY a value — a lone date (any _DATE_FORMATS form,
    same parse as coerce) or a bare number — with no other words. Surrounding
    whitespace and trailing punctuation ('.', '!', ',') are stripped first; any
    remaining words -> not bare. doc-18.1 "code owns placement": such a value must
    not be bound from its type alone, so we route it through the binding cascade."""
    s = user_message.strip().rstrip(".!,").strip()
    if not s:
        return False
    if re.match(r"^\d+(\.\d+)?$", s):
        return True
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(s, fmt)
            return True
        except ValueError:
            continue
    return False


def validate(pairs: list[dict], state: TurnState, user_message: str = "") -> list[Outcome]:
    """Run the cascade on unplaced pairs, then validate every attributed pair.

    doc-18.1 "code owns placement": when the message is bare-value-only (a lone date
    or number, no words tying it to a field), every pair's field_id is demoted to
    None BEFORE per-pair validation, so placement runs solely through the binding
    cascade (pending-of-type -> unique-distinctive-type -> else CLARIFY). This
    overrides the extractor's confident type-alone attribution in code. A nonsensical
    {field_id, ""} engagement pair demotes to {null, ""}, which the cascade fails
    cleanly (-> CLARIFY). `user_message` defaults to "" so pre-existing callers that
    pass only (pairs, state) keep working unchanged."""
    demote = _is_bare_value(user_message)
    outcomes: list[Outcome] = []
    for p in pairs:
        fid, value = p.get("field_id"), p.get("value", "")
        if demote:
            fid = None
        if fid is None:
            fid = _bind_unplaced(value, state)
            if fid is None:
                outcomes.append(Outcome(CLARIFY, None, value=value, reason="unplaced value"))
                continue
        outcomes.append(_validate_pair(fid, value, state))
    return outcomes
