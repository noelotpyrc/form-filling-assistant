"""eval_responder.py — doc-20 chapter-1 item 3: the Tier-1 responder scorer.

Five code-scored check families (doc-20 §2), all offline, no model, no network.
The composer's directives are the ground truth for what a reply must contain
(doc-20 §2 "we built the message, so we already know the answer"), so scoring is
deterministic comparison of prose against the directive/action list that produced
it.

A `case` is the unit both downstream consumers share (item 4 frozen eval runner,
item 5 sim_to_sft curation veto):

    case = {
        "form_state":    {field_id: value, ...},   # state AFTER this turn's sets
        "user_message":  str,                       # this turn's user utterance
        "actions":       [ {"type": ...}, ... ],    # harness-computed (composer.compose)
        "directives":    [ (kind, payload), ... ],  # harness-computed (composer.compose)
        "completion":    str,                        # the responder's raw completion
    }

score_case(case) -> {passed, turn_type, tokens, checks:{name:{pass,reason}}}.

Reuses (never re-implements) the shared logic doc-20 pins:
  format     datagen.is_well_formed("responder", …)
  grounding  validator.value_supported(f, value, user_message)   (§2: do NOT write a second one)
  echo       validator.coerce(value, f)                          (phones by digit string)

  Selftest (free, no model):  tuning/v2/.venv/bin/python -m tuning.v2.eval_responder --selftest
  Score a case file:          tuning/v2/.venv/bin/python -m tuning.v2.eval_responder --cases <file.jsonl>
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from .schema import Schema, load_schema
from .program import strip_markers
from .datagen import is_well_formed
from .validator import value_supported, coerce

# ---------------------------------------------------------------------------
# Verbosity budgets — PROVISIONAL. doc-20 §6 #2 leaves these OPEN; step 6 sets
# them from the teacher's own token distribution on the frozen set. Override by
# passing `budgets=` to score_case or --budgets <json> on the CLI.
# ---------------------------------------------------------------------------
DEFAULT_BUDGETS = {   # PROVISIONAL — tokens (whitespace-split) per turn type
    "ask": 60,
    "ack": 45,
    "clarify": 55,
    "terminal": 75,
    "submit_blocked": 85,
}

# cue vocabularies for directive realization (heuristic, deliberately lenient —
# Tier-1 vetoes clear misses, not borderline phrasing).
_ACK_CUES = ("thank", "got it", "great", "perfect", "noted", "all set",
             "sure thing", "of course", "done", "gotcha")
_APOLOGY_CUES = ("sorry", "apolog", "oops", "my mistake")
_REASK_CUES = ("could you", "can you", "please", "would you", "mind sharing", "again")
_CLARIFY_CUES = ("clarify", "which", "not sure", "do you mean", "didn't catch",
                 "could you", "what do you", "which one")
_CANT_SUBMIT_CUES = ("can't submit", "cannot submit", "can't be submitted", "not yet",
                     "before you submit", "before submitting", "before we can", "still need",
                     "still missing", "still have", "a few more", "few required",
                     "couple of required", "required fields left", "required sections",
                     "left to complete", "almost there", "not quite ready", "haven't filled")
_SAVE_CONTINUE_CUES = ("save", "draft", "continue", "keep going", "come back",
                       "pick up", "for now", "finish later")
_TERMINAL_CUES = ("review", "submit", "all set", "looks complete", "ready to submit",
                  "take a look", "everything looks", "double-check", "go ahead")
_NOT_REQUIRED_CUES = ("not required", "isn't required", "not needed", "don't need",
                      "doesn't need", "optional", "not necessary", "no need", "aren't required")
_RECORDED_CUES = ("record", "noted", "saved", "kept", "logged", "on file", "stored",
                  "have it", "got it", "jotted", "held onto")

_STOP = {"of", "the", "a", "an", "your", "and", "to", "in", "id", "you", "yes", "if"}


# ---- token extraction --------------------------------------------------------

@dataclass
class _TF:
    """Minimal Field stand-in — value_supported/coerce read only .type/.is_choice
    (and .min/.max for number, which value_supported short-circuits as out-of-scope)."""
    type: str
    is_choice: bool = False
    min: object = None
    max: object = None


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_MONTHS = ("January|February|March|April|May|June|July|August|September|October|"
           "November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec")
_DATE_RES = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(rf"\b(?:{_MONTHS})\s+\d{{1,2}},?\s+\d{{4}}\b", re.I),
    re.compile(rf"\b\d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}}\b", re.I),
]
_PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{5,}\d")
_NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_MARKER_RE = re.compile(r"\[\[\s*##.*?##\s*\]\]")


def _typed_tokens(prose: str) -> list[tuple[str, str]]:
    """Extract (type, token) for email/phone/date/number in the prose. Matched spans
    are masked so a date's digits aren't re-read as a phone/number."""
    out: list[tuple[str, str]] = []
    text = prose

    def take(regex, typ, s, validate=None):
        found = []

        def repl(m):
            tok = m.group(0)
            if validate is None or validate(tok):
                found.append((typ, tok))
                return " " * len(tok)
            return tok
        return found, regex.sub(repl, s)

    em, text = take(_EMAIL_RE, "email", text)
    out += em
    for r in _DATE_RES:
        d, text = take(r, "date", text, validate=lambda t: coerce(t, _TF("date"))[0])
        out += d
    ph, text = take(_PHONE_RE, "phone", text, validate=lambda t: len(re.sub(r"\D", "", t)) >= 7)
    out += ph
    nm, text = take(_NUM_RE, "number", text)
    out += nm
    return out


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _has_cue(low: str, cues) -> bool:
    return any(c in low for c in cues)


def _distinctive_terms(text: str) -> list[str]:
    """Content words of a label/option — lowercased, >=4 chars, non-stopword. The
    >=4-char cut is the distinctiveness guard: it drops boolean option labels
    ('Yes'/'No') so a bare 'yes' in prose can't count as asking a boolean field."""
    return [w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) >= 4 and w not in _STOP]


def _mentions_field(prose: str, f) -> bool:
    """Does the prose refer to field `f` — its full label, a content word of it, or a
    content word of one of its OPTION LABELS (a field asked via its choices, e.g.
    'full-time or part-time?' asks enrollment_type). doc-20 directive check, amended."""
    if f is None:
        return False
    low = prose.lower()
    if _norm(f.label) and _norm(f.label) in _norm(prose):
        return True
    terms = _distinctive_terms(f.label)
    for _, olabel in getattr(f, "options", []):
        terms += _distinctive_terms(str(olabel))
    return any(re.search(rf"\b{re.escape(w)}", low) for w in terms)


def _canon(f, value) -> str:
    """Canonical comparison form, reusing validator.coerce (phones -> digits, dates
    -> ISO). Email compares case-insensitively (coerce leaves email case as-is)."""
    if getattr(f, "type", None) == "email":
        return str(value).strip().lower()
    return str(coerce(str(value), f)[1])


# ---- the five checks ---------------------------------------------------------

def check_format(completion: str) -> tuple[bool, str]:
    """Well-formed responder markers, and no stray [[ ## … ]] leaking into the prose."""
    if not is_well_formed("responder", completion):
        return False, "not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])"
    seg = _response_segment(completion)
    leaked = _MARKER_RE.findall(seg)
    if leaked:
        return False, f"leaked marker(s) in prose: {leaked}"
    return True, ""


_RT = "[[ ## response_text ## ]]"


def _response_segment(c: str) -> str:
    i = c.find(_RT)
    if i < 0:
        return c
    i += len(_RT)
    j = c.find("[[ ## completed", i)
    return c[i:j] if j >= 0 else c[i:]


def _low(prose: str) -> str:
    """Lowercased prose with unicode apostrophes/quotes folded to ASCII, so cue matching
    ("isn't", "can't", "don't") fires on curly-quote prose ("isn't" U+2019) too. One
    place — every cue family that reads `low` benefits."""
    return prose.lower().translate(_QUOTE_FOLD)


_QUOTE_FOLD = str.maketrans({"’": "'", "‘": "'", "ʼ": "'",
                             "“": '"', "”": '"'})


def check_directive(schema: Schema, case: dict, prose: str) -> tuple[bool, str]:
    """Every directive + set_fields action of the turn is reflected in the prose.
    Pre-step directives (ack, fix) are first-class (doc-20 §3 — ~half of turns)."""
    low = _low(prose)
    fails = []
    for kind, payload in case.get("directives", []):
        if kind in ("ask_target", "reask_pending"):
            if not _mentions_field(prose, schema.field(payload)):
                fails.append(f"{kind}: field {payload!r} not asked about")
        elif kind == "clarify":
            fid = getattr(payload, "field_id", None)
            if fid is None and isinstance(payload, dict):
                fid = payload.get("field_id")
            f = schema.field(fid) if fid else None
            if not (_has_cue(low, _CLARIFY_CUES) or (f and _mentions_field(prose, f))):
                fails.append("clarify: no clarify cue and target field not mentioned")
        elif kind == "ack":
            xtok = _norm(payload)
            # accept: an ack cue, a literal echo of the payload, OR a normalized
            # token-overlap with the payload's distinctive terms (so "Your draft has
            # been saved!" acknowledges a "Save Draft" click via "draft"/"saved").
            pterms = _distinctive_terms(str(payload))
            overlap = any(re.search(rf"\b{re.escape(w)}", low) for w in pterms)
            if not (_has_cue(low, _ACK_CUES) or (xtok and xtok in _norm(prose)) or overlap):
                fails.append(f"ack: neither an ack cue nor {str(payload)!r} acknowledged")
        elif kind == "fix":
            if not (_has_cue(low, _APOLOGY_CUES) and ("?" in prose or _has_cue(low, _REASK_CUES))):
                fails.append("fix: needs an apology plus a re-ask")
        elif kind == "submit_blocked":
            if not (_has_cue(low, _CANT_SUBMIT_CUES) and _has_cue(low, _SAVE_CONTINUE_CUES)):
                fails.append("submit_blocked: needs can't-submit-yet plus a save/continue offer")
        elif kind == "dormant_set":
            pass   # per-TURN check after the loop (one caveat covers all dormant fields)
        elif kind == "terminal":
            if not _has_cue(low, _TERMINAL_CUES):
                fails.append("terminal: no review/submit invitation")
    # set_fields: the turn ACKNOWLEDGES the recorded value(s) — an ack cue (one cue
    # covers a whole bulk set) OR naming at least one set field (label/option). doc-20
    # amended: acknowledged, not by-name. A reply that neither acks nor names any set
    # field fails.
    set_fields = [fld for a in case.get("actions", []) if a.get("type") == "set_fields"
                  for fld in a.get("fields", [])]
    if set_fields:
        acked = _has_cue(low, _ACK_CUES) or any(
            _mentions_field(prose, schema.field(fld["field_id"])) for fld in set_fields)
        if not acked:
            fids = [fld["field_id"] for fld in set_fields]
            fails.append(f"set_fields: neither an ack cue nor any set field named ({fids})")
    # dormant_set: per-TURN (doc-22). One caveat sentence covering the volunteered fact
    # satisfies all dormant_set directives of the turn — a not-required cue PLUS a recorded
    # cue or a mention of ANY dormant field (label/option-label).
    dormant_fids = [p for k, p in case.get("directives", []) if k == "dormant_set"]
    if dormant_fids:
        not_req = _has_cue(low, _NOT_REQUIRED_CUES)
        recorded = _has_cue(low, _RECORDED_CUES) or any(
            _mentions_field(prose, schema.field(fid)) for fid in dormant_fids)
        if not (not_req and recorded):
            fails.append(f"dormant_set: {dormant_fids} needs a not-required caveat + recorded/field mention")
    return (not fails), "; ".join(fails)


def _grounding_corpus(schema: Schema, case: dict) -> str:
    parts = [case.get("user_message", "")]
    parts += [str(v) for v in case.get("form_state", {}).values()]
    parts.append(_schema_text(schema))
    return " ".join(parts)


_SCHEMA_TEXT: dict[int, str] = {}


def _schema_text(schema: Schema) -> str:
    key = id(schema)
    if key not in _SCHEMA_TEXT:
        bits = []
        for f in schema.fields:
            bits.append(f.label)
            bits += [str(lab) for _, lab in f.options]
        _SCHEMA_TEXT[key] = " ".join(bits)
    return _SCHEMA_TEXT[key]


def check_grounding(schema: Schema, case: dict, prose: str) -> tuple[bool, str]:
    """Every email/phone/date/number token in the prose is supported by user_message,
    form_state, or the schema (labels/option labels) — via validator.value_supported.
    Note: value_supported treats numbers as out-of-scope (always True), so bare numeric
    tokens are not grounded here; that's the shared support test's definition, not a
    second one (doc-20 §2 forbids a second)."""
    corpus = _grounding_corpus(schema, case)
    fails = []
    for typ, tok in _typed_tokens(prose):
        if not value_supported(_TF(typ), tok, corpus):
            fails.append(f"{typ} {tok!r} not grounded in message/state/schema")
    return (not fails), "; ".join(fails)


_ECHO_TYPES = ("phone", "email", "date")


def check_echo(schema: Schema, case: dict, prose: str) -> tuple[bool, str]:
    """A stored value repeated in the prose must match form_state after coerce
    (phones compare by digit string). A prose token that contradicts the stored value
    for its type — and isn't a fresh value from this turn's user_message — is a trust bug."""
    fs = case.get("form_state", {})
    um = case.get("user_message", "")
    stored: dict[str, set] = defaultdict(set)
    for fid, v in fs.items():
        f = schema.field(fid)
        if f and f.type in _ECHO_TYPES and str(v):
            stored[f.type].add(_canon(f, v))
    fails = []
    for typ, tok in _typed_tokens(prose):
        if typ not in _ECHO_TYPES or not stored.get(typ):
            continue                                   # nothing of this type to contradict
        if _canon(_TF(typ), tok) in stored[typ]:
            continue                                   # faithful echo
        if value_supported(_TF(typ), tok, um):
            continue                                   # a fresh value the user just gave
        fails.append(f"{typ} {tok!r} contradicts stored {sorted(stored[typ])}")
    return (not fails), "; ".join(fails)


def turn_type(case: dict) -> str:
    """Verbosity budget index. Priority: submit_blocked > terminal > clarify > ask > ack."""
    kinds = {d[0] for d in case.get("directives", [])}
    if "submit_blocked" in kinds:
        return "submit_blocked"
    if "terminal" in kinds:
        return "terminal"
    if "clarify" in kinds:
        return "clarify"
    if kinds & {"ask_target", "reask_pending"}:
        return "ask"
    if kinds & {"ack", "fix"}:
        return "ack"
    return "ask"


def check_verbosity(case: dict, prose: str, budgets: dict, tt: str) -> tuple[bool, str, int]:
    """Token count within the budget for this turn type. The known wordiness mode is
    option re-enumeration (an ask_choice turn re-listing every button in prose); that
    inflates the count past the ask budget and is caught here (doc-20 §2)."""
    n = len(prose.split())
    budget = budgets.get(tt, budgets["ask"])
    if n > budget:
        reenum = any(a.get("type") == "ask_choice" for a in case.get("actions", []))
        why = " (option re-enumeration?)" if reenum and tt == "ask" else ""
        return False, f"{n} tokens > {tt} budget {budget}{why}", n
    return True, "", n


def check_repetition(prose: str) -> tuple[bool, str]:
    """Deterministic degenerate-text detector (doc-20 standing direction — a discovered
    miss becomes a Tier-1 check). A stuck/looping decode repeats a whole span verbatim
    and NEAR-ADJACENTLY ("Your draft has been saved draft has been saved"). We flag a
    normalized word 4-gram whose two occurrences start within 5 tokens of each other —
    a back-to-back loop. Legitimately restating a field name across a sentence boundary
    ("Now I need your country of residence. What is your country of residence?") repeats
    the same 4-gram but with a real gap (>=6), so it does NOT trip; option lists and a
    varied terminal summary never repeat a 4-word span at all."""
    toks = re.findall(r"[a-z0-9]+", prose.lower())
    if len(toks) < 8:                              # too short to loop a 4-gram
        return True, ""
    positions: dict = defaultdict(list)
    for i in range(len(toks) - 3):
        positions[tuple(toks[i:i + 4])].append(i)
    for g, pos in positions.items():
        for a, b in zip(pos, pos[1:]):
            if b - a <= 5:                         # near-adjacent repeat = a decode loop
                return False, f"degenerate repeat: 4-gram {' '.join(g)!r} @ {a},{b}"
    return True, ""


# ---- combined scorer ---------------------------------------------------------

def score_case(case: dict, schema: Schema | None = None, budgets: dict | None = None) -> dict:
    """Run all six checks. Returns per-check pass/fail + reason and an overall `passed`."""
    schema = schema or load_schema()
    budgets = budgets or DEFAULT_BUDGETS
    completion = case["completion"]
    prose = strip_markers(completion)

    fmt = check_format(completion)
    drc = check_directive(schema, case, prose)
    gnd = check_grounding(schema, case, prose)
    echo = check_echo(schema, case, prose)
    tt = turn_type(case)
    vb_ok, vb_reason, ntok = check_verbosity(case, prose, budgets, tt)

    checks = {
        "format": fmt, "directive": drc, "grounding": gnd,
        "echo": echo, "verbosity": (vb_ok, vb_reason), "repetition": check_repetition(prose),
    }
    return {
        "passed": all(ok for ok, _ in checks.values()),
        "turn_type": tt,
        "tokens": ntok,
        "checks": {k: {"pass": ok, "reason": r} for k, (ok, r) in checks.items()},
    }


def aggregate(scored: list[dict]) -> dict:
    """Pass rates overall + per check family, for the item-4 runner's report."""
    n = len(scored)
    fams = ("format", "directive", "grounding", "echo", "verbosity", "repetition")
    per = {f: sum(1 for s in scored if s["checks"][f]["pass"]) for f in fams}
    return {
        "n": n,
        "passed": sum(1 for s in scored if s["passed"]),
        "by_check": {f: {"pass": per[f], "rate": (per[f] / n if n else None)} for f in fams},
        "by_turn_type": dict(Counter(s["turn_type"] for s in scored)),
    }


def print_report(agg: dict) -> None:
    n = agg["n"]
    print("=== Tier-1 responder metrics ===")
    print(f"overall pass: {agg['passed']}/{n}" + (f"  ({agg['passed']/n:.1%})" if n else ""))
    for fam, d in agg["by_check"].items():
        rate = f"{d['rate']:.1%}" if d["rate"] is not None else "-"
        print(f"  {fam:12} {d['pass']}/{n}  {rate}")
    print(f"turn types: {agg['by_turn_type']}")


# ---- shared recompute: (actions, directives) without an LLM (doc-20 items 4/5) ----

def recompute_actions_directives(schema: Schema, snap: dict, ext_completion: str | None):
    """Re-derive this turn's (actions, directives) DETERMINISTICALLY — the exact
    program.forward path (prestep.run -> validate if not prestep-handled -> compose),
    no model. `ext_completion` is the recaptured extractor row's completion for this
    (session, turn), or None when there is none (a prestep-handled turn has no
    extractor row — that absence is the signal).

    Returns (actions, directives, post_form_state, diag). `post_form_state` is the
    state AFTER this turn's sets (what the responder saw as filled_fields). `diag` is
    None normally, or a string flagging a source mismatch (a non-prestep turn missing
    its extractor row, or a prestep-handled turn that unexpectedly has one) — the
    caller decides whether to fail."""
    from . import prestep
    from .validator import validate
    from .composer import compose
    from .datagen import rebuild_state
    from .sim_to_sft import parse_extractions

    state = rebuild_state(schema, snap)
    um = snap.get("user_message", "")
    ps = prestep.run(um, state)
    diag = None
    if ps.handled:
        outcomes = []
        if ext_completion is not None:
            diag = "prestep-handled turn unexpectedly has an extractor row"
    else:
        if ext_completion is None:
            diag = "non-prestep turn has NO extractor row — cannot recompute pairs"
            pairs = []
        else:
            pairs = parse_extractions(ext_completion)
            if pairs is None:      # mirror program.forward's AdapterParseError -> pairs=[]
                pairs = []
        outcomes = validate(pairs, state, um)
    actions, directives = compose(state, ps, outcomes)
    return actions, directives, dict(state.form_state), diag


def jsonable_directives(directives: list) -> list:
    """Serialize composer directives to a JSON-safe form score_case tolerates. Only
    `clarify` carries a non-serializable payload (a validator Outcome) — canonicalize
    it to {"field_id": …} (flag #3 from item 3). All others (str / None / list) pass
    through. Tuples become 2-element lists."""
    out = []
    for kind, payload in directives:
        if kind == "clarify":
            fid = getattr(payload, "field_id", None)
            if fid is None and isinstance(payload, dict):
                fid = payload.get("field_id")
            out.append([kind, {"field_id": fid}])
        else:
            out.append([kind, payload])
    return out


def _injected_user_message(user_content: str) -> str:
    """The message the responder actually saw, from an inject row's own rendered
    [[ ## user_message ## ]] block (the snapshot's stored user_message is the original
    farm turn, not the injected one)."""
    m = re.search(r"\[\[ ## user_message ## \]\]\n(.*?)\n\n\[\[ ## ", user_content, re.DOTALL)
    return m.group(1) if m else ""


def recompute_cases_from_rows(rows: list, snaps: dict, schema: Schema | None = None,
                              only_behavior: str | None = None) -> list:
    """One place that turns captured RESPONDER rows (farm or inject) into recomputed
    cases — shared by the probe builder and the coverage tool so the pairing/override
    logic lives once. `snaps` is {(session,turn): snapshot}. For each responder row it
    yields a dict {row, source, behavior, session, turn, user_message, form_state,
    actions, directives (raw compose tuples), diag}. Inject rows: snapshot by the row's
    snapshot ref, user_message OVERRIDDEN with the injected one, extractor paired FIFO
    by (snapshot, behavior). Farm rows: (session,turn) key, the snapshot's own message,
    farm extractor by (session,turn). `diag` = 'no-snapshot' when the join misses."""
    schema = schema or load_schema()
    farm_ext = {(r["session"], r["turn"]): r["completion"]
                for r in rows if r["module"] == "extractor" and r.get("source") == "farm"}
    pending_ext: dict = defaultdict(list)
    out = []
    for r in rows:
        src = r.get("source")
        if r["module"] == "extractor":
            if src == "inject":
                ref = r.get("snapshot")
                gkey = ((ref["session"], ref["turn"]) if ref else None, r.get("behavior"))
                pending_ext[gkey].append(r["completion"])
            continue
        if r["module"] != "responder":
            continue
        if only_behavior is not None and r.get("behavior") != only_behavior:
            continue
        if src == "inject":
            ref = r.get("snapshot")
            gkey = ((ref["session"], ref["turn"]) if ref else None, r.get("behavior"))
            exts = pending_ext[gkey]
            ext_completion = exts.pop(0) if exts else None
            key = (ref["session"], ref["turn"]) if ref else None
            snap = snaps.get(key) if key else None
            um = _injected_user_message(r["messages"][-1]["content"]) if snap else None
        else:
            key = (r.get("session"), r.get("turn"))
            snap = snaps.get(key)
            ext_completion = farm_ext.get(key)
            um = snap.get("user_message", "") if snap else None
        session, turn = key if key else (None, None)
        base = {"row": r, "source": src, "behavior": r.get("behavior"),
                "session": session, "turn": turn}
        if snap is None:
            out.append({**base, "user_message": None, "form_state": None,
                        "actions": None, "directives": None, "diag": "no-snapshot"})
            continue
        actions, directives, fs, diag = recompute_actions_directives(
            schema, {**snap, "user_message": um}, ext_completion)
        out.append({**base, "user_message": um, "form_state": fs,
                    "actions": actions, "directives": directives, "diag": diag})
    return out


# ---- CLI + selftest ----------------------------------------------------------

def _run_cases(path: str, budgets_path: str = "") -> None:
    schema = load_schema()
    budgets = json.load(open(budgets_path)) if budgets_path else DEFAULT_BUDGETS
    cases = [json.loads(l) for l in open(path)]
    scored = [score_case(c, schema, budgets) for c in cases]
    print_report(aggregate(scored))


def selftest() -> bool:
    schema = load_schema()

    def W(prose: str) -> str:
        return f"[[ ## response_text ## ]]\n{prose}\n\n[[ ## completed ## ]]"

    def case(prose, directives=None, actions=None, form_state=None, user_message="", wrapped=True):
        return {"form_state": form_state or {}, "user_message": user_message,
                "actions": actions or [], "directives": directives or [],
                "completion": W(prose) if wrapped else prose}

    # (name, case, check_family, expected_pass_of_that_check)
    cases = [
        # -- format -----------------------------------------------------------
        ("format PASS: clean markers",
         case("Thanks, got it! What's your phone number?",
              directives=[("ask_target", "phone")]), "format", True),
        ("format FAIL #5: leaked [[ ## … ]] marker in prose",
         case("Sure! [[ ## thoughts ## ]] What's your email address?",
              directives=[("ask_target", "email")]), "format", False),

        # -- directive realization -------------------------------------------
        ("directive PASS: ask_target(program) mentions the program",
         case("Which program of interest were you considering?",
              directives=[("ask_target", "program")]), "directive", True),
        ("directive FAIL #3: asks the WRONG field (email asked, phone in prose)",
         case("Could you share your phone number?",
              directives=[("ask_target", "email")]), "directive", False),
        ("directive PASS: fix -> apology + re-ask",
         case("Sorry about that! Could you re-enter your email address?",
              directives=[("fix", "invalid email (field: email)")]), "directive", True),
        # doc-22 dormant_set: not-required caveat + recorded cue
        ("directive PASS: dormant_set caveat ('isn't required' + 'noted')",
         case("I've noted your TOEFL score, though it isn't required given your current answers.",
              directives=[("dormant_set", "english_test_score")]), "directive", True),
        # curly apostrophe (U+2019) must still match the "isn't" cue
        ("directive PASS: dormant caveat with a curly apostrophe (isn’t)",
         case("Noted — the English proficiency test isn’t required given your current answers, "
              "but I’ve recorded it anyway.",
              directives=[("dormant_set", "english_test_type")]), "directive", True),
        # per-TURN: ONE caveat sentence covers TWO dormant fields
        ("directive PASS: two dormant fields, one caveat covers both",
         case("Thanks — I've recorded those, though they aren't required given your current answers.",
              directives=[("dormant_set", "english_test_score"), ("dormant_set", "english_test_type")]),
         "directive", True),
        ("directive FAIL: dormant_set with no not-required caveat",
         case("Got it! Now, what's your program of interest?",
              directives=[("dormant_set", "english_test_score")]), "directive", False),
        ("directive FAIL: two dormant fields, no caveat at all",
         case("Great, and what's your program of interest?",
              directives=[("dormant_set", "english_test_score"), ("dormant_set", "english_test_type")]),
         "directive", False),
        # ack payload token-overlap: a save-click confirmation with no ack-cue word
        ("directive PASS: ack via payload token-overlap ('draft'/'saved' <- 'Save Draft')",
         case("Your draft has been saved!", directives=[("ack", "Save Draft")]), "directive", True),
        ("directive FAIL: ack ignored entirely (no cue, no payload reference)",
         case("What's your email address?", directives=[("ack", "Save Draft")]), "directive", False),
        ("directive PASS: submit_blocked -> can't-submit + save/continue",
         case("We can't submit yet — a couple of fields are still missing. "
              "Want to keep going, or save a draft and come back later?",
              directives=[("submit_blocked", ["dob", "phone"])],
              actions=[{"type": "show_button", "button": "save_draft"}]), "directive", True),
        # FIX 1: natural teacher phrasings for submit_blocked (cue widening)
        ("directive PASS: submit_blocked natural phrasing 'required sections ... complete first'",
         case("Almost there! There are still a few required sections we need to complete "
              "first — shall we keep going, or save a draft for now?",
              directives=[("submit_blocked", ["dob"])],
              actions=[{"type": "show_button", "button": "save_draft"}]), "directive", True),
        ("directive PASS: submit_blocked natural phrasing 'before we can send it off'",
         case("Before we can send it off, we still have a couple of required fields left — "
              "want to continue now or save and finish later?",
              directives=[("submit_blocked", ["phone"])],
              actions=[{"type": "show_button", "button": "save_draft"}]), "directive", True),
        # FIX 1 guard: a FALSE completeness claim must NOT satisfy submit_blocked
        ("directive FAIL: false-completeness claim does not satisfy submit_blocked",
         case("You're all set — everything's complete, submitting your application now!",
              directives=[("submit_blocked", ["dob", "phone"])],
              actions=[{"type": "show_button", "button": "save_draft"}]), "directive", False),
        ("directive PASS: set_fields acknowledged (ack cue)",
         case("Great, I've noted your full legal name. What's next?",
              directives=[("ack", "answer")],
              actions=[{"type": "set_fields", "fields": [{"field_id": "full_name", "value": "Ada Lovelace"}]}],
              form_state={"full_name": "Ada Lovelace"}, user_message="I'm Ada Lovelace"),
         "directive", True),
        # CHANGE 1 (a): a field asked via its OPTION LABELS counts as asking it
        ("directive PASS: option-label ask (full-time/part-time -> enrollment_type)",
         case("Would you like to enroll full-time or part-time?",
              directives=[("ask_target", "enrollment_type")]), "directive", True),
        # CHANGE 2 (b): one generic ack cue covers a multi-field bulk set
        ("directive PASS: generic ack covers a bulk set (no field named)",
         case("Perfect, thanks — all noted! What would you like to add next?",
              directives=[("ack", "answer")],
              actions=[{"type": "set_fields", "fields": [
                  {"field_id": "program", "value": "cs"},
                  {"field_id": "start_term", "value": "Fall 2026"}]}],
              form_state={"program": "cs", "start_term": "Fall 2026"}), "directive", True),
        # CHANGE 2 (c): a set with NO ack and NO field named still fails
        ("directive FAIL: set_fields with neither ack nor any field named",
         case("Will you be enrolling full-time or part-time?",
              directives=[("ask_target", "enrollment_type")],
              actions=[{"type": "set_fields", "fields": [{"field_id": "start_term", "value": "Fall 2026"}]}]),
         "directive", False),
        # CHANGE 1 guard (d): a bare 'yes' must NOT count as asking a boolean field
        ("directive FAIL: bare 'yes' does not ask a boolean field (option-label guard)",
         case("Yes, absolutely — could you share your email address?",
              directives=[("ask_target", "prior_application")]), "directive", False),

        # -- grounding --------------------------------------------------------
        ("grounding PASS: date echoed matches state",
         case("Thanks! I've recorded your date of birth as May 1, 2000.",
              directives=[("ack", "answer")],
              form_state={"dob": "2000-05-01"}, user_message="born May 1, 2000"), "grounding", True),
        ("grounding FAIL #1: fabricated policy with an ungrounded date",
         case("Noted. Part-time students only become eligible for funding after January 10, 2029.",
              directives=[("ack", "funding question")],
              user_message="are part-timers eligible for funding?"), "grounding", False),

        # -- echo fidelity ----------------------------------------------------
        ("echo PASS: phone echoed matches state (by digits)",
         case("Got it — I have your phone number as (415) 782-3311.",
              directives=[("ack", "answer")],
              form_state={"phone": "4157823311"}, user_message="my number is 415-782-3311"), "echo", True),
        ("echo FAIL #2: phone digits not in state (contradicts stored)",
         case("Got it — I have your phone number as (415) 782-9999.",
              directives=[("ack", "answer")],
              form_state={"phone": "4157823311"}, user_message="that's my number"), "echo", False),

        # -- verbosity --------------------------------------------------------
        ("verbosity PASS: short ask",
         case("Sure — which program of interest are you leaning toward?",
              directives=[("ask_target", "program")],
              actions=[{"type": "ask_choice", "question": "Program of Interest?", "options": []}]),
         "verbosity", True),
        ("verbosity FAIL #4: over-budget option re-enumeration",
         case("Wonderful, let's pick your program of interest! You can choose from the "
              "Computer Science masters, the Data Science masters, the Business "
              "Administration MBA, the Education masters, and several other wonderful "
              "and enriching options that our distinguished faculty have carefully "
              "designed for you, so please do take your time to read through every "
              "single one of them slowly before you decide which single program truly "
              "speaks to your heart and your long term career ambitions today okay?",
              directives=[("ask_target", "program")],
              actions=[{"type": "ask_choice", "question": "Program of Interest?", "options": []}]),
         "verbosity", False),

        # -- repetition (degenerate-text detector) ----------------------------
        # the real degenerate save_draft sample -> fails on a repeated 4-gram
        ("repetition FAIL: degenerate looped decode (real sample)",
         case("Your draft has been saved draft has been saved. Let's pick up where you "
              "left off. To continue whenever you're ready. Which program are you ready. "
              "interested in? You can choose from Computer Science.",
              directives=[("ack", "Save Draft")]), "repetition", False),
        # clean, diverse replies must NOT false-positive:
        ("repetition PASS: short clean ack",
         case("Your draft has been saved! Pick up anytime.", directives=[("ack", "Save Draft")]),
         "repetition", True),
        ("repetition PASS: option-mention ask (full-time/part-time, 'time' twice)",
         case("Would you like to enroll full-time or part-time?",
              directives=[("ask_target", "enrollment_type")]), "repetition", True),
        # legit state-then-ask restatement (field name twice across a sentence break) must PASS
        ("repetition PASS: field name restated across a sentence break",
         case("Thanks! Now I need to know your country of residence. "
              "What is your country of residence?",
              directives=[("reask_pending", "country_residence")]), "repetition", True),
        ("repetition PASS: long-but-clean terminal summary (many distinct bullets)",
         case("Everything looks complete. Here's what I have: your program is Computer "
              "Science, your start term is Fall 2026, enrollment is full-time, your name "
              "is Ada Lovelace, email ada@example.com, phone on file, and citizenship "
              "United States. Please review the summary card and submit when ready.",
              directives=[("terminal", None)]), "repetition", True),
    ]

    checks: list[tuple[str, bool]] = []

    def ck(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    families_hit = set()
    for name, c, fam, want in cases:
        s = score_case(c, schema)
        families_hit.add(fam)
        got = s["checks"][fam]["pass"]
        detail = "" if got == want else f"  <<< got {got} want {want}; reason={s['checks'][fam]['reason']!r}"
        ck(f"{name} [{fam}={'pass' if want else 'fail'}]{detail}", got == want)
        # a FAIL case must also make the whole case fail overall
        if not want:
            ck(f"    -> overall passed == False for: {name}", s["passed"] is False)

    ck("all six families exercised",
       families_hit == {"format", "directive", "grounding", "echo", "verbosity", "repetition"})

    # sanity: a fully-clean case passes every family at once
    clean = case("Thanks! What's your email address?", directives=[("ask_target", "email")])
    ck("a fully-clean ask passes all six families", score_case(clean, schema)["passed"] is True)

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n=== eval_responder selftest: {passed}/{len(checks)} checks passed ===")
    return passed == len(checks)


def main():
    ap = argparse.ArgumentParser(description="Tier-1 responder scorer (doc-20 §2).")
    ap.add_argument("--selftest", action="store_true", help="offline, no model — hand-built PASS/FAIL per family")
    ap.add_argument("--cases", help="score a jsonl of cases (offline)")
    ap.add_argument("--budgets", default="", help="json file overriding the provisional verbosity budgets")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if args.cases:
        _run_cases(args.cases, args.budgets)
        return
    ap.error("nothing to do — pass --selftest or --cases")


if __name__ == "__main__":
    main()
