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

Leaf helpers are reused from sim.py (untouched): claude_p / render_screen / llm_u
/ STYLE_DESC (which transitively reuse render_persona, U_SYS, DIRECTIVES,
_parse_action). Capture path classifies each lm.history entry by CONTENT — module
from the system prompt's output field, adapter (chat vs json) from the final user
message's closing instruction — because DSPy 3.3.0b1's ChatAdapter silently RE-CALLS
the LM as a JSONAdapter when chat-parse fails, so one Predict can append TWO entries
(chat attempt + json retry). Consecutive same-module entries form one call chain
([chat] or [chat, json-retry]); we emit ONLY the chat entry as a training row
(the student's prompt format) and strip the teacher's few-shot demos from `messages`.

Run:
  selftest (free):   tuning/v2/.venv/bin/python -m tuning.v2.datagen --selftest
  parity  (free):    tuning/v2/.venv/bin/python -m tuning.v2.datagen --parity
  farm+inject ($$):  tuning/v2/.venv/bin/python -m tuning.v2.datagen --farm 5 --inject --quota 5 --run pilot
  inject only ($$):  tuning/v2/.venv/bin/python -m tuning.v2.datagen --inject --snapshots tuning/v2/datagen_runs/pilot/snapshots.jsonl
Outputs (gitignored): tuning/v2/datagen_runs/<run>/{snapshots.jsonl,train.jsonl,report.json}
"""
from __future__ import annotations
import argparse
import json
import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .schema import load_schema, Schema
from .state import TurnState, Pending, CONFIRM_SUBMIT
from .program import build_teacher
from .claude_lm import ClaudeLM
from . import context
from . import persona as personas
from .sim import claude_p, render_screen, llm_u, STYLE_DESC

RUN_DIR = Path(__file__).resolve().parent / "datagen_runs"
# Reference record for the parity anchor: the first extractor pair the old sim
# produced (same {messages, completion} shape we must reproduce).
REF_PATH = Path(__file__).resolve().parent / "sims" / "dryrun" / "train.jsonl"
BLOCK_ORDER = ["form_schema", "filled_fields", "recent_history", "user_message"]


# ======================================================================
# capture path (shared by both layers)
# ======================================================================

def strip_demos(messages: list[dict], module: str) -> list[dict]:
    """Drop any ChatAdapter demo pairs, keeping [system, user]. Retained defensively:
    the teacher's extract demos were retired 2026-07-13 (build_teacher has 0 demos),
    so today both modules render as [system, user] and this is a no-op — but a future
    demo-carrying teacher would render [system, demo_u, demo_a, ..., user] and this
    keeps the student learning the behavior, not the crutch."""
    assert len(messages) >= 2, f"expected >=2 messages, got {len(messages)}"
    n_mid = len(messages) - 2
    if module == "extractor" and n_mid not in (0, 4):
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
    (roles / block order / completion markers on the reference itself); the demo-
    attachment check is replaced by (a) the current Extract renders offline and lists
    `extractions`, and (b) build_teacher has 0 demos attached (demos retired)."""
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
        ("build_teacher(load_schema()) has 0 extract demos (demos retired)", len(teacher.extract.demos) == 0),
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

def farm_session(agent, lm, schema: Schema, seed: int, max_turns: int = 24) -> dict:
    """One natural LLM-U <-> teacher session. Logs a per-turn snapshot before each
    forward() and captures the turn as training pairs. Farm turns are never
    naturalized (the U model already speaks naturally), so no naturalize param."""
    rng = random.Random(seed)
    persona = personas.gen_persona(schema, rng)
    style = personas.gen_style(rng)
    state = TurnState(schema=schema, form_state={})
    history: list[dict] = []
    snapshots: list[dict] = []
    rows: list[dict] = []
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

        action, ucost = llm_u(schema, persona, style, render_screen(pred), "answer")
        u_cost += ucost
        kind = action.get("action", "message")
        if kind == "stop":
            break
        elif kind == "select":
            user_msg = f'[system] User selected option: "{action.get("label", "")}"'
        else:
            user_msg = action.get("text", "").strip()
            if not user_msg:
                break

    return {"seed": seed, "style": style, "persona": persona, "turns": turn + 1,
            "filled": dict(state.form_state), "snapshots": snapshots, "rows": rows,
            "teacher_cost": teacher_cost, "u_cost": u_cost}


# ======================================================================
# Layer 2 — behavior registry
# ======================================================================

@dataclass
class Behavior:
    name: str
    context: str                                   # "farm" | "constructed"
    precondition: Callable[[dict, Schema], bool]   # farm: filters snapshots
    make_message: Callable[[dict, Schema, random.Random], str]
    make_context: Optional[Callable[[Schema, random.Random], dict]] = None  # constructed only


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


# ---- message templates ---------------------------------------------------

def _mk_correction(snap, schema, rng):
    persona = personas.gen_persona(schema, rng)
    cands = [k for k in _filled(snap) if k in persona]
    f = schema.field(rng.choice(cands))
    val = _pv(schema, persona, f.field_id)
    return rng.choice([
        "Actually I need to fix something — my {l} should be {v}.",
        "Oh wait, let me correct that: my {l} is actually {v}.",
        "Sorry, I gave the wrong {l} earlier — it's {v}.",
    ]).format(l=f.label, v=val)


def _other_select(schema, exclude_fid, rng):
    return rng.choice([f for f in schema.fields if f.is_choice and f.field_id != exclude_fid])


def _mk_deflect(snap, schema, rng):
    other = _other_select(schema, pf(snap, schema).field_id, rng)
    return rng.choice([
        "Hold on — what are my choices for {l}?",
        "Before I answer, can you tell me the options for {l}?",
        "Wait, what can I pick for {l}?",
    ]).format(l=other.label)


_RESTRAINT_Q = [
    "Quick question first — how long does the review usually take?",
    "Before that, when is the application deadline?",
    "One thing — how long until I hear back after submitting?",
    "Actually, how many weeks does the whole process take?",
]


def _mk_restraint(snap, schema, rng):
    return rng.choice(_RESTRAINT_Q)


def _mk_refusal(snap, schema, rng):
    p = pf(snap, schema)
    return rng.choice([
        "I'd rather not give my {l} just yet, if that's okay.",
        "Can we skip my {l} for now? I'd prefer not to share it yet.",
        "I'm not comfortable giving my {l} at the moment.",
    ]).format(l=p.label)


def _mk_typed_choice(snap, schema, rng):
    _val, lab = rng.choice(pf(snap, schema).options)
    low = str(lab).lower()
    return rng.choice([
        "{x} works for me", "let's go with {x}", "{x}, please", "i'll do {x}",
    ]).format(x=low)


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
    return rng.choice(["I'd like {v}.", "Put me down for {v}.", "{v}, please."]).format(v=val)


def _mk_precedence(snap, schema, rng):
    email = personas.gen_persona(schema, rng)["email"]
    return rng.choice([
        "Oh — my email is {e}.", "Hang on, my email is {e}.",
        "By the way, the best email for me is {e}.",
    ]).format(e=email)


def _mk_compound(snap, schema, rng):
    p = pf(snap, schema)
    persona = personas.gen_persona(schema, rng)
    other = _compound_other(snap, schema, p.type)
    pval = _typed_value(schema, persona, p.type)
    oval = _typed_value(schema, persona, other.type)
    return f"{pval} — oh, and my {other.label} is {oval}."


def _mk_bulk(snap, schema, rng):
    persona = personas.gen_persona(schema, rng)
    return rng.choice([
        "While I'm at it: I'm {n}, {e}, {p}.",
        "Let me just give you a few things — {n}, reachable at {e} or {p}.",
        "Might as well: name's {n}, email {e}, phone {p}.",
    ]).format(n=persona["full_name"], e=persona["email"], p=persona["phone"])


# ---- constructed contexts + their messages -------------------------------

def _empty_ctx(schema, rng):
    return {"form_state": {}, "pending": None, "history": []}


_ASK_SELECTS = ["start_term", "enrollment_type", "program", "gender", "how_heard"]


def _mk_asks(snap, schema, rng):
    f = schema.field(rng.choice(_ASK_SELECTS))
    return rng.choice([
        "What options do I have for {l}?",
        "Which choices are there for {l}?",
        "Can you list the {l} options?",
    ]).format(l=f.label)


_CHITCHAT = [
    "Man, this coffee is not kicking in today.",
    "Is it just me or is it freezing in here?",
    "My cat just knocked a plant off the windowsill, one sec.",
    "Long week already and it's only Tuesday.",
    "The traffic getting here was unreal.",
]


def _mk_chitchat(snap, schema, rng):
    return rng.choice(_CHITCHAT)


def _mk_wrapped(snap, schema, rng):
    email = personas.gen_persona(schema, rng)["email"]
    return rng.choice([
        "Sorry, hectic morning — anyway the best email for me is {e}.",
        "Kids are yelling in the background, ignore that — my email's {e}.",
        "Phone's about to die, quick: reach me at {e}.",
    ]).format(e=email)


def _mk_third_party(snap, schema, rng):
    name = f"{rng.choice(personas.FIRST)} {rng.choice(personas.LAST)}"
    return rng.choice([
        "My roommate {n} thinks these forms are endless.",
        "{n}, my neighbor, said this school has a great campus.",
        "Funny, my friend {n} applied here years ago.",
    ]).format(n=name)


_TRAP_CITIES = ["Austin", "Portland", "Nashville", "Boise", "Tucson", "Raleigh"]


def _mk_trap(snap, schema, rng):
    city = rng.choice(_TRAP_CITIES)
    return rng.choice([
        "We just moved to {c} — loving it so far.",
        "Grew up near {c}, great memories.",
        "Visiting {c} next month for a wedding.",
    ]).format(c=city)


_BARE_NUMS = ["2019", "42", "7", "128", "2015", "3"]


def _mk_bare_ambiguous(snap, schema, rng):
    return rng.choice(_BARE_NUMS)


# NOT "August 10, 2000" / "August 3, 1990" — those are the eval/demo instances.
_BARE_DATES = ["June 12, 1994", "March 3, 1988", "November 20, 2001",
               "July 7, 1979", "January 15, 1998"]


def _mk_bare_date(snap, schema, rng):
    return rng.choice(_BARE_DATES)


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
    Behavior("asks_about_field", "constructed", _true, _mk_asks, _empty_ctx),
    Behavior("chitchat", "constructed", _true, _mk_chitchat, _empty_ctx),
    Behavior("wrapped_value", "constructed", _true, _mk_wrapped, _empty_ctx),
    Behavior("third_party", "constructed", _true, _mk_third_party, _empty_ctx),
    Behavior("trap", "constructed", _true, _mk_trap, _empty_ctx),
    Behavior("bare_ambiguous", "constructed", _true, _mk_bare_ambiguous, _empty_ctx),
    Behavior("bare_date", "constructed", _true, _mk_bare_date, _empty_ctx),
]


# ======================================================================
# Layer 2 — injection driver
# ======================================================================

def rebuild_state(schema: Schema, snap: dict) -> TurnState:
    tgt = snap.get("pending")
    return TurnState(schema=schema, form_state=dict(snap["form_state"]),
                     pending=Pending(tgt) if tgt else None)


def eligible_snaps(beh: Behavior, snapshots: list[dict], schema: Schema) -> list[dict]:
    """Farm snapshots satisfying the behavior's precondition. confirm_submit is
    excluded everywhere (pf-based preconditions already exclude it; this covers
    the non-pending behaviors too)."""
    return [s for s in snapshots
            if s.get("pending") != CONFIRM_SUBMIT and beh.precondition(s, schema)]


def naturalize_message(msg: str, schema: Schema, rng: random.Random) -> tuple[str, float]:
    style = personas.gen_style(rng)
    sys = ("Rephrase the user's message in the voice of this persona/style, keeping the same "
           "intent and any concrete values (names, emails, dates, numbers, option words). "
           "Reply with only the rephrased text — one short chat message.\n\n"
           f"Style: {style} — {STYLE_DESC[style]}.")
    text, cost = claude_p(sys, msg)
    return (text.strip() or msg), cost


def run_injection(agent, lm, schema: Schema, snapshots: list[dict], quota: int,
                  rng: random.Random, naturalize: bool) -> dict:
    rows: list[dict] = []
    coverage: list[dict] = []
    inj_cost = nat_cost = 0.0
    prestep_handled = 0

    for beh in REGISTRY:
        if beh.context == "farm":
            eligible = eligible_snaps(beh, snapshots, schema)
            n_elig = len(eligible)
            if n_elig == 0:
                print(f"[WARN] behavior {beh.name!r}: ZERO eligible snapshots — "
                      f"recording gap of {quota}, not skipping silently")
                coverage.append({"behavior": beh.name, "context": "farm", "eligible": 0,
                                 "produced": 0, "failed": 0, "quota": quota, "gap": quota})
                continue
            picks = [rng.choice(eligible) for _ in range(quota)]   # with replacement if n_elig < quota
        else:
            picks = [None] * quota
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
                msg = beh.make_message(snap, schema, rng)
                if naturalize:
                    msg, c = naturalize_message(msg, schema, rng)
                    nat_cost += c

                state = rebuild_state(schema, snap)
                prev = len(lm.history)
                agent(state=state, user_message=msg, history=snap["history"], with_response=False)
                inj_cost += sum((c.get("cost") or 0.0) for c in lm.history[prev:])
                base = {"source": "inject", "behavior": beh.name,
                        "session": None, "turn": None, "snapshot": snap_ref}
                new_rows, ph = capture_pairs(lm, prev, False, base)
                prestep_handled += ph
                rows.extend(new_rows)
                produced += len(new_rows)
            except Exception as e:
                failed += 1
                print(f"[warn] inject {beh.name}: {type(e).__name__}: {str(e)[:120]} — skipping case",
                      flush=True)

        coverage.append({"behavior": beh.name, "context": beh.context, "eligible": n_elig,
                         "produced": produced, "failed": failed, "quota": quota,
                         "gap": max(0, quota - produced)})

    return {"rows": rows, "coverage": coverage, "prestep_handled": prestep_handled,
            "inject_teacher": inj_cost, "naturalizer": nat_cost}


# ======================================================================
# report
# ======================================================================

def build_report(schema, farm_summaries, snapshots, coverage, prestep_handled,
                 train_rows, costs, parity, args) -> dict:
    n_req = sum(1 for f in schema.fields if f.required)
    ms = Counter((r["source"], r["module"]) for r in train_rows)

    def _rate(module: str, field: str, want) -> dict:
        sub = [r for r in train_rows if r["module"] == module]
        hits = sum(1 for r in sub if r.get(field) == want)
        return {"n": len(sub), "hits": hits, "rate": round(hits / len(sub), 4) if sub else None}

    quality = {m: {"chat_malformed": _rate(m, "well_formed", False),
                   "adapter_retried": _rate(m, "adapter_retried", True)}
               for m in ("extractor", "responder")}
    return {
        "args": {"farm": args.farm, "inject": args.inject, "quota": args.quota,
                 "seed": args.seed, "max_turns": args.max_turns, "naturalize": args.naturalize},
        "farm_sessions": [
            {"seed": s["seed"], "style": s["style"], "turns": s["turns"],
             "filled": len(s["filled"]), "required": n_req,
             "complete": len(s["filled"]) >= n_req} for s in farm_summaries],
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

    # --- strip-demos on synthetic 6-msg (extractor+demos) and 2-msg lists ---
    six = [{"role": "system", "content": "S"},
           {"role": "user", "content": "du1"}, {"role": "assistant", "content": "da1"},
           {"role": "user", "content": "du2"}, {"role": "assistant", "content": "da2"},
           {"role": "user", "content": "U"}]
    assert strip_demos(six, "extractor") == [six[0], six[-1]]
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
        mid = ([{"role": "user", "content": "d"}, {"role": "assistant", "content": "d"}] * 2
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
    def snap(form_state=None, pending=None, history=None):
        return {"session": 0, "turn": 0, "form_state": form_state or {},
                "pending": pending, "history": history or [], "user_message": ""}

    farm_snaps = {
        "correction": snap(form_state={"full_name": "Maria Lee", "email": "m@e.com"}),
        "deflect": snap(pending="dob"),
        "restraint_question": snap(pending="dob"),
        "refusal": snap(pending="phone"),
        "typed_choice": snap(pending="enrollment_type"),
        "no_match": snap(pending="program"),
        "precedence": snap(pending="phone"),
        "compound": snap(pending="dob"),
        "bulk": snap(pending="dob"),
    }
    for beh in REGISTRY:
        if beh.context == "farm":
            s = farm_snaps[beh.name]
            assert beh.precondition(s, schema), f"{beh.name}: precondition should hold"
            assert eligible_snaps(beh, [s], schema) == [s], f"{beh.name}: should be eligible"
        else:
            s = beh.make_context(schema, rng)
            assert set(s) >= {"form_state", "pending", "history"}, f"{beh.name}: ctx shape"
            assert len(s["form_state"]) <= 2 and len(s["history"]) <= 2, f"{beh.name}: minimal ctx"
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

    # --- TurnState round-trip ---
    st = rebuild_state(schema, snap(form_state={"email": "m@e.com"}, pending="dob"))
    assert st.form_state == {"email": "m@e.com"} and st.pending.target == "dob"
    assert rebuild_state(schema, snap(pending=None)).pending is None

    print("selftest: all assertions passed")


# ======================================================================
# CLI
# ======================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--farm", type=int, default=0, help="number of context-farm sessions")
    ap.add_argument("--inject", action="store_true", help="run behavior injection over the snapshots")
    ap.add_argument("--quota", type=int, default=5, help="injected cases per behavior")
    ap.add_argument("--run", default="pilot")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-turns", type=int, default=24)
    ap.add_argument("--naturalize", action="store_true", help="rephrase injected messages via claude_p")
    ap.add_argument("--snapshots", default="", help="load snapshots.jsonl (when --farm 0 --inject)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--parity", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if args.parity:
        parity_offline()
        return

    import dspy
    lm = ClaudeLM()
    dspy.configure(lm=lm)
    schema = load_schema()
    agent = build_teacher(schema)
    rng = random.Random(args.seed)

    if args.inject and not args.farm and not args.snapshots:
        ap.error("--inject with --farm 0 requires --snapshots PATH")

    out = RUN_DIR / args.run
    out.mkdir(parents=True, exist_ok=True)

    snapshots: list[dict] = []
    train_rows: list[dict] = []
    farm_summaries: list[dict] = []
    coverage: list[dict] = []
    prestep_handled = 0
    costs = {"farm_teacher": 0.0, "farm_u": 0.0, "inject_teacher": 0.0, "naturalizer": 0.0}

    try:
        # Layer 1 — farm
        for i in range(args.farm):
            seed = args.seed + i
            print(f"[farm {i+1}/{args.farm}] seed={seed} ...", flush=True)
            try:
                s = farm_session(agent, lm, schema, seed, args.max_turns)
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
            inj = run_injection(agent, lm, schema, snapshots, args.quota, rng, args.naturalize)
            train_rows.extend(inj["rows"])
            coverage = inj["coverage"]
            prestep_handled = inj["prestep_handled"]
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
                              train_rows, costs, parity, args)
        json.dump(report, open(out / "report.json", "w"), indent=2, default=str)
        print_report(report, out)


if __name__ == "__main__":
    main()
