"""M4 data-gen — hybrid generator: context farm + behavior injection (M4_PLAN P1).

Two layers, one training corpus (`{module, messages, completion}` pairs, the
same shape sim.py emits so P2's bridge is layer-agnostic):

  Layer 1 — context farm (multi-turn).  LLM-U <-> build_teacher(schema) run
  *natural* (always the "answer" directive). Per turn we log a snapshot
  {form_state, pending, history, user_message} BEFORE the forward() call and
  capture the natural turn as training pairs (source="farm", behavior="natural").

  Layer 2 — behavior injection (single-turn, quota-driven).  For each behavior in
  the registry: sample a farm snapshot whose preconditions hold (or build a
  minimal constructed context), template a message performing that behavior,
  optionally naturalize, run one forward(with_response=False), capture the
  extractor pair (source="inject", behavior=name).

ORACLE mode (--oracle, injection only): the injected row's extractor target comes
from the injection SPEC, not the teacher — the maker knows exactly which values it
inserted, so `make_oracle` returns (message, expected) and the prompt is rendered
offline (demo-stripped [system, user], byte-identical to a captured row). No LM call
per row; two build gates (harness round-trip + utterance support) and the behavior's
own sim_to_sft.CURATION rule are asserted on every label. With --naturalize the
rewrite passes `guard_naturalization` (no new question / no new hedging / no mutated
value), re-rolling up to 3 times then falling back to the raw template. Farm sessions
stay teacher-labeled, so --oracle with --farm is refused.

Leaf helpers are reused from sim.py (untouched): claude_p / render_screen / llm_u
/ STYLE_DESC (which transitively reuse render_persona, U_SYS, DIRECTIVES,
_parse_action). Capture path classifies each lm.history entry by CONTENT — module
from the system prompt's output field, adapter (chat vs json) from the final user
message's closing instruction — because DSPy 3.3.0b1's ChatAdapter silently RE-CALLS
the LM as a JSONAdapter when chat-parse fails, so one Predict can append TWO entries
(chat attempt + json retry). Consecutive same-module entries form one call chain
([chat] or [chat, json-retry]); we emit ONLY the chat entry as a training row
(the student's prompt format) and strip the teacher's few-shot demos from `messages`.

Teacher backend defaults to openrouter (the canonical nemotron teacher); override
with --backend claude / --model ID. The LLM-U (simulated user) always runs via the
claude CLI (sim.claude_p / llm_u) regardless of the teacher backend.

Run:
  selftest (free):   tuning/v2/.venv/bin/python -m tuning.v2.datagen --selftest
  parity  (free):    tuning/v2/.venv/bin/python -m tuning.v2.datagen --parity
  farm+inject ($$):  tuning/v2/.venv/bin/python -m tuning.v2.datagen --farm 5 --inject --quota 5 --run pilot
  inject only ($$):  tuning/v2/.venv/bin/python -m tuning.v2.datagen --inject --snapshots tuning/v2/datagen_runs/pilot/snapshots.jsonl
  oracle inject:     tuning/v2/.venv/bin/python -m tuning.v2.datagen --inject --oracle --naturalize \
                         --snapshots tuning/v2/datagen_runs/h1a/snapshots.jsonl --quota 25 --run r3_oracle
  claude teacher:    tuning/v2/.venv/bin/python -m tuning.v2.datagen --backend claude --farm 5 --inject --run pilot
Outputs (gitignored): tuning/v2/datagen_runs/<run>/{snapshots.jsonl,train.jsonl,report.json}
"""
from __future__ import annotations
import argparse
import json
import os
import random
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .schema import load_schema, Schema
from .state import TurnState, Pending, CONFIRM_SUBMIT, queue, is_active
from .program import build_teacher
from .claude_lm import ClaudeLM
from . import context
from . import persona as personas
from .sim import claude_p, render_screen, llm_u, STYLE_DESC, shown_button_labels
from .validator import coerce, match_options
# oracle-label support gate: reuse the probe's utterance-support logic verbatim
from .probe import _invention_check, _norm

RUN_DIR = Path(__file__).resolve().parent / "datagen_runs"
# Reference record for the parity anchor: the first extractor pair the old sim
# produced (same {messages, completion} shape we must reproduce).
REF_PATH = Path(__file__).resolve().parent / "sims" / "dryrun" / "train.jsonl"
BLOCK_ORDER = ["form_schema", "filled_fields", "recent_history", "user_message"]


# ======================================================================
# capture path (shared by both layers)
# ======================================================================

def strip_demos(messages: list[dict], module: str) -> list[dict]:
    """Drop any ChatAdapter demo pairs, keeping [system, user]. Active again as of
    2026-07-14: the teacher's extract now carries ONE compound demo, so the captured
    extractor renders as [system, demo_u, demo_a, user] (2 middle messages) and this
    strips that pair back to [system, user] — the student learns the behavior, not the
    crutch. The responder carries no demos and renders [system, user] already (no-op).
    A future multi-demo teacher (>1 pair) collapses the same way, module-agnostically."""
    assert len(messages) >= 2, f"expected >=2 messages, got {len(messages)}"
    n_mid = len(messages) - 2
    if module == "extractor" and n_mid not in (0, 2):
        print(f"[warn] extractor capture unexpected middle count={n_mid} "
              f"roles={[m['role'] for m in messages]}")
    stripped = [messages[0], messages[-1]]
    assert stripped[0]["role"] == "system", f"first role {stripped[0]['role']}"
    assert stripped[-1]["role"] == "user", f"last role {stripped[-1]['role']}"
    return stripped


# Content discriminators (validated: classifies all 48 pilot1 rows correctly).
# module   <- system prompt names the output field.
# adapter  <- final USER message's closing instruction: ChatAdapter ends "...with the
#             marker for [[ ## completed ## ]]"; JSONAdapter asks for a JSON object /
#             a "valid Python list[Extraction])". The JSON-retry entry keeps the same
#             system (so same module) but rewrites that closing instruction.
_CHAT_SIG = "ending with the marker for `[[ ## completed ## ]]`"
_JSON_SIGS = ("valid Python list[Extraction])", "JSON object in the following order")
_MARKERS = {"extractor": "[[ ## extractions ## ]]", "responder": "[[ ## response_text ## ]]"}


def classify_entry(messages: list[dict]) -> tuple[str, str]:
    """(module, adapter_format) for one lm.history entry, by CONTENT only. Looks at
    the system message (messages[0]) and the final user message (messages[-1]) so it
    is agnostic to attached demos. Returns "unknown" for either axis on no match."""
    sys = messages[0]["content"] if messages else ""
    usr = messages[-1]["content"] if messages else ""
    module = ("extractor" if "`extractions`" in sys else
              "responder" if "`response_text`" in sys else "unknown")
    fmt = ("chat" if _CHAT_SIG in usr else
           "json" if any(s in usr for s in _JSON_SIGS) else "unknown")
    return module, fmt


def is_well_formed(module: str, completion: str) -> bool:
    """Module-appropriate marker check on a CHAT completion (the extract/respond
    field marker plus the completed marker). Malformed chat is what makes the
    ChatAdapter fall back to a JSON retry."""
    m = _MARKERS.get(module)
    return bool(m) and m in completion and "[[ ## completed" in completion


def group_chains(entries: list[dict]) -> list[list[dict]]:
    """Consecutive entries of the SAME module = one Predict call chain
    ([chat] or [chat, json-retry]). A module change starts a new chain."""
    chains: list[list[dict]] = []
    for e in entries:
        if chains and chains[-1][-1]["module"] == e["module"]:
            chains[-1].append(e)
        else:
            chains.append([e])
    return chains


def _row_from_chain(chain: list[dict], base: dict) -> Optional[dict]:
    """One training row from a call chain — the CHAT entry only. JSON entries never
    become rows; a following json sibling is recorded as adapter_retried +
    retry_completion (chat and json attempts have been seen to disagree)."""
    module = chain[0]["module"]
    if module == "unknown":
        print(f"[warn] chain with UNKNOWN module — formats={[e['format'] for e in chain]}, dropping")
        return None
    chat = next((e for e in chain if e["format"] == "chat"), None)
    jsons = [e for e in chain if e["format"] == "json"]
    if any(e["format"] == "unknown" for e in chain):
        print(f"[warn] {module} chain has UNKNOWN-format entry — formats={[e['format'] for e in chain]}")
    if chat is None:
        print(f"[warn] {module} chain has NO chat entry (formats={[e['format'] for e in chain]}) — "
              f"no training row emitted")
        return None
    if len(chain) > 2 or len(jsons) > 1:
        print(f"[warn] {module} chain unexpected shape formats={[e['format'] for e in chain]}")
    messages = strip_demos(chat["messages"], module)
    completion = chat["completion"]
    return {**base, "module": module, "messages": messages, "completion": completion,
            "cost": chat["cost"], "well_formed": is_well_formed(module, completion),
            "adapter_retried": bool(jsons),
            "retry_completion": jsons[0]["completion"] if jsons else None}


def capture_pairs(lm, prev: int, with_response: bool, base: dict) -> tuple[list[dict], bool]:
    """Turn lm.history[prev:] into train rows via content classification + chain
    grouping. `base` carries the row's shared fields (source/behavior/session/turn/
    snapshot). Returns (rows, prestep_handled). prestep_handled == zero new entries."""
    entries = []
    for call in lm.history[prev:]:
        module, fmt = classify_entry(call.get("messages", []))
        entries.append({"messages": call.get("messages", []),
                        "completion": call["outputs"][0] if call.get("outputs") else "",
                        "cost": call.get("cost") or 0.0, "module": module, "format": fmt})
    chains = group_chains(entries)
    modules = [c[0]["module"] for c in chains]
    if not with_response and any(m == "responder" for m in modules):
        print(f"[warn] with_response=False slice has responder chain(s): modules={modules}")
    if with_response and chains and "responder" not in modules:
        print(f"[warn] with_response=True slice has NO responder chain: modules={modules}")
    rows = [r for r in (_row_from_chain(c, base) for c in chains) if r]
    return rows, len(entries) == 0


# ======================================================================
# parity anchor
# ======================================================================

def load_reference() -> dict:
    for line in open(REF_PATH):
        r = json.loads(line)
        if r.get("module") == "extractor":
            return r
    raise RuntimeError(f"no extractor row in reference {REF_PATH}")


def _block_indices(user_content: str) -> tuple[list[int], int]:
    return ([user_content.find(f"[[ ## {b} ## ]]") for b in BLOCK_ORDER],
            user_content.find("[[ ## completed ## ]]"))


def _blocks_ordered(user_content: str) -> bool:
    idx, comp = _block_indices(user_content)
    seq = idx + [comp]
    return all(i >= 0 for i in seq) and seq == sorted(seq)


def expected_extractor_system() -> str:
    """Offline ChatAdapter render of the CURRENT Extract signature's system prompt
    (no demos, no LM call) — the live-parity anchor. The captured extractor system
    must byte-equal this, which catches capture-path divergence while TOLERATING
    deliberate prompt evolution (the Extract docstring changes without breaking
    parity, unlike a frozen byte-reference to an old captured prompt)."""
    from dspy.adapters.chat_adapter import ChatAdapter
    from .program import Extract
    dummy = {f: "" for f in BLOCK_ORDER}   # system message is signature+demos only
    return ChatAdapter().format(Extract, [], dummy)[0]["content"]


def parity_check(train_row: dict, expected_system: str, wf_row: Optional[dict]) -> tuple[bool, dict]:
    """Compare a captured extractor CHAT pair against the current expectation. The
    system message must byte-equal `expected_system` (the offline ChatAdapter render
    of the live Extract signature); if it isn't, report the first differing line
    (don't crash). completion_markers is judged on the first WELL-FORMED extractor row
    (`wf_row`); if the whole run has none, that component is False +
    no_well_formed_extractor — a real signal, not a crash."""
    tr = train_row["messages"]
    detail: dict = {}
    detail["roles"] = [m["role"] for m in tr] == ["system", "user"]
    detail["system_byte_equal"] = tr[0]["content"] == expected_system
    if not detail["system_byte_equal"]:
        detail["first_diff"] = _first_diff(expected_system, tr[0]["content"])
    detail["block_order"] = _blocks_ordered(tr[-1]["content"])
    if wf_row is None:
        detail["completion_markers"] = False
        detail["no_well_formed_extractor"] = True
    else:
        detail["completion_markers"] = ("[[ ## extractions ## ]]" in wf_row["completion"]
                                         and "[[ ## completed ## ]]" in wf_row["completion"])
    passed = all(detail[k] for k in ("roles", "system_byte_equal", "block_order", "completion_markers"))
    return passed, detail


def _first_diff(ref: str, new: str) -> dict:
    a, b = ref.splitlines(), new.splitlines()
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return {"line": i, "ref": x, "new": y}
    return {"line": "length", "ref_lines": len(a), "new_lines": len(b)}


def run_parity(train_rows: list[dict]) -> dict:
    """Live parity: check the first captured extractor CHAT pair against the OFFLINE
    render of the current Extract signature (prompt structure), and completion markers
    on the first well-formed extractor row."""
    exts = [r for r in train_rows if r["module"] == "extractor"]
    if not exts:
        print("\n=== parity: no extractor pair captured — skipped ===")
        return {"pass": None, "detail": "no extractor pair captured"}
    ext = exts[0]
    wf = next((r for r in exts if r.get("well_formed")), None)
    passed, detail = parity_check(ext, expected_extractor_system(), wf)
    print(f"\n=== parity (live, first captured extractor vs offline render) ===")
    print(f"  parity: {'PASS' if passed else 'FAIL'}")
    for k, v in detail.items():
        print(f"    {k}: {v}")
    return {"pass": passed, "detail": detail}


def parity_offline() -> bool:
    """--parity CLI mode: offline structural checks that survive the demo retirement.
    No LLM call. The still-valid structural checks run on the old sim reference
    (roles / block order / completion markers on the reference itself); plus (a) the
    current Extract renders offline and lists `extractions`, and (b) build_teacher
    attaches ONE extract demo (the compound convention, back 2026-07-14). Demos DON'T
    change the offline-rendered system prompt (ChatAdapter renders them as separate
    message turns), so the parity anchor still holds."""
    teacher = build_teacher(load_schema())
    ref = load_reference()
    usr = ref["messages"][-1]["content"]
    try:
        expected = expected_extractor_system()
        render_ok = bool(expected) and "`extractions`" in expected
    except Exception as e:
        render_ok = False
        print(f"  [render error] {type(e).__name__}: {e}")
    checks = [
        ("offline ChatAdapter render of Extract succeeds + lists `extractions` output field", render_ok),
        ("build_teacher(load_schema()) has 1 extract demo (compound convention, back 2026-07-14)",
         len(teacher.extract.demos) == 1),
        ("reference roles == [system, user]", [m["role"] for m in ref["messages"]] == ["system", "user"]),
        ("reference user blocks in order form_schema<filled_fields<recent_history<user_message<completed",
         _blocks_ordered(usr)),
        ("reference completion has extractions + completed markers",
         "[[ ## extractions ## ]]" in ref["completion"] and "[[ ## completed ## ]]" in ref["completion"]),
    ]
    print("=== parity (offline reference structural checks) ===")
    allok = True
    for name, ok in checks:
        allok &= ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\nparity offline: {'all checks passed' if allok else 'SOME CHECKS FAILED'}")
    return allok


# ======================================================================
# Layer 1 — context farm
# ======================================================================

def farm_session(agent, lm, schema: Schema, seed: int, max_turns: int = 24,
                 mix: float = 0.0) -> dict:
    """One natural LLM-U <-> teacher session. Logs a per-turn snapshot before each
    forward() and captures the turn as training pairs. Farm turns are never
    naturalized (the U model already speaks naturally), so no naturalize param.

    mix: per-turn probability of drawing a non-answer LLM-U directive (chitchat/
    deflect/bulk) instead of "answer", for turns >= 1. mix=0 (default) preserves
    the original always-answer behavior."""
    rng = random.Random(seed)
    persona = personas.gen_persona(schema, rng)
    style = personas.gen_style(rng)
    state = TurnState(schema=schema, form_state={})
    history: list[dict] = []
    snapshots: list[dict] = []
    rows: list[dict] = []
    mixed_turns: list[dict] = []
    user_msg = ""
    teacher_cost = u_cost = 0.0
    turn = 0

    for turn in range(max_turns):
        snapshots.append({"session": seed, "turn": turn,
                          "form_state": dict(state.form_state),
                          "pending": state.pending.target if state.pending else None,
                          "history": list(history), "user_message": user_msg})

        prev = len(lm.history)
        pred = agent(state=state, user_message=user_msg, history=history)   # with_response=True
        base = {"source": "farm", "behavior": "natural", "session": seed,
                "turn": turn, "snapshot": None}
        new_rows, _ = capture_pairs(lm, prev, True, base)
        rows.extend(new_rows)
        teacher_cost += sum((c.get("cost") or 0.0) for c in lm.history[prev:])

        if user_msg:
            history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": pred.text})

        if state.pending and state.pending.target == CONFIRM_SUBMIT:
            break

        # Opening turn always engages the form; only later turns may be mixed.
        directive = "answer"
        if turn >= 1 and mix and rng.random() < mix:
            directive = rng.choices(["chitchat", "deflect", "bulk"],
                                    weights=[0.5, 0.25, 0.25])[0]
            mixed_turns.append({"turn": turn, "directive": directive})
            print(f"    [mix] turn={turn} directive={directive}", flush=True)

        buttons = shown_button_labels(pred)
        action, ucost = llm_u(schema, persona, style, render_screen(pred), directive)
        u_cost += ucost
        kind = action.get("action", "message")
        if kind == "stop":
            break
        elif kind == "select":
            # mirror of sim.run_session: a save/submit ACTION button -> click event
            label = action.get("label", "").strip()
            if label.lower() in buttons:
                user_msg = f"[system] User clicked: {label}"
            else:
                user_msg = f'[system] User selected option: "{label}"'
        else:
            user_msg = action.get("text", "").strip()
            if not user_msg:
                break

    return {"seed": seed, "style": style, "persona": persona, "turns": turn + 1,
            "filled": dict(state.form_state), "snapshots": snapshots, "rows": rows,
            "mixed_turns": mixed_turns,
            "teacher_cost": teacher_cost, "u_cost": u_cost}


# ======================================================================
# Layer 2 — behavior registry
# ======================================================================

@dataclass
class Behavior:
    """A behavior template. `make_oracle(snap, schema, rng)` returns
    (message, expected) where `expected` is the ORACLE extraction label — the
    designed convention for this behavior, known because the maker inserted the
    values itself (same authority as sim_to_sft.CURATION). The legacy path calls
    `make_message(...)`, which is the same draw with `expected` discarded, so a
    given (snap, rng state) yields the identical message either way."""
    name: str
    context: str                                   # "farm" | "constructed"
    precondition: Callable[[dict, Schema], bool]   # farm: filters snapshots
    make_oracle: Callable[[dict, Schema, random.Random], tuple]
    make_context: Optional[Callable[[Schema, random.Random], dict]] = None  # constructed only
    with_response: bool = False                    # True -> capture the RESPONDER turn too
                                                   # (responder-directive behaviors: submit_blocked,
                                                   # terminal_complete). Default extractor-only.

    def make_message(self, snap: dict, schema: Schema, rng: random.Random) -> str:
        return self.make_oracle(snap, schema, rng)[0]


def _date_phrase(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%B %-d, %Y")


def _persona_coverable(schema: Schema) -> set:
    """Field ids gen_persona populates (which keys is deterministic; only values
    depend on the rng) — the fields we can synthesize a replacement value for."""
    return set(personas.gen_persona(schema, random.Random(0)))


def _filled(snap: dict) -> dict:
    return {k: v for k, v in snap["form_state"].items() if v not in (None, "", [])}


def pf(snap: dict, schema: Schema):
    """The pending Field, or None (also None for confirm_submit — excluded everywhere)."""
    tgt = snap.get("pending")
    if not tgt or tgt == CONFIRM_SUBMIT:
        return None
    return schema.field(tgt)


def _pv(schema: Schema, persona: dict, fid: str) -> str:
    return context._display(schema, fid, persona[fid])


def _typed_value(schema: Schema, persona: dict, ftype: str) -> str:
    """A plausible value of the given free-text-ish type, drawn from a persona."""
    if ftype == "email":
        return persona["email"]
    if ftype == "phone":
        return persona["phone"]
    if ftype == "date":
        return _date_phrase(persona["dob"])
    return persona["full_name"]                    # text


# ---- preconditions -------------------------------------------------------

def _true(snap, schema):            # constructed contexts satisfy their own precondition
    return True


def _pre_pending(snap, schema):     # deflect / restraint / refusal / bulk
    return pf(snap, schema) is not None


def _pre_correction(snap, schema):
    cover = _persona_coverable(schema)
    return any(k in cover for k in _filled(snap))


def _pre_typed_choice(snap, schema):
    p = pf(snap, schema)
    return bool(p and p.button_choice)


def _pre_no_match(snap, schema):
    p = pf(snap, schema)
    return bool(p and p.is_choice)


def _pre_precedence(snap, schema):
    p = pf(snap, schema)
    return bool(p and p.type != "email")


_FREE_TYPES = {"text", "date", "phone", "email"}
_DISTINCTIVE = {"email", "phone"}


def _compound_other(snap, schema, ptype):
    filled = _filled(snap)
    for f in schema.fields:
        if f.required and f.field_id not in filled and f.type in _DISTINCTIVE and f.type != ptype:
            return f
    return None


def _pre_compound(snap, schema):
    p = pf(snap, schema)
    return bool(p and p.type in _FREE_TYPES and _compound_other(snap, schema, p.type))


# partial_select: field_id -> {term, phrases}. `term` is a normalized substring of
# >=2 option labels (verified against validator.match_options in selftest); phrases
# wrap that category term. Pending must be one of these choice fields.
_PARTIAL = {
    "program": {"term": "science",
                "phrases": ["a science program", "something science-related",
                            "one of the science tracks"]},
    "funding_type": {"term": "assistantship",
                     "phrases": ["an assistantship", "some kind of assistantship",
                                 "one of the assistantship options"]},
}


def _pre_partial(snap, schema):
    p = pf(snap, schema)
    return bool(p and p.is_choice and p.field_id in _PARTIAL)


# invalid_value: per-type uncoercible values (verified to FAIL validator.coerce in
# selftest). Wrapped in a sentence by the maker so the bare-value demotion guard
# (validate's _is_bare_value) does not fire.
_INVALID = {
    "date":  ["February 30, 1990", "the 32nd of Maypril", "sometime last autumn"],
    "phone": ["555-CALL", "just a sec, 12", "my old landline"],
    "email": ["jane dot doe at gmail dot com", "reach me on instagram", "jane@nowhere"],
}


def _pre_invalid(snap, schema):
    p = pf(snap, schema)
    return bool(p and p.type in _INVALID)


def _cross_candidates(snap, schema):
    """Unfilled button-choice selects (excluding booleans) other than the pending
    field — targets for a volunteered cross-field option label."""
    filled = _filled(snap)
    p = pf(snap, schema)
    pfid = p.field_id if p else None
    return [f for f in schema.fields
            if f.button_choice and f.type != "boolean"
            and f.field_id != pfid and f.field_id not in filled]


def _pre_cross(snap, schema):
    return bool(pf(snap, schema) and _cross_candidates(snap, schema))


# ---- message templates ---------------------------------------------------
# Every maker returns (message, expected_extractions). See Behavior.

def _pair(fid, value):
    return {"field_id": fid, "value": value}


def _mk_correction(snap, schema, rng):
    persona = personas.gen_persona(schema, rng)
    cands = [k for k in _filled(snap) if k in persona]
    f = schema.field(rng.choice(cands))
    val = _pv(schema, persona, f.field_id)
    msg = rng.choice([
        "Actually I need to fix something — my {l} should be {v}.",
        "Oh wait, let me correct that: my {l} is actually {v}.",
        "Sorry, I gave the wrong {l} earlier — it's {v}.",
    ]).format(l=f.label, v=val)
    return msg, [_pair(f.field_id, val)]


def _other_select(schema, exclude_fid, rng):
    return rng.choice([f for f in schema.fields if f.is_choice and f.field_id != exclude_fid])


def _mk_deflect(snap, schema, rng):
    other = _other_select(schema, pf(snap, schema).field_id, rng)
    msg = rng.choice([
        "Hold on — what are my choices for {l}?",
        "Before I answer, can you tell me the options for {l}?",
        "Wait, what can I pick for {l}?",
    ]).format(l=other.label)
    return msg, [_pair(other.field_id, "")]


def _other_free(schema, exclude_fid, rng):
    """A non-choice free field (text/date/phone/email) other than the pending one."""
    return rng.choice([f for f in schema.fields
                       if not f.is_choice and f.type in _FREE_TYPES and f.field_id != exclude_fid])


def _mk_deflect_free(snap, schema, rng):
    other = _other_free(schema, pf(snap, schema).field_id, rng)
    msg = rng.choice([
        "Hold on — what exactly do you need for {l}?",
        "Wait, what format should the {l} be in?",
        "Before I answer — what should I put for {l}?",
    ]).format(l=other.label)
    return msg, [_pair(other.field_id, "")]


def _mk_partial(snap, schema, rng):
    p = pf(snap, schema)
    spec = _PARTIAL[p.field_id]
    x = rng.choice(spec["phrases"])
    msg = rng.choice(["I'm thinking {x}.", "Probably {x}.", "{x}, I guess."]).format(x=x)
    # the CATEGORY TERM (not the whole phrase) is the value the options narrow on
    return msg, [_pair(p.field_id, spec["term"])]


def _mk_invalid(snap, schema, rng):
    p = pf(snap, schema)
    v = rng.choice(_INVALID[p.type])
    msg = rng.choice(["It's {v}.", "Sure — {v}.", "Oh, it's {v}."]).format(v=v)
    # transcription, not validation: the invalid surface IS the label (coerce fails downstream)
    return msg, [_pair(p.field_id, v)]


def _mk_cross(snap, schema, rng):
    f = rng.choice(_cross_candidates(snap, schema))
    _val, label = rng.choice(f.options)
    msg = rng.choice([
        "Oh — put me down for {label}.",
        "Actually, {label} please.",
        "Let's make it {label}.",
    ]).format(label=label)
    return msg, [_pair(f.field_id, str(label))]


_RESTRAINT_Q = [
    "Quick question first — how long does the review usually take?",
    "Before that, when is the application deadline?",
    "One thing — how long until I hear back after submitting?",
    "Actually, how many weeks does the whole process take?",
    "I think that's everything — can I submit now?",
    "Can I save this and finish later tonight?",
    "Can you show me a quick summary of what we have so far?",
]


def _mk_restraint(snap, schema, rng):
    return rng.choice(_RESTRAINT_Q), []


def _mk_refusal(snap, schema, rng):
    p = pf(snap, schema)
    msg = rng.choice([
        "I'd rather not give my {l} just yet, if that's okay.",
        "Can we skip my {l} for now? I'd prefer not to share it yet.",
        "I'm not comfortable giving my {l} at the moment.",
    ]).format(l=p.label)
    return msg, []


def _mk_typed_choice(snap, schema, rng):
    p = pf(snap, schema)
    _val, lab = rng.choice(p.options)
    low = str(lab).lower()
    msg = rng.choice([
        "{x} works for me", "let's go with {x}", "{x}, please", "i'll do {x}",
    ]).format(x=low)
    return msg, [_pair(p.field_id, low)]


_NO_MATCH = {
    "program": ["astronomy", "philosophy", "law"],
    "start_term": ["Summer 2028", "Winter 2029"],
    "enrollment_type": ["weekends only", "evenings only"],
    "gender": ["cyborg"],
    "how_heard": ["a skywriting plane", "my dentist"],
    "english_test_type": ["Duolingo", "PTE"],
    "country_citizenship": ["Atlantis", "Wakanda"],
    "country_residence": ["Atlantis", "Narnia"],
    "funding_type": ["a bake sale"],
}


def _mk_no_match(snap, schema, rng):
    p = pf(snap, schema)
    val = rng.choice(_NO_MATCH.get(p.field_id, ["something not on your list"]))
    msg = rng.choice(["I'd like {v}.", "Put me down for {v}.", "{v}, please."]).format(v=val)
    # transcription: the unlisted surface bound to the engaged field (no option matches)
    return msg, [_pair(p.field_id, val)]


def _mk_precedence(snap, schema, rng):
    email = personas.gen_persona(schema, rng)["email"]
    msg = rng.choice([
        "Oh — my email is {e}.", "Hang on, my email is {e}.",
        "By the way, the best email for me is {e}.",
    ]).format(e=email)
    return msg, [_pair("email", email)]


def _mk_compound(snap, schema, rng):
    p = pf(snap, schema)
    persona = personas.gen_persona(schema, rng)
    other = _compound_other(snap, schema, p.type)
    pval = _typed_value(schema, persona, p.type)
    oval = _typed_value(schema, persona, other.type)
    msg = f"{pval} — oh, and my {other.label} is {oval}."
    return msg, [_pair(p.field_id, pval), _pair(other.field_id, oval)]


def _mk_bulk(snap, schema, rng):
    persona = personas.gen_persona(schema, rng)
    msg = rng.choice([
        "While I'm at it: I'm {n}, {e}, {p}.",
        "Let me just give you a few things — {n}, reachable at {e} or {p}.",
        "Might as well: name's {n}, email {e}, phone {p}.",
    ]).format(n=persona["full_name"], e=persona["email"], p=persona["phone"])
    return msg, [_pair("full_name", persona["full_name"]),
                 _pair("email", persona["email"]), _pair("phone", persona["phone"])]


# ---- constructed contexts + their messages -------------------------------

def _empty_ctx(schema, rng):
    return {"form_state": {}, "pending": None, "history": []}


_ASK_SELECTS = ["start_term", "enrollment_type", "program", "gender", "how_heard"]


def _mk_asks(snap, schema, rng):
    f = schema.field(rng.choice(_ASK_SELECTS))
    msg = rng.choice([
        "What options do I have for {l}?",
        "Which choices are there for {l}?",
        "Can you list the {l} options?",
    ]).format(l=f.label)
    return msg, [_pair(f.field_id, "")]


_CHITCHAT = [
    "Man, this coffee is not kicking in today.",
    "Is it just me or is it freezing in here?",
    "My cat just knocked a plant off the windowsill, one sec.",
    "Long week already and it's only Tuesday.",
    "The traffic getting here was unreal.",
]


def _mk_chitchat(snap, schema, rng):
    return rng.choice(_CHITCHAT), []


def _mk_wrapped(snap, schema, rng):
    """A distractor-wrapped bare value. The value type is sampled uniformly across
    email / phone / dob (the eval wrapped a phone; training used to wrap only email)."""
    persona = personas.gen_persona(schema, rng)
    kind = rng.choice(["email", "phone", "dob"])
    if kind == "email":
        v = persona["email"]
        msg = rng.choice([
            "Sorry, hectic morning — anyway the best email for me is {v}.",
            "Kids are yelling in the background, ignore that — my email's {v}.",
            "Phone's about to die, quick: reach me at {v}.",
        ]).format(v=v)
    elif kind == "phone":
        v = persona["phone"]
        msg = rng.choice([
            "In line at the store — you can text me at {v}.",
            "Sorry, chaos here. Best number is {v}.",
        ]).format(v=v)
    else:
        v = _date_phrase(persona["dob"])
        msg = rng.choice([
            "Long day! Anyway, born {v} if you need it.",
            "Kids finally asleep — for the record I was born {v}.",
        ]).format(v=v)
    return msg, [_pair(kind, v)]


def _mk_third_party(snap, schema, rng):
    name = f"{rng.choice(personas.FIRST)} {rng.choice(personas.LAST)}"
    # the old "great campus" line was how_heard-adjacent (teacher bound how_heard on
    # it); the two neighbor rewrites stay third-person mentions with zero how-heard scent.
    msg = rng.choice([
        "My roommate {n} thinks these forms are endless.",
        "My neighbor {n} keeps asking how my application is going.",
        "{n}, my neighbor, is applying to a totally different school.",
        "Funny, my friend {n} applied here years ago.",
    ]).format(n=name)
    return msg, []


_TRAP_CITIES = ["Austin", "Portland", "Nashville", "Boise", "Tucson", "Raleigh"]

# narrative-embedded dates/numbers: values buried in a story that must NOT bind to
# any field (the message is not bare, so validate's demotion guard is irrelevant).
_TRAP_NARRATIVE = [
    "I've been at my current job since 2019 — time flies.",
    "My brother applied here back in March 2020.",
    "We've moved twice in the last 3 years.",
    "I graduated college over a decade ago, believe it or not.",
    "Our lease is up in 6 months, so the timing is tricky.",
]


def _mk_trap(snap, schema, rng):
    if rng.random() < 0.5:
        return rng.choice(_TRAP_NARRATIVE), []
    city = rng.choice(_TRAP_CITIES)
    msg = rng.choice([
        "We just moved to {c} — loving it so far.",
        "Grew up near {c}, great memories.",
        "Visiting {c} next month for a wedding.",
    ]).format(c=city)
    return msg, []


_BARE_NUMS = ["2019", "42", "7", "128", "2015", "3"]


def _mk_bare_ambiguous(snap, schema, rng):
    tok = rng.choice(_BARE_NUMS)
    return tok, [_pair(None, tok)]   # code owns binding: never a field from type alone


# NOT "August 10, 2000" / "August 3, 1990" — those are the eval/demo instances.
_BARE_DATES = ["June 12, 1994", "March 3, 1988", "November 20, 2001",
               "July 7, 1979", "January 15, 1998"]


def _mk_bare_date(snap, schema, rng):
    d = rng.choice(_BARE_DATES)
    return d, [_pair(None, d)]        # verbatim surface; the cascade places it


# Greeting lines with NO field ask (used by pending_bare / boolean_phrase to build
# the "history has a turn, but not the ask this answer belongs to" case). Kept
# question-free so there is unambiguously no field solicitation.
_GREETINGS = [
    "Welcome back! Let's continue your application.",
    "Good to see you again — let's pick up where we left off.",
    "Hi there, glad you're back. Let's keep going with your application.",
]


def _greet_history(rng):
    """[] (50%) or a single greeting assistant turn without any field ask (50%)."""
    return [] if rng.random() < 0.5 else [{"role": "assistant", "content": rng.choice(_GREETINGS)}]


# pending_bare: a bare persona value answering a pending field, with thin/no history
# (the H4 gap — training only ever showed pending answers WITH the ask in history).
# make_context RECORDS the pending field in the snapshot (rebuild_state reads "pending"),
# so make_message can emit that field's bare value.
_PENDING_BARE_FIELDS = ["full_name", "phone", "email", "dob"]


def _pending_bare_ctx(schema, rng):
    persona = personas.gen_persona(schema, rng)
    fid = rng.choice(_PENDING_BARE_FIELDS)
    pool = [k for k in _PENDING_BARE_FIELDS if k != fid]        # other persona-filled fields
    if rng.random() < 0.5:
        form_state = {}
    else:
        chosen = rng.sample(pool, rng.randint(2, 3))
        form_state = {c: persona[c] for c in chosen}
    return {"form_state": form_state, "pending": fid, "history": _greet_history(rng)}


def _mk_pending_bare(snap, schema, rng):
    f = schema.field(snap["pending"])
    persona = personas.gen_persona(schema, rng)
    val = _typed_value(schema, persona, f.type)
    msg = val + ("." if rng.random() < 0.5 else "")            # optional trailing period
    # null-fallback IS the convention: `pending` is never rendered, so the model
    # cannot attribute — the binding cascade owns placement (doc-18.1).
    return msg, [_pair(None, val)]


# boolean_phrase: natural yes/no phrasings for a pending boolean field that do NOT
# merely quote the "Yes"/"No" option label. value + phrase sampled together.
#
# SUPPORTABILITY RULE (2026-07-26): every phrase must NAME ITS OWN TOPIC. The context
# is a greeting with no field ask and `pending` is never rendered, so a phrase that
# doesn't self-identify ("I did take it last fall" — take WHAT?) carries a label the
# visible input cannot support. _BOOL_KEYWORDS below is the assertion the selftest runs.
_BOOLEAN_FIELDS = ["prior_application", "has_work_experience", "funding_interest", "gre_taken"]
_BOOL_KEYWORDS = {
    "prior_application": ("appl",),                    # applied / applying / application
    "has_work_experience": ("work",),                  # work / working / work experience
    "funding_interest": ("funding", "assistantship"),
    "gre_taken": ("gre",),
}
_BOOLEAN_PHRASES = {
    "prior_application": {
        True:  ["Yes — I applied once before.", "Yeah, I put in an application a couple years back."],
        False: ["Nope, first time applying.", "Never applied here before.",
                "No, this is my first time applying here."],
    },
    "has_work_experience": {
        True:  ["Yeah, I've been working for a few years.",
                "Yes, a few years of work experience in the field.",
                "I do — about five years of work experience."],
        False: ["No work experience — coming straight from undergrad.",
                "Not really, no work experience yet."],
    },
    "funding_interest": {
        True:  ["Yes, I'd love to hear about funding.", "Definitely interested in assistantships."],
        False: ["No interest in funding, I'm covered.", "Nah, I don't need any funding."],
    },
    "gre_taken": {
        True:  ["Yes — I took the GRE back in 2019, actually.", "I did take the GRE last fall."],
        False: ["No, I haven't taken the GRE.", "Nope, never sat for the GRE."],
    },
}


def _boolean_phrase_ctx(schema, rng):
    return {"form_state": {}, "pending": rng.choice(_BOOLEAN_FIELDS),
            "history": _greet_history(rng)}


def _mk_boolean_phrase(snap, schema, rng):
    val = rng.choice([True, False])
    msg = rng.choice(_BOOLEAN_PHRASES[snap["pending"]][val])
    return msg, [_pair(snap["pending"], "Yes" if val else "No")]


# compound_volunteer: TWO self-labeled values in one sentence (empty context), the
# pair varied across name+email / name+phone / email+phone / dob+phone.
_COMPOUND_PAIRS = [("full_name", "email"), ("full_name", "phone"),
                   ("email", "phone"), ("dob", "phone")]
_COMPOUND_TEMPLATES = {
    ("full_name", "email"): ["I'm {a} and you can reach me at {b}.",
                             "Name's {a}, email is {b}."],
    ("full_name", "phone"): ["Quick intro — {a}, cell {b}.",
                             "I'm {a}, and my number is {b}."],
    ("email", "phone"):     ["You can email me at {a} or call {b}.",
                             "Best email is {a}, and my phone's {b}."],
    ("dob", "phone"):       ["I was born {a}, and my number is {b}.",
                             "Date of birth {a}; phone is {b}."],
}


def _compound_pair_values(schema, persona, pair):
    a_fid, b_fid = pair
    return (_typed_value(schema, persona, schema.field(a_fid).type),
            _typed_value(schema, persona, schema.field(b_fid).type))


def _mk_compound_volunteer(snap, schema, rng):
    persona = personas.gen_persona(schema, rng)
    pair = rng.choice(_COMPOUND_PAIRS)
    a, b = _compound_pair_values(schema, persona, pair)
    msg = rng.choice(_COMPOUND_TEMPLATES[pair]).format(a=a, b=b)
    return msg, [_pair(pair[0], a), _pair(pair[1], b)]


# ---- responder-directive injection (doc-20 round 2): scarce submit_blocked / terminal --
# These are the FIRST with_response=True behaviors: their training value is the RESPONDER
# reply to a submit/completion turn, not an extraction. Both are hard-guarded to TRAINING
# snapshots only (seeds <=146); the frozen eval (147-161) and RL reserves (162-191) can
# never be selected, whatever --snapshots is pointed at.

TRAIN_SESSION_MAX = 146


def _train_only(snap: dict) -> bool:
    return snap.get("session", TRAIN_SESSION_MAX + 1) <= TRAIN_SESSION_MAX


# premature-submit user messages — each contains a prestep _SUBMIT trigger
# (submit / send it / finalize / turn it in) so wants_submit fires; with the queue
# non-empty, compose emits the submit_blocked directive.
_SUBMIT_MSGS = [
    "Can I just submit this now?",
    "I think I'm done — submit it, please.",
    "Okay, let's finalize and send it in.",
    "Ready to go — please submit my application.",
    "Are we all set? Go ahead and submit.",
    "I'd like to turn it in now.",
    "Can you send it off for me?",
    "I think that's everything — can I submit now?",
    "Let's submit — I'm ready to finalize.",
    "Just submit what we have so far, please.",
    "Can we submit this already?",
    "That's good enough — go ahead and submit.",
    "How do I submit? I think I'm finished.",
    "Alright, send it in.",
]


def _pre_submit_blocked(snap, schema):
    """A training snapshot with a non-empty required queue: a submit attempt here is
    premature, so compose -> submit_blocked."""
    return _train_only(snap) and len(queue(rebuild_state(schema, snap))) > 0


def _mk_submit_blocked(snap, schema, rng):
    return rng.choice(_SUBMIT_MSGS), []   # premature submit; no extraction


def _pre_terminal(snap, schema):
    """Filling the (choice) pending field would empty the queue — the pre-step select
    completes the form and the agenda declares terminal. This is the only offline,
    deterministic route to a terminal turn on these snapshots (the farm loop breaks at
    completion, so no snapshot is ever logged already at queue==0)."""
    if not _train_only(snap):
        return False
    st = rebuild_state(schema, snap)
    q = queue(st)
    pfd = st.pending_field()
    return len(q) == 1 and pfd is not None and pfd.is_choice and q[0].field_id == pfd.field_id


def _mk_terminal(snap, schema, rng):
    pfd = rebuild_state(schema, snap).pending_field()
    label = rng.choice([lab for _v, lab in pfd.options])
    return f'[system] User selected option: "{label}"', []


# ---- chitchat-steer-back probe (round-2 s2b failure class) --------------------
# The student answered a pleasantry while a field was pending and never steered back.
# This behavior injects social small-talk onto EVAL snapshots that carry a pending
# field: the empty extraction leaves pending open, so compose emits reask_pending, and
# the responder is expected to steer back. GUARD IS INVERTED vs the training behaviors —
# this selects ONLY the eval range (147-161); it must never touch training (<=146) or the
# RL reserves (>=162).

EVAL_SESSION_LO, EVAL_SESSION_HI = 147, 161


def _eval_only(snap: dict) -> bool:
    s = snap.get("session")
    return s is not None and EVAL_SESSION_LO <= s <= EVAL_SESSION_HI


# social small-talk aimed at the assistant; NO field values and NO prestep trigger words
# (save/pause/later/submit/finalize/review/summary/so far/progress) so the turn stays a
# pure pleasantry that leaves the pending field open.
_CHITCHAT_STEER = [
    "Hey there! How's your day going?",
    "You're really helpful, thank you!",
    "Lovely weather we're having, isn't it?",
    "Got any fun weekend plans?",
    "Hi again! Hope you're doing well.",
    "This is a nice little chat, honestly.",
    "You seem to really know your stuff!",
    "How are you doing today?",
    "It's been quite a week, hasn't it?",
    "I appreciate you walking me through all this.",
    "Are you having a good one today?",
    "Nice to be chatting with such a friendly assistant.",
    "Hope the sun is out where you are!",
    "You're doing a wonderful job, by the way.",
]


def _pre_chitchat_steer(snap, schema):
    """A snapshot whose pending field is present and still unfilled — an empty extraction
    leaves it open and compose emits reask_pending. Seed range (train <=146 / eval 147-161)
    is applied by the run-level --seed-range filter, same as the other both-mode behaviors,
    so this runs for BOTH probe (eval) and training (<=146) injection."""
    st = rebuild_state(schema, snap)
    p = st.pending_field()
    return p is not None and not st.is_filled(p.field_id)


def _mk_chitchat_steer(snap, schema, rng):
    return rng.choice(_CHITCHAT_STEER), []


# ---- round-3 both-mode behaviors -------------------------------------------
# No baked-in seed guard: they carry only their STRUCTURAL precondition, and the
# run-level seed-range filter (eligible_snaps seed_lo/hi, CLI --seed-range) scopes
# them to training (<=146) for data-gen or eval (147-161) for probes. One behavior,
# both modes, no duplication.

def _pending_unfilled(snap, schema):
    st = rebuild_state(schema, snap)
    p = st.pending_field()
    return p is not None and not st.is_filled(p.field_id)


def _pending_large_select_unfilled(snap, schema):
    st = rebuild_state(schema, snap)
    p = st.pending_field()
    return (p is not None and p.is_choice and not p.button_choice
            and not st.is_filled(p.field_id))


# (a) clarify_answer — a vague answer to a LARGE-select pending field that matches NO
# option -> validator CLARIFY -> compose clarify directive. (button choices give
# CHOICE_NEEDED, not clarify; large-select no-match is the clarify route.) The realized
# directive depends on the LIVE teacher extraction, so the probe builder must filter to
# cases where clarify actually fired.
_CLARIFY_ANSWER = [
    "Somewhere in Scandinavia, I think.",
    "A small island nation, if that helps.",
    "Up in the north somewhere.",
    "One of the Gulf states.",
    "A country in central Europe.",
    "Hard to say — I've moved around a lot.",
    "Somewhere warm, near the equator.",
    "A little place you've probably never heard of.",
    "It's complicated — dual heritage, honestly.",
    "Somewhere in the Balkans.",
    "One of the smaller European ones.",
    "The old country, as my family calls it.",
]


def _mk_clarify_answer(snap, schema, rng):
    return rng.choice(_CLARIFY_ANSWER), []


# (b) validation_error — a [system] Validation error event (some carrying a (field: X)
# hint) at a pending state -> prestep FIX directive (deterministic; re-pends + holds).
def _mk_validation_error(snap, schema, rng):
    p = rebuild_state(schema, snap).pending_field()
    hint = p.field_id if p else None
    hinted = [
        "[system] Validation error: that value doesn't look right (field: {f}).",
        "[system] Validation error: please correct your entry (field: {f}).",
        "[system] Validation error: the value for {f} is invalid (field: {f}).",
    ]
    bare = [
        "[system] Validation error: the last entry couldn't be saved.",
        "[system] Validation error: something's off with that value.",
        "[system] Validation error: please re-enter that field.",
    ]
    if hint and rng.random() < 0.6:
        return rng.choice(hinted).format(f=hint), []
    return rng.choice(bare), []


# (c) save_draft — two realized paths: a clicked [system] event -> prestep ACK (the
# agenda then re-asks the still-pending field, so ack + reask_pending); a plain
# "save & finish later" -> wants_save intent -> show_button(save_draft) action and the
# agenda stands down (respond naturally, no directive).
_SAVE_DRAFT_PLAIN = [
    "I'd like to save and finish this later.",
    "Can we pause here and come back to it later?",
    "Let me save my progress and pick this up later.",
    "I need to stop for now — save it for later, please.",
]


def _mk_save_draft(snap, schema, rng):
    if rng.random() < 0.5:
        return "[system] User clicked: Save Draft", []
    return rng.choice(_SAVE_DRAFT_PLAIN), []


# (d) offform_question — a policy / off-form question at a pending state: the assistant
# should answer within what it knows (grounding) then steer back -> reask_pending. NO
# prestep trigger words (no 'review'/'summary'/'save'/'later'/'submit'/'progress').
_OFFFORM_Q = [
    "Do you offer scholarships for veterans?",
    "How long does the application process take?",
    "Is there an interview stage?",
    "What's your acceptance rate?",
    "Do you provide visa support for international students?",
    "Are there evening or part-time class options?",
    "How much is tuition per year?",
    "Do you have on-campus housing?",
    "Is financial aid available for part-timers?",
    "What are the class sizes like?",
    "Do employers recognize this program?",
    "Are there any application fee waivers?",
]


def _mk_offform_question(snap, schema, rng):
    return rng.choice(_OFFFORM_Q), []


# (e) dormant_value — the user VOLUNTEERS a value for a condition-INACTIVE field
# (english_test_score before toefl_required=True; prior_application_year when the user
# hasn't said they applied before). The validator sets it anyway (dormant storage) and
# compose emits dormant_set. Natural volunteering; no prestep trigger words.
_DORMANT_FIELDS = ("english_test_score", "prior_application_year")
_DORMANT_MSGS = {
    "english_test_score": [
        "oh and my TOEFL score is 100",
        "by the way, I got a 105 on the TOEFL",
        "my TOEFL came back at 98, if that helps",
        "just so you have it, I scored 110 on the TOEFL",
    ],
    "prior_application_year": [
        "by the way I applied back in 2015",
        "oh, I actually applied once before, in 2018",
        "I think I first applied in 2016",
        "just so you know, I applied previously in 2019",
    ],
}


def _dormant_targets(snap, schema):
    """Condition-INACTIVE, unfilled fields the user could volunteer a value for."""
    st = rebuild_state(schema, snap)
    return [fid for fid in _DORMANT_FIELDS
            if schema.field(fid) is not None and not st.is_filled(fid)
            and not is_active(schema.field(fid), st.form_state)]


def _pre_dormant_value(snap, schema):
    return len(_dormant_targets(snap, schema)) > 0


def _mk_dormant_value(snap, schema, rng):
    fid = rng.choice(_dormant_targets(snap, schema))
    return rng.choice(_DORMANT_MSGS[fid]), []


REGISTRY = [
    Behavior("correction", "farm", _pre_correction, _mk_correction),
    Behavior("deflect", "farm", _pre_pending, _mk_deflect),
    Behavior("restraint_question", "farm", _pre_pending, _mk_restraint),
    Behavior("refusal", "farm", _pre_pending, _mk_refusal),
    Behavior("typed_choice", "farm", _pre_typed_choice, _mk_typed_choice),
    Behavior("no_match", "farm", _pre_no_match, _mk_no_match),
    Behavior("precedence", "farm", _pre_precedence, _mk_precedence),
    Behavior("compound", "farm", _pre_compound, _mk_compound),
    Behavior("bulk", "farm", _pre_pending, _mk_bulk),
    Behavior("deflect_free", "farm", _pre_pending, _mk_deflect_free),
    Behavior("partial_select", "farm", _pre_partial, _mk_partial),
    Behavior("invalid_value", "farm", _pre_invalid, _mk_invalid),
    Behavior("cross_select", "farm", _pre_cross, _mk_cross),
    Behavior("asks_about_field", "constructed", _true, _mk_asks, _empty_ctx),
    Behavior("chitchat", "constructed", _true, _mk_chitchat, _empty_ctx),
    Behavior("wrapped_value", "constructed", _true, _mk_wrapped, _empty_ctx),
    Behavior("third_party", "constructed", _true, _mk_third_party, _empty_ctx),
    Behavior("trap", "constructed", _true, _mk_trap, _empty_ctx),
    Behavior("bare_ambiguous", "constructed", _true, _mk_bare_ambiguous, _empty_ctx),
    Behavior("bare_date", "constructed", _true, _mk_bare_date, _empty_ctx),
    Behavior("pending_bare", "constructed", _true, _mk_pending_bare, _pending_bare_ctx),
    Behavior("boolean_phrase", "constructed", _true, _mk_boolean_phrase, _boolean_phrase_ctx),
    Behavior("compound_volunteer", "constructed", _true, _mk_compound_volunteer, _empty_ctx),
    Behavior("submit_blocked", "farm", _pre_submit_blocked, _mk_submit_blocked, with_response=True),
    Behavior("terminal_complete", "farm", _pre_terminal, _mk_terminal, with_response=True),
    Behavior("chitchat_steer", "farm", _pre_chitchat_steer, _mk_chitchat_steer, with_response=True),
    # round-3 both-mode behaviors (structural precondition only; seed range via CLI)
    Behavior("clarify_answer", "farm", _pending_large_select_unfilled, _mk_clarify_answer, with_response=True),
    Behavior("validation_error", "farm", _pending_unfilled, _mk_validation_error, with_response=True),
    Behavior("save_draft", "farm", _pending_unfilled, _mk_save_draft, with_response=True),
    Behavior("offform_question", "farm", _pending_unfilled, _mk_offform_question, with_response=True),
    Behavior("dormant_value", "farm", _pre_dormant_value, _mk_dormant_value, with_response=True),
]


# ======================================================================
# Layer 2b — ORACLE labels (--oracle): the spec labels the row, not the teacher
# ======================================================================
# The maker knows exactly which values it inserted, so the extraction label is
# derivable without an LM call. Two build gates keep an oracle label honest:
#   (a) round-trip — the harness must be able to PROCESS the value
#       (validator.coerce for free fields / match_options for choices);
#   (b) support    — the value must be findable in the message the model sees
#       (probe._invention_check, the same utterance-support logic the probe uses).
# Values are the VERBATIM SURFACE form the user typed; code owns canonicalization
# (coerce turns "January 15, 1998" into 1998-01-15 downstream).

# Designed-invalid surfaces: the whole point is that the harness REJECTS them
# downstream, so gate (a) is inverted for these (selftest asserts they do NOT
# coerce / do NOT match an option).
_ORACLE_NO_ROUNDTRIP = {"no_match", "invalid_value"}
_HEDGE_RE = re.compile(r"should we|are we sure|maybe|i think|not sure|"
                       r"is that (ok|okay|right|alright)|do you think|would that work|"
                       r"perhaps|i guess", re.I)


def oracle_roundtrip_ok(schema: Schema, behavior: str, fid, value) -> bool:
    """Gate (a). A valued label the harness cannot process is a maker bug.
    Skipped for null-field / engagement pairs (nothing to bind) and for the
    designed-invalid behaviors."""
    if fid is None or str(value).strip() == "" or behavior in _ORACLE_NO_ROUNDTRIP:
        return True
    f = schema.field(fid)
    if f is None:
        return False
    if f.is_choice:
        hits = match_options(value, f)
        # partial_select deliberately narrows to a SUBSET (>=2 options); every other
        # choice behavior inserts an exact option label -> exactly one hit.
        return len(hits) >= 2 if behavior == "partial_select" else len(hits) == 1
    return coerce(str(value), f)[0]


def oracle_support_ok(schema: Schema, fid, value, msg: str) -> bool:
    """Gate (b). Is `value` findable in `msg`? Reuses probe._invention_check
    (email substring / phone digit-run / normalized text / date coerce-span).
    Booleans are UNCHECKED there and here ("Yes"/"No" is never the surface text);
    choices fall back to a normalized substring of the inserted label/term."""
    if str(value).strip() == "":
        return True
    f = schema.field(fid) if fid else None
    if f is None:
        return _norm(value) in _norm(msg)          # bare token / unplaced value
    if f.type == "boolean":
        return True
    if f.is_choice:
        return _norm(value) in _norm(msg)
    check = value
    if f.type == "date":
        ok, iso = coerce(str(value), f)
        if not ok:
            return _norm(value) in _norm(msg)      # uncoercible (invalid_value)
        check = iso                                 # _invention_check compares ISO
    verdict = _invention_check(schema, fid, check, [msg], {})
    return True if verdict is None else bool(verdict)


def check_oracle(schema: Schema, behavior: str, msg: str, expected: list) -> list[str]:
    """Both gates over one (message, oracle label). Returns problem strings ([] = ok)."""
    probs = []
    for p in expected:
        fid, val = p.get("field_id"), p.get("value", "")
        if not oracle_roundtrip_ok(schema, behavior, fid, val):
            probs.append(f"roundtrip {behavior} {fid}={val!r}")
        if not oracle_support_ok(schema, fid, val, msg):
            probs.append(f"support {behavior} {fid}={val!r} not in {msg!r}")
    return probs


def oracle_completion(expected: list) -> str:
    """The extractor CHAT completion for an oracle label — byte-format identical to
    the kept teacher completions (json.dumps defaults: ", " / ": " separators)."""
    return f"[[ ## extractions ## ]]\n{json.dumps(expected)}\n\n[[ ## completed ## ]]"


def render_extract_prompt(schema: Schema, snap: dict, user_message: str) -> list[dict]:
    """The demo-stripped [system, user] extractor prompt, rendered OFFLINE (no LM).
    Same machinery as the parity anchor (`expected_extractor_system`); verified
    byte-equal to captured h1b rows (system + every block before user_message)."""
    from dspy.adapters.chat_adapter import ChatAdapter
    from .program import Extract
    inputs = {"form_schema": context.render_schema(schema),
              "filled_fields": context.render_filled(schema, snap["form_state"]),
              "recent_history": context.render_history(snap["history"]),
              "user_message": user_message}
    msgs = ChatAdapter().format(Extract, [], inputs)
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user"], f"offline render roles {roles}"
    return [{"role": m["role"], "content": m["content"]} for m in msgs]


def guard_naturalization(raw_msg: str, nat_msg: str, expected: list,
                         schema: Schema) -> tuple[bool, str]:
    """Did the temp-0.8 rewrite change the SEMANTICS the oracle label asserts?
    Measured drift on round 2: 78/542 statement-shaped injections came back with a
    "?", 41/542 hedged ("Let's make it TOEFL." -> "should we go with TOEFL then?"),
    which no longer commits. Teacher labels self-corrected (the teacher labels the
    text it sees); an oracle label would sit on non-committal text, so reject.
    Only NEW drift counts — a raw template that already asks or hedges is fine."""
    if "?" in nat_msg and "?" not in raw_msg:
        return False, "question_added"
    if _HEDGE_RE.search(nat_msg) and not _HEDGE_RE.search(raw_msg):
        return False, "hedge_added"
    for p in expected:
        if not oracle_support_ok(schema, p.get("field_id"), p.get("value", ""), nat_msg):
            return False, "value_unsupported"
    return True, ""


def naturalize_guarded(raw: str, expected: list, schema: Schema, rng: random.Random,
                       tries: int = 3) -> tuple[str, float, dict]:
    """Naturalize under the guard: re-roll a rejected rewrite (fresh LM call) up to
    `tries` total, then FALL BACK to the raw template. Never drops the case, never
    keeps a mismatched (label, text) pair."""
    cost = 0.0
    stats = {"attempts": 0, "rejections": [], "fallback": False}
    for _ in range(tries):
        nat, c = naturalize_message(raw, schema, rng)
        cost += c
        stats["attempts"] += 1
        ok, reason = guard_naturalization(raw, nat, expected, schema)
        if ok:
            return nat, cost, stats
        stats["rejections"].append(reason)
    stats["fallback"] = True
    return raw, cost, stats


# ======================================================================
# Layer 2 — injection driver
# ======================================================================

def rebuild_state(schema: Schema, snap: dict) -> TurnState:
    tgt = snap.get("pending")
    return TurnState(schema=schema, form_state=dict(snap["form_state"]),
                     pending=Pending(tgt) if tgt else None)


def _seed_in_range(session, seed_lo, seed_hi) -> bool:
    if session is None:
        return seed_lo is None and seed_hi is None
    return (seed_lo is None or session >= seed_lo) and (seed_hi is None or session <= seed_hi)


def eligible_snaps(beh: Behavior, snapshots: list[dict], schema: Schema,
                   seed_lo: int | None = None, seed_hi: int | None = None) -> list[dict]:
    """Farm snapshots satisfying the behavior's precondition. confirm_submit is
    excluded everywhere (pf-based preconditions already exclude it; this covers
    the non-pending behaviors too). `seed_lo`/`seed_hi` are the run-level seed-range
    guard (CLI --seed-range): the both-mode behaviors carry no baked-in seed guard, so
    this scopes them to training (<=146) or eval (147-161). Default = no restriction."""
    return [s for s in snapshots
            if s.get("pending") != CONFIRM_SUBMIT and _seed_in_range(s.get("session"), seed_lo, seed_hi)
            and beh.precondition(s, schema)]


# Naturalizer LM: a SEPARATE OpenRouterLM from the teacher `lm` — the capture path
# slices the teacher's lm.history by position, so the naturalizer must never append
# to it. Lazily built (first --naturalize use) so --selftest/--parity stay offline.
# temp=0.8 for phrasing variety; 300 tokens is plenty for one short chat message.
# paid slug: the :free route was pulled 2026-07-20 (~$0.0001/call; free routes churn)
_NAT_MODEL = os.getenv("V2_NAT_MODEL", "tencent/hy3")
_nat_lm = None


def _naturalizer():
    global _nat_lm
    if _nat_lm is None:
        from .openrouter_lm import OpenRouterLM
        _nat_lm = OpenRouterLM(model=_NAT_MODEL, temperature=0.8, max_tokens=300)
    return _nat_lm


def naturalize_message(msg: str, schema: Schema, rng: random.Random) -> tuple[str, float]:
    style = personas.gen_style(rng)
    sys = ("Rephrase the user's message in the voice of this persona/style, keeping the same "
           "intent and any concrete values (names, emails, dates, numbers, option words). "
           "Reply with only the rephrased text — one short chat message.\n\n"
           f"Style: {style} — {STYLE_DESC[style]}.")
    lm = _naturalizer()
    out = lm(messages=[{"role": "system", "content": sys}, {"role": "user", "content": msg}])
    text = (out[0] if out else "").strip()
    cost = (lm.history[-1].get("cost") if lm.history else 0.0) or 0.0
    return (text or msg), cost


def oracle_row(schema: Schema, beh_name: str, snap: dict, snap_ref, msg: str,
               expected: list) -> dict:
    """One inject row labeled by the SPEC, no LM call. Same keys as a captured
    inject row (so the bridge/report stay layer-agnostic) plus label_source."""
    probs = check_oracle(schema, beh_name, msg, expected)
    assert not probs, f"oracle gate failure [{beh_name}]: {probs}"
    completion = oracle_completion(expected)
    assert is_well_formed("extractor", completion), f"oracle completion malformed: {completion!r}"
    from .sim_to_sft import CURATION, curation_passes, parse_extractions
    pairs = parse_extractions(completion)
    assert pairs is not None, f"oracle completion unparseable: {completion!r}"
    rule = CURATION.get(beh_name)
    assert rule is None or curation_passes(rule, pairs), \
        f"oracle label violates its own convention [{beh_name}/{rule}]: {pairs}"
    return {"source": "inject", "behavior": beh_name, "session": None, "turn": None,
            "snapshot": snap_ref, "module": "extractor",
            "messages": render_extract_prompt(schema, snap, msg),
            "completion": completion, "cost": 0.0, "well_formed": True,
            "adapter_retried": False, "retry_completion": None,
            "label_source": "oracle"}


def run_injection(agent, lm, schema: Schema, snapshots: list[dict], quota: int,
                  rng: random.Random, naturalize: bool, only: set[str] | None = None,
                  oracle: bool = False, quotas: dict | None = None,
                  seed_lo: int | None = None, seed_hi: int | None = None) -> dict:
    rows: list[dict] = []
    coverage: list[dict] = []
    inj_cost = nat_cost = 0.0
    prestep_handled = 0
    guard = {"attempts": 0, "rejections": Counter(), "fallbacks": 0, "cases": 0}

    for beh in REGISTRY:
        if only and beh.name not in only:   # restrict to named subset; coverage naturally excludes skipped
            continue
        q = (quotas or {}).get(beh.name, quota)
        if beh.context == "farm":
            eligible = eligible_snaps(beh, snapshots, schema, seed_lo, seed_hi)
            n_elig = len(eligible)
            if n_elig == 0:
                print(f"[WARN] behavior {beh.name!r}: ZERO eligible snapshots — "
                      f"recording gap of {q}, not skipping silently")
                coverage.append({"behavior": beh.name, "context": "farm", "eligible": 0,
                                 "produced": 0, "failed": 0, "quota": q, "gap": q})
                continue
            picks = [rng.choice(eligible) for _ in range(q)]   # with replacement if n_elig < q
        else:
            picks = [None] * q
            n_elig = None

        produced = failed = 0
        for pick in picks:
            try:   # a transient CLI failure must not kill the run — skip the case, keep going
                if beh.context == "farm":
                    snap = pick
                    snap_ref = {"session": snap["session"], "turn": snap["turn"]}
                else:
                    snap = beh.make_context(schema, rng)
                    snap_ref = None
                if oracle:
                    msg, expected = beh.make_oracle(snap, schema, rng)
                    if naturalize:
                        msg, c, st = naturalize_guarded(msg, expected, schema, rng)
                        nat_cost += c
                        guard["cases"] += 1
                        guard["attempts"] += st["attempts"]
                        guard["fallbacks"] += int(st["fallback"])
                        for reason in st["rejections"]:
                            guard["rejections"][reason] += 1
                    rows.append(oracle_row(schema, beh.name, snap, snap_ref, msg, expected))
                    produced += 1
                    continue

                msg = beh.make_message(snap, schema, rng)
                # never naturalize a [system] event — prestep matches it literally, and
                # rephrasing would break the terminal_complete select.
                if naturalize and not msg.startswith("[system]"):
                    msg, c = naturalize_message(msg, schema, rng)
                    nat_cost += c

                state = rebuild_state(schema, snap)
                prev = len(lm.history)
                wr = beh.with_response   # responder-directive behaviors capture the reply too
                agent(state=state, user_message=msg, history=snap["history"], with_response=wr)
                inj_cost += sum((c.get("cost") or 0.0) for c in lm.history[prev:])
                base = {"source": "inject", "behavior": beh.name,
                        "session": None, "turn": None, "snapshot": snap_ref}
                new_rows, ph = capture_pairs(lm, prev, wr, base)
                prestep_handled += ph
                rows.extend(new_rows)
                produced += len(new_rows)
            except Exception as e:
                failed += 1
                print(f"[warn] inject {beh.name}: {type(e).__name__}: {str(e)[:120]} — skipping case",
                      flush=True)

        coverage.append({"behavior": beh.name, "context": beh.context, "eligible": n_elig,
                         "produced": produced, "failed": failed, "quota": q,
                         "gap": max(0, q - produced)})

    out = {"rows": rows, "coverage": coverage, "prestep_handled": prestep_handled,
           "inject_teacher": inj_cost, "naturalizer": nat_cost}
    if oracle and naturalize:
        out["nat_guard"] = {**guard, "rejections": dict(guard["rejections"])}
    return out


# ======================================================================
# report
# ======================================================================

def build_report(schema, farm_summaries, snapshots, coverage, prestep_handled,
                 train_rows, costs, parity, args, nat_guard=None) -> dict:
    n_req = sum(1 for f in schema.fields if f.required)
    ms = Counter((r["source"], r["module"]) for r in train_rows)

    def _rate(module: str, field: str, want) -> dict:
        sub = [r for r in train_rows if r["module"] == module]
        hits = sum(1 for r in sub if r.get(field) == want)
        return {"n": len(sub), "hits": hits, "rate": round(hits / len(sub), 4) if sub else None}

    quality = {m: {"chat_malformed": _rate(m, "well_formed", False),
                   "adapter_retried": _rate(m, "adapter_retried", True)}
               for m in ("extractor", "responder")}
    rep_extra = {}
    if nat_guard is not None:
        rep_extra["naturalizer_guard"] = nat_guard
    n_oracle = sum(1 for r in train_rows if r.get("label_source") == "oracle")
    if n_oracle:
        rep_extra["oracle_rows"] = n_oracle
    return {
        "args": {"farm": args.farm, "inject": args.inject, "quota": args.quota,
                 "seed": args.seed, "max_turns": args.max_turns, "naturalize": args.naturalize,
                 "mix": args.mix, "oracle": getattr(args, "oracle", False),
                 "quotas": getattr(args, "quotas", "")},
        **rep_extra,
        "farm_sessions": [
            {"seed": s["seed"], "style": s["style"], "turns": s["turns"],
             "filled": len(s["filled"]), "required": n_req,
             "complete": len(s["filled"]) >= n_req,
             "mixed_turns": s.get("mixed_turns", [])} for s in farm_summaries],
        "snapshots": len(snapshots),
        "coverage": coverage,
        "zero_eligible": [c["behavior"] for c in coverage if c.get("eligible") == 0],
        "prestep_handled": prestep_handled,
        "pairs": {
            "total": len(train_rows),
            "by_module": dict(Counter(r["module"] for r in train_rows)),
            "by_source": dict(Counter(r["source"] for r in train_rows)),
            "by_source_module": {f"{s}/{m}": n for (s, m), n in sorted(ms.items())},
        },
        "quality": quality,
        "distinct_personas": len({s["persona"]["full_name"] for s in farm_summaries}),
        "cost": {**{k: round(v, 4) for k, v in costs.items()},
                 "total": round(sum(costs.values()), 4)},
        "parity": parity,
    }


def print_report(rep: dict, out: Path):
    print("\n=== datagen report ===")
    if rep["farm_sessions"]:
        print(f"farm sessions: {len(rep['farm_sessions'])}  (snapshots logged: {rep['snapshots']})")
        for s in rep["farm_sessions"]:
            done = "complete" if s["complete"] else f"{s['filled']}/{s['required']}"
            print(f"  seed={s['seed']} style={s['style']:9} turns={s['turns']:2} filled={done}")
        print(f"distinct applicants: {rep['distinct_personas']}")
    else:
        print(f"farm sessions: 0  (snapshots loaded: {rep['snapshots']})")

    if rep["coverage"]:
        print("\nper-behavior injection (produced / quota, eligible snapshots):")
        for c in rep["coverage"]:
            elig = "constructed" if c["eligible"] is None else f"elig={c['eligible']}"
            gap = f"  GAP={c['gap']}" if c["gap"] else ""
            fail = f"  failed={c['failed']}" if c.get("failed") else ""
            print(f"  {c['behavior']:18} {c['produced']:3}/{c['quota']:<3} {elig}{gap}{fail}")
        if rep["zero_eligible"]:
            print(f"  !! ZERO-eligible behaviors: {', '.join(rep['zero_eligible'])}")
        print(f"prestep_handled (no pair captured): {rep['prestep_handled']}")

    p = rep["pairs"]
    print(f"\ntraining pairs: {p['total']}  by_module={p['by_module']}  by_source={p['by_source']}")
    print(f"  by source/module: {p['by_source_module']}")
    if rep.get("oracle_rows"):
        print(f"  label_source=oracle rows: {rep['oracle_rows']} (no teacher call)")
    if rep.get("naturalizer_guard"):
        g = rep["naturalizer_guard"]
        print(f"naturalizer guard: {g['cases']} cases, {g['attempts']} LM attempts, "
              f"{g['fallbacks']} fell back to the raw template")
        print(f"  rejections by reason: {g['rejections'] or '{}'}")

    print("quality (captured CHAT rows):")
    for m, q in rep["quality"].items():
        mf, rt = q["chat_malformed"], q["adapter_retried"]
        def _fmt(d):
            return "n/a" if d["rate"] is None else f"{d['rate']:.1%} ({d['hits']}/{d['n']})"
        print(f"  {m:10} chat_malformed={_fmt(mf):18} adapter_retried={_fmt(rt)}")

    c = rep["cost"]
    print(f"\ncost: ${c['total']:.4f} total  (farm teacher ${c['farm_teacher']:.4f} + "
          f"farm U ${c['farm_u']:.4f} + inject teacher ${c['inject_teacher']:.4f} + "
          f"naturalizer ${c['naturalizer']:.4f})")

    pa = rep["parity"]
    print(f"\nparity: {pa['pass']}")
    print(f"\nwritten to {out}/")


# ======================================================================
# selftest (free, no LLM)
# ======================================================================

def selftest():
    schema = load_schema()
    rng = random.Random(0)

    # --- strip-demos: today's one-demo extractor [system, du, da, U] -> [system, U] ---
    four = [{"role": "system", "content": "S"},
            {"role": "user", "content": "du"}, {"role": "assistant", "content": "da"},
            {"role": "user", "content": "U"}]
    assert strip_demos(four, "extractor") == [four[0], four[-1]]   # one demo pair (mid=2)
    # generic: any number of demo pairs collapses to [system, user] (module-agnostic;
    # run as responder so the extractor-only n_mid sanity warning stays quiet)
    six = [{"role": "system", "content": "S"},
           {"role": "user", "content": "du1"}, {"role": "assistant", "content": "da1"},
           {"role": "user", "content": "du2"}, {"role": "assistant", "content": "da2"},
           {"role": "user", "content": "U"}]
    assert strip_demos(six, "responder") == [six[0], six[-1]]
    two = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]
    assert strip_demos(two, "responder") == two
    assert strip_demos(two, "extractor") == two          # no-demos extractor is legal (mid=0)

    # --- content classifier + chain grouping (the M4 capture rewrite) ---
    def _entry(module, fmt, completion, demos=False):
        field = "`extractions`" if module == "extractor" else "`response_text`"
        sysc = f"...respond with the output field {field} ..."
        if fmt == "chat":
            tail = ("Respond with the corresponding output fields, starting with the field "
                    f"{field}, and then ending with the marker for `[[ ## completed ## ]]`.")
        elif module == "extractor":
            tail = f"...(must be formatted as a valid Python list[Extraction])."
        else:
            tail = f"Respond with a JSON object in the following order of fields: {field}."
        usr = {"role": "user", "content": "[[ ## form_schema ## ]] ...\n\n" + tail}
        mid = ([{"role": "user", "content": "d"}, {"role": "assistant", "content": "d"}]  # one demo pair
               if demos and module == "extractor" else [])
        return {"messages": [{"role": "system", "content": sysc}] + mid + [usr],
                "outputs": [completion], "cost": 0.0}

    XC = "[[ ## extractions ## ]]\n[]\n\n[[ ## completed ## ]]"       # extract chat, well-formed
    XJ = '{"extractions": []}'                                        # extract json retry completion
    RCbad = "Got it, next question?"                                  # respond chat, malformed
    RJ = '{"response_text": "Got it, next question?"}'                # respond json retry completion

    class _FakeLM:
        def __init__(self, calls): self.history = calls

    def _cap(calls, with_response):
        return capture_pairs(_FakeLM(calls), 0, with_response, {"source": "t", "behavior": "b"})

    # classifier axes
    assert classify_entry(_entry("extractor", "chat", XC)["messages"]) == ("extractor", "chat")
    assert classify_entry(_entry("extractor", "json", XJ)["messages"]) == ("extractor", "json")
    assert classify_entry(_entry("responder", "chat", RCbad)["messages"]) == ("responder", "chat")
    assert classify_entry(_entry("responder", "json", RJ)["messages"]) == ("responder", "json")
    assert classify_entry([{"role": "system", "content": "x"}, {"role": "user", "content": "y"}]) == ("unknown", "unknown")
    assert is_well_formed("extractor", XC) and not is_well_formed("responder", RCbad)

    # scenario 1: [extract-chat] alone (with_response=False)
    rows, ph = _cap([_entry("extractor", "chat", XC, demos=True)], False)
    assert not ph and len(rows) == 1
    r = rows[0]
    assert r["module"] == "extractor" and [m["role"] for m in r["messages"]] == ["system", "user"]
    assert r["well_formed"] and not r["adapter_retried"] and r["retry_completion"] is None

    # scenario 2: [extract-chat, extract-json, respond-chat, respond-json] (with_response=True)
    rows, ph = _cap([_entry("extractor", "chat", XC, demos=True), _entry("extractor", "json", XJ),
                     _entry("responder", "chat", RCbad), _entry("responder", "json", RJ)], True)
    assert not ph and len(rows) == 2
    ext, res = rows
    assert (ext["module"], ext["adapter_retried"], ext["retry_completion"], ext["well_formed"]) == ("extractor", True, XJ, True)
    assert (res["module"], res["adapter_retried"], res["retry_completion"], res["well_formed"]) == ("responder", True, RJ, False)
    # JSON entries never become rows
    assert all(r["retry_completion"] != r["completion"] for r in rows)
    assert not any(r["completion"].strip().startswith("{") for r in rows)

    # scenario 3: [respond-chat, respond-json] (prestep-handled turn: no extractor)
    rows, ph = _cap([_entry("responder", "chat", RCbad), _entry("responder", "json", RJ)], True)
    assert not ph and len(rows) == 1 and rows[0]["module"] == "responder" and rows[0]["adapter_retried"]

    # scenario 4: [extract-chat, respond-chat] — no retries
    rows, ph = _cap([_entry("extractor", "chat", XC, demos=True), _entry("responder", "chat", RCbad)], True)
    assert len(rows) == 2 and not any(r["adapter_retried"] for r in rows)
    assert all(r["retry_completion"] is None for r in rows)

    # scenario 5: with_response=False slice [extract-chat, extract-json]
    rows, ph = _cap([_entry("extractor", "chat", XC, demos=True), _entry("extractor", "json", XJ)], False)
    assert len(rows) == 1 and rows[0]["module"] == "extractor" and rows[0]["adapter_retried"]
    assert rows[0]["retry_completion"] == XJ

    # prestep-handled turn == zero entries
    rows, ph = _cap([], True)
    assert ph and rows == []

    # classifier over ALL 48 real pilot1 rows (skip silently if gitignored file absent)
    pilot = Path(__file__).resolve().parent / "datagen_runs" / "pilot1" / "train.jsonl"
    if pilot.exists():
        expect = {("farm", "extractor"): ("responder", "chat"),
                  ("farm", "responder"): ("responder", "json"),
                  ("inject", "extractor"): ("extractor", "chat")}
        n = 0
        for line in open(pilot):
            row = json.loads(line)
            got = classify_entry(row["messages"])
            exp = expect[(row["source"], row["module"])]
            assert got == exp, f"pilot1 misclassify {row['source']}/{row['module']}: {got} != {exp}"
            n += 1
        assert n == 48, f"expected 48 pilot1 rows, got {n}"
        print(f"selftest: classified all {n} pilot1 rows against ground truth")

    # --- every registry behavior: precondition True on a satisfying snapshot,
    #     make_message non-empty; constructed -> minimal (state,history,message) shape ---
    def snap(form_state=None, pending=None, history=None, session=0):
        return {"session": session, "turn": 0, "form_state": form_state or {},
                "pending": pending, "history": history or [], "user_message": ""}

    # a state one required boolean short of complete (pending that boolean) — the only
    # terminal_complete-eligible shape: filling it empties the queue.
    def _synth_val(f):
        return (f.options[0][0] if f.is_choice else "x@e.com" if f.type == "email"
                else "2000-01-01" if f.type == "date" else "5551234567" if f.type == "phone"
                else 5 if f.type == "number" else "X")
    _last_bool = next(f for f in schema.fields if f.type == "boolean" and f.required)
    _near_complete = {f.field_id: _synth_val(f) for f in schema.fields
                      if f.required and f.field_id != _last_bool.field_id}

    farm_snaps = {
        "submit_blocked": snap(),                              # empty form -> queue non-empty
        "terminal_complete": snap(form_state=_near_complete, pending=_last_bool.field_id),
        "chitchat_steer": snap(pending="dob", session=150),    # EVAL session, pending unfilled
        "clarify_answer": snap(pending="country_citizenship"),  # pending LARGE select, unfilled
        "validation_error": snap(pending="dob"),
        "save_draft": snap(pending="dob"),
        "offform_question": snap(pending="dob"),
        "dormant_value": snap(pending="dob"),   # english_test_score/prior_application_year inactive

        "correction": snap(form_state={"full_name": "Maria Lee", "email": "m@e.com"}),
        "deflect": snap(pending="dob"),
        "restraint_question": snap(pending="dob"),
        "refusal": snap(pending="phone"),
        "typed_choice": snap(pending="enrollment_type"),
        "no_match": snap(pending="program"),
        "precedence": snap(pending="phone"),
        "compound": snap(pending="dob"),
        "bulk": snap(pending="dob"),
        "deflect_free": snap(pending="dob"),
        "partial_select": snap(pending="program"),
        "invalid_value": snap(pending="dob"),
        "cross_select": snap(pending="dob"),
    }
    for beh in REGISTRY:
        if beh.context == "farm":
            s = farm_snaps[beh.name]
            assert beh.precondition(s, schema), f"{beh.name}: precondition should hold"
            assert eligible_snaps(beh, [s], schema) == [s], f"{beh.name}: should be eligible"
        else:
            s = beh.make_context(schema, rng)
            assert set(s) >= {"form_state", "pending", "history"}, f"{beh.name}: ctx shape"
            # <=3 form_state fields: pending_bare pre-fills 2-3 persona fields; the rest are empty
            assert len(s["form_state"]) <= 3 and len(s["history"]) <= 2, f"{beh.name}: minimal ctx"
            assert beh.precondition(s, schema), f"{beh.name}: constructed precondition"
        msg = beh.make_message(s, schema, rng)
        assert isinstance(msg, str) and msg.strip(), f"{beh.name}: empty message"

    # --- precondition False cases ---
    by_name = {b.name: b for b in REGISTRY}
    assert not by_name["typed_choice"].precondition(snap(pending="full_name"), schema)  # not button_choice
    assert not by_name["correction"].precondition(snap(), schema)                       # empty form
    assert not by_name["precedence"].precondition(snap(pending="email"), schema)        # type X != email
    assert not by_name["no_match"].precondition(snap(pending="full_name"), schema)      # not a choice
    # confirm_submit excluded everywhere: pf None, and eligibility drops it even when fields are filled
    cs = snap(form_state={"email": "m@e.com"}, pending=CONFIRM_SUBMIT)
    assert pf(cs, schema) is None
    assert not by_name["deflect"].precondition(cs, schema)
    assert eligible_snaps(by_name["correction"], [cs], schema) == []

    # --- new-behavior data invariants (offline, no LLM) ---
    from .validator import match_options as _mo, coerce as _co
    # partial_select: every field's core term matches >=2 options
    for fid, spec in _PARTIAL.items():
        hits = _mo(spec["term"], schema.field(fid))
        assert len(hits) >= 2, f"partial_select {fid}: term {spec['term']!r} -> {len(hits)} hits (<2)"
    # invalid_value: every value actually FAILS coerce for its type
    for ftype, vals in _INVALID.items():
        f = next(fd for fd in schema.fields if fd.type == ftype)
        for v in vals:
            assert not _co(v, f)[0], f"invalid_value {ftype}: {v!r} should fail coerce"
    # deflect_free maker names a non-choice free field's label
    dm = by_name["deflect_free"].make_message(farm_snaps["deflect_free"], schema, rng)
    free_labels = {f.label for f in schema.fields if not f.is_choice and f.type in _FREE_TYPES}
    assert any(l in dm for l in free_labels), f"deflect_free names no free field: {dm!r}"
    # cross_select maker names an exact option label of a button-choice select
    cm = by_name["cross_select"].make_message(farm_snaps["cross_select"], schema, rng)
    opt_labels = {str(lab) for f in schema.fields if f.button_choice and f.type != "boolean"
                  for _v, lab in f.options}
    assert any(l in cm for l in opt_labels), f"cross_select names no option label: {cm!r}"

    # --- new constructed behaviors (pending_bare / boolean_phrase / compound_volunteer) ---
    pb = by_name["pending_bare"]
    for _ in range(20):
        s = pb.make_context(schema, rng)
        assert s["pending"] in _PENDING_BARE_FIELDS, f"pending_bare pending: {s['pending']!r}"
        assert len(s["history"]) in (0, 1), f"pending_bare history len {len(s['history'])}"
        if s["history"]:
            g = s["history"][0]
            assert g["role"] == "assistant" and "?" not in g["content"]   # greeting, no field ask
        assert pb.make_message(s, schema, rng).strip()

    bp = by_name["boolean_phrase"]
    for _ in range(20):
        s = bp.make_context(schema, rng)
        assert s["pending"] in _BOOLEAN_FIELDS, f"boolean_phrase pending: {s['pending']!r}"
        assert len(s["history"]) in (0, 1)
        m = bp.make_message(s, schema, rng)
        assert m.strip() and m not in ("Yes", "No"), f"boolean_phrase bare label: {m!r}"

    # compound_volunteer: every template carries both value slots, both render into the message
    cv_persona = personas.gen_persona(schema, random.Random(7))
    for pair, tmpls in _COMPOUND_TEMPLATES.items():
        a, b = _compound_pair_values(schema, cv_persona, pair)
        for t in tmpls:
            assert "{a}" in t and "{b}" in t, f"compound template missing slot: {t!r}"
            msg = t.format(a=a, b=b)
            assert a in msg and b in msg, f"compound values not both present: {msg!r}"
    cv = by_name["compound_volunteer"]
    for _ in range(10):
        assert cv.make_message(_empty_ctx(schema, rng), schema, rng).strip()

    # wrapped_value now spans email/phone/dob (email + phone via distinctive signatures)
    wv, seen = by_name["wrapped_value"], set()
    for _ in range(60):
        m = wv.make_message(_empty_ctx(schema, rng), schema, rng)
        seen.add("email" if "@" in m else "phone" if "555-" in m else "dob")
    assert {"email", "phone", "dob"} <= seen, f"wrapped_value kinds: {seen}"

    # third_party carries no how_heard scent
    tp = by_name["third_party"]
    for _ in range(40):
        m = tp.make_message(_empty_ctx(schema, rng), schema, rng).lower()
        assert "campus" not in m and "heard" not in m, f"third_party how_heard scent: {m!r}"

    # --- TurnState round-trip ---
    st = rebuild_state(schema, snap(form_state={"email": "m@e.com"}, pending="dob"))
    assert st.form_state == {"email": "m@e.com"} and st.pending.target == "dob"
    assert rebuild_state(schema, snap(pending=None)).pending is None

    oracle_selftest(schema, farm_snaps)

    print("selftest: all assertions passed")


# ---------------------------------------------------------------------------
# oracle-mode selftest (offline: no LM, no naturalizer, no teacher)
# ---------------------------------------------------------------------------

def oracle_selftest(schema: Schema, farm_snaps: dict):
    from .sim_to_sft import CURATION, curation_passes, parse_extractions
    by_name = {b.name: b for b in REGISTRY}

    # real h1a farm snapshots if present (gitignored), else the synthetic ones
    snap_path = RUN_DIR / "h1a" / "snapshots.jsonl"
    real = [json.loads(l) for l in open(snap_path)] if snap_path.exists() else []
    src = "h1a snapshots" if real else "synthetic snapshots"

    # 1. every behavior, many seeds: label satisfies its CURATION rule + both gates
    n_labels = 0
    for beh in REGISTRY:
        for seed in range(50):
            pick = random.Random(1000 + seed)
            if beh.context == "farm":
                pool = [s for s in real if beh.precondition(s, schema)] if real else []
                s = pick.choice(pool) if pool else farm_snaps[beh.name]
            else:
                s = beh.make_context(schema, pick)
            msg, expected = beh.make_oracle(s, schema, random.Random(2000 + seed))
            assert isinstance(msg, str) and msg.strip(), f"{beh.name}: empty message"
            assert isinstance(expected, list), f"{beh.name}: expected must be a list"
            # determinism: make_message is the same draw with `expected` discarded
            assert beh.make_message(s, schema, random.Random(2000 + seed)) == msg, \
                f"{beh.name}: make_message diverges from make_oracle"
            completion = oracle_completion(expected)
            assert is_well_formed("extractor", completion), f"{beh.name}: {completion!r}"
            pairs = parse_extractions(completion)
            assert pairs == expected, f"{beh.name}: completion round-trip {pairs} != {expected}"
            rule = CURATION.get(beh.name)
            assert rule is None or curation_passes(rule, pairs), \
                f"{beh.name}/{rule}: oracle label violates its own convention: {pairs}"
            probs = check_oracle(schema, beh.name, msg, expected)
            assert not probs, f"{beh.name}: {probs}"
            n_labels += 1
    print(f"oracle selftest: {n_labels} labels over {len(REGISTRY)} behaviors ({src}) "
          f"pass CURATION + round-trip + support")

    # designed-invalid behaviors: assert the harness REALLY rejects the surface
    for _ in range(20):
        rng = random.Random(7)
        m, exp = by_name["no_match"].make_oracle(farm_snaps["no_match"], schema, rng)
        f = schema.field(exp[0]["field_id"])
        assert match_options(exp[0]["value"], f) == [], f"no_match value matched an option: {exp}"
        m, exp = by_name["invalid_value"].make_oracle(farm_snaps["invalid_value"], schema, rng)
        f = schema.field(exp[0]["field_id"])
        assert not coerce(exp[0]["value"], f)[0], f"invalid_value coerced: {exp}"

    # 2. boolean_phrase phrase audit: every phrase self-identifies its field
    for fid, byval in _BOOLEAN_PHRASES.items():
        kws = _BOOL_KEYWORDS[fid]
        for val, phrases in byval.items():
            for ph in phrases:
                assert any(k in ph.lower() for k in kws), \
                    f"boolean_phrase {fid}/{val}: {ph!r} names no field keyword {kws}"
    assert set(_BOOLEAN_PHRASES) == set(_BOOL_KEYWORDS) == set(_BOOLEAN_FIELDS)

    # 3. naturalizer guard — canned cases, no LM
    toefl_exp = [{"field_id": "english_test_type", "value": "TOEFL"}]
    ok, why = guard_naturalization(
        "Let's make it TOEFL.",
        "um, so should we go with TOEFL then? like, are we sure that's the one we want to pick?",
        toefl_exp, schema)
    assert not ok and why == "question_added", (ok, why)
    ok, why = guard_naturalization("Let's make it TOEFL.", "hmm, maybe TOEFL.", toefl_exp, schema)
    assert not ok and why == "hedge_added", (ok, why)
    ok, why = guard_naturalization("Let's make it TOEFL.", "Ok cool, let's just do TOEFL.",
                                   toefl_exp, schema)
    assert ok and why == "", (ok, why)
    # value mutated (phone digits changed) -> rejected
    ph_exp = [{"field_id": "phone", "value": "(614) 555-5969"}]
    ok, why = guard_naturalization("My number is (614) 555-5969.",
                                   "My number is (614) 555-1234.", ph_exp, schema)
    assert not ok and why == "value_unsupported", (ok, why)
    ok, why = guard_naturalization("My number is (614) 555-5969.",
                                   "hey — so my cell is (614) 555-5969, ok!", ph_exp, schema)
    assert ok, (ok, why)
    # value dropped entirely -> rejected
    ok, why = guard_naturalization("My number is (614) 555-5969.", "I'll send my number later.",
                                   ph_exp, schema)
    assert not ok and why == "value_unsupported", (ok, why)
    # hedge ALREADY in the raw template (partial_select "I guess") is not new drift
    part_exp = [{"field_id": "program", "value": "science"}]
    ok, why = guard_naturalization("a science program, I guess.",
                                   "eh, a science program, I guess.", part_exp, schema)
    assert ok and why == "", (ok, why)
    # a question-shaped raw template stays legal when the rewrite keeps asking
    ok, why = guard_naturalization("Wait, what can I pick for Gender?",
                                   "hold on, what are the Gender options?",
                                   [{"field_id": "gender", "value": ""}], schema)
    assert ok, (ok, why)

    # 4. offline prompt render == the captured shape (structural parity)
    s = {"form_state": {"full_name": "Maria Lee"}, "pending": "dob", "history": []}
    msgs = render_extract_prompt(schema, s, "June 12, 1994")
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert msgs[0]["content"] == expected_extractor_system(), "offline system != parity anchor"
    assert _blocks_ordered(msgs[-1]["content"]), "offline user blocks out of order"

    # ...and byte-parity against a REAL captured h1b_merged inject row (gitignored ->
    # skipped when absent): same snapshot, same system message, same block framing.
    ref_run = RUN_DIR / "h1b_merged"
    if (ref_run / "train.jsonl").exists() and (ref_run / "snapshots.jsonl").exists():
        snaps = {(x["session"], x["turn"]): x
                 for x in (json.loads(l) for l in open(ref_run / "snapshots.jsonl"))}
        checked = 0
        for line in open(ref_run / "train.jsonl"):
            row = json.loads(line)
            if row["source"] != "inject" or not row.get("snapshot"):
                continue
            key = (row["snapshot"]["session"], row["snapshot"]["turn"])
            if key not in snaps:
                continue
            got = render_extract_prompt(schema, snaps[key], "PLACEHOLDER")
            assert got[0]["content"] == row["messages"][0]["content"], \
                f"oracle system != captured system (snapshot {key})"
            ref, new = row["messages"][-1]["content"], got[-1]["content"]
            i, j = ref.find("[[ ## user_message ## ]]"), new.find("[[ ## user_message ## ]]")
            assert i > 0 and j > 0 and ref[:i] == new[:j], \
                f"oracle user blocks differ before user_message (snapshot {key})"
            checked += 1
            if checked >= 25:
                break
        assert checked, "h1b_merged has inject rows but none resolved to a snapshot"
        print(f"oracle selftest: offline render byte-parity vs {checked} captured h1b_merged rows")
        # no inject row in the reference run is a responder row (oracle emits none)
        assert not any(json.loads(l)["module"] == "responder"
                       for l in open(ref_run / "train.jsonl")
                       if json.loads(l)["source"] == "inject")

    # 5. emitted row shape (oracle_row is the live emitter) + legacy rows carry no label_source
    row = oracle_row(schema, "bare_date", s, None, "June 12, 1994",
                     [{"field_id": None, "value": "June 12, 1994"}])
    assert row["label_source"] == "oracle" and row["module"] == "extractor"
    assert row["source"] == "inject" and row["session"] is None and row["turn"] is None
    assert row["well_formed"] and not row["adapter_retried"] and row["cost"] == 0.0
    assert row["completion"] == ('[[ ## extractions ## ]]\n'
                                '[{"field_id": null, "value": "June 12, 1994"}]\n\n'
                                '[[ ## completed ## ]]')
    legacy = _row_from_chain(
        [{"module": "extractor", "format": "chat", "messages":
          [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}],
          "completion": "[[ ## extractions ## ]]\n[]\n\n[[ ## completed ## ]]", "cost": 0.0}],
        {"source": "inject", "behavior": "chitchat"})
    assert "label_source" not in legacy, "legacy teacher row must not gain label_source"
    # a label violating its convention is a BUG -> raises
    try:
        oracle_row(schema, "chitchat", s, None, "nice weather",
                   [{"field_id": "dob", "value": "June 12, 1994"}])
        raise AssertionError("oracle_row accepted a convention-violating label")
    except AssertionError as e:
        assert "convention" in str(e) or "gate failure" in str(e), e

    # 6. --quotas parsing
    valid = {b.name for b in REGISTRY}
    assert parse_quotas("compound=75,wrapped_value=50, third_party=50 ,cross_select=43",
                        valid) == {"compound": 75, "wrapped_value": 50,
                                   "third_party": 50, "cross_select": 43}
    assert parse_quotas("", valid) == {}
    for bad in ("compund=75", "compound=x", "compound=-3"):
        try:
            parse_quotas(bad, valid)
            raise AssertionError(f"parse_quotas accepted {bad!r}")
        except ValueError:
            pass
    print("oracle selftest: guard / render / row shape / quotas all pass")

    # 7. responder-directive injection (doc-20 round 2): submit_blocked / terminal_complete
    from . import prestep
    from .validator import validate
    from .composer import compose
    reg = {b.name: b for b in REGISTRY}
    sb, tm = reg["submit_blocked"], reg["terminal_complete"]
    assert sb.with_response and tm.with_response, "responder behaviors must set with_response"

    def _snap(session, form_state, pending=None):
        return {"session": session, "turn": 0, "form_state": dict(form_state),
                "pending": pending, "history": [], "user_message": ""}

    # eligible-state selection: submit_blocked only on a NON-empty queue --------------
    empty_state = _snap(1, {})                     # nothing filled -> queue non-empty
    assert sb.precondition(empty_state, schema) is True
    # a fully-filled state -> queue empty -> submit_blocked must NOT fire
    full_fs = {f.field_id: (f.options[0][0] if f.is_choice else ("x@e.com" if f.type == "email"
               else "2000-01-01" if f.type == "date" else "5551234567" if f.type == "phone"
               else 5 if f.type == "number" else "X"))
               for f in schema.fields if f.required}
    full_state = _snap(1, full_fs)
    assert len(queue(rebuild_state(schema, full_state))) == 0
    assert sb.precondition(full_state, schema) is False, "submit_blocked fired on an empty queue"

    # the SUBMIT message actually drives compose -> submit_blocked (real harness) -------
    def _fires(snap, msg):
        st = rebuild_state(schema, snap)
        ps = prestep.run(msg, st)
        outs = [] if ps.handled else validate([], st, msg)
        _, dirs = compose(st, ps, outs)
        return {k for k, _ in dirs}
    for m in _SUBMIT_MSGS:
        assert "submit_blocked" in _fires(empty_state, m), f"no submit_blocked for {m!r}"

    # terminal_complete: fires only when the pending CHOICE is the last required field --
    # build a state one boolean short of complete, pending that boolean.
    last_bool = next(f for f in schema.fields if f.type == "boolean" and f.required)
    near_fs = {k: v for k, v in full_fs.items() if k != last_bool.field_id}
    near = _snap(1, near_fs, pending=last_bool.field_id)
    assert tm.precondition(near, schema) is True
    assert sb.precondition(near, schema) is True     # queue still non-empty until the select
    term_msg, _ = tm.make_oracle(near, schema, random.Random(0))
    assert term_msg.startswith("[system] User selected option:")
    assert "terminal" in _fires(near, term_msg), "terminal did not fire on the completing select"
    # a state with 2+ required missing -> terminal precondition False
    assert tm.precondition(empty_state, schema) is False

    # HARD GUARD: nothing selects sessions >= 147 (frozen eval / RL reserves) ----------
    for bad_sess in (147, 161, 162, 191):
        s = _snap(bad_sess, {})
        assert sb.precondition(s, schema) is False, f"submit_blocked selected session {bad_sess}"
        assert tm.precondition(_snap(bad_sess, near_fs, pending=last_bool.field_id), schema) is False
    mixed = [empty_state, near, _snap(147, {}), _snap(200, near_fs, pending=last_bool.field_id)]
    assert all(s["session"] <= TRAIN_SESSION_MAX for s in eligible_snaps(sb, mixed, schema))
    assert all(s["session"] <= TRAIN_SESSION_MAX for s in eligible_snaps(tm, mixed, schema))

    # injected rows carry the right base metadata (stub LM, offline) -------------------
    import dspy
    from .program import FormAssistant

    class _StubLM(dspy.BaseLM):
        def __init__(self):
            super().__init__(model="stub", cache=False)

        def forward(self, prompt=None, messages=None, **kw):
            from dataclasses import dataclass, field as _f

            @dataclass
            class _M:
                content: str
                role: str = "assistant"
                tool_calls = None
                reasoning_content = None

            @dataclass
            class _C:
                message: _M
                index: int = 0
                finish_reason: str = "stop"

            @dataclass
            class _R:
                choices: list
                model: str
                usage: dict = _f(default_factory=dict)
                _hidden_params: dict = _f(default_factory=dict)
            return _R(choices=[_C(_M("[[ ## response_text ## ]]\nOK\n\n[[ ## completed ## ]]"))],
                      model="stub", _hidden_params={"response_cost": 0.0})

    stub = _StubLM()
    dspy.configure(lm=stub)
    inj = run_injection(FormAssistant(), stub, schema, [empty_state], quota=2,
                        rng=random.Random(0), naturalize=False, only={"submit_blocked"})
    resp_rows = [r for r in inj["rows"] if r["module"] == "responder"]
    assert resp_rows, "submit_blocked injection produced no responder row"
    r0 = resp_rows[0]
    assert r0["source"] == "inject" and r0["behavior"] == "submit_blocked"
    assert r0["session"] is None and r0["turn"] is None
    assert r0["snapshot"] == {"session": 1, "turn": 0}, r0["snapshot"]
    print("responder-injection selftest: eligibility / directive-fires / session-guard / "
          "base-metadata all pass")

    # 8. chitchat_steer (round-2 s2b failure class) — now a both-mode behavior: structural
    # precondition only, seed range applied by the run-level --seed-range filter.
    cs_beh = reg["chitchat_steer"]
    assert cs_beh.with_response
    # structural precondition ignores the seed (works on train AND eval snapshots)
    eval_snap = _snap(150, {}, pending="dob")
    train_snap = _snap(5, {}, pending="dob")
    assert cs_beh.precondition(eval_snap, schema) is True
    assert cs_beh.precondition(train_snap, schema) is True
    for m in _CHITCHAT_STEER:
        assert not any(t in m.lower() for t in ("submit", "save", "later", "so far",
                       "review", "summary", "recap", "progress", "finalize", "pause")), \
            f"chitchat template has a prestep trigger word: {m!r}"
        assert "reask_pending" in _fires(eval_snap, m), f"no reask_pending for {m!r}"
    # a snapshot with NO pending field -> not eligible
    assert cs_beh.precondition(_snap(150, {}), schema) is False
    # seed-range guard via the run-level filter, BOTH directions
    train = [_snap(5, {}, pending="dob"), _snap(146, {}, pending="dob")]
    ev = [_snap(147, {}, pending="dob"), _snap(161, {}, pending="dob")]
    pool = train + ev + [_snap(170, {}, pending="dob")]
    assert eligible_snaps(cs_beh, pool, schema, None, 146) == train    # train scope (<=146)
    assert eligible_snaps(cs_beh, pool, schema, 147, 161) == ev        # eval scope (147-161)
    # submit_blocked / terminal_complete keep their baked train-only guard (UNTOUCHED):
    # both reject an EVAL (147) snapshot even when it is structurally eligible.
    assert reg["submit_blocked"].precondition(_snap(147, {}), schema) is False
    assert reg["terminal_complete"].precondition(
        _snap(147, near_fs, pending=last_bool.field_id), schema) is False
    print("chitchat_steer selftest: both-mode structural precondition / seed-range filter "
          "both directions / reask_pending fires / submit+terminal baked guards intact")

    # 9. round-3 both-mode behaviors: intended directive fires (real harness, stub
    # extraction), seed-range guard both directions, no accidental trigger words.
    def _fires_p(snap, msg, pairs):
        st = rebuild_state(schema, snap)
        ps = prestep.run(msg, st)
        outs = [] if ps.handled else validate(pairs, st, msg)
        a, d = compose(st, ps, outs)
        return {k for k, _ in d}, a

    _NO_TRIG = ("submit", "save", "later", "review", "summary", "recap", "progress",
                "so far", "pause", "finalize", "come back")

    ca, ve, sd, oq = reg["clarify_answer"], reg["validation_error"], reg["save_draft"], reg["offform_question"]

    # (a) clarify_answer — stub a non-matching value on the pending LARGE select -> CLARIFY
    ca_snap = _snap(150, {}, pending="country_citizenship")
    assert ca.precondition(ca_snap, schema) is True
    assert ca.precondition(_snap(150, {}, pending="enrollment_type"), schema) is False   # button != large
    d_ca, _ = _fires_p(ca_snap, "A small island nation, if that helps.",
                       [{"field_id": "country_citizenship", "value": "a small island nation"}])
    assert "clarify" in d_ca, d_ca
    for m in _CLARIFY_ANSWER:
        assert not any(t in m.lower() for t in _NO_TRIG), f"clarify template trigger word: {m!r}"

    # (b) validation_error — [system] event -> fix (deterministic, empty extraction)
    ve_snap = _snap(150, {}, pending="dob")
    ve_msg, _ = ve.make_oracle(ve_snap, schema, random.Random(0))
    assert ve_msg.startswith("[system] Validation error")
    d_ve, _ = _fires_p(ve_snap, ve_msg, [])
    assert "fix" in d_ve, d_ve

    # (c) save_draft — clicked -> ack (+ reask_pending); plain -> save_draft action, no directive
    sd_snap = _snap(150, {}, pending="dob")
    d_click, _ = _fires_p(sd_snap, "[system] User clicked: Save Draft", [])
    assert "ack" in d_click and "reask_pending" in d_click, d_click
    d_plain, a_plain = _fires_p(sd_snap, "I'd like to save and finish this later.", [])
    assert any(x["type"] == "show_button" and x["button"] == "save_draft" for x in a_plain), a_plain
    assert not d_plain, d_plain                                                     # agenda stands down

    # (d) offform_question — pending state -> reask_pending; no trigger words
    for m in _OFFFORM_Q:
        assert not any(t in m.lower() for t in _NO_TRIG), f"offform template trigger word: {m!r}"
    d_oq, _ = _fires_p(_snap(150, {}, pending="dob"), _OFFFORM_Q[0], [])
    assert "reask_pending" in d_oq, d_oq

    # seed-range guard BOTH directions (no baked guard -> eligible_snaps seed filter)
    for beh in (ca, ve, sd, oq):
        pend = "country_citizenship" if beh.name == "clarify_answer" else "dob"
        train = [_snap(5, {}, pending=pend), _snap(146, {}, pending=pend)]
        ev = [_snap(147, {}, pending=pend), _snap(161, {}, pending=pend)]
        pool = train + ev + [_snap(170, {}, pending=pend)]
        assert eligible_snaps(beh, pool, schema, None, 146) == train, f"{beh.name} train-scope"
        assert eligible_snaps(beh, pool, schema, 147, 161) == ev, f"{beh.name} eval-scope"
    print("round-3 both-mode selftest: clarify/validation_error/save_draft/offform fire intended "
          "directive / seed-range both directions / no trigger words all pass")

    # 10. dormant_value (doc-22): volunteering a value for a condition-INACTIVE field ->
    # validator SETS it (dormant storage) -> compose emits dormant_set.
    dv = reg["dormant_value"]
    assert dv.with_response
    # a snapshot where toefl_required is unset -> english_test_score is inactive+unfilled -> eligible
    dv_snap = _snap(150, {}, pending="dob")
    assert dv.precondition(dv_snap, schema) is True
    # if toefl_required=True is already set, english_test_score becomes ACTIVE; and if
    # prior_application=True, prior_application_year is active -> neither is dormant -> ineligible
    active_fs = {"toefl_required": True, "prior_application": True}
    assert dv.precondition(_snap(150, active_fs, pending="dob"), schema) is False
    dv_msg, _ = dv.make_oracle(dv_snap, schema, random.Random(0))
    assert not any(t in dv_msg.lower() for t in _NO_TRIG), f"dormant_value trigger word: {dv_msg!r}"
    # the validator actually SETS the volunteered value, and compose emits dormant_set
    d_dv, a_dv = _fires_p(dv_snap, "oh and my TOEFL score is 100",
                          [{"field_id": "english_test_score", "value": "100"}])
    assert "dormant_set" in d_dv, d_dv
    assert any(x["type"] == "set_fields" and any(fl["field_id"] == "english_test_score"
               for fl in x["fields"]) for x in a_dv), a_dv
    # seed-range guard both directions
    pool = ([_snap(5, {}, pending="dob"), _snap(146, {}, pending="dob")]
            + [_snap(147, {}, pending="dob"), _snap(161, {}, pending="dob")] + [_snap(170, {}, pending="dob")])
    assert eligible_snaps(dv, pool, schema, None, 146) == pool[:2]
    assert eligible_snaps(dv, pool, schema, 147, 161) == pool[2:4]
    print("dormant_value selftest: validator sets the inactive field / dormant_set fires / "
          "seed-range both directions / no trigger words all pass")


# ======================================================================
# CLI
# ======================================================================

def parse_quotas(spec: str, valid: set[str]) -> dict:
    """"name=N,name=N" -> {name: N}. Raises ValueError on a typo or a bad count, so
    one run can mirror an accumulated multi-run per-behavior total in one shot."""
    out: dict[str, int] = {}
    for part in (p.strip() for p in spec.split(",")):
        if not part:
            continue
        name, _, n = part.partition("=")
        name = name.strip()
        if name not in valid:
            raise ValueError(f"--quotas: unknown behavior name {name!r}\n"
                             f"valid names: {', '.join(sorted(valid))}")
        if not n.strip().isdigit():
            raise ValueError(f"--quotas: {name} needs a non-negative integer, got {n.strip()!r}")
        out[name] = int(n)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--farm", type=int, default=0, help="number of context-farm sessions")
    ap.add_argument("--inject", action="store_true", help="run behavior injection over the snapshots")
    ap.add_argument("--quota", type=int, default=5, help="injected cases per behavior")
    ap.add_argument("--run", default="pilot")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-turns", type=int, default=24)
    ap.add_argument("--mix", type=float, default=0.0,
                    help="per-turn probability of a non-answer LLM-U directive in farm sessions")
    ap.add_argument("--naturalize", action="store_true",
                    help="rephrase injected messages via OpenRouter (V2_NAT_MODEL)")
    ap.add_argument("--snapshots", default="", help="load snapshots.jsonl (when --farm 0 --inject)")
    ap.add_argument("--backend", choices=["claude", "openrouter"], default="openrouter",
                    help="teacher LM backend (default openrouter = canonical nemotron teacher)")
    ap.add_argument("--model", default="", help="override the model id passed to the backend LM")
    ap.add_argument("--behaviors", default="",
                    help="comma-separated behavior names — restrict injection to these; empty = all")
    ap.add_argument("--quotas", default="",
                    help="per-behavior quota overrides on top of --quota, e.g. "
                         "'compound=75,wrapped_value=50'")
    ap.add_argument("--oracle", action="store_true",
                    help="label injected rows from the injection spec (no teacher call). "
                         "Farm sessions are teacher-labeled, so --farm is not allowed.")
    ap.add_argument("--seed-range", choices=["train", "eval", "all"], default="all",
                    help="run-level seed guard for injection: train (<=146) / eval (147-161) / "
                         "all. The both-mode behaviors carry no baked-in guard; this scopes them.")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--parity", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if args.parity:
        parity_offline()
        return

    # validate --behaviors / --quotas before any LM construction/injection — fail fast on a typo
    valid = {b.name for b in REGISTRY}
    only = {b.strip() for b in args.behaviors.split(",") if b.strip()} or None
    if only:
        bad = sorted(only - valid)
        if bad:
            ap.error(f"unknown behavior name(s): {', '.join(bad)}\n"
                     f"valid names: {', '.join(sorted(valid))}")
    try:
        quotas = parse_quotas(args.quotas, valid)
    except ValueError as e:
        ap.error(str(e))
    if args.oracle:
        if args.farm:
            ap.error("--oracle labels INJECTED rows from the spec; farm sessions stay "
                     "teacher-labeled, so --oracle with --farm > 0 is not supported")
        if not args.inject:
            ap.error("--oracle only affects injection — pass --inject")

    schema = load_schema()
    rng = random.Random(args.seed)
    lm = agent = None
    if args.oracle:
        # No teacher at all: labels come from the injection spec, prompts are rendered
        # offline. (The naturalizer, if enabled, is still an LM — a separate one.)
        print("oracle mode: injected rows labeled from the injection spec (no teacher LM)",
              flush=True)
    else:
        import dspy
        # datagen generates training data, so it must use the canonical teacher
        # (openrouter nemotron) by default — unlike eval_score, which keeps claude for
        # legacy comparisons. The teacher LM only drives build_teacher; the LLM-U path
        # (sim.claude_p / llm_u) always uses the claude CLI regardless.
        if args.backend == "openrouter":
            from .openrouter_lm import OpenRouterLM
            lm = OpenRouterLM(model=args.model) if args.model else OpenRouterLM()
        else:
            lm = ClaudeLM(model=args.model) if args.model else ClaudeLM()
        dspy.configure(lm=lm)
        agent = build_teacher(schema)
        print(f"teacher backend={args.backend}  model={lm.model}", flush=True)

    if args.inject and not args.farm and not args.snapshots:
        ap.error("--inject with --farm 0 requires --snapshots PATH")

    out = RUN_DIR / args.run
    out.mkdir(parents=True, exist_ok=True)

    snapshots: list[dict] = []
    train_rows: list[dict] = []
    farm_summaries: list[dict] = []
    coverage: list[dict] = []
    prestep_handled = 0
    nat_guard = None
    costs = {"farm_teacher": 0.0, "farm_u": 0.0, "inject_teacher": 0.0, "naturalizer": 0.0}

    try:
        # Layer 1 — farm
        for i in range(args.farm):
            seed = args.seed + i
            print(f"[farm {i+1}/{args.farm}] seed={seed} ...", flush=True)
            try:
                s = farm_session(agent, lm, schema, seed, args.max_turns, args.mix)
            except Exception as e:
                print(f"  !! farm session failed: {type(e).__name__}: {str(e)[:160]} — skipping", flush=True)
                continue
            snapshots.extend(s["snapshots"])
            train_rows.extend(s["rows"])
            farm_summaries.append(s)
            costs["farm_teacher"] += s["teacher_cost"]
            costs["farm_u"] += s["u_cost"]

        # Layer 2 — injection
        if args.inject:
            if not args.farm:
                snapshots = [json.loads(l) for l in open(args.snapshots)]
                print(f"loaded {len(snapshots)} snapshots from {args.snapshots}", flush=True)
            _sr = {"train": (None, 146), "eval": (147, 161), "all": (None, None)}[args.seed_range]
            inj = run_injection(agent, lm, schema, snapshots, args.quota, rng, args.naturalize,
                                only, args.oracle, quotas, seed_lo=_sr[0], seed_hi=_sr[1])
            train_rows.extend(inj["rows"])
            coverage = inj["coverage"]
            prestep_handled = inj["prestep_handled"]
            nat_guard = inj.get("nat_guard")
            costs["inject_teacher"] += inj["inject_teacher"]
            costs["naturalizer"] += inj["naturalizer"]
    finally:
        # Write whatever was collected even if the run crashed mid-way — the farm
        # data is already paid for. try/finally re-raises the original exception,
        # so a failed run still exits non-zero.
        parity = run_parity(train_rows)
        with open(out / "snapshots.jsonl", "w") as f:
            for s in snapshots:
                f.write(json.dumps(s) + "\n")
        with open(out / "train.jsonl", "w") as f:
            for r in train_rows:
                f.write(json.dumps(r) + "\n")
        report = build_report(schema, farm_summaries, snapshots, coverage, prestep_handled,
                              train_rows, costs, parity, args, nat_guard)
        json.dump(report, open(out / "report.json", "w"), indent=2, default=str)
        print_report(report, out)


if __name__ == "__main__":
    main()
