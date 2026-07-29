"""Invention stress sweep — how often does the SFT'd extractor emit a value that
nobody uttered, and where does that value come from?

Every sweep turn is authored to contain NO bindable answer, so the correct
extraction is `[]` (for the `deflect_ask` class, an engagement pair
{field_id, ""} — which becomes an ask_choice, not a set, so `got_sets` is still
empty). Any non-empty set is therefore over-attribution; any set value that the
turn's own utterance does not support is INVENTION. Each emitted (field_id,
value) pair is classified:

  supported        utterance-supported (reused probe.py `_invention_check`)
  expected_hint    country_residence / country_citizenship on a travel_story turn
                   (the narrative genuinely names a country — debatable, never
                   counted as invention)
  semantic         choice / boolean / multi_select / number field — a substring
                   check is meaningless; over-attribution, but its own column
  from_history     appears in the rendered history or rendered filled-fields
                   block (copy-forward)
  from_corpus      appears verbatim in the SFT training corpus
  novel_in_format  matches persona.py's generator format for that value type —
                   a value nobody ever wrote, shaped exactly like the generator's
  other_novel      none of the above

invention = {from_corpus, novel_in_format, other_novel}.

`utterances` for the support check is the CURRENT turn's user_message only —
history-borne values must fall through to `from_history`, which is the whole
point of the pii_in_history factor.

GRID (two fractional blocks, not the full cross product):
  main  content(6) x filled(3) x pending(6), fixed history_depth=HISTORY_TURNS,
        pii_in_history=absent                                 -> 108 cells
  hist  content(6) x history_depth(3) x pii_in_history(2), fixed filled=half,
        pending=enrollment_type                               ->  36 cells
With --seeds 4 that is (108 + 36) * 4 = 576 extractor calls.

Notes on the levels:
  * history_depth beyond context.HISTORY_TURNS renders identically (render_history
    keeps only the last HISTORY_TURNS messages), which is why 10 is not a level.
  * history_depth=0 + pii_in_history=present has no window to inject into: the
    cell is kept (so the block stays a clean cross product) with
    pii_effective=false recorded — at temperature 0 it doubles as a determinism
    check against the `absent` cell.
  * filled=near_complete holds out email and phone (the two fields the anchor
    invented) so a copy-forward from state is never available for them.
  * a (filled, pending) pair where the pending field is already filled drops that
    field from the state for that cell; the drop is recorded per row.

ANCHOR GATE (runs first): the one known real failure from the M3b probe —
trap/seed 1, turn 3 ("Actually, I moved to Seoul in 2019 for work...") which set
country_residence=KR, country_citizenship=KR, email=sara.yamamoto14@example.com,
phone=(892) 555-1089 — is rebuilt from probe_runs/m3b_hybrid/sessions.jsonl and
re-run through THIS harness. got_sets must equal the recorded sets or the sweep
aborts. Anchors are model-specific: the gate is only meaningful for the
checkpoint that produced it (the slice1b model). For any other checkpoint pass
--no-gate — the anchor turn is still run and its output recorded for comparison.

Run (needs a live student MLX server; no other network):
  tuning/v2/.venv/bin/python -m tuning.v2.stress_invent \
      --label slice1b --port 8101 --student-model /path/to/student
  # other checkpoints: add --no-gate

Offline self-test (no server, no network):
  tuning/v2/.venv/bin/python -m tuning.v2.stress_invent --selftest

Outputs (tuning/v2/stress_runs/<label>/, gitignored):
  results.jsonl  one row per call, appended+flushed as it completes (resume-safe)
  report.json    anchor record, grid definition, per-factor tables, totals
"""
from __future__ import annotations
import argparse
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from .context import HISTORY_TURNS, render_filled, render_history
from .eval_score import run_case
from .persona import CITIES, FIRST, LAST, STREETS, USTATES, gen_persona
from .probe import RESUME_PREFILL, _invention_check, _norm
from .schema import load_schema

STRESS_DIR = Path(__file__).resolve().parent / "stress_runs"
DEFAULT_CORPUS = "tuning/v2/datagen_runs/h1b_merged/train.jsonl"
ANCHOR_SESSIONS = "tuning/v2/probe_runs/m3b_hybrid/sessions.jsonl"
ANCHOR_TURN = 3
ANCHOR_SCENARIO, ANCHOR_SEED = "trap", 1

BUCKETS = ["supported", "expected_hint", "semantic",
           "from_history", "from_corpus", "novel_in_format", "other_novel"]
INVENTION = {"from_corpus", "novel_in_format", "other_novel"}
COUNTRY_FIELDS = {"country_residence", "country_citizenship"}
HOLD_OUT = ("email", "phone")            # never in near_complete state
FACTORS = ["content", "filled", "pending", "history_depth", "pii_in_history"]


# ======================================================================
# turn content — 6 classes x 6 templates, no real email/phone/address/DOB
# ======================================================================

_PLACES = [("Seoul", "South Korea"), ("Lisbon", "Portugal"), ("Nairobi", "Kenya"),
           ("Osaka", "Japan"), ("Medellin", "Colombia"), ("Toronto", "Canada")]
_HOMES = ["Brazil", "India", "Germany", "Mexico", "Nigeria", "Vietnam"]

CONTENT = {
    "travel_story": [
        "Actually, I moved to {city} in {year} for work. Been living in {country} ever since — amazing experience, though I do miss {home} sometimes.",
        "Funny thing, I spent {year} through {year2} in {city}. {country} really grew on me.",
        "My family relocated to {city} back in {year}; we were in {home} before that.",
        "I did a semester abroad in {city} in {year} — {country} was a whole different world.",
        "Ever since {year} I've been bouncing between {city} and {home}, mostly for work.",
        "We left {home} in {year} and ended up near {city}. Long story.",
    ],
    "third_person": [
        "My cousin {name} applied here two years ago and said the whole thing was painless.",
        "{name}, my old roommate, is doing the same degree at another school right now.",
        "A friend of mine — {name} — told me to double-check everything before I press the button.",
        "{name} in my office went through this exact process and swore by it.",
        "My sister-in-law {name} works in admissions somewhere else, so she's been coaching me.",
        "{name} is the one who talked me into going back to school at all.",
    ],
    "numeric_filler": [
        "Been studying maybe 3 hours a day with 2 kids at home, so my brain is fried.",
        "I've got about 4 tabs open and 7 browser windows trying to figure this out.",
        "Between a 45-minute commute and 2 jobs there isn't much time for this.",
        "I read something like 12 pages of instructions before I gave up on them.",
        "It's 11 at night and I'm on cup number 3.",
        "My internet dropped 5 times in the past 20 minutes.",
    ],
    "emotional_filler": [
        "I'm ready to knock this out!",
        "Honestly a bit nervous about all this.",
        "Okay, deep breath. Let's do this.",
        "This is genuinely exciting — I've wanted to do it for years.",
        "I'll be honest, forms like this stress me out.",
        "Feeling good about it today, let's keep the momentum going.",
    ],
    "chitchat": [
        "It's absolutely pouring here today, terrible weather for anything.",
        "Whoever designed this page did a nice job — the layout is easy on the eyes.",
        "Sorry, I got distracted making coffee. Where were we?",
        "My cat just walked across the keyboard, apologies for any nonsense.",
        "The heat here has been unreal all week.",
        "Nice change from the usual grey skies, at least.",
    ],
    "deflect_ask": [
        "Wait, is there an application fee?",
        "Quick question — do you need transcripts from every school I attended?",
        "Hold on, how long does a decision usually take?",
        "Is there an interview at some point?",
        "Is there someone I can call if I get stuck?",
        "Before I go on, what happens to my data here?",
    ],
}
CONTENT_CLASSES = list(CONTENT)


def render_message(content: str, rng: random.Random, persona: dict) -> str:
    """One authored message for `content`, chosen with the cell's rng."""
    tmpl = rng.choice(CONTENT[content])
    city, country = rng.choice(_PLACES)
    y = rng.randint(2011, 2019)
    name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    while name == persona.get("full_name"):
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    return tmpl.format(city=city, country=country, home=rng.choice(_HOMES),
                       year=y, year2=y + 2, name=name)


# ======================================================================
# form state / pending / history levels
# ======================================================================

FILLED_LEVELS = ["empty", "half", "near_complete"]
PENDING_LEVELS = [None, "enrollment_type", "full_name", "email", "phone", "dob"]
HISTORY_DEPTHS = [0, 2, HISTORY_TURNS]
PII_LEVELS = ["absent", "present"]


def filled_state(persona: dict, level: str) -> dict:
    if level == "empty":
        return {}
    if level == "half":
        return {fid: persona[fid] for fid in RESUME_PREFILL if fid in persona}
    return {fid: v for fid, v in persona.items() if fid not in HOLD_OUT}


# plausible prior conversation: (assistant ask, user answer) pairs, oldest first
_HIST_PAIRS = [
    ("Welcome! I'll help you through this application — ready when you are.",
     "Sounds good, let's go."),
    ("Which program are you interested in?", "The education one, I think."),
    ("And will you be starting in Fall 2026 or Spring 2027?", "Fall 2026."),
    ("Have you applied to Northfield before?", "No, this is my first time."),
]


def build_history(schema, persona: dict, depth: int, pending: str | None,
                  pii: str) -> tuple[list, bool]:
    """`depth` messages of alternating prior conversation, ending with the
    assistant's ask for `pending` (a neutral closer when pending is None).
    pii='present' rewrites the earliest USER message in the window so the user
    gave their real email + phone there. Returns (history, pii_effective)."""
    if depth <= 0:
        return [], False
    pf = schema.field(pending) if pending else None
    closer = (f"Could you tell me your {pf.label}?" if pf
              else "Let me know whenever you want to keep going.")
    msgs = []
    for ask, answer in _HIST_PAIRS:
        msgs.append({"role": "assistant", "content": ask})
        msgs.append({"role": "user", "content": answer})
    msgs.append({"role": "assistant", "content": closer})
    msgs = [dict(m) for m in msgs[-depth:]]

    pii_effective = False
    if pii == "present":
        for m in msgs:
            if m["role"] == "user":
                m["content"] = (f"Oh — you can reach me at {persona['email']} "
                                f"or {persona['phone']}, whichever is easier.")
                pii_effective = True
                break
    return msgs, pii_effective


# ======================================================================
# cells + cases
# ======================================================================

def cell_key(cell: dict) -> str:
    return "|".join(f"{k}={cell[k]}" for k in FACTORS)


def build_cells(block: str) -> list[dict]:
    cells = []
    if block in ("main", "both"):
        for c in CONTENT_CLASSES:
            for fl in FILLED_LEVELS:
                for pd in PENDING_LEVELS:
                    cells.append({"block": "main", "content": c, "filled": fl,
                                  "pending": pd, "history_depth": HISTORY_TURNS,
                                  "pii_in_history": "absent"})
    if block in ("hist", "both"):
        for c in CONTENT_CLASSES:
            for d in HISTORY_DEPTHS:
                for pii in PII_LEVELS:
                    cells.append({"block": "hist", "content": c, "filled": "half",
                                  "pending": "enrollment_type", "history_depth": d,
                                  "pii_in_history": pii})
    return cells


def make_case(schema, cell: dict, seed: int) -> dict:
    """Deterministic: the rng is seeded from the cell key + seed."""
    key = cell_key(cell)
    rng = random.Random(f"{key}#{seed}")
    persona = gen_persona(schema, rng)
    state = filled_state(persona, cell["filled"])
    pending = cell["pending"]
    dropped = None
    if pending and pending in state:      # self-contradictory -> drop from state
        state.pop(pending)
        dropped = pending
    history, pii_effective = build_history(schema, persona, cell["history_depth"],
                                           pending, cell["pii_in_history"])
    msg = render_message(cell["content"], rng, persona)
    case = {
        "id": f"{cell['block']}-{key}-s{seed}",
        "scenario": cell["content"],
        "form_state": state,
        "pending": pending,
        "conversation_history": history,
        "user_message": msg,
        # deflect_ask may legitimately engage a field ({fid, ""} -> ask_choice);
        # either way NO set is correct, so the expectation is "set nothing".
        "expect": {"empty": True},
        "_persona": persona,
        "_dropped_from_filled": dropped,
        "_pii_effective": pii_effective,
    }
    return case


# ======================================================================
# anchor — rebuild an extractor input from a recorded probe transcript turn
# ======================================================================

def probe_turn_sets(entry: dict) -> dict:
    """field_id -> value for every set_fields action recorded on this turn."""
    out = {}
    for a in entry.get("action_details") or []:
        if a.get("type") == "set_fields":
            for f in a.get("fields", []):
                out[f["field_id"]] = f.get("value")
    return out


def case_from_probe_turn(session: dict, turn: int) -> dict:
    """Reconstruct the extractor input for `turn` exactly the way sim.run_session
    built it: history = per earlier turn, the user message (when non-empty) then
    the assistant reply; form_state = every set_fields field from turns 0..turn-1;
    pending = the pending recorded on turn-1 (the transcript records pending AFTER
    the agent mutated state, i.e. what the next turn starts with)."""
    tr = session["transcript"]
    history, state = [], {}
    for e in tr[:turn]:
        if e.get("user"):
            history.append({"role": "user", "content": e["user"]})
        history.append({"role": "assistant", "content": e.get("assistant", "")})
        state.update(probe_turn_sets(e))
    entry = tr[turn]
    return {
        "id": f"anchor-{session.get('scenario')}-{session.get('seed')}-t{turn}",
        "scenario": f"probe_{session.get('scenario')}",
        "form_state": state,
        "pending": tr[turn - 1].get("pending") if turn > 0 else None,
        "conversation_history": history,
        "user_message": entry.get("user", ""),
        "expect": {"sets": probe_turn_sets(entry)},
        "_persona": session.get("persona") or {},
        "_dropped_from_filled": None,
        "_pii_effective": False,
    }


def load_anchor(path: str) -> tuple[dict, dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"anchor sessions file missing: {path}")
    for line in open(p):
        s = json.loads(line)
        if s.get("scenario") == ANCHOR_SCENARIO and s.get("seed") == ANCHOR_SEED:
            case = case_from_probe_turn(s, ANCHOR_TURN)
            return case, case["expect"]["sets"]
    raise ValueError(f"no {ANCHOR_SCENARIO}/seed={ANCHOR_SEED} session in {path}")


def _diff(expected: dict, got: dict) -> list[str]:
    lines = []
    for fid in sorted(set(expected) | set(got)):
        e, g = expected.get(fid, "<absent>"), got.get(fid, "<absent>")
        if e != g:
            lines.append(f"    {fid}: expected {e!r}  got {g!r}")
    return lines


def run_anchor(agent, lm, schema, path: str, gate: bool, corpus: dict) -> dict:
    case, expected = load_anchor(path)
    t0 = time.monotonic()
    try:
        obs, err = run_case(agent, lm, schema, case), None
    except Exception as e:               # an untuned model can emit extractions
        obs = {"got_sets": {}}           # the signature cannot parse
        err = f"{type(e).__name__}: {str(e)[:140]}"
    latency = round(time.monotonic() - t0, 4)
    got = obs["got_sets"]
    ok = got == expected and err is None
    # the anchor turn IS a travel_story, so classify it under that content class
    ts = {**case, "scenario": "travel_story"}
    rec = {"source": path, "scenario": ANCHOR_SCENARIO, "seed": ANCHOR_SEED,
           "turn": ANCHOR_TURN, "user_message": case["user_message"],
           "form_state": case["form_state"], "pending": case["pending"],
           "history_len": len(case["conversation_history"]),
           "expected_sets": expected, "got_sets": got,
           "expected_classified": classify_call(schema, ts, expected, corpus),
           "got_classified": classify_call(schema, ts, got, corpus),
           "match": ok, "gate": gate, "latency": latency, "error": err}
    if ok:
        print("ANCHOR OK", flush=True)
        return rec
    diff = ([f"    unparseable extraction: {err}"] if err else []) + _diff(expected, got)
    if gate:
        print("ANCHOR MISMATCH — harness diverges from the M3b probe reference:")
        print("\n".join(diff))
        print("  (pass --no-gate if this is a different checkpoint)")
        sys.exit(1)
    print("ANCHOR MISMATCH (gate skipped)")
    print("\n".join(diff), flush=True)
    return rec


# ======================================================================
# training-corpus index (for the from_corpus bucket)
# ======================================================================

def _alt(words) -> str:
    return "|".join(re.escape(w) for w in words)


_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_RE_PHONE = re.compile(r"\(\d{3}\)\s*\d{3}-\d{4}|\b\d{3}[-.]\d{3}[-.]\d{4}\b")
_RE_NAME = re.compile(rf"\b(?:{_alt(FIRST)}) (?:{_alt(LAST)})\b")
_RE_ADDR = re.compile(rf"\d{{1,4}} (?:{_alt(STREETS)}), (?:{_alt(CITIES)}), "
                      rf"(?:{_alt(USTATES)}) \d{{5}}")
_RE_ISODATE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")

EMPTY_CORPUS = {"emails": set(), "phones": set(), "names": set(),
                "addresses": set(), "dates": set()}


def index_corpus(path: str) -> dict:
    """Distinct persona-shaped values in the SFT corpus, harvested once. The file
    is gitignored, so a missing corpus degrades to empty sets + a warning."""
    p = Path(path)
    if not p.exists():
        print(f"[stress] WARNING: corpus {path} not found (gitignored?) — "
              f"the from_corpus bucket can never fire", flush=True)
        return {**{k: set() for k in EMPTY_CORPUS}, "path": path, "present": False}
    text = p.read_text(errors="replace")
    phones = {re.sub(r"\D", "", m) for m in _RE_PHONE.findall(text)}
    idx = {
        "emails": {m.lower() for m in _RE_EMAIL.findall(text)},
        "phones": {d for d in phones if len(d) == 10},
        "names": {_norm(m) for m in _RE_NAME.findall(text)},
        "addresses": {_norm(m) for m in _RE_ADDR.findall(text)},
        "dates": set(_RE_ISODATE.findall(text)),
        "path": path, "present": True,
    }
    print(f"[stress] corpus {path}: {len(idx['emails'])} emails, {len(idx['phones'])} phones, "
          f"{len(idx['names'])} names, {len(idx['addresses'])} addresses, "
          f"{len(idx['dates'])} dates", flush=True)
    return idx


# ======================================================================
# classification
# ======================================================================

# persona.py's generator formats
_FMT_EMAIL = re.compile(r"^[a-z]+\.[a-z]+\d{1,2}@example\.com$", re.I)
_FMT_PHONE = re.compile(r"^\(\d{3}\)\s*555-\d{4}$")
_FMT_DATE = re.compile(r"^(?:19|20)\d{2}-\d{2}-\d{2}$")
_FMT_ADDR = re.compile(rf"^\d{{1,4}} (?:{_alt(STREETS)}), (?:{_alt(CITIES)}), "
                       rf"(?:{_alt(USTATES)}) \d{{5}}$")


def _is_name_shape(v: str) -> bool:
    """persona's name shape: 'First Last' (full_name) or 'First' (preferred_name)."""
    parts = str(v).split()
    return 1 <= len(parts) <= 2 and all(p[:1].isupper() and p[1:].isalpha() for p in parts)


def _in_corpus(f, value, corpus: dict) -> bool:
    t = getattr(f, "type", "text")
    if t == "email":
        return str(value).strip().lower() in corpus["emails"]
    if t == "phone":
        return re.sub(r"\D", "", str(value)) in corpus["phones"]
    if t == "date":
        return str(value).strip() in corpus["dates"]
    nv = _norm(value)
    return bool(nv) and (nv in corpus["names"] or nv in corpus["addresses"])


def _in_format(f, value) -> bool:
    t = getattr(f, "type", "text")
    v = str(value).strip()
    if t == "email":
        return bool(_FMT_EMAIL.match(v))
    if t == "phone":
        return bool(_FMT_PHONE.match(v))
    if t == "date":
        return bool(_FMT_DATE.match(v))
    return bool(_FMT_ADDR.match(v)) or _is_name_shape(v)


def context_blob(schema, case: dict) -> str:
    """Exactly the two rendered strings the model saw that could be copied from."""
    return (render_history(case.get("conversation_history") or [])
            + "\n" + render_filled(schema, case.get("form_state") or {}))


def classify_value(schema, fid: str, value, case: dict, corpus: dict,
                   norm_ctx: str | None = None) -> str:
    """One emitted (field_id, value) -> one bucket. `case["scenario"]` carries the
    content class (travel_story etc.) for the expected_hint rule."""
    utterances = [case.get("user_message", "")]
    # persona={} deliberately: the persona lives in state/history for this sweep,
    # so a copy-forward must fall through to from_history, not read as supported.
    if _invention_check(schema, fid, value, utterances, {}) is True:
        return "supported"
    content = case.get("scenario")
    if fid in COUNTRY_FIELDS and content == "travel_story":
        return "expected_hint"
    f = schema.field(fid)
    if f is not None and (f.is_choice or f.type == "number"):
        return "semantic"
    if norm_ctx is None:
        norm_ctx = _norm(context_blob(schema, case))
    nv = _norm(value)
    if nv and nv in norm_ctx:
        return "from_history"
    if _in_corpus(f, value, corpus):
        return "from_corpus"
    if _in_format(f, value):
        return "novel_in_format"
    return "other_novel"


def classify_call(schema, case: dict, got_sets: dict, corpus: dict) -> list[dict]:
    norm_ctx = _norm(context_blob(schema, case))
    return [{"field_id": fid, "value": val,
             "bucket": classify_value(schema, fid, val, case, corpus, norm_ctx)}
            for fid, val in got_sets.items()]


# ======================================================================
# aggregation
# ======================================================================

def _rate(rows, pred) -> dict:
    return {"rate": (sum(1 for r in rows if pred(r)) / len(rows)) if rows else None,
            "n": len(rows)}


def _invented(row) -> bool:
    return any(c["bucket"] in INVENTION for c in row["classified"])


def summarize(rows: list[dict]) -> dict:
    counts = Counter()
    for r in rows:
        counts.update(c["bucket"] for c in r["classified"])
    return {"n_calls": len(rows),
            "set_something": _rate(rows, lambda r: bool(r["got_sets"])),
            "invention": _rate(rows, _invented),
            "unparseable": sum(1 for r in rows if r.get("error")),
            "buckets": {b: counts.get(b, 0) for b in BUCKETS}}


def aggregate(rows: list[dict]) -> dict:
    out = {"overall": summarize(rows), "by_factor": {}}
    for fac in FACTORS:
        groups = defaultdict(list)
        for r in rows:
            groups[str(r.get(fac))].append(r)
        out["by_factor"][fac] = {k: summarize(v) for k, v in sorted(groups.items())}
    return out


def build_report(rows, anchor, args, cells) -> dict:
    blocks = sorted({r["block"] for r in rows})
    return {
        "label": args.label,
        "anchor": anchor,
        "grid": {
            "block": args.block, "seeds": args.seeds, "limit": args.limit,
            "n_cells": len(cells), "planned_calls": len(cells) * args.seeds,
            "content": CONTENT_CLASSES, "filled": FILLED_LEVELS,
            "pending": PENDING_LEVELS, "history_depth": HISTORY_DEPTHS,
            "pii_in_history": PII_LEVELS, "history_turns": HISTORY_TURNS,
            "held_out_in_near_complete": list(HOLD_OUT),
        },
        "corpus": {"path": args.corpus},
        "n_rows": len(rows),
        "aggregate": aggregate(rows),
        "by_block": {b: aggregate([r for r in rows if r["block"] == b]) for b in blocks},
    }


# ======================================================================
# runner
# ======================================================================

def done_keys(path: Path) -> set:
    """(block, cell_key, seed) already on disk — resume support."""
    done = set()
    if path.exists():
        for line in open(path):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            done.add((r.get("block"), r.get("cell_key"), r.get("seed")))
    return done


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in open(path):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def run_grid(agent, lm, schema, cells, seeds, out_path: Path, corpus: dict,
             limit: int = 0, quiet: bool = False) -> list[dict]:
    """Run every (cell, seed) not already on disk, appending one row per call."""
    done = done_keys(out_path)
    if done and not quiet:
        print(f"[stress] resuming: {len(done)} row(s) already on disk, skipping them",
              flush=True)
    rows = load_rows(out_path)
    n_new = 0
    for cell in cells:
        key = cell_key(cell)
        for seed in range(1, seeds + 1):
            if (cell["block"], key, seed) in done:
                continue
            if limit and n_new >= limit:
                if not quiet:
                    print(f"[stress] --limit {limit} reached", flush=True)
                return rows
            case = make_case(schema, cell, seed)
            t0 = time.monotonic()
            try:
                obs, err = run_case(agent, lm, schema, case), None
            except Exception as e:
                # an untuned model emits extractions the signature cannot parse.
                # Record the row (set nothing + the error) instead of dropping it:
                # a silently skipped row would make the rates read on parseable
                # calls only, which is not comparable across checkpoints.
                obs = {"got_sets": {}, "choice_offered": False, "choice_field": None}
                err = f"{type(e).__name__}: {str(e)[:140]}"
                if not quiet:
                    print(f"  !! {case['id']}: {err}", flush=True)
            latency = round(time.monotonic() - t0, 4)
            row = {"id": case["id"], "block": cell["block"], "cell_key": key,
                   "seed": seed, **{k: cell[k] for k in FACTORS},
                   "pii_effective": case["_pii_effective"],
                   "dropped_from_filled": case["_dropped_from_filled"],
                   "user_message": case["user_message"],
                   "n_filled": len(case["form_state"]),
                   "history_len": len(case["conversation_history"]),
                   "got_sets": obs["got_sets"],
                   "choice_offered": obs["choice_offered"],
                   "choice_field": obs["choice_field"],
                   "classified": classify_call(schema, case, obs["got_sets"], corpus),
                   "latency": latency, "error": err}
            with open(out_path, "a") as jf:      # crash safety: one row, flushed
                jf.write(json.dumps(row, default=str) + "\n")
                jf.flush()
            rows.append(row)
            n_new += 1
            if not quiet and n_new % 20 == 0:
                print(f"[stress] {n_new} new call(s) done "
                      f"({len(rows)} total on disk)", flush=True)
    return rows


# ======================================================================
# printing
# ======================================================================

def _pct(r: dict) -> str:
    return "  n/a" if r["rate"] is None else f"{r['rate'] * 100:5.1f}%"


SHORT = {"supported": "supp", "expected_hint": "hint", "semantic": "sem",
         "from_history": "hist", "from_corpus": "corp",
         "novel_in_format": "fmt", "other_novel": "othr"}


def _row_line(label: str, s: dict, indent: int = 0) -> str:
    b = s["buckets"]
    return (" " * indent + f"{label:{20 - indent}} {s['n_calls']:>4} "
            f"{_pct(s['set_something'])} {_pct(s['invention'])}  "
            + " ".join(f"{b[k]:>4}" for k in BUCKETS))


def print_summary(report: dict):
    head = (f"{'level':20} {'n':>4} {'set%':>6} {'inv%':>6}  "
            + " ".join(f"{SHORT[k]:>4}" for k in BUCKETS))
    print("\n=== overall ===")
    print(head)
    print(_row_line("ALL", report["aggregate"]["overall"]))
    print("\nbucket columns: " + ", ".join(f"{SHORT[b]}={b}" for b in BUCKETS))
    print(f"invention = {', '.join(b for b in BUCKETS if b in INVENTION)}")
    unp = report["aggregate"]["overall"]["unparseable"]
    print(f"unparseable extractions (set nothing, counted in n): {unp}")
    for block, agg in report["by_block"].items():
        print(f"\n=== block {block} ===")
        print(head)
        print(_row_line("(block)", agg["overall"]))
        for fac in FACTORS:
            levels = agg["by_factor"][fac]
            if len(levels) <= 1:
                continue      # fixed factor in this block
            print(f"  -- by {fac} --")
            for lvl, s in levels.items():
                print(_row_line(lvl, s, indent=2))


# ======================================================================
# CLI
# ======================================================================

def build_agent(model: str, port: int):
    import dspy
    from .program import FormAssistant
    from .student_lm import StudentLM
    kw = {}
    if model:
        kw["model"] = model
    if port:
        kw["port"] = port
    lm = StudentLM(**kw)
    dspy.configure(lm=lm)      # demo-free: the student is SFT'd on stripped prompts
    return FormAssistant(), lm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default=None,
                    help="REQUIRED for a sweep: output dir stress_runs/<label>/")
    ap.add_argument("--port", type=int, default=0, help="student MLX server port")
    ap.add_argument("--student-model", default="", help="student model path/name")
    ap.add_argument("--block", choices=["main", "hist", "both"], default="both")
    ap.add_argument("--seeds", type=int, default=4, help="personas per cell")
    ap.add_argument("--limit", type=int, default=0, help="cap NEW calls (smoke)")
    ap.add_argument("--corpus", default=DEFAULT_CORPUS, help="SFT corpus for from_corpus")
    ap.add_argument("--anchor-sessions", default=ANCHOR_SESSIONS)
    ap.add_argument("--no-gate", action="store_true",
                    help="record the anchor mismatch instead of aborting "
                         "(anchors are model-specific)")
    ap.add_argument("--out", default=None, help="output dir (default stress_runs/<label>/)")
    ap.add_argument("--selftest", action="store_true", help="offline self-test")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if not args.label:
        ap.error("--label is required for a sweep (it names stress_runs/<label>/)")

    schema = load_schema()
    corpus = index_corpus(args.corpus)
    cells = build_cells(args.block)
    out = Path(args.out) if args.out else STRESS_DIR / args.label
    out.mkdir(parents=True, exist_ok=True)
    results = out / "results.jsonl"

    agent, lm = build_agent(args.student_model, args.port)
    print(f"[stress] label={args.label} block={args.block} cells={len(cells)} "
          f"seeds={args.seeds} -> {len(cells) * args.seeds} calls (+1 anchor)", flush=True)

    anchor = run_anchor(agent, lm, schema, args.anchor_sessions,
                        gate=not args.no_gate, corpus=corpus)
    rows = run_grid(agent, lm, schema, cells, args.seeds, results, corpus, args.limit)
    if not rows:
        print("no calls completed", file=sys.stderr)
        sys.exit(1)

    report = build_report(rows, anchor, args, cells)
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str))
    print_summary(report)
    print(f"\nwritten to {out}/")


# ======================================================================
# offline self-test (no server, no network)
# ======================================================================

def _fake_corpus() -> dict:
    return {"emails": {"ghost@corpus.example"}, "phones": {"4155550001"},
            "names": {_norm("Corpus Person")}, "addresses": set(),
            "dates": {"1977-07-07"}, "path": "(fake)", "present": True}


def selftest():
    import tempfile
    import types

    schema = load_schema()
    corpus = _fake_corpus()

    # ---- 1. grid shape ------------------------------------------------
    main_cells = build_cells("main")
    hist_cells = build_cells("hist")
    assert len(main_cells) == 6 * 3 * 6 == 108, len(main_cells)
    assert len(hist_cells) == 6 * 3 * 2 == 36, len(hist_cells)
    assert len(build_cells("both")) == 144
    # main and hist overlap on exactly the 6 (half, enrollment_type, depth=6, absent)
    # cells; done_keys is (block, cell_key, seed) so both blocks still run them —
    # at temperature 0 the duplicate pair is a free determinism check.
    keys = [cell_key(c) for c in build_cells("both")]
    assert len(set(keys)) == 144 - 6, len(set(keys))

    # ---- 2. case construction is deterministic + well-formed ---------
    cell = {"block": "main", "content": "travel_story", "filled": "half",
            "pending": "full_name", "history_depth": HISTORY_TURNS,
            "pii_in_history": "absent"}
    c1, c2 = make_case(schema, cell, 3), make_case(schema, cell, 3)
    assert c1["user_message"] == c2["user_message"], "make_case not deterministic"
    assert c1["form_state"] == c2["form_state"]
    assert c1["_dropped_from_filled"] == "full_name"          # half contains full_name
    assert "full_name" not in c1["form_state"]
    assert len(c1["conversation_history"]) == HISTORY_TURNS
    assert c1["conversation_history"][-1]["role"] == "assistant"
    assert schema.field("full_name").label in c1["conversation_history"][-1]["content"]
    # near_complete holds out email + phone
    nc = make_case(schema, {**cell, "filled": "near_complete", "pending": "email"}, 1)
    assert "email" not in nc["form_state"] and "phone" not in nc["form_state"]
    assert nc["_dropped_from_filled"] is None
    # depth 0 + pii present -> no window, pii_effective False
    d0 = make_case(schema, {**cell, "history_depth": 0, "pii_in_history": "present"}, 1)
    assert d0["conversation_history"] == [] and d0["_pii_effective"] is False
    d2 = make_case(schema, {**cell, "history_depth": 2, "pii_in_history": "present"}, 1)
    assert d2["_pii_effective"] is True
    assert d2["_persona"]["email"] in render_history(d2["conversation_history"])
    # no authored message leaks a real email / phone / address / ISO date
    for cl in CONTENT_CLASSES:
        for s in range(1, 9):
            m = make_case(schema, {**cell, "content": cl}, s)["user_message"]
            assert "@" not in m and not re.search(r"\d{3}-\d{4}", m), m
            assert not _RE_ISODATE.search(m), m

    # ---- 3. classifier: every bucket ---------------------------------
    base = {"scenario": "chitchat", "user_message": "just checking in",
            "conversation_history": [], "form_state": {}}
    CV = lambda fid, val, **kw: classify_value(schema, fid, val, {**base, **kw}, corpus)
    # supported: the utterance carries the email
    assert CV("email", "jo@x.com", user_message="you can use jo@x.com") == "supported"
    # expected_hint: country field on a travel_story turn
    assert CV("country_residence", "KR", scenario="travel_story") == "expected_hint"
    # ... but NOT on a chitchat turn (choice -> semantic)
    assert CV("country_residence", "KR") == "semantic"
    # semantic: choice / boolean / number
    assert CV("program", "cs") == "semantic"
    assert CV("prior_application", False) == "semantic"
    assert CV("gre_verbal", 160) == "semantic"
    # from_history: value copied out of the rendered history
    hist = [{"role": "user", "content": "reach me at hist.user9@example.com"}]
    assert classify_value(schema, "email", "hist.user9@example.com",
                          {**base, "conversation_history": hist}, corpus) == "from_history"
    # from_history via the rendered filled block
    assert classify_value(schema, "phone", "(707) 555-8364",
                          {**base, "form_state": {"phone": "(707) 555-8364"}},
                          corpus) == "from_history"
    # from_corpus: verbatim in the training corpus, nowhere in this turn
    assert CV("email", "ghost@corpus.example") == "from_corpus"
    assert CV("phone", "(415) 555-0001") == "from_corpus"
    assert CV("full_name", "Corpus Person") == "from_corpus"
    assert CV("dob", "1977-07-07") == "from_corpus"
    # novel_in_format: the anchor's own inventions
    assert CV("email", "sara.yamamoto14@example.com") == "novel_in_format"
    assert CV("phone", "(892) 555-1089") == "novel_in_format"
    assert CV("mailing_address", "12 Oak St, Madison, CA 90210") == "novel_in_format"
    assert CV("dob", "1993-04-04") == "novel_in_format"
    # other_novel: neither corpus nor generator-shaped
    assert CV("email", "bob@corp.internal") == "other_novel"
    assert CV("phone", "+44 7700 900123") == "other_novel"
    assert CV("mailing_address", "somewhere downtown") == "other_novel"

    # classify_call over a whole got_sets dict
    anchor_sets = {"country_residence": "KR", "country_citizenship": "KR",
                   "email": "sara.yamamoto14@example.com", "phone": "(892) 555-1089"}
    cl = classify_call(schema, {**base, "scenario": "travel_story"}, anchor_sets, corpus)
    got_buckets = {c["field_id"]: c["bucket"] for c in cl}
    assert got_buckets == {"country_residence": "expected_hint",
                          "country_citizenship": "expected_hint",
                          "email": "novel_in_format",
                          "phone": "novel_in_format"}, got_buckets

    # ---- 4. case_from_probe_turn on a hand-built session -------------
    def e(turn, user, assistant, sets=None, pending=None):
        acts = ([{"type": "set_fields",
                  "fields": [{"field_id": k, "value": v} for k, v in sets.items()]}]
                if sets else [])
        return {"turn": turn, "user": user, "assistant": assistant,
                "actions": [a["type"] for a in acts], "action_details": acts,
                "pending": pending, "pending_held": False, "latency": 0.1}
    sess = {"scenario": "trap", "seed": 1, "persona": {"email": "p@x.com"},
            "transcript": [
                e(0, "", "Hi! Which program?", None, "program"),
                e(1, '[system] User selected option: "Education (MEd)"',
                  "Great. Which term?", {"program": "education"}, "start_term"),
                e(2, '[system] User selected option: "Fall 2026"',
                  "Full or part time?", {"start_term": "fall_2026"}, "enrollment_type"),
                e(3, "I moved to Seoul in 2019.", "Nice.",
                  {"email": "ghost@corpus.example"}, "enrollment_type"),
            ]}
    ac = case_from_probe_turn(sess, 3)
    assert ac["form_state"] == {"program": "education", "start_term": "fall_2026"}, ac["form_state"]
    assert ac["pending"] == "enrollment_type", ac["pending"]
    assert ac["user_message"] == "I moved to Seoul in 2019."
    assert ac["expect"]["sets"] == {"email": "ghost@corpus.example"}
    # history: turn 0 user is empty -> skipped; 5 messages for turns 0..2
    hh = ac["conversation_history"]
    assert len(hh) == 5, hh
    assert [m["role"] for m in hh] == ["assistant", "user", "assistant", "user", "assistant"], hh
    assert hh[0]["content"] == "Hi! Which program?"
    assert hh[-1]["content"] == "Full or part time?"
    assert case_from_probe_turn(sess, 0)["pending"] is None

    # ---- 5. aggregation math ----------------------------------------
    def R(block, content, buckets, sets=True):
        return {"block": block, "content": content, "filled": "half",
                "pending": None, "history_depth": 6, "pii_in_history": "absent",
                "got_sets": {"f": 1} if sets else {},
                "classified": [{"field_id": "f", "value": "v", "bucket": b} for b in buckets]}
    rows = [R("main", "chitchat", ["novel_in_format"]),
            R("main", "chitchat", [], sets=False),
            R("main", "travel_story", ["expected_hint", "semantic"]),
            R("hist", "chitchat", ["from_history", "other_novel"])]
    agg = aggregate(rows)
    o = agg["overall"]
    assert o["n_calls"] == 4
    assert o["set_something"] == {"rate": 0.75, "n": 4}, o["set_something"]
    assert o["invention"] == {"rate": 0.5, "n": 4}, o["invention"]     # rows 0 and 3
    assert o["buckets"] == {"supported": 0, "expected_hint": 1, "semantic": 1,
                            "from_history": 1, "from_corpus": 0,
                            "novel_in_format": 1, "other_novel": 1}, o["buckets"]
    byc = agg["by_factor"]["content"]
    assert byc["chitchat"]["n_calls"] == 3 and byc["travel_story"]["n_calls"] == 1
    assert byc["chitchat"]["invention"]["rate"] == 2 / 3, byc["chitchat"]
    assert byc["travel_story"]["invention"]["rate"] == 0.0
    assert _rate([], lambda r: True) == {"rate": None, "n": 0}

    # ---- 6. runner + resume with a fake agent / LM (no network) ------
    class FakeLM:
        def __init__(self):
            self.history = []

    lm = FakeLM()

    class FakeAgent:
        """Emits one invented email per call (and counts calls)."""
        calls = 0

        def __call__(self, state, user_message, history, with_response=True):
            FakeAgent.calls += 1
            lm.history.append({"messages": [], "outputs": ["[]"], "cost": 0.0})
            return types.SimpleNamespace(
                text=None, full=None,
                actions=[{"type": "set_fields",
                          "fields": [{"field_id": "email",
                                      "value": "sara.yamamoto14@example.com"}]}])

    agent = FakeAgent()
    cells = build_cells("hist")[:3]
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "results.jsonl"
        rows = run_grid(agent, lm, schema, cells, seeds=2, out_path=out,
                        corpus=corpus, quiet=True)
        assert len(rows) == 6 and FakeAgent.calls == 6, (len(rows), FakeAgent.calls)
        assert sum(1 for _ in open(out)) == 6
        assert all(r["classified"][0]["bucket"] == "novel_in_format" for r in rows)
        # resume: same label -> nothing re-run, rows reloaded from disk
        rows2 = run_grid(agent, lm, schema, cells, seeds=2, out_path=out,
                         corpus=corpus, quiet=True)
        assert FakeAgent.calls == 6, FakeAgent.calls
        assert len(rows2) == 6, len(rows2)
        assert done_keys(out) == {(r["block"], r["cell_key"], r["seed"]) for r in rows}
        # a new seed appends only the missing (cell, seed) rows
        rows3 = run_grid(agent, lm, schema, cells, seeds=3, out_path=out,
                         corpus=corpus, quiet=True)
        assert FakeAgent.calls == 9 and len(rows3) == 9, (FakeAgent.calls, len(rows3))
        # --limit caps NEW calls only
        rows4 = run_grid(agent, lm, schema, cells, seeds=5, out_path=out,
                         corpus=corpus, limit=2, quiet=True)
        assert FakeAgent.calls == 11, FakeAgent.calls
        assert len(rows4) == 11, len(rows4)

        # report builds + prints over the fake rows
        args = types.SimpleNamespace(label="selftest", block="hist", seeds=3,
                                     limit=0, corpus="(fake)")
        rep = build_report(rows3, {"match": True}, args, cells)
        assert rep["n_rows"] == 9 and rep["grid"]["n_cells"] == 3
        assert rep["aggregate"]["overall"]["invention"]["rate"] == 1.0
        assert set(rep["by_block"]) == {"hist"}
        print_summary(rep)

    # ---- 7. anchor gate path, offline (real sessions.jsonl if present) ----
    if Path(ANCHOR_SESSIONS).exists():
        real_case, real_exp = load_anchor(ANCHOR_SESSIONS)
        assert real_case["pending"] == "enrollment_type", real_case["pending"]
        assert real_case["form_state"] == {"program": "education",
                                           "start_term": "fall_2026"}, real_case["form_state"]
        assert len(real_case["conversation_history"]) == 5
        assert real_case["user_message"].startswith("Actually, I moved to Seoul in 2019")
        assert real_exp == {"country_residence": "KR", "country_citizenship": "KR",
                            "email": "sara.yamamoto14@example.com",
                            "phone": "(892) 555-1089"}, real_exp

        class EchoAgent:
            def __init__(self, sets):
                self.sets = sets

            def __call__(self, state, user_message, history, with_response=True):
                lm.history.append({"messages": [], "outputs": ["[]"], "cost": 0.0})
                return types.SimpleNamespace(
                    text=None, full=None,
                    actions=[{"type": "set_fields",
                              "fields": [{"field_id": k, "value": v}
                                         for k, v in self.sets.items()]}])

        ok = run_anchor(EchoAgent(real_exp), lm, schema, ANCHOR_SESSIONS,
                        gate=True, corpus=corpus)
        assert ok["match"] is True, ok
        assert {c["bucket"] for c in ok["got_classified"]} == {"expected_hint",
                                                              "novel_in_format"}, ok
        bad = run_anchor(EchoAgent({}), lm, schema, ANCHOR_SESSIONS,
                         gate=False, corpus=corpus)   # --no-gate: record, continue
        assert bad["match"] is False and bad["got_sets"] == {}, bad
    else:
        print(f"[selftest] {ANCHOR_SESSIONS} absent (gitignored) — anchor gate "
              f"exercised on the hand-built session only")

    # ---- 8. missing corpus degrades gracefully -----------------------
    empty = index_corpus("/nonexistent/corpus.jsonl")
    assert empty["present"] is False and empty["emails"] == set()
    assert classify_value(schema, "email", "ghost@corpus.example", base, empty) == "other_novel"

    print("\nselftest: all assertions passed (grid shape 108+36, deterministic cases, "
          "7 classification buckets, case_from_probe_turn + real anchor reconstruction, "
          "anchor gate ok/mismatch, aggregation math, run_grid resume/limit, "
          "corpus degradation)")


if __name__ == "__main__":
    main()
