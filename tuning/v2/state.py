"""Turn state — form_state, pending, queue (doc-18.1 "State objects").

All three are harness-owned. `pending` is NEVER injected into a model prompt
(doc-18.1): it is read only by the binding cascade, the agenda guards, and the
on-screen buttons.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from .schema import Schema, Field

CONFIRM_SUBMIT = "confirm_submit"


@dataclass
class Pending:
    """The single open question. `target` is a field_id or CONFIRM_SUBMIT.
    `held` is set by a validation-error fix directive to freeze the agenda."""
    target: str
    held: bool = False


@dataclass
class TurnState:
    schema: Schema
    form_state: dict = field(default_factory=dict)   # field_id -> canonical value
    pending: Pending | None = None

    def is_filled(self, fid: str) -> bool:
        return fid in self.form_state and self.form_state[fid] not in (None, "", [])

    def pending_field(self) -> Field | None:
        if self.pending and self.pending.target != CONFIRM_SUBMIT:
            return self.schema.field(self.pending.target)
        return None


def is_active(f: Field, form_state: dict) -> bool:
    """A conditional field is active only when its condition holds. v0's required
    fields are all unconditional, so this is exercised only once optional fields
    enter the agenda — but the logic is correct by construction."""
    c = f.condition
    if not c:
        return True
    val = form_state.get(c["field_id"])
    op = c.get("operator", "equals")
    if op == "equals":
        return val == c["value"]
    return True  # unknown operator -> don't gate


def queue(state: TurnState) -> list[Field]:
    """Unfilled, active, required fields in schema order — the agenda's worklist."""
    return [
        f for f in state.schema.fields
        if f.required and is_active(f, state.form_state) and not state.is_filled(f.field_id)
    ]
