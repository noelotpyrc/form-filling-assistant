"""Step 0 — Pre-step (doc-18.1). Handle what code can settle before any model call.

A `[system]` event is handled here and skips steps 1-2. A plain message is
scanned for additive lexical intents (save / submit / review) and still flows on
to the extractor.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re

from .state import TurnState, Pending
from .validator import Outcome, VALID_SET, match_options

# Directive kinds handed to the responder (doc-18.1 "Directives")
ACK = "ack"
FIX = "fix"

_SAVE = re.compile(r"\b(save|pause|come back|later|finish later|bookmark)\b", re.I)
_SUBMIT = re.compile(r"\b(submit|send it|finalize|turn it in|all done)\b", re.I)
_REVIEW = re.compile(r"\b(review|summary|recap|what (do|have) we|so far|progress)\b", re.I)


@dataclass
class PreStep:
    handled: bool = False              # True -> skip steps 1 & 2
    set_outcomes: list = field(default_factory=list)   # responsive sets from a [system] event
    directives: list = field(default_factory=list)     # (kind, payload) for the responder
    intents: dict = field(default_factory=dict)        # wants_save / wants_submit / wants_review
    repend: str | None = None          # field_id to re-pend (validation error)
    hold: bool = False                 # freeze the agenda this turn


def _sys_match(msg: str, label: str) -> str | None:
    m = re.match(rf"\[system\]\s*{label}\s*:?\s*(.*)", msg.strip(), re.I)
    return m.group(1).strip().strip('"') if m else None


def run(user_message: str, state: TurnState) -> PreStep:
    msg = user_message.strip()

    # --- [system] events: handle, skip 1-2 ---
    if msg.startswith("[system]"):
        opt = _sys_match(msg, r"User selected option")
        if opt is not None:
            pf = state.pending_field()
            if pf and pf.is_choice:
                hits = match_options(opt, pf)
                if not hits:
                    # unknown label = UI anomaly; never write an off-schema value
                    # (doc-18.1 'options come from the schema'). Leave pending open —
                    # the agenda's reask handles recovery.
                    return PreStep(handled=True)
                return PreStep(handled=True,
                               set_outcomes=[Outcome(VALID_SET, pf.field_id, value=hits[0][0])])
            return PreStep(handled=True)

        clicked = _sys_match(msg, r"User clicked")
        if clicked is not None:
            return PreStep(handled=True, directives=[(ACK, clicked)])

        verr = _sys_match(msg, r"Validation error")
        if verr is not None:
            # payload may carry a field hint: "...(field: start_term)"
            fm = re.search(r"field:\s*([a-z0-9_]+)", verr, re.I)
            fid = fm.group(1) if fm else (state.pending.target if state.pending else None)
            return PreStep(handled=True, directives=[(FIX, verr)], repend=fid, hold=True)

        # generic confirmation ([system] Draft saved., etc.)
        return PreStep(handled=True, directives=[(ACK, msg[len("[system]"):].strip())])

    # --- plain message: additive lexical intents, continue to extractor ---
    return PreStep(intents={
        "wants_save": bool(_SAVE.search(msg)),
        "wants_submit": bool(_SUBMIT.search(msg)),
        "wants_review": bool(_REVIEW.search(msg)),
    })
