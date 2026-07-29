"""v3 frozen eval set — REAL contexts (farmed sim snapshots) + authored messages.

Why v3 exists. v1 and v2 both hand-authored their contexts and both were
defective for it: v1 shipped `pending` with an empty history (a state the product
can never reach), and v2 gave its 17 hand-authored edges a blanket program
greeting that contradicts their `pending` field. Every v2 realistic case carries
exactly ONE history message and a near-empty form, so v2 cannot exercise
mid-conversation behavior — which is where every real failure has been found.

v3 keeps the authored half (message + expectation) and takes the context from the
farm: each case is a real extractor input recorded mid-session by
`datagen.farm_session` (form_state, pending, history verbatim). The snapshot's own
user_message is DISCARDED and replaced by the injected eval message.

Four build-blocking gates, all offline:
  1. registry — every scenario emits its message AND its expectation together
     (`variants()` returns [(message, expect)]). There is nowhere to attach an
     expectation after the fact, and so nowhere to add a scoring-time exemption.
  2. coercion round-trip — every expectation value survives the harness's own
     canonicalization (validator.coerce / match_options); the CANONICAL value is
     what gets stored. An unsatisfiable expectation measures the validator.
  3. collision detector — training-template phrasings (datagen.py) and prior eval
     messages (eval_set*.jsonl) must not leak into v3 frames. Exact frame match or
     a shared 5-word span fails the build; token overlap is printed for review.
  4. snapshot-used-once — no two cases share a context.

Value pools are format-DISJOINT from persona.py: the student memorized
`first.last##@example.com` / `(NXX) 555-XXXX` / `#### <Street>, <City>, <ST> #####`
shapes (a stress sweep found every invented value generator-shaped, zero verbatim
training values), so an eval reusing those shapes cannot tell transcription from
format completion.

  Human review BEFORE generating (all scenarios x all variants, on real contexts):
    tuning/v2/.venv/bin/python -m tuning.v2.eval_gen --templates
  Offline self-test (registry, gates, quotas, bands, scorer schema):
    tuning/v2/.venv/bin/python -m tuning.v2.eval_gen --selftest
  Build the set (writes eval_set_v3.jsonl + cases_v3.md + report_v3.json):
    tuning/v2/.venv/bin/python -m tuning.v2.eval_gen --per-scenario 20 --seed 0
"""
from __future__ import annotations
import argparse
import ast
import json
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import persona as personas
from . import validator
from .schema import Schema, load_schema
from .state import TurnState, Pending, CONFIRM_SUBMIT

SNAPSHOTS_DEFAULT = ["tuning/v2/datagen_runs/eval_farm_p1/snapshots.jsonl",
                     "tuning/v2/datagen_runs/eval_farm_p2/snapshots.jsonl"]
OUT_DIR = Path("tuning/v2/eval")
DATAGEN_PY = Path(__file__).resolve().parent / "datagen.py"
PRIOR_EVALS = [OUT_DIR / "eval_set.jsonl", OUT_DIR / "eval_set_v2.jsonl"]

BANDS = ("early", "mid", "late")

# cases per scenario. 23 scenarios x 18 = 414 <= 423 usable snapshots, and each
# snapshot is used at most once, so this is the pool's capacity — not a preference.
QUOTA = 18

# seeds 132-191 (eval_farm_p3..p6) are RESERVED and unallocated — never read here.


# ======================================================================
# value pools — formats disjoint from persona.py (asserted in --selftest)
# ======================================================================

NAMES = ["Beatrix Ohlmann", "Cormac Ifeanyi", "Halvard Sitole",
         "Perpetua Vanterpool", "Ingeborg Castellanos", "Aurelio Mkhwanazi"]
# real short names / nicknames, not truncations of the full name, and disjoint
# from persona.FIRST (which is what gen_persona uses for preferred_name)
PREFERRED = ["Bea", "Rusty", "Sunny", "Dot", "Bram", "Lettie"]
EMAILS = ["l.nguyen@sundaipartners.co.uk", "rmt3@student.northfield.edu",
          "k.oyelaran+apps@mailbox.org", "b.ohlmann@hallcroft-works.de",
          "cif2027@protonmail.ch", "perpetua@vanterpool.family"]
PHONES = ["415.782.3311", "212-903-4471", "07700 900461",
          "+49 30 901820", "0161 496 0123", "+81 3-6205-4111"]
# every date form here is one validator._DATE_FORMATS accepts (gate 2 proves it)
DATES = ["14 July 1996", "2 Feb 1993", "November 3, 1988",
         "07/22/1991", "1990-04-17", "28 Sep 1995"]
# street types absent from persona.STREETS; extra unit/postcode parts break the shape
ADDRESSES = ["88 Halyard Court, Apt 4B, New Bedford, MA 02740",
             "Flat 12, 3 Kirkgate Terrace, Leeds LS2 7DJ",
             "1704 Quarry Bend Parkway, Chattanooga, TN 37405",
             "Unit 9, 250 Coalbrook Row, Dunedin 9016, New Zealand",
             "62 Ashgrove Crescent, Ottawa, ON K1S 5B6"]
NOTES = ["I may need to defer a term if my visa is late.",
         "Happy to send anything else you need by email."]

# per-field raw values. Only fields listed here can carry an authored answer.
FIELD_VALUES = {
    "full_name": NAMES, "preferred_name": PREFERRED, "email": EMAILS,
    "phone": PHONES, "dob": DATES, "mailing_address": ADDRESSES,
    "anything_else": NOTES,
    "prior_application_year": ["2021", "2018", "2023"],
    "gre_verbal": ["163", "152"], "gre_quant": ["167", "159"],
    "gre_writing": ["4.5", "5.0"], "english_test_score": ["104", "97"],
    "gre_date": ["12 October 2024", "9 Mar 2025"],
    "english_test_date": ["6 Apr 2025", "19 January 2025"],
}

# fields a message can plausibly volunteer / correct, in the order bulk lists them
VOL = ["full_name", "email", "phone", "dob", "mailing_address", "preferred_name"]

# third-party mentions: names outside persona.FIRST/LAST so the student cannot have
# seen them in training (datagen's third_party maker draws FIRST+LAST pairs).
THIRD_PARTY_NAMES = ["Ravindra Achterberg", "Marguerite Ibori", "Desmond Quaintrell",
                     "Yolanda Ferreira-Sund", "Anselm Bergkamp"]


# ======================================================================
# snapshot helpers
# ======================================================================

def load_snapshots(paths: list[str]) -> list[dict]:
    """Farm snapshots, deduped by (session, turn), in a stable order. The recorded
    user_message is dropped here — v3 replaces it.

    Turn 0 is EXCLUDED: it is logged before the agent's first forward, so its
    history is empty and nothing is filled. Injecting a user message there means
    "the user speaks before the assistant has greeted", which the product never
    produces (the assistant always greets first, on turn 0's empty user message).
    That empty-history shape is the v1 eval defect; the earliest reachable user
    turn is turn 1, whose history holds the greeting."""
    seen, out = set(), []
    for p in paths:
        for line in open(p):
            s = json.loads(line)
            k = (s["session"], s["turn"])
            if k in seen or s["turn"] == 0:
                continue
            seen.add(k)
            out.append({"session": s["session"], "turn": s["turn"],
                        "form_state": s["form_state"], "pending": s.get("pending"),
                        "history": s.get("history") or []})
    out.sort(key=lambda s: (s["session"], s["turn"]))
    return out


def band_of(snap: dict) -> str:
    """Depth band from how much of the form is already filled. Replaces v2's
    realistic/contract-synthetic split, which sorted cases by how they were BUILT."""
    n = len(snap["form_state"])
    return "early" if n <= 3 else "mid" if n <= 7 else "late"


def _filled(snap: dict) -> dict:
    return {k: v for k, v in snap["form_state"].items() if v not in (None, "", [])}


def _pf(snap: dict, schema: Schema):
    """The pending Field, or None (confirm_submit is excluded everywhere)."""
    tgt = snap.get("pending")
    if not tgt or tgt == CONFIRM_SUBMIT:
        return None
    return schema.field(tgt)


def _state(snap: dict, schema: Schema) -> TurnState:
    tgt = snap.get("pending")
    return TurnState(schema=schema, form_state=dict(snap["form_state"]),
                     pending=Pending(tgt) if tgt else None)


def _binds_nowhere(raw: str, snap: dict, schema: Schema) -> bool:
    """True when the harness's own binding cascade places `raw` on NO field — the
    only way an `empty` expectation is reachable for a value-bearing token."""
    return validator._bind_unplaced(raw, _state(snap, schema)) is None


def last_assistant(snap: dict) -> str:
    for m in reversed(snap["history"]):
        if m.get("role") == "assistant":
            return m["content"]
    return ""


def _idx(snap: dict, i: int) -> int:
    """Deterministic rotation index — varies values/targets across snapshots while
    keeping variants() a pure function of (snapshot, schema)."""
    return snap["session"] * 7 + snap["turn"] * 3 + i


def _pick(pool: list, snap: dict, i: int):
    return pool[_idx(snap, i) % len(pool)]


def _unfilled_vol(snap: dict, exclude=()) -> list[str]:
    filled = _filled(snap)
    return [fid for fid in VOL if fid not in filled and fid not in exclude]


# ======================================================================
# gate 2 — coercion round-trip (build-blocking)
# ======================================================================

class GateError(Exception):
    """An expectation value the harness cannot produce."""


def canonicalize(raw: str, f) -> object:
    """The canonical value validator would store for `raw` on field `f`, or raise.
    Non-choice: validator.coerce. Choice: validator.match_options must yield exactly
    one option. multi_select: the same conjunction split the validator uses, every
    part matching exactly one option."""
    if f.is_choice:
        if f.is_multi:
            parts = [p for p in re.split(r"\s*(?:,|&|\band\b)\s*", str(raw)) if p.strip()]
            hits = [validator.match_options(p, f) for p in parts]
            if len(parts) < 2 or not all(len(h) == 1 for h in hits):
                raise GateError(f"{f.field_id}: multi_select parts do not each match one option: {raw!r}")
            vals, seen = [], set()
            for h in hits:
                v = h[0][0]
                if v not in seen:
                    seen.add(v)
                    vals.append(v)
            return vals
        hits = validator.match_options(raw, f)
        if len(hits) != 1:
            raise GateError(f"{f.field_id}: {len(hits)} options match {raw!r} (need exactly 1)")
        return hits[0][0]
    ok, canonical = validator.coerce(raw, f)
    if not ok:
        raise GateError(f"{f.field_id}: does not coerce to {f.type}: {raw!r}")
    return canonical


def _sets(schema: Schema, pairs: list[tuple]) -> dict:
    """expect = {"sets": {fid: CANONICAL}} — canonical, never the raw string."""
    out = {}
    for fid, raw in pairs:
        f = schema.field(fid)
        if f is None:
            raise GateError(f"{fid}: not in schema")
        out[fid] = canonicalize(raw, f)
    return {"sets": out}


def _empty() -> dict:
    return {"empty": True}


def _choice(fid: str) -> dict:
    return {"choice": [fid]}


def _no_match_ok(raw: str, f) -> bool:
    """The inverse gate: a no_match value must match NO option."""
    return validator.match_options(raw, f) == []


def _uncoercible(raw: str, f) -> bool:
    return not validator.coerce(raw, f)[0]


# ======================================================================
# message frames — 4-6 variants per scenario
#
# SCHEMA-LABEL DISCIPLINE: handing the model the exact schema label tests
# label-matching, not extraction, and is off-distribution in the EASY direction —
# datagen's own makers say "name's {n}, email {e}, phone {p}", never "Phone Number
# 415.782.3311". Every scenario that names a field therefore uses natural
# references (VOLUNTEER clauses / REF nouns) and keeps AT MOST ONE label-echoing
# variant, which is realistic because the assistant's last turn just named the
# field. `report_v3.json -> per_scenario.label_echo_*` audits this.
# ======================================================================

def _option_phrase(label) -> str:
    """How a user types an option in prose: "Part-time" -> "part time",
    "Computer Science (MS)" -> "computer science". validator.match_options still
    resolves it to exactly one option (proved by the coercion gate)."""
    s = re.sub(r"\s*\([^)]*\)$", "", str(label))
    return s.lower().replace("-", " ")


# how a real applicant volunteers a field in passing — natural words, no label.
# {v} is the value; the clause drops into the outer frames below.
VOLUNTEER = {
    "full_name": ["the name's {v}", "I'm {v}"],
    "preferred_name": ["everyone calls me {v}", "friends call me {v}"],
    # NOT "reach me on {v}" (datagen _INVALID 'reach me on instagram') and NOT
    # "I'm at {v}" (echoes _mk_bulk's "While I'm at it:") — both flagged by gate 3
    "email": ["my email's {v}", "drop me a line at {v}"],
    "phone": ["give me a ring on {v}", "my number's {v}"],
    "dob": ["I was born {v}", "my birthday's {v}"],
    "mailing_address": ["post goes to {v}", "mail comes to {v}"],
}
# short natural nouns for referring to a field without quoting its label.
# Single-word labels (Gender) are their own natural noun — the audit counts those
# as echoes even though there is no plainer English word.
REF = {
    "program": "program choice", "start_term": "start date",
    "enrollment_type": "how I'll be attending",
    "prior_application": "whether I applied before",
    "prior_application_year": "when that was",
    "full_name": "name", "preferred_name": "nickname", "dob": "birthday",
    "gender": "gender", "country_citizenship": "citizenship",
    "country_residence": "where I live", "email": "email", "phone": "number",
    "mailing_address": "address", "gre_taken": "GRE history",
    "gre_verbal": "verbal score", "gre_quant": "quant score",
    "gre_writing": "writing score", "gre_date": "GRE date",
    "toefl_required": "English test question", "english_test_type": "which test I took",
    "english_test_score": "test score", "english_test_date": "date I sat it",
    "has_work_experience": "work history", "funding_interest": "funding question",
    "funding_type": "funding preference", "disability_accommodation": "accommodations",
    "how_heard": "how I found you", "anything_else": "extra notes",
}


def _ref(f) -> str:
    return REF.get(f.field_id, str(f.label).lower())


def _clause(fid: str, raw: str, i: int) -> str:
    """A natural volunteer clause for (field, value)."""
    pool = VOLUNTEER[fid]
    return pool[i % len(pool)].format(v=raw)


F_PENDING = ["{v}", "That would be {v}.", "Here you go: {v}.",
             "Go ahead and use {v}.", "{v} — let me know if you need anything else.",
             "For the {l}, {v}."]                      # <- the one label echo

F_COMPOUND = ["{v}. Also, {c}.",
              "{v} — and while I'm here, {c}.",
              "{v}. Oh, {c} too.",
              "{v}. Put my {ol} down as {ov} while you're there."]   # <- label echo

F_BULK = ["To save time — {c1}, {c2}, {c3}.",
          "Since I'm here: {c1}; {c2}; {c3}.",
          "Three things at once — {c1}, {c2}, {c3}.",
          "Copying from my notes: {l1} is {v1}, {l2} is {v2}, {l3} is {v3}."]  # <- label echo

# typed_choice is per-field: an option label only reads as an ANSWER inside a frame
# that fits the question the assistant asked. "Sign me up for social media." is not
# an answer to "How did you hear about Northfield?" — it inverts the meaning.
TYPED_FRAMES = {
    "program": ["{x} is what I'm after.", "I'd like to do {x}.",
                "{x}, definitely.", "Put me in {x}."],
    "start_term": ["I'm aiming for {x}.", "{x} would be ideal.",
                   "Let's start {x}.", "{x}, if there's space."],
    "enrollment_type": ["{x} is what I need.", "I can only manage {x}.",
                        "Planning to go {x}.", "{x} suits my schedule."],
    # NOT "Go with {x}." / "{x} for me." — too close to _mk_typed_choice's
    # "let's go with {x}" / "{x} works for me" (gate 3 near-misses at J=0.67)
    "gender": ["{x}, thanks.", "I'd put {x}.", "Mark me as {x}.", "I identify as {x}."],
    "how_heard": ["Found you through {x}.", "It came up via {x}.",
                  "{x} — that's how I heard about you.", "Through {x}, if that's an option."],
}
# catch-alls read as nonsense in prose ("It came up via other") — never typed
SKIP_OPTIONS = {"other", "prefer_not_to_say", "OTHER"}

F_CORRECTION = ["Scratch the {r} I gave you — use {v} instead.",
                "One fix: change my {r} to {v}.",
                "I mistyped my {r}; the right one is {v}.",
                "Hmm, the {r} I said isn't current. It's {v} now.",
                "Please update the {l} on file to {v}."]        # <- the one label echo

# (target field, frame) — a real value buried in chatter. Distinct scenes from
# datagen's wrapped_value (hectic morning / kids yelling / dying phone / store queue).
WRAPPED = [
    ("email", "Sorry, the dog just got into the recycling — anyway {v} is my email."),
    ("phone", "One sec, someone's at the door. My number is {v}."),
    ("dob", "Ignore the background noise, upstairs neighbours again — born {v}."),
    ("mailing_address", "Half-listening, sorry, the kettle's going — post goes to {v}."),
    ("email", "Between meetings so I'll be quick — email {v}."),
    ("phone", "Typing one-handed with a toddler on me, so: {v}."),
]

# per-field, because "I'm a citizen of X" and "I live in X" are not interchangeable.
# One label echo each (the assistant just asked for that exact field).
FREETEXT_FRAMES = {
    "country_citizenship": ["{c} for citizenship.", "{c} — that's my citizenship.",
                            "My passport is from {c}.", "{c}, going by my passport.",
                            "For {l} that's {c}."],
    "country_residence": ["I live in {c}.", "{c} is home these days.",
                          "Based in {c} at the moment.",
                          "{c} — that's where I'm writing from.",
                          "For {l} that's {c}."],
}
COUNTRIES = ["South Korea", "Nigeria", "Germany", "Brazil", "Japan", "Mexico"]

# residence_statement: a PRESENT-TENSE residence claim volunteered mid-conversation.
# This used to be narrative_trap variant 0 ("Moved to Seoul in 2019 and I've been
# living in South Korea since"), where expect=empty scored a correct
# country_residence=KR as a failure — the same defect as attaching a blanket empty
# expectation to travel narratives. It is a POSITIVE case, and it independently
# covers the stress-sweep failure where the student answered a city/country
# narrative with country_citizenship (wrong field) instead of country_residence.
RESIDENCE_PAIRS = [("Seoul", "South Korea"), ("Osaka", "Japan"), ("Lagos", "Nigeria"),
                   ("Munich", "Germany"), ("Guadalajara", "Mexico"), ("Toronto", "Canada")]
F_RESIDENCE = ["Moved to {city} in 2019 and I've been living in {country} since.",
               "I'm over in {city} these days, so {country}.",
               "Been based in {city} for years now — {country}, that is.",
               "We relocated to {country} last spring; {city}, specifically.",
               "Living in {country} at the moment, out in {city}."]

# natural yes/no that never quotes the "Yes"/"No" button label. Mostly EXPLICIT
# (a stated yes/no in natural words); exactly two entries are indirect, marked
# below, and both are unambiguous. Anything a careful human would hesitate over
# ("I'm all set on that front") is out — a hesitant reading is a broken expectation.
BOOL_PHRASES = {
    "prior_application": [
        (True, "Yes, there's an earlier application under my name."),
        (True, "Yes — I started one a couple of years back."),
        (False, "No, this is a fresh application."),
        (False, "No, I've never applied."),
    ],
    "has_work_experience": [
        (True, "Yes, six years in industry."),
        (True, "I've been working full-time since I graduated."),   # indirect (1/2)
        (False, "No, I've not held a job yet."),
        (False, "No — I've been in school throughout."),
    ],
    "funding_interest": [
        (True, "Yes, I'd want to be considered."),
        (True, "Please — anything that lowers the bill."),          # indirect (2/2)
        (False, "No, I won't need any."),
        (False, "No thanks, tuition is covered."),
    ],
    "gre_taken": [
        (True, "Yes, I took it in the spring."),
        (False, "Not yet — it's still on my list."),
    ],
    "disability_accommodation": [
        (True, "Yes, I'll need accommodations arranged."),
        (False, "No, nothing needed."),
    ],
    "toefl_required": [
        (True, "Yes, I'll need to sit an English test."),
        (False, "No, my degree was taught in English."),
    ],
}
BOOL_FALLBACK = [(True, "Yes, that applies to me."), (False, "No, that doesn't apply.")]

F_MULTI = ["I'd go for {p} — both, if that's allowed.", "{p}, those two.",
           "Both apply: {p}.", "I'm after {p}, nothing else.",
           "{p} — those are the ones I'd qualify for."]
MULTI_PAIRS = [("teaching_assistantship", "fellowship"),
               ("research_assistantship", "scholarship"),
               ("fellowship", "scholarship"),
               ("teaching_assistantship", "research_assistantship")]

F_PRECEDENCE = ["Before I forget — {c}.", "Quick aside: {c}.",
                "Not what you asked, but {c}.",
                "While it's on my mind, my {l} is {v}."]      # <- the one label echo
PRECEDENCE_TARGETS = ["email", "phone", "dob", "mailing_address"]

CHITCHAT = ["The upstairs neighbour is learning the trumpet, apparently.",
            "I should really eat something before I keep going.",
            "It's pouring outside and of course I forgot a jacket.",
            "My tea went cold while I was typing.",
            "Wild how fast this month went by."]

RESTRAINT_Q = ["What documents will I need later on?",
               "Do you need transcripts uploaded, or is that a separate step?",
               "Is there an application fee at the end of this?",
               "Will I be able to edit anything once I've submitted?",
               "Does the programme require letters of recommendation?"]

F_REFUSAL = ["I'd rather keep my {r} to myself for now.",
             "Let's leave the {r} blank if that's allowed.",
             "I'll hold off on the {r} until I've spoken to my partner.",
             "I'd sooner not put that down yet.",
             "Skip the {l} for me, please."]                   # <- the one label echo

F_THIRD_NAME = ["{n} is the one who talked me into going back to school.",
                "{n} keeps texting me about deadlines, it's a lot.",
                "I carpool with {n}, who is doing something similar.",
                "{n} filled one of these out for a different university.",
                "My old manager {n} wrote one of my references."]

# (shadowed field, message) — a THIRD PARTY's fact that maps onto a form field.
# The stress sweep's real failure shape (26-30/96): the fact is not the applicant's.
# Every message states a fact about the THIRD PARTY ONLY. No claim — positive or
# negative — about the applicant, because a denial is itself an answer: the earlier
# "...under my cousin's name, not mine." made prior_application=False a legitimate
# reading, so `empty` would have scored a defensible answer as a failure. The
# selftest enforces this structurally: no first-person pronoun but the possessive
# "my". Frames also stay clear of datagen's "Funny, my friend {n} applied here
# years ago."
THIRD_PARTY_FACT = [
    ("prior_application", "My cousin went through this same application a couple of years back."),
    ("has_work_experience", "My partner has been working in the field for a decade."),
    ("country_residence", "My brother lives in Germany these days."),
    ("country_citizenship", "My father is a Canadian citizen."),
    ("dob", "My sister was born in 1994, if that gives you a sense of the family."),
    ("gre_taken", "My roommate took the GRE last month and is still recovering."),
]

# place/year narrative with NO answer in it. Every variant is checked against the
# whole schema by hand: no current residence claim (that is residence_statement,
# a positive case), no "my current job" (that would legitimately imply
# has_work_experience=True), no applicant date or number that maps to a field.
NARRATIVE = ["I did my undergrad in Lagos, ages ago now.",
             "We spent 2020 bouncing between my parents' place and a sublet.",
             "My daughter was born the year we moved house, 2017.",
             "Wild to think it's been a decade since graduation.",
             "Rent round here has doubled since 2016, honestly."]

# unlisted_country: the user names a country that is NOT one of the 14 options.
# Convention B (no inference): the extractor emits what the user said,
# match_options finds no hit, and a large select yields Outcome(CLARIFY) — nothing
# is set, the field stays pending, the assistant asks them to pick. OTHER binds
# only when the user themselves says "Other". So ANY set fails these cases.
#
# Variant 0 is the shape the stress sweep actually failed on: that turn made the
# student emit country_citizenship='NG' — wrong field AND wrong country — and no
# other eval case can catch it. It is the deliberate minimal pair of
# residence_statement's frame0 (same narrative, a LISTED country, expect=sets).
#
# NO near-miss names ("Britain", "America", "Holland", "Korea"): match_options
# returns [] for those today, but that is a validator alias gap, not correct
# behavior — "Britain" SHOULD reach United Kingdom. Freezing expect=empty for them
# would encode a harness weakness as ground truth, the same defect as the
# "the 3rd of March, 1994" case. See REVIEW_FLAGS.
UNLISTED = [
    ("Kenya", "Moved to Nairobi in 2014 for work. Been living in Kenya ever since."),
    ("Portugal", "Portugal, though I don't see it on the list."),
    ("Ghana", "Ghana is where I'm from."),
    ("Vietnam", "Home is Vietnam at present."),
    ("Egypt", "Egypt — hopefully that's alright."),
    ("Peru", "It's Peru for me."),
]
COUNTRY_FIELDS = ("country_citizenship", "country_residence")

# bare tokens that could be several things. Kept out of every numeric field's
# [min, max] so the cascade has no unique target (checked per snapshot anyway).
BARE_TOKENS = ["1999", "1987", "1996", "1974"]

# values with NO matching option, only for fields WITHOUT a catch-all "Other"
# option (how_heard / country_* are excluded: "Other" makes `empty` arguable).
NO_MATCH_VALUES = {
    "program": ["marine biology", "creative writing", "art history", "sports management"],
    "start_term": ["Summer 2029", "Winter 2030", "Spring 2031"],
    "enrollment_type": ["hybrid, mostly online", "weekend intensives", "self-paced online"],
    "gender": ["none of those fit me"],
    "english_test_type": ["the Cambridge one"],
    "funding_type": ["a grant from my old employer", "a sports bursary",
                     "a loan from my uncle"],
}
F_NO_MATCH = ["Can I do {v} instead?", "None of those — I want {v}.",
              "What I actually need is {v}.", "{v} is the one I had in mind."]

# uncoercible for the pending field's type (gate: validator.coerce must FAIL).
# Every value must be genuinely UNINTERPRETABLE, not merely unparseable by
# validator._DATE_FORMATS: "the 3rd of March, 1994" was dropped because a student
# emitting 1994-03-03 is right and would have been scored wrong — that encodes a
# harness limitation as ground truth. "31 February 1990" is an impossible date.
INVALID_VALUES = {
    "date": ["sometime in early 1993", "31 February 1990",
             "the summer after I graduated", "whatever my passport says"],
    "number": ["I don't remember the exact figure", "somewhere in the mid range"],
}
F_INVALID = ["Let's say {v}.", "I believe it was {v}.",
             "As best I recall, {v}.", "{v} — close enough?"]

F_ASKS = ["Remind me what {l} choices exist?",
          "I'm not sure what to put for {l} — what's available?",
          "Show me the {l} choices before I decide.",
          "What am I choosing between for {l}?"]
# short spoken terms, not f.label: how_heard's label is itself a question
# ("How did you hear about Northfield?") and reads as nonsense inside these frames.
ASK_TERMS = {"program": "program", "start_term": "start date",
             "enrollment_type": "enrollment", "gender": "gender"}
ASK_FIELDS = list(ASK_TERMS)

F_DEFLECT = ["Actually, let's do {l} first — what can I choose there?",
             "Can we jump to {l}? I want to see those options.",
             "I'd rather sort out {l} first. What's on offer?",
             "Hmm, park that — show me {l} choices."]

ALL_CLAUSES = [c for cs in VOLUNTEER.values() for c in cs]


def _composed(outer: list[str], slots: tuple) -> list[str]:
    """Outer frames with a VOLUNTEER clause substituted in, so the detector sees the
    text the user actually reads. Slot-only frames (no clause) pass through, and a
    clause is also registered on its own — a leak in either half gets caught."""
    out = []
    for frame in outer:
        if slots[0] in frame:
            for c in ALL_CLAUSES:
                out.append(frame.replace(slots[0], c))
        else:
            out.append(frame)
    return out


# Every literal message frame v3 can emit, per scenario. The collision detector
# (gate 3) reads THIS — so a new frame cannot dodge the check by living elsewhere.
EVAL_FRAMES = {
    "pending_answer": F_PENDING,
    "typed_choice": [f for fs in TYPED_FRAMES.values() for f in fs],
    "compound": _composed(F_COMPOUND, ("{c}",)) + ALL_CLAUSES,
    "bulk": _composed(F_BULK, ("{c1}",)) + ALL_CLAUSES,
    "correction": F_CORRECTION,
    "wrapped_value": [f for _fid, f in WRAPPED],
    "freetext_select": [f for fs in FREETEXT_FRAMES.values() for f in fs],
    "residence_statement": F_RESIDENCE,
    "boolean_phrase": [p for ps in BOOL_PHRASES.values() for _v, p in ps]
                      + [p for _v, p in BOOL_FALLBACK],
    "multi_select_subset": F_MULTI,
    "precedence": _composed(F_PRECEDENCE, ("{c}",)) + ALL_CLAUSES,
    "chitchat": CHITCHAT, "restraint_question": RESTRAINT_Q, "refusal": F_REFUSAL,
    "third_party_name": F_THIRD_NAME,
    "third_party_fact": [m for _fid, m in THIRD_PARTY_FACT],
    "narrative_trap": NARRATIVE, "bare_ambiguous": BARE_TOKENS,
    "unlisted_country": [m for _c, m in UNLISTED],
    "no_match": F_NO_MATCH, "invalid_value": F_INVALID,
    "asks_about_field": F_ASKS, "deflect": F_DEFLECT,
}

REVIEW_FLAGS = [
    ("third_party_name", F_THIRD_NAME[0],
     "'talked me into going back to school' is not 'told me about Northfield', so "
     "expect=empty; a model that binds how_heard=referral here is over-attributing, "
     "but the line is the closest any empty case comes to a defensible answer"),
    ("residence_statement", F_RESIDENCE[0],
     "was narrative_trap variant 0 under expect=empty, which scored a correct "
     "country_residence=KR as a failure; it is now a POSITIVE case. Countries are "
     "restricted to the 14 in the option list — a narrative naming a country that is "
     "NOT an option (the sweep's Nairobi/Kenya turn) has no unarguable expectation "
     "(Other? clarify?) and is therefore not in v3 at all. Snapshots whose pending "
     "field is country_citizenship or country_residence are excluded, so the "
     "residence reading is the only reading"),
    ("invalid_value", "the 3rd of March, 1994",
     "REMOVED: a clear date that validator._DATE_FORMATS simply cannot parse. A "
     "student emitting 1994-03-03 is right, so the case measured the harness"),
    ("unlisted_country", "(alias gap — near-miss country names are NOT in v3)",
     "convention B (no inference): an unlisted country sets nothing and the field "
     "stays pending; OTHER binds only when the user says 'Other'. v3 uses only "
     "genuinely unlisted countries (Kenya, Portugal, Ghana, Vietnam, Egypt, Peru). "
     "'Britain', 'Great Britain', 'America', 'Holland', 'Korea' also return [] from "
     "match_options today, but they SHOULD reach United Kingdom / United States / "
     "South Korea — that is a validator alias gap, a separate question from this "
     "convention, and freezing expect=empty for them would make a harness weakness "
     "into ground truth"),
]


# ======================================================================
# scenario variant builders — (variant_key, message, expect) emitted TOGETHER
#
# `variant_key` is STABLE across snapshots: it names the authored frame, not its
# position in this snapshot's (possibly filtered) list. Assignment rotates over
# keys, so a scenario whose best variants are only available on some contexts —
# third_party_fact needs its shadow field UNFILLED — cannot collapse onto the two
# variants that happen to be available in whatever snapshots are left over.
# ======================================================================

def v_pending_answer(snap, schema):
    f = _pf(snap, schema)
    if f is None or f.is_choice or f.field_id not in FIELD_VALUES:
        return []
    out = []
    for i, frame in enumerate(F_PENDING):
        raw = _pick(FIELD_VALUES[f.field_id], snap, i)
        out.append((f"frame{i}", frame.format(v=raw, l=f.label),
                    _sets(schema, [(f.field_id, raw)])))
    return out


def v_typed_choice(snap, schema):
    f = _pf(snap, schema)
    if f is None or f.field_id not in TYPED_FRAMES or not f.button_choice \
            or f.type == "boolean" or f.is_multi:
        return []
    opts = [o for o in f.options if o[0] not in SKIP_OPTIONS]
    out = []
    for i, frame in enumerate(TYPED_FRAMES[f.field_id]):
        _val, label = _pick(opts, snap, i)
        phrase = _option_phrase(label)
        out.append((f"{f.field_id}:{i}", frame.format(x=phrase),
                    _sets(schema, [(f.field_id, phrase)])))
    return out


def v_compound(snap, schema):
    f = _pf(snap, schema)
    if f is None or f.is_choice or f.field_id not in FIELD_VALUES:
        return []
    others = [o for o in _unfilled_vol(snap, (f.field_id,)) if o in VOLUNTEER]
    if not others:
        return []
    out = []
    for i, frame in enumerate(F_COMPOUND):
        o = schema.field(_pick(others, snap, i))
        pv = _pick(FIELD_VALUES[f.field_id], snap, i)
        ov = _pick(FIELD_VALUES[o.field_id], snap, i + 1)
        msg = frame.format(v=pv, c=_clause(o.field_id, ov, i), ol=o.label, ov=ov)
        out.append((f"frame{i}", msg,
                    _sets(schema, [(f.field_id, pv), (o.field_id, ov)])))
    return out


def v_bulk(snap, schema):
    unf = [fid for fid in _unfilled_vol(snap) if fid in VOLUNTEER]
    if len(unf) < 3:
        return []
    out = []
    for i, frame in enumerate(F_BULK):
        trio = unf[:3]
        vals = [_pick(FIELD_VALUES[fid], snap, i + j) for j, fid in enumerate(trio)]
        labels = [schema.field(fid).label for fid in trio]
        cl = [_clause(fid, v, i + j) for j, (fid, v) in enumerate(zip(trio, vals))]
        msg = frame.format(c1=cl[0], c2=cl[1], c3=cl[2],
                           l1=labels[0], v1=vals[0], l2=labels[1], v2=vals[1],
                           l3=labels[2], v3=vals[2])
        out.append((f"frame{i}", msg, _sets(schema, list(zip(trio, vals)))))
    return out


def v_correction(snap, schema):
    filled = [fid for fid in VOL if fid in _filled(snap) and fid in FIELD_VALUES]
    if not filled:
        return []
    out = []
    for i, frame in enumerate(F_CORRECTION):
        f = schema.field(_pick(filled, snap, i))
        raw = _pick(FIELD_VALUES[f.field_id], snap, i)
        out.append((f"frame{i}", frame.format(l=f.label, r=_ref(f), v=raw),
                    _sets(schema, [(f.field_id, raw)])))
    return out


def v_wrapped_value(snap, schema):
    filled = _filled(snap)
    out = []
    for i, (fid, frame) in enumerate(WRAPPED):
        if fid in filled:
            continue
        raw = _pick(FIELD_VALUES[fid], snap, i)
        out.append((f"{fid}:{i}", frame.format(v=raw), _sets(schema, [(fid, raw)])))
    return out


def v_freetext_select(snap, schema):
    f = _pf(snap, schema)
    if f is None or not f.is_choice or f.button_choice or f.field_id not in FREETEXT_FRAMES:
        return []
    out = []
    for i, frame in enumerate(FREETEXT_FRAMES[f.field_id]):
        c = _pick(COUNTRIES, snap, i)
        out.append((f"{f.field_id}:{i}", frame.format(c=c, l=f.label),
                    _sets(schema, [(f.field_id, c)])))
    return out


def v_residence_statement(snap, schema):
    """A present-tense residence claim volunteered while something else is pending.
    Positive case: the ISO code for the stated country of RESIDENCE (not citizenship)."""
    if "country_residence" in _filled(snap):
        return []
    # pending=country_residence is freetext_select, not a volunteer. pending=
    # country_citizenship is excluded too: answering "I've been living in Japan
    # since" to a CITIZENSHIP ask makes country_citizenship=JP defensible, and an
    # expectation that penalizes a defensible answer is the defect this scenario
    # was created to remove.
    if snap.get("pending") in ("country_residence", "country_citizenship"):
        return []
    out = []
    for i, frame in enumerate(F_RESIDENCE):
        city, country = _pick(RESIDENCE_PAIRS, snap, i)
        out.append((f"frame{i}", frame.format(city=city, country=country),
                    _sets(schema, [("country_residence", country)])))
    return out


def v_boolean_phrase(snap, schema):
    f = _pf(snap, schema)
    if f is None or f.type != "boolean":
        return []
    out = []
    for i, (val, phrase) in enumerate(BOOL_PHRASES.get(f.field_id, BOOL_FALLBACK)):
        raw = "Yes" if val else "No"          # the option label the phrase means
        out.append((f"{f.field_id}:{i}", phrase, _sets(schema, [(f.field_id, raw)])))
    return out


def _parent_boolean(f, schema):
    """(parent Field, activating value) for a conditional field whose condition is an
    equals-test on a boolean — read from the schema, not hardcoded, so it follows a
    change in the form's conditional structure."""
    c = f.condition or {}
    p = schema.field(c.get("field_id", "")) if c else None
    if p is None or p.type != "boolean" or c.get("operator", "equals") != "equals":
        return None, None
    return p, c.get("value")


def v_multi_select_subset(snap, schema):
    """Names 2 of N options for the multi_select.

    If the multi_select's PARENT boolean is the pending question and is still
    unfilled, naming the types also ANSWERS that question, so the expectation
    includes the parent set to its activating value. Leaving it out was wrong: the
    harness would re-ask "are you interested in funding?" immediately after the user
    said which kinds they want. The parent value goes through the same coercion gate
    as everything else ("Yes" -> canonical True)."""
    f = next((x for x in schema.fields if x.is_multi), None)
    if f is None or f.field_id in _filled(snap):
        return []
    parent, activating = _parent_boolean(f, schema)
    answers_parent = (parent is not None and activating is True
                      and snap.get("pending") == parent.field_id
                      and parent.field_id not in _filled(snap))
    out = []
    for i, frame in enumerate(F_MULTI):
        a, b = _pick(MULTI_PAIRS, snap, i)
        labels = dict((v, l) for v, l in f.options)
        raw = f"{labels[a]} and {labels[b]}"
        pairs = [(parent.field_id, "Yes")] if answers_parent else []
        pairs.append((f.field_id, raw))
        out.append((f"frame{i}", frame.format(p=raw), _sets(schema, pairs)))
    return out


def v_precedence(snap, schema):
    p = _pf(snap, schema)
    if p is None:
        return []
    targets = [t for t in PRECEDENCE_TARGETS
               if t != p.field_id and t not in _filled(snap)]
    if not targets:
        return []
    out = []
    for i, frame in enumerate(F_PRECEDENCE):
        f = schema.field(_pick(targets, snap, i))
        raw = _pick(FIELD_VALUES[f.field_id], snap, i)
        msg = frame.format(c=_clause(f.field_id, raw, i), l=f.label, v=raw)
        out.append((f"frame{i}", msg, _sets(schema, [(f.field_id, raw)])))
    return out


def v_chitchat(snap, schema):
    return [(f"frame{i}", m, _empty()) for i, m in enumerate(CHITCHAT)]


def v_restraint_question(snap, schema):
    return [(f"frame{i}", m, _empty()) for i, m in enumerate(RESTRAINT_Q)]


def v_refusal(snap, schema):
    f = _pf(snap, schema)
    if f is None:
        return []
    return [(f"frame{i}", frame.format(l=f.label, r=_ref(f)), _empty())
            for i, frame in enumerate(F_REFUSAL)]


def v_third_party_name(snap, schema):
    return [(f"frame{i}", frame.format(n=_pick(THIRD_PARTY_NAMES, snap, i)), _empty())
            for i, frame in enumerate(F_THIRD_NAME)]


def v_third_party_fact(snap, schema):
    """A THIRD PARTY's fact that maps onto a form field. The shadowed field must be
    UNFILLED — a trap for a field already answered is not the failure being probed —
    so the variants available depend on the context, and assignment must rotate over
    them (see build_cases) or the scenario collapses onto whichever two survive late."""
    filled = _filled(snap)
    return [(f"{fid}:{i}", m, _empty())
            for i, (fid, m) in enumerate(THIRD_PARTY_FACT) if fid not in filled]


def v_narrative_trap(snap, schema):
    return [(f"frame{i}", m, _empty()) for i, m in enumerate(NARRATIVE)]


def v_bare_ambiguous(snap, schema):
    # only tokens the cascade cannot place — otherwise `empty` is not the harness's
    # own answer and the case would measure the validator, not the student.
    return [(t, t, _empty()) for t in BARE_TOKENS if _binds_nowhere(t, snap, schema)]


def v_unlisted_country(snap, schema):
    """The user names a country that is not among the 14 options. Convention B: no
    inference to OTHER, so the harness sets nothing (large select -> CLARIFY) and any
    set at all fails the case."""
    filled = _filled(snap)
    if not [fid for fid in COUNTRY_FIELDS if fid not in filled]:
        return []
    return [(c.lower(), m, _empty()) for c, m in UNLISTED
            if _binds_nowhere(c, snap, schema)]


def _pending_country(snap, schema) -> bool:
    """Soft context preference: the user is answering the country question."""
    return snap.get("pending") in COUNTRY_FIELDS


def v_no_match(snap, schema):
    f = _pf(snap, schema)
    if f is None or f.field_id not in NO_MATCH_VALUES:
        return []
    out = []
    for i, frame in enumerate(F_NO_MATCH):
        raw = _pick(NO_MATCH_VALUES[f.field_id], snap, i)
        if not _no_match_ok(raw, f):
            raise GateError(f"no_match: {raw!r} DOES match an option of {f.field_id}")
        if not _binds_nowhere(raw, snap, schema):
            continue
        out.append((f"{f.field_id}:{i}", frame.format(v=raw), _empty()))
    return out


def v_invalid_value(snap, schema):
    f = _pf(snap, schema)
    if f is None or f.type not in INVALID_VALUES:
        return []
    out = []
    for i, frame in enumerate(F_INVALID):
        raw = _pick(INVALID_VALUES[f.type], snap, i)
        if not _uncoercible(raw, f):
            raise GateError(f"invalid_value: {raw!r} DOES coerce to {f.type}")
        if not _binds_nowhere(raw, snap, schema):
            continue
        out.append((f"{f.type}:{i}", frame.format(v=raw), _empty()))
    return out


def v_asks_about_field(snap, schema):
    filled = _filled(snap)
    fields = [fid for fid in ASK_FIELDS
              if fid not in filled and schema.field(fid).button_choice]
    if not fields:
        return []
    out = []
    for i, frame in enumerate(F_ASKS):
        fid = _pick(fields, snap, i)
        out.append((f"frame{i}:{fid}", frame.format(l=ASK_TERMS[fid]), _choice(fid)))
    return out


def v_deflect(snap, schema):
    p = _pf(snap, schema)
    if p is None:
        return []
    filled = _filled(snap)
    fields = [fid for fid in ASK_FIELDS
              if fid != p.field_id and fid not in filled and schema.field(fid).button_choice]
    if not fields:
        return []
    out = []
    for i, frame in enumerate(F_DEFLECT):
        fid = _pick(fields, snap, i)
        out.append((f"frame{i}:{fid}", frame.format(l=ASK_TERMS[fid]), _choice(fid)))
    return out


# ======================================================================
# gate 1 — the registry
# ======================================================================

@dataclass
class Scenario:
    name: str
    variants: Callable[[dict, Schema], list[tuple]]
    kind: str                 # sets | empty | choice (documentation + report only)
    prefer: str = ""          # "late" -> weight late-depth snapshots
    prefer_ctx: Callable[[dict, Schema], bool] | None = None
    """Soft context preference, applied WITHIN each band so it cannot flatten the
    band spread: matching contexts are drawn first, then the rest."""

    def precondition(self, snap: dict, schema: Schema) -> bool:
        return bool(self.variants(snap, schema))

    def make(self, snap: dict, schema: Schema, rng: random.Random) -> tuple:
        """(message, expect) for a random available variant. The BUILD does not use
        this — build_cases rotates over variant keys so no variant can starve — it is
        the registry's documented single-case entry point."""
        _k, msg, expect = rng.choice(self.variants(snap, schema))
        return msg, expect


REGISTRY = [
    # answer-bearing
    Scenario("pending_answer", v_pending_answer, "sets"),
    Scenario("typed_choice", v_typed_choice, "sets"),
    Scenario("compound", v_compound, "sets"),
    Scenario("bulk", v_bulk, "sets"),
    Scenario("correction", v_correction, "sets"),
    Scenario("wrapped_value", v_wrapped_value, "sets"),
    Scenario("freetext_select", v_freetext_select, "sets"),
    Scenario("residence_statement", v_residence_statement, "sets"),
    Scenario("boolean_phrase", v_boolean_phrase, "sets"),
    Scenario("multi_select_subset", v_multi_select_subset, "sets"),
    Scenario("precedence", v_precedence, "sets"),
    # non-answer
    Scenario("chitchat", v_chitchat, "empty"),
    Scenario("restraint_question", v_restraint_question, "empty"),
    Scenario("refusal", v_refusal, "empty"),
    Scenario("third_party_name", v_third_party_name, "empty"),
    Scenario("third_party_fact", v_third_party_fact, "empty"),
    Scenario("narrative_trap", v_narrative_trap, "empty", prefer="late"),
    Scenario("unlisted_country", v_unlisted_country, "empty",
             prefer_ctx=_pending_country),
    Scenario("bare_ambiguous", v_bare_ambiguous, "empty"),
    Scenario("no_match", v_no_match, "empty"),
    Scenario("invalid_value", v_invalid_value, "empty"),
    # engagement
    Scenario("asks_about_field", v_asks_about_field, "choice"),
    Scenario("deflect", v_deflect, "choice"),
]
BY_NAME = {s.name: s for s in REGISTRY}


def run_coercion_gate(snapshots: list[dict], schema: Schema) -> dict:
    """Enumerate EVERY scenario's variants against EVERY snapshot. Any GateError is
    a build failure: an expectation the harness cannot produce measures the
    validator, not the student."""
    checks, failures = 0, []
    for s in REGISTRY:
        for snap in snapshots:
            try:
                vs = s.variants(snap, schema)
            except GateError as e:
                failures.append({"scenario": s.name,
                                 "snapshot": [snap["session"], snap["turn"]],
                                 "error": str(e)})
                continue
            checks += len(vs)
    return {"variant_checks": checks, "failures": failures,
            "passed": not failures}


# ======================================================================
# gate 3 — template collision detector
# ======================================================================

_SLOT = re.compile(r"\{[^{}]*\}")


def norm_tokens(s: str) -> list[str]:
    """Frame -> comparable word list. Slots and values (emails, digit runs, all
    punctuation) are stripped; apostrophes close up so "I'd" -> "id"."""
    s = _SLOT.sub(" ", str(s))
    s = re.sub(r"\S+@\S+", " ", s)
    s = s.replace("'", "").replace("\u2019", "")
    s = re.sub(r"[^A-Za-z]+", " ", s)
    return s.lower().split()


def _ngrams(toks: list[str], n: int) -> set:
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def harvest_datagen(path: Path = DATAGEN_PY) -> list[tuple]:
    """(source, string) for every literal message template in datagen.py: strings
    inside the `_mk_*` makers (their rng.choice lists) and strings anywhere inside
    module-level UPPER_CASE assignments (_COMPOUND_TEMPLATES, _CHITCHAT, ...).
    A manual grep rule missed one leak already; this is the build step."""
    tree = ast.parse(open(path).read())
    out = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_mk_"):
            body = node.body[1:] if (node.body and isinstance(node.body[0], ast.Expr)
                                     and isinstance(node.body[0].value, ast.Constant)) else node.body
            src = node.name
            nodes = body
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                and re.match(r"^_?[A-Z][A-Z0-9_]*$", node.targets[0].id):
            src = node.targets[0].id
            nodes = [node.value]
        else:
            continue
        for sub in nodes:
            for n in ast.walk(sub):
                if isinstance(n, ast.Constant) and isinstance(n.value, str):
                    out.append((src, n.value))
    return out


def harvest_prior_evals(paths=PRIOR_EVALS) -> list[tuple]:
    out = []
    for p in paths:
        if not Path(p).exists():
            continue
        for line in open(p):
            c = json.loads(line)
            out.append((f"{Path(p).name}:{c['id']}", c["user_message"]))
    return out


def training_frames() -> list[dict]:
    """Every phrasing v3 must not reuse: datagen templates + prior eval messages."""
    frames = []
    for src, s in harvest_datagen() + harvest_prior_evals():
        toks = norm_tokens(s)
        if len(toks) < 3:           # field ids, type names, punctuation fragments
            continue
        frames.append({"source": src, "text": s, "tokens": toks})
    return frames


NEAR_JACCARD = 0.5   # spec bar for printing is 0.6; we print from 0.5 so borderline
                     # pairs land in the human-review list. Never a fail bar.
SPAN_WORDS = 5


def detect_collisions(eval_frames: dict = None, train: list[dict] = None) -> dict:
    """Compare every v3 frame against every training frame.
      exact token match, or a shared contiguous span of >=SPAN_WORDS -> FAIL
      Jaccard >= NEAR_JACCARD                                        -> near-miss
    """
    eval_frames = EVAL_FRAMES if eval_frames is None else eval_frames
    train = training_frames() if train is None else train
    fails, near = [], []
    n_pairs = 0
    for scn, frames in eval_frames.items():
        for frame in frames:
            et = norm_tokens(frame)
            if not et:
                continue
            e5 = _ngrams(et, SPAN_WORDS)
            es = set(et)
            for t in train:
                n_pairs += 1
                shared = e5 & _ngrams(t["tokens"], SPAN_WORDS)
                if et == t["tokens"]:
                    fails.append({"scenario": scn, "eval": frame, "kind": "exact_frame",
                                  "train_source": t["source"], "train": t["text"]})
                    continue
                if shared:
                    fails.append({"scenario": scn, "eval": frame, "kind": f"{SPAN_WORDS}_word_span",
                                  "span": " ".join(sorted(shared)[0]),
                                  "train_source": t["source"], "train": t["text"]})
                    continue
                ts = set(t["tokens"])
                j = len(es & ts) / len(es | ts)
                if j >= NEAR_JACCARD:
                    near.append({"scenario": scn, "eval": frame, "jaccard": round(j, 3),
                                 "train_source": t["source"], "train": t["text"]})
    near.sort(key=lambda r: -r["jaccard"])
    return {"eval_frames": sum(len(v) for v in eval_frames.values()),
            "training_frames": len(train), "comparisons": n_pairs,
            "failures": fails, "near_misses": near, "passed": not fails}


# ======================================================================
# assignment — snapshot used at most once, quotas, bands
# ======================================================================

def _band_cycle(prefer: str) -> list[str]:
    return ["late", "late", "mid", "early"] if prefer == "late" else ["early", "mid", "late"]


# every scenario must use at least min(VARIANT_MIN, available) distinct variants;
# the scenarios listed here must use EVERY variant they have. third_party_fact
# probes the failure the stress sweep found in 26-30 of 96 turns (a third party's
# fact attributed to the applicant), and four of its six variants only exist where
# their shadow field is unfilled — so it gets a full-coverage requirement.
VARIANT_MIN = 4
VARIANT_ALL = {"third_party_fact"}


def _sk(snap: dict) -> tuple:
    return (snap["session"], snap["turn"])


def variant_offers(s: Scenario, snapshots: list[dict], schema: Schema) -> dict:
    """{(session, turn): {variant_key, ...}} — which variants each context supports."""
    return {_sk(snap): {k for k, _m, _e in s.variants(snap, schema)} for snap in snapshots}


def variant_keys(s: Scenario, snapshots: list[dict], schema: Schema) -> list[str]:
    """Every variant key the scenario can offer anywhere in the pool, in authored
    (first-seen) order."""
    seen: list[str] = []
    for snap in snapshots:
        for k, _m, _e in s.variants(snap, schema):
            if k not in seen:
                seen.append(k)
    return seen


def _grab(buckets: dict, offers: dict, vkey: str, cycle: list, bi: int):
    """The next unused snapshot offering `vkey`: preferred band first (band cycle),
    then any band. Returns (band, index, snapshot) or None."""
    for b in [cycle[bi % len(cycle)]] + list(BANDS):
        for j, snap in enumerate(buckets[b]):
            if vkey in offers[_sk(snap)]:
                return b, j, snap
    return None


def assign(snapshots: list[dict], schema: Schema, per_scenario: int, seed: int) -> tuple:
    """Deterministic assignment of (snapshot, variant) pairs, in two phases.

    Scenario order is scarcest-first, measured by the RAREST VARIANT's supply and
    then by eligible-snapshot count. Eligible-count alone is the wrong metric:
    third_party_fact is eligible on all 423 contexts, so it sorted last, yet four of
    its six variants need their shadow field unfilled and by then only late contexts
    remained — it collapsed onto 2 of 6 messages.

    Phase 1 RESERVES one context per variant (rarest variant first, capped at the
    quota) for every scenario, before any scenario fills its quota. Coverage is then
    structural, not a hoped-for side effect of the ordering.

    Phase 2 fills the rest VARIANT-FIRST: take the next variant in rotation and look
    for an unused context offering THAT variant, falling back to the next available
    variant only when none does. Picking the context first and accepting whatever
    variant it allowed is what starved the sharp variants. Band spreading stays one
    rung lower: among contexts offering the wanted variant, the band cycle is tried
    first.

    A snapshot is consumed by at most ONE case (cases sharing a context are
    correlated). A quota that cannot be met is a recorded shortfall — a snapshot is
    NEVER reused to hit it."""
    eligible = {s.name: [snap for snap in snapshots if s.precondition(snap, schema)]
                for s in REGISTRY}
    offers_all = {s.name: variant_offers(s, eligible[s.name], schema) for s in REGISTRY}
    supply = {s.name: Counter(k for ks in offers_all[s.name].values() for k in ks)
              for s in REGISTRY}
    order = sorted(REGISTRY, key=lambda s: (min(supply[s.name].values(), default=0),
                                            len(eligible[s.name]), s.name))
    used: set = set()

    def pool(s: Scenario):
        """Unused eligible contexts, bucketed by band and shuffled (seeded). A
        scenario's soft context preference is applied INSIDE each band, so preferred
        contexts go first without collapsing the band spread."""
        rng = random.Random(f"{seed}:{s.name}")
        buckets = {b: [] for b in BANDS}
        for snap in eligible[s.name]:
            if _sk(snap) not in used:
                buckets[band_of(snap)].append(snap)
        for b in BANDS:
            rng.shuffle(buckets[b])
            if s.prefer_ctx:
                buckets[b] = ([x for x in buckets[b] if s.prefer_ctx(x, schema)]
                              + [x for x in buckets[b] if not s.prefer_ctx(x, schema)])
        return buckets

    # ---- phase 1: reserve one context per variant, rarest variant first ----
    reserved: dict[str, list] = {}
    for s in order:
        offers, buckets = offers_all[s.name], pool(s)
        cycle = _band_cycle(s.prefer)
        take, bi = [], 0
        rare_first = sorted(supply[s.name], key=lambda k: (supply[s.name][k], k))
        for vkey in rare_first[:per_scenario]:
            hit = _grab(buckets, offers, vkey, cycle, bi)
            if hit is None:
                continue                       # nothing left offering it; gate reports
            b, j, snap = hit
            buckets[b].pop(j)
            used.add(_sk(snap))
            take.append((snap, vkey))
            bi += 1
        reserved[s.name] = take

    # ---- phase 2: fill the quota, rotating over variants ----
    picked: dict[str, list] = {}
    for s in order:
        take = list(reserved[s.name])
        offers, buckets = offers_all[s.name], pool(s)
        cycle = _band_cycle(s.prefer)
        keys = variant_keys(s, eligible[s.name], schema)     # authored order
        vi, bi = 0, len(take)
        while len(take) < per_scenario and keys:
            hit = None
            for off in range(len(keys)):
                vkey = keys[(vi + off) % len(keys)]
                g = _grab(buckets, offers, vkey, cycle, bi)
                if g:
                    hit = (*g, vkey, off)
                    break
            if hit is None:
                break                      # no unused snapshot offers any variant
            b, j, snap, vkey, off = hit
            buckets[b].pop(j)
            used.add(_sk(snap))
            take.append((snap, vkey))
            vi = (vi + off + 1) % len(keys)
            bi += 1
        picked[s.name] = take
    return eligible, picked


def build_cases(snapshots: list[dict], schema: Schema, per_scenario: int, seed: int) -> tuple:
    eligible, picked = assign(snapshots, schema, per_scenario, seed)
    cases = []
    for s in REGISTRY:                                  # registry order in the file
        for i, (snap, vkey) in enumerate(picked[s.name]):
            msg, expect = next((m, e) for k, m, e in s.variants(snap, schema) if k == vkey)
            cases.append({
                "id": f"{s.name}-{i:02d}", "scenario": s.name, "band": band_of(snap),
                "variant": vkey,
                "form_state": dict(snap["form_state"]), "pending": snap.get("pending"),
                "conversation_history": list(snap["history"]),
                "user_message": msg, "expect": expect,
                "source": {"session": snap["session"], "turn": snap["turn"]},
            })
    return cases, eligible, picked


def variant_gate(cases: list[dict], eligible: dict, snapshots: list[dict],
                 schema: Schema) -> dict:
    """Build-blocking: silent variant collapse looks fine in a summary table, so it
    gets a gate. Every scenario must use at least min(VARIANT_MIN, available)
    distinct variants; VARIANT_ALL scenarios must use every one they have."""
    rows, failures = {}, []
    for s in REGISTRY:
        used = Counter(c["variant"] for c in cases if c["scenario"] == s.name)
        avail = variant_keys(s, eligible[s.name], schema)
        need = len(avail) if s.name in VARIANT_ALL else min(VARIANT_MIN, len(avail))
        row = {"available": len(avail), "used": len(used), "required": need,
               "counts": dict(used),
               "unused": [k for k in avail if k not in used]}
        rows[s.name] = row
        if len(used) < need:
            failures.append({"scenario": s.name, **row})
    return {"per_scenario": rows, "failures": failures, "passed": not failures}


# ======================================================================
# report + digest
# ======================================================================

def label_echoes(msg: str, schema: Schema) -> list[str]:
    """MULTI-WORD schema labels quoted verbatim (case-insensitive). Single-word
    labels ("Gender") are excluded on purpose: the label and the only natural
    English noun are the same string, so counting them measures nothing. They are
    reported separately as `single_word_label_words`."""
    m = msg.lower()
    return [str(f.label) for f in schema.fields
            if " " in str(f.label) and str(f.label).lower() in m]


def _single_word_labels(msg: str, schema: Schema) -> list[str]:
    words = set(re.findall(r"[a-z]+", msg.lower()))
    return [str(f.label) for f in schema.fields
            if " " not in str(f.label) and str(f.label).lower() in words]


def label_echo_audit(snapshots: list[dict], schema: Schema) -> dict:
    """Per scenario: how many of a snapshot's rendered variants quote a schema label
    verbatim. `max_per_snapshot` is the headline — the cap is ONE."""
    out = {}
    for s in REGISTRY:
        tot = hit = mx = sw = 0
        for snap in snapshots:
            vs = s.variants(snap, schema)
            h = sum(1 for _k, m, _e in vs if label_echoes(m, schema))
            sw += sum(1 for _k, m, _e in vs if _single_word_labels(m, schema))
            tot += len(vs)
            hit += h
            mx = max(mx, h)
        out[s.name] = {"variants_rendered": tot, "with_label": hit,
                       "pct": round(100 * hit / tot, 1) if tot else 0.0,
                       "max_per_snapshot": mx, "single_word_label_words": sw}
    return out


def build_report(cases, eligible, picked, snapshots, per_scenario, seed,
                 collisions, gate, schema: Schema, variants: dict) -> dict:
    bands = Counter(c["band"] for c in cases)
    audit = label_echo_audit(snapshots, schema)
    per_scn = {}
    for s in REGISTRY:
        rows = [c for c in cases if c["scenario"] == s.name]
        vals, fields = set(), set()
        for c in rows:
            for fid, v in (c["expect"].get("sets") or {}).items():
                fields.add(fid)
                vals.add(f"{fid}={v}")
            for fid in c["expect"].get("choice") or []:
                fields.add(fid)
        per_scn[s.name] = {
            "kind": s.kind, "prefer": s.prefer or None,
            "eligible": len(eligible[s.name]), "quota": per_scenario,
            "achieved": len(rows), "shortfall": per_scenario - len(rows),
            "frames": len(EVAL_FRAMES[s.name]),   # pool size, not per-snapshot count
            "bands": dict(Counter(c["band"] for c in rows)),
            # variety WITHIN the 20 generated cases (not just the template pool)
            "distinct_messages": len({c["user_message"] for c in rows}),
            "distinct_expected_values": len(vals),
            "distinct_target_fields": len(fields),
            "target_fields": dict(Counter(
                fid for c in rows
                for fid in list((c["expect"].get("sets") or {})) + list(c["expect"].get("choice") or []))),
            "label_echo": audit[s.name],
            "variant_coverage": variants["per_scenario"][s.name],
        }
    shortfalls = {k: v["shortfall"] for k, v in per_scn.items() if v["shortfall"]}
    srcs = [(c["source"]["session"], c["source"]["turn"]) for c in cases]
    return {
        "eval_set": "v3", "seed": seed, "quota": per_scenario,
        "snapshots_available": len(snapshots),
        "snapshot_bands": dict(Counter(band_of(s) for s in snapshots)),
        "cases": len(cases), "scenarios": len(REGISTRY),
        "band_distribution": dict(bands),
        "snapshots_used": len(set(srcs)), "snapshot_reuse": len(srcs) - len(set(srcs)),
        "per_scenario": per_scn, "shortfalls": shortfalls,
        "coercion_gate": gate,
        "variant_gate": {"passed": variants["passed"], "failures": variants["failures"],
                         "min_distinct": VARIANT_MIN, "full_coverage": sorted(VARIANT_ALL)},
        "collisions": collisions,
        "review_flags": [{"scenario": s, "message": m, "note": n} for s, m, n in REVIEW_FLAGS],
    }


def print_report(rep: dict):
    print(f"\n=== v3 eval set — {rep['cases']} cases / {rep['scenarios']} scenarios "
          f"(seed {rep['seed']}, quota {rep['quota']}) ===")
    print(f"snapshots: {rep['snapshots_used']}/{rep['snapshots_available']} used, "
          f"reuse={rep['snapshot_reuse']} (must be 0)   supply {rep['snapshot_bands']}")
    print(f"band distribution: {rep['band_distribution']}")
    print(f"\n{'scenario':21} {'kind':7} {'elig':>5} {'got':>4} {'sh':>3}  {'bands':13} "
          f"{'vars':>7} {'msgs':>4} {'vals':>4} {'flds':>4}  label echo")
    for name, r in rep["per_scenario"].items():
        b = " ".join(f"{k[0]}{r['bands'].get(k, 0)}" for k in BANDS)
        le, vc = r["label_echo"], r["variant_coverage"]
        print(f"{name:21} {r['kind']:7} {r['eligible']:5} {r['achieved']:4} "
              f"{r['shortfall']:3}  {b:13} "
              f"{str(vc['used']) + '/' + str(vc['available']):>7} "
              f"{r['distinct_messages']:4} "
              f"{r['distinct_expected_values']:4} {r['distinct_target_fields']:4}  "
              f"max {le['max_per_snapshot']} per case, {le['pct']}% of rendered")
    print("\nper-scenario variant coverage (variant_key x cases):")
    for name, r in rep["per_scenario"].items():
        vc = r["variant_coverage"]
        counts = ", ".join(f"{k}x{n}" for k, n in sorted(vc["counts"].items()))
        flag = "" if vc["used"] >= vc["required"] else "   <<< BELOW REQUIRED"
        print(f"  {name:21} {vc['used']}/{vc['available']} (need {vc['required']}): "
              f"{counts}{flag}")
        if vc["unused"]:
            print(f"  {'':21} unused: {', '.join(vc['unused'])}")
    if rep["shortfalls"]:
        print("\n!! SHORTFALLS (quota NOT met; snapshots were never reused to hide it):")
        for k, v in rep["shortfalls"].items():
            print(f"   {k}: short {v} of {rep['quota']} "
                  f"(eligible {rep['per_scenario'][k]['eligible']}, "
                  f"got {rep['per_scenario'][k]['achieved']})")
    else:
        print("\nshortfalls: none")
    g = rep["coercion_gate"]
    print(f"\ncoercion gate: {g['variant_checks']} variant expectations round-tripped, "
          f"{len(g['failures'])} failures")
    vg = rep["variant_gate"]
    print(f"variant gate: min {vg['min_distinct']} distinct variants per scenario, "
          f"full coverage required for {', '.join(vg['full_coverage'])}; "
          f"{len(vg['failures'])} failures")
    for f in vg["failures"]:
        print(f"   FAIL [{f['scenario']}] used {f['used']} of {f['available']} "
              f"(need {f['required']}); unused: {', '.join(f['unused'])}")
    c = rep["collisions"]
    print(f"collision gate: {c['eval_frames']} v3 frames x {c['training_frames']} "
          f"training frames = {c['comparisons']} comparisons; "
          f"{len(c['failures'])} failures, {len(c['near_misses'])} near-misses")
    for f in c["failures"]:
        print(f"   FAIL [{f['scenario']}] {f['kind']}: {f['eval']!r}\n"
              f"        vs {f['train_source']}: {f['train']!r}")
    for n in c["near_misses"]:
        print(f"   near [{n['scenario']}] J={n['jaccard']}: {n['eval']!r}\n"
              f"        vs {n['train_source']}: {n['train']!r}")


def _fmt_expect(e: dict) -> str:
    if e.get("sets"):
        return "sets " + ", ".join(f"`{k}`={v!r}" for k, v in e["sets"].items())
    if e.get("choice"):
        return "offer choices for " + ", ".join(f"`{c}`" for c in e["choice"])
    return "**no field set**"


def write_md(cases: list[dict], rep: dict, path: Path):
    by = defaultdict(list)
    for c in cases:
        by[c["scenario"]].append(c)
    out = ["# v3 eval set — case review\n",
           f"\n**{rep['cases']} cases**, {rep['scenarios']} scenarios, quota "
           f"{rep['quota']}/scenario, seed {rep['seed']}. Contexts are REAL: "
           f"{rep['snapshots_used']} distinct farmed-session snapshots "
           f"(`eval_farm_p1`/`p2`, seeds 102-131), each used once. Generated by "
           "`eval_gen.py` — do not edit by hand.\n",
           f"\nBands are conversation depth (`len(form_state)`): early 0-3, mid 4-7, "
           f"late 8+. Achieved: {rep['band_distribution']}.\n",
           "\n## Coverage\n",
           "\n| scenario | expects | frames | eligible | cases | early | mid | late | "
           "variants used | distinct msgs | distinct values | target fields | label echoes |\n",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"]
    for name, r in rep["per_scenario"].items():
        vc = r["variant_coverage"]
        out.append(f"| `{name}` | {r['kind']} | {r['frames']} | {r['eligible']} | "
                   f"{r['achieved']} | {r['bands'].get('early', 0)} | "
                   f"{r['bands'].get('mid', 0)} | {r['bands'].get('late', 0)} | "
                   f"{vc['used']}/{vc['available']} (need {vc['required']}) | "
                   f"{r['distinct_messages']} | {r['distinct_expected_values']} | "
                   f"{r['distinct_target_fields']} | "
                   f"max {r['label_echo']['max_per_snapshot']}/case, "
                   f"{r['label_echo']['pct']}% |\n")
    out.append("\n## Variant coverage (variant key x cases)\n\n")
    for name, r in rep["per_scenario"].items():
        vc = r["variant_coverage"]
        out.append(f"- `{name}` {vc['used']}/{vc['available']}: "
                   + ", ".join(f"`{k}`x{n}" for k, n in sorted(vc["counts"].items()))
                   + (f" — unused: {', '.join('`' + k + '`' for k in vc['unused'])}"
                      if vc["unused"] else "") + "\n")
    if rep["shortfalls"]:
        out.append("\n**Shortfalls** (quota not met from eligible snapshots; no snapshot "
                   "was reused to hide them): " +
                   ", ".join(f"`{k}` short {v}" for k, v in rep["shortfalls"].items()) + "\n")
    out.append("\n## Samples (3 per scenario)\n"
               "\nsetup = form/pending before the turn; expected = what the harness should do.\n"
               "\n| id | band | setup | user says | expected |\n|---|---|---|---|---|\n")
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
    for name in rep["per_scenario"]:
        for c in by[name][:3]:
            setup = f"{len(c['form_state'])} filled, pending `{c['pending']}`, " \
                    f"{len(c['conversation_history'])} history msgs"
            out.append(f"| `{c['id']}` | {c['band']} | {setup} | {esc(c['user_message'])} "
                       f"| {esc(_fmt_expect(c['expect']))} |\n")
    out.append("\n## Review flags\n")
    for f in rep["review_flags"]:
        out.append(f"\n- `{f['scenario']}` — {esc(f['message'])}\n  - {f['note']}\n")
    near = rep["collisions"]["near_misses"]
    out.append(f"\n## Collision near-misses ({len(near)}; nothing at or above the fail bar)\n")
    for n in near:
        out.append(f"\n- J={n['jaccard']} `{n['scenario']}`: {esc(n['eval'])}\n"
                   f"  - vs `{n['train_source']}`: {esc(n['train'])}\n")
    path.write_text("".join(out))


# ======================================================================
# --templates (the human review artifact)
# ======================================================================

def templates_snapshot(s: Scenario, snapshots: list[dict], schema: Schema):
    """The eligible snapshot showing the MOST variants, then one covering at least
    TWO distinct target fields (so asks_about_field / deflect do not render the same
    field four times), then the DEEPEST context — reviewing a scenario on an empty
    greeting turn is exactly the v2 blind spot v3 exists to fix."""
    best, key = None, None
    for snap in snapshots:
        vs = s.variants(snap, schema)
        if not vs:
            continue
        targets = {fid for _k, _m, e in vs for fid in (e.get("sets") or e.get("choice") or [])}
        k = (len(vs), min(len(targets), 2), len(snap["form_state"]), len(snap["history"]))
        if key is None or k > key:
            best, key = snap, k
    return best


def print_templates(snapshots: list[dict], schema: Schema):
    print(f"v3 scenario templates — every variant rendered on a real farm snapshot")
    print(f"snapshots: {len(snapshots)}  bands: {dict(Counter(band_of(s) for s in snapshots))}")
    for s in REGISTRY:
        snap = templates_snapshot(s, snapshots, schema)
        print("\n" + "=" * 78)
        print(f"[{s.name}]  expects={s.kind}"
              + (f"  prefer={s.prefer}" if s.prefer else ""))
        elig = [x for x in snapshots if s.precondition(x, schema)]
        eb = Counter(band_of(x) for x in elig)
        keys = variant_keys(s, elig, schema)
        print(f"  eligible snapshots: {len(elig)}  "
              f"(early {eb['early']} / mid {eb['mid']} / late {eb['late']})"
              f"   variants in pool: {len(keys)}")
        if snap is None:
            print("  !! NO eligible snapshot")
            continue
        print("-" * 78)
        print(f"  context: session {snap['session']} turn {snap['turn']}  "
              f"band={band_of(snap)}  pending={snap['pending']}")
        print(f"  form_state ({len(snap['form_state'])}): "
              f"{json.dumps(snap['form_state'])}")
        la = last_assistant(snap).replace("\n", " ")
        print(f"  last assistant ({len(snap['history'])} history msgs): "
              f"{(la[:200] + '...') if len(la) > 200 else (la or '(no history)')}")
        print("-" * 78)
        for key, msg, expect in s.variants(snap, schema):
            print(f"  [{key}] user: {msg}")
            print(f"        expect: {json.dumps(expect)}")
    print("\n" + "=" * 78)
    print("REVIEW FLAGS")
    for scn, msg, note in REVIEW_FLAGS:
        print(f"\n[{scn}] {msg}\n   -> {note}")


# ======================================================================
# offline self-test
# ======================================================================

_P_EMAIL = re.compile(r"^[a-z]+\.[a-z]+\d{1,2}@example\.com$")
_P_PHONE = re.compile(r"^\(\d{3}\) 555-\d{4}$")
_P_ADDR = re.compile(r"^\d{1,4} (" + "|".join(map(re.escape, personas.STREETS)) + r"), ("
                     + "|".join(map(re.escape, personas.CITIES)) + r"), ("
                     + "|".join(personas.USTATES) + r") \d{5}$")


def persona_shaped(v) -> str:
    """Non-empty reason when `v` reuses one of persona.py's generator formats."""
    if not isinstance(v, str):
        return ""
    if _P_EMAIL.match(v):
        return "persona email format"
    if _P_PHONE.match(v):
        return "persona phone format"
    if _P_ADDR.match(v):
        return "persona address format"
    parts = v.split()
    if len(parts) == 2 and parts[0] in personas.FIRST and parts[1] in personas.LAST:
        return "persona FIRST LAST pair"
    return ""


def _synthetic_obs(case: dict) -> dict:
    """The perfect harness answer for a case — used to prove the case schema is
    consumable by eval_score.score_observation."""
    e = case["expect"]
    if e.get("sets"):
        return {"got_sets": dict(e["sets"]), "choice_offered": False, "choice_field": None}
    if e.get("choice"):
        return {"got_sets": {}, "choice_offered": True, "choice_field": e["choice"][0]}
    return {"got_sets": {}, "choice_offered": False, "choice_field": None}


def selftest(snapshot_paths: list[str]):
    from . import eval_score

    schema = load_schema()
    snaps = load_snapshots(snapshot_paths)
    # supply after the turn-0 exclusion (see load_snapshots): 453 raw rows, 30 of
    # them turn 0 (one per session), leaving 423 with a non-empty history.
    assert len(snaps) == 423, len(snaps)
    assert dict(Counter(band_of(s) for s in snaps)) == {"early": 125, "mid": 124, "late": 174}
    assert not [x for x in snaps if x["turn"] == 0], "turn 0 must be excluded"
    assert min(x["turn"] for x in snaps) == 1
    assert all(x["history"] for x in snaps), "every case must have a real history"

    # ---- 1. registry completeness ------------------------------------
    assert len(REGISTRY) == 23, len(REGISTRY)
    assert len(BY_NAME) == len(REGISTRY), "duplicate scenario name"
    for s in REGISTRY:
        assert callable(s.precondition) and callable(s.make), s.name
        assert s.kind in ("sets", "empty", "choice"), s.name
        assert s.name in EVAL_FRAMES, f"{s.name} missing from EVAL_FRAMES"
        assert len(EVAL_FRAMES[s.name]) >= 4, (s.name, len(EVAL_FRAMES[s.name]))
        assert any(s.precondition(x, schema) for x in snaps), f"{s.name}: 0 eligible"
    assert set(EVAL_FRAMES) == set(BY_NAME), "EVAL_FRAMES / REGISTRY mismatch"

    # ---- 1b. schema-label discipline: at most ONE echoing variant ----
    audit = label_echo_audit(snaps, schema)
    for name, a in audit.items():
        assert a["max_per_snapshot"] <= 1, (name, a)
    # natural references, not labels, carry the field in these scenarios
    for name in ("compound", "bulk", "precedence", "refusal"):
        assert audit[name]["pct"] < 40, (name, audit[name])

    # ---- 1c. no `empty` case a correct extractor could legitimately answer ----
    countries = [lab for _v, lab in schema.field("country_residence").options
                 if lab != "Other"]
    for msg in NARRATIVE + CHITCHAT + RESTRAINT_Q:
        for c in countries:
            assert c.lower() not in msg.lower(), (msg, c)   # -> residence reading
        assert "current job" not in msg.lower(), msg        # -> work-experience reading
    # typed_choice never types a catch-all option ("It came up via other")
    for snap in snaps:
        for _k, msg, _e in v_typed_choice(snap, schema):
            assert "other" not in msg.lower() and "prefer not to say" not in msg.lower(), msg

    # ---- 1c2. third_party_fact says nothing about the APPLICANT ----------
    # a first-person claim (especially a denial: "...not mine") is itself an answer,
    # so `empty` would penalize a defensible reading. Possessive "my" is fine — it
    # names the relationship, not an applicant attribute.
    FIRST_PERSON = {"i", "im", "ive", "id", "ill", "me", "mine", "myself", "own"}
    for fid, msg in THIRD_PARTY_FACT:
        bad = FIRST_PERSON & set(norm_tokens(msg))
        assert not bad, (msg, bad)
        assert not re.search(r"\bnot\b|\bnever\b|\bdidn|\bdon'?t\b", msg.lower()), msg

    # ---- 1d. unlisted_country: convention B, and no near-miss aliases ----
    opts = schema.field("country_citizenship").options
    labels = {str(lab) for _v, lab in opts}
    for c, msg in UNLISTED:
        assert c in msg, (c, msg)                       # the message states it
        assert c not in labels, f"{c} IS an option — the option list changed"
        for fid in COUNTRY_FIELDS:
            hits = validator.match_options(c, schema.field(fid))
            assert hits == [], (c, fid, hits)           # -> CLARIFY, nothing set
        for lab in labels:                              # no listed country sneaks in
            if lab != "Other":
                assert lab.lower() not in msg.lower(), (lab, msg)
    # near-miss aliases are a validator gap, not ground truth — keep them OUT
    for alias in ("Britain", "Great Britain", "America", "Holland", "Korea",
                  "USA", "Deutschland"):
        assert not any(alias.lower() in m.lower() for _c, m in UNLISTED), alias
    # "Other" still binds when the user says it themselves (convention B's escape)
    assert validator.match_options("Other", schema.field("country_residence")) \
        == [("OTHER", "Other")]

    # ---- 2. persona-format disjointness ------------------------------
    for pool in [NAMES, PREFERRED, EMAILS, PHONES, DATES, ADDRESSES, NOTES,
                 THIRD_PARTY_NAMES] + list(FIELD_VALUES.values()):
        for v in pool:
            assert not persona_shaped(v), f"{v!r}: {persona_shaped(v)}"
    # ... and nothing persona-shaped can reach an expectation
    for s in REGISTRY:
        for snap in snaps:
            for _k, _msg, expect in s.variants(snap, schema):
                for v in expect.get("sets", {}).values():
                    assert not persona_shaped(v), (s.name, v, persona_shaped(v))

    # ---- 3. coercion round-trip over every variant x snapshot --------
    gate = run_coercion_gate(snaps, schema)
    assert gate["passed"], gate["failures"][:5]
    assert gate["variant_checks"] > 10000, gate["variant_checks"]
    # canonical, not raw: a %d %B %Y date becomes ISO; a country name becomes a code
    dob_snap = next(x for x in snaps if x.get("pending") == "dob")
    dsets = [e["sets"]["dob"] for _k, _m, e in v_pending_answer(dob_snap, schema)]
    assert all(re.match(r"^\d{4}-\d{2}-\d{2}$", d) for d in dsets), dsets
    cc = next(x for x in snaps if x.get("pending") == "country_citizenship")
    assert {e["sets"]["country_citizenship"] for _k, _m, e in v_freetext_select(cc, schema)} \
        <= {"KR", "NG", "DE", "BR", "JP", "MX"}
    # a bad value fails the gate loudly rather than shipping
    try:
        canonicalize("3rd of March 1994", schema.field("dob"))
        raise AssertionError("gate accepted an uncoercible date")
    except GateError:
        pass
    try:
        canonicalize("astrophysics", schema.field("program"))
        raise AssertionError("gate accepted a non-option")
    except GateError:
        pass
    # multi_select keeps BOTH options, in message order
    ms = next(x for x in snaps if v_multi_select_subset(x, schema))
    for _k, _m, e in v_multi_select_subset(ms, schema):
        v = e["sets"]["funding_type"]
        assert isinstance(v, list) and len(v) == 2, v
    # ... and when the parent boolean is the pending question, answering with the
    # types answers it too (canonical True), else the harness would re-ask it
    mf = next(x for x in schema.fields if x.is_multi)
    parent, activating = _parent_boolean(mf, schema)
    assert parent is not None and parent.type == "boolean" and activating is True, parent
    p_snap = next(x for x in snaps if x.get("pending") == parent.field_id
                  and mf.field_id not in _filled(x))
    for _k, _m, e in v_multi_select_subset(p_snap, schema):
        assert e["sets"][parent.field_id] is True, e
        assert len(e["sets"]) == 2, e
    o_snap = next(x for x in snaps if v_multi_select_subset(x, schema)
                  and x.get("pending") not in (None, parent.field_id))
    for _k, _m, e in v_multi_select_subset(o_snap, schema):
        assert set(e["sets"]) == {mf.field_id}, e       # unaffected
    # boolean phrasing canonicalizes to a real bool
    bs = next(x for x in snaps if _pf(x, schema) and _pf(x, schema).type == "boolean")
    for _k, _m, e in v_boolean_phrase(bs, schema):
        assert isinstance(list(e["sets"].values())[0], bool), e

    # ---- 4. collision detector: known positive + the real corpus -----
    train = training_frames()
    assert len(train) > 100, len(train)
    known = {"compound_volunteer": ["I'm {a} and you can reach me at {b}."]}
    caught = detect_collisions(known, train)
    assert not caught["passed"], "detector missed the compound_volunteer frame"
    assert caught["failures"][0]["kind"] in ("exact_frame", "5_word_span"), caught["failures"][0]
    # the second known leak (v2 edge_chitchat_with_value vs datagen's store-queue
    # wrapper) is a >=5-word span, not an exact frame — the case a grep rule missed
    span_case = {"x": ["Sorry, typing in line at the store — anyway you can reach me at {v}."]}
    assert not detect_collisions(span_case, train)["passed"]
    collisions = detect_collisions(None, train)
    assert collisions["passed"], collisions["failures"]

    # ---- 5. assignment: used-once, quotas, shortfalls, bands ---------
    cases, eligible, picked = build_cases(snaps, schema, QUOTA, 0)
    srcs = [(c["source"]["session"], c["source"]["turn"]) for c in cases]
    assert len(srcs) == len(set(srcs)), "a snapshot was reused"
    assert len(cases) <= len(snaps)
    for s in REGISTRY:
        got = [c for c in cases if c["scenario"] == s.name]
        assert len(got) == len(picked[s.name]) <= QUOTA, s.name
        assert len(got) <= len(eligible[s.name]), s.name
        for c in got:                                  # bands follow form_state size
            n = len(c["form_state"])
            assert c["band"] == ("early" if n <= 3 else "mid" if n <= 7 else "late")
    # shortfall accounting is exact, and a tiny quota is always met
    variants = variant_gate(cases, eligible, snaps, schema)
    rep = build_report(cases, eligible, picked, snaps, QUOTA, 0, collisions, gate,
                       schema, variants)
    for name, r in rep["per_scenario"].items():
        assert r["shortfall"] == QUOTA - r["achieved"] == r["quota"] - r["achieved"]
        assert r["achieved"] == sum(r["bands"].values())
    small, el2, pk2 = build_cases(snaps, schema, 3, 0)
    assert len(small) == 3 * len(REGISTRY), len(small)
    assert all(len(v) == 3 for v in pk2.values())
    # determinism
    again, _, _ = build_cases(snaps, schema, QUOTA, 0)
    assert [c["user_message"] for c in cases] == [c["user_message"] for c in again]
    assert [c["source"] for c in cases] == [c["source"] for c in again]
    assert [c["variant"] for c in cases] == [c["variant"] for c in again]
    # narrative_trap leans late
    nb = Counter(c["band"] for c in cases if c["scenario"] == "narrative_trap")
    assert nb["late"] >= nb["early"], nb

    # ---- 5b. variant coverage: no scenario collapses onto 1-2 messages ----
    assert variants["passed"], variants["failures"]
    for name, r in variants["per_scenario"].items():
        assert r["used"] >= min(VARIANT_MIN, r["available"]), (name, r)
    tpf = variants["per_scenario"]["third_party_fact"]
    assert tpf["used"] == tpf["available"] == 6, tpf     # all 6 traps must appear
    assert len({c["user_message"] for c in cases if c["scenario"] == "third_party_fact"}) == 6

    # ---- 6. every case is consumable by the scorer -------------------
    for c in cases:
        assert set(c) == {"id", "scenario", "band", "variant", "form_state", "pending",
                          "conversation_history", "user_message", "expect", "source"}, set(c)
        assert c["band"] in BANDS
        assert isinstance(c["user_message"], str) and c["user_message"].strip()
        assert isinstance(c["conversation_history"], list)
        s = eval_score.score_observation(c, _synthetic_obs(c))
        assert s["passed"], (c["id"], c["expect"])
        # no transcription-sensitive expectation is already sitting in the case's own
        # context — a copy-forward from state/history must not be able to pass it
        ctx = json.dumps(c["form_state"]) + json.dumps(c["conversation_history"])
        for fid, v in c["expect"].get("sets", {}).items():
            if isinstance(v, str) and not schema.field(fid).is_choice:
                assert v not in ctx, (c["id"], fid, v)
        assert eval_score.band_of(c) in ("positive", "choice", "no_value", "unplaceable")
        # and the WRONG answer must fail (no case is vacuously passable)
        wrong = {"got_sets": {"anything_else": "x"}, "choice_offered": False,
                 "choice_field": None}
        assert not eval_score.score_observation(c, wrong)["passed"], c["id"]
        json.dumps(c)                                   # jsonl-serializable

    print(f"selftest: all assertions passed "
          f"({len(REGISTRY)} scenarios, {gate['variant_checks']} gated expectations, "
          f"{collisions['comparisons']} collision comparisons, {len(cases)} cases)")
    return rep


# ======================================================================
# main
# ======================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="offline gates + accounting")
    ap.add_argument("--templates", action="store_true",
                    help="print every scenario's variants on a real snapshot (human review)")
    ap.add_argument("--snapshots", nargs="+", default=SNAPSHOTS_DEFAULT,
                    help="farm snapshot jsonl(s); seeds 132-191 are reserved, do not add them")
    ap.add_argument("--per-scenario", type=int, default=QUOTA,
                    help="cases per scenario (default sized to the 423-snapshot pool: "
                         "22 scenarios x 19 = 418, each snapshot used at most once)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()

    if args.selftest:
        selftest(args.snapshots)
        return
    schema = load_schema()
    snaps = load_snapshots(args.snapshots)
    if args.templates:
        print_templates(snaps, schema)
        return

    gate = run_coercion_gate(snaps, schema)
    collisions = detect_collisions()
    if not gate["passed"] or not collisions["passed"]:
        print("!! BUILD BLOCKED — gates failed, nothing written")
        for f in gate["failures"][:20]:
            print(f"   coercion FAIL [{f['scenario']}] {f['snapshot']}: {f['error']}")
        for f in collisions["failures"][:20]:
            print(f"   collision FAIL [{f['scenario']}] {f['kind']}: {f['eval']!r} "
                  f"vs {f['train_source']}: {f['train']!r}")
        sys.exit(1)

    cases, eligible, picked = build_cases(snaps, schema, args.per_scenario, args.seed)
    variants = variant_gate(cases, eligible, snaps, schema)
    if not variants["passed"]:
        print("!! BUILD BLOCKED — variant coverage gate failed, nothing written")
        for f in variants["failures"]:
            print(f"   variant FAIL [{f['scenario']}] used {f['used']} of "
                  f"{f['available']} (need {f['required']}); unused: {', '.join(f['unused'])}")
        sys.exit(1)
    rep = build_report(cases, eligible, picked, snaps, args.per_scenario, args.seed,
                       collisions, gate, schema, variants)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "eval_set_v3.jsonl", "w") as f:
        for c in cases:
            f.write(json.dumps(c) + "\n")
    write_md(cases, rep, out / "cases_v3.md")
    json.dump(rep, open(out / "report_v3.json", "w"), indent=2, default=str)
    print_report(rep)
    print(f"\nwrote {len(cases)} cases to {out/'eval_set_v3.jsonl'}, digest to "
          f"{out/'cases_v3.md'}, report to {out/'report_v3.json'}")


if __name__ == "__main__":
    main()
