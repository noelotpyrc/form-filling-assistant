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


def canon_phone(value) -> str:
    """Canonical phone form: digits only, keeping a leading '+' when the surface had
    one. '(415) 782-3311' -> '4157823311'; '+49 30 901820' -> '+4930901820'. Punctuation
    is a model/user quirk, not data — the form stores one shape."""
    v = str(value).strip()
    digits = re.sub(r"\D", "", v)
    return ("+" + digits) if v.startswith("+") else digits


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
        return (len(digits) >= 7, canon_phone(v))
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


# Common names for a listed option that neither its label nor its value contains, so
# normalized matching alone cannot reach it ("Britain" -> United Kingdom, doc-19 §5).
# Keyed by OPTION VALUE, so an alias can only fire on a field that carries that option
# — no cross-field misfire. An alias hit ranks like an exact hit.
# Deliberately absent: "holland" (the Netherlands is NOT an option; mapping it anywhere
# would file the applicant under the wrong country). "korea" needs no entry — it already
# reaches South Korea by substring containment.
_OPTION_ALIASES = {
    "UK": {"britain", "greatbritain", "england"},
    "US": {"america", "usa", "thestates", "unitedstatesofamerica"},
}


def match_options(value: str, f: Field) -> list[tuple]:
    """Return the option tuples a free-typed value matches (label/value, normalized,
    with substring containment for >=3-char queries, plus the option-value alias
    table). Drives the unique/ambiguous/no-match branches."""
    nv = _norm(value)
    if not nv:
        return []
    exact, partial = [], []
    for opt in f.options:
        val, label = opt
        nval, nlabel = _norm(val), _norm(label)
        if nv == nval or nv == nlabel or nv in _OPTION_ALIASES.get(val, ()):
            exact.append(opt)
        elif len(nv) >= 3 and (nv in nlabel or nlabel.startswith(nv) or nv in nval):
            partial.append(opt)
    return exact or partial


# ---- provenance gate (doc-18.1 "code owns provenance") -------------------
# One shared support test for the whole v2 stack: the validator's issue-#1 gate,
# probe.py's invention check, stress_invent's bucketing and datagen's oracle gate
# all call `value_supported`, so they cannot drift apart.

_DATE_WINDOW = 5          # longest date phrase in _DATE_FORMATS is 3-4 tokens
_EDGE_PUNCT = " \t\r\n.,;:!?()[]{}<>\"'“”‘’"


def _date_windows(user_message: str):
    """Every 1..5-token window of the message, as written and with edge punctuation
    trimmed ("1993." -> "1993", "(2 Feb 1993)" -> "2 Feb 1993"). Interior punctuation
    is preserved, so "March 3, 1994" survives whole."""
    tokens = str(user_message).split()
    seen = set()
    for i in range(len(tokens)):
        for n in range(1, _DATE_WINDOW + 1):
            if i + n > len(tokens):
                break
            win = " ".join(tokens[i:i + n])
            for cand in (win, win.strip(_EDGE_PUNCT)):
                if cand and any(ch.isdigit() for ch in cand) and cand not in seen:
                    seen.add(cand)
                    yield cand


def _date_supported(value, f: Field, user_message: str) -> bool:
    """A date is supported when some span of the message COERCES to the same ISO value.
    Never a raw substring: "January 15, 1998" -> "1998-01-15" is not one.

    The spans are found by asking `coerce` itself — a sliding token window, not a
    regex. A regex date-matcher is a second, silently drifting copy of `_DATE_FORMATS`:
    it once missed the day-first "2 Feb 1993" (`%d %b %Y`) that `coerce` accepts, and
    the gate dropped correct answers (v3 run, 2026-08-02). Any format `coerce` learns
    is now automatically supported."""
    ok, target = coerce(str(value), f)
    target = target if ok else str(value)
    for span in _date_windows(user_message):
        ok, c = coerce(span, f)
        if ok and c == target:
            return True
    return False


def value_supported(f: Field | None, value, user_message: str) -> bool:
    """Is `value` findable in THIS utterance? Type-aware, deterministic, no model.

    email     case-insensitive substring
    phone     the value's digit run appears in the message's digits
    date      a span in the message coerces to the same ISO date (never a substring)
    text      normalized ("[^a-z0-9]" stripped) substring
    f=None    text-style (an unplaced value is raw user text by construction)

    Choices, booleans and numbers are OUT OF SCOPE and answer True ("unchecked"):
    their value space is the schema, not the message, so a semantic value has no
    span to find. So does a value with no comparable content (a phone with no digits,
    a text that normalizes to nothing) — there is nothing to check. Callers reach this
    only for a NON-EMPTY value; `_validate_pair` routes the engagement pair
    (`{field, ""}`) through its own branch before the gate."""
    t = getattr(f, "type", None)
    if f is not None and (f.is_choice or t == "number"):
        return True
    if t == "email":
        v = str(value).lower()
        return (v.strip() or v) in str(user_message).lower()   # padding is not content
    if t == "phone":
        d = re.sub(r"\D", "", str(value))
        return (not d) or d in re.sub(r"\D", "", str(user_message))
    if t == "date":
        return _date_supported(value, f, user_message)
    nv = _norm(value)                       # text / textarea / unplaced
    return (not nv) or nv in _norm(user_message)


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

def _validate_pair(fid: str, value: str, state: TurnState, user_message: str = "") -> Outcome:
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

    # provenance: a free-text value the utterance does not carry is not the user's
    # (invented PII / a name copied forward off the persona) -> set nothing, leave the
    # field unfilled; pending stays pending so the agenda re-asks.
    if not value_supported(f, value, user_message):
        return Outcome(DROPPED, fid, reason="value not in message")

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
    pass only (pairs, state) keep working unchanged.

    doc-18.1 "code owns provenance" (2026-08-02): every non-choice valued pair must be
    supported by `user_message` (`value_supported`); an unsupported one is DROPPED —
    nothing set, pending untouched. Callers that pass no `user_message` therefore drop
    every free-text value, which is why the two model paths (program.py, serve.py) and
    the harnesses all pass it."""
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
            # provenance on the unplaced path: the message must carry the value either
            # as typed (text-style, which also covers a bound CHOICE — the only branch
            # `_validate_pair` leaves unchecked) or under the bound field's own type
            # test, since the extractor may hand back the CANONICAL form of a span the
            # user spelled differently ("August 10, 2000." -> "2000-08-10").
            f_bound = state.schema.field(fid)
            if not (value_supported(None, value, user_message)
                    or value_supported(f_bound, value, user_message)):
                outcomes.append(Outcome(DROPPED, fid, reason="value not in message"))
                continue
        outcomes.append(_validate_pair(fid, value, state, user_message))
    return outcomes
