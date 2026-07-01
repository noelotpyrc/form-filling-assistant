"""M3a frozen eval set — extractor correctness against ground truth (doc-18 §6).

Two sources, both correct-by-construction (no per-case hand-labeling):
  - TEMPLATES: messages that reference persona fields, instantiated with random
    personas -> the expected extraction falls out of the persona.
  - EDGE_CASES: hand-authored hard/CANNOT cases (restraint, trap, deflection,
    ambiguous) with fixed expected behavior. Distinct from the v1 P1-P12 probe
    taxonomy in tuning/harness/probes/ (that is the Tier-2 multi-turn sweep).

Each case is scored end-to-end (extract -> validate -> compose), comparing the
resulting set_fields to the expected canonical values. The deterministic
composer/agenda is already anchored by smoke_deterministic; this evals the
learned extractor.

Preview:  tuning/v2/.venv/bin/python -m tuning.v2.eval_set --preview
"""
from __future__ import annotations
import argparse
import json
import random
from datetime import datetime

from .schema import load_schema, Schema
from . import persona as personas

SCHEMA = load_schema()


def _date_phrase(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%B %-d, %Y")


def _label(fid: str, value) -> str:
    f = SCHEMA.field(fid)
    for val, lab in (f.options if f else []):
        if val == value:
            return lab
    return str(value)


# ---- TEMPLATES (persona p, rng) -> case ----------------------------------
# Each returns: (message, expect) where expect = {"sets": {fid: canonical},
# "empty": bool, "choice": [fid]}. setup defaults to empty state / no pending.

def t_single_name(p, rng):
    return f"Hi, my name is {p['full_name']}.", {"sets": {"full_name": p["full_name"]}}

def t_single_email(p, rng):
    return f"My email is {p['email']}.", {"sets": {"email": p["email"]}}

def t_multi(p, rng):
    return (f"I'm {p['full_name']} and you can reach me at {p['email']}.",
            {"sets": {"full_name": p["full_name"], "email": p["email"]}})

def t_select_by_label(p, rng):
    lab = _label("program", p["program"])
    return f"I'd like to apply for the {lab} program.", {"sets": {"program": p["program"]}}

def t_boolean(p, rng):
    yn = "Yes" if p["prior_application"] else "No"
    return (f"{'Yes, I have' if p['prior_application'] else 'No, I have not'} applied before.",
            {"sets": {"prior_application": p["prior_application"]}})

def t_bulk(p, rng):
    return (f"Here's my info: name {p['full_name']}, email {p['email']}, phone {p['phone']}.",
            {"sets": {"full_name": p["full_name"], "email": p["email"], "phone": p["phone"]}})

def t_elliptical_dob(p, rng):
    # pending=dob; user gives just the date -> cascade binds to dob
    return _date_phrase(p["dob"]), {"sets": {"dob": p["dob"]}, "pending": "dob"}

def t_pending_name(p, rng):
    # pending=full_name; bare answer -> cascade binds to pending (the bulk real turn)
    return p["full_name"], {"sets": {"full_name": p["full_name"]}, "pending": "full_name"}

def t_pending_phone(p, rng):
    # pending=phone; bare answer -> cascade binds to pending
    return p["phone"], {"sets": {"phone": p["phone"]}, "pending": "phone"}

def t_correction_email(p, rng):
    new = f"new.{p['email']}"
    return (f"Wait, my email is actually {new}.",
            {"sets": {"email": new}, "form_state": {"email": p["email"]}})

def t_asks_about_program(p, rng):
    return "What programs do you offer?", {"choice": ["program"], "empty": False}

def t_chitchat(p, rng):
    return rng.choice(["Ugh, the weather has been wild lately.",
                       "Phew, this is a long form, huh?",
                       "Hope you're having a good day!"]), {"empty": True}

TEMPLATES = [
    ("single_name", t_single_name), ("single_email", t_single_email),
    ("multi", t_multi), ("select_by_label", t_select_by_label),
    ("boolean", t_boolean), ("bulk", t_bulk),
    ("elliptical_dob", t_elliptical_dob),
    ("pending_name", t_pending_name), ("pending_phone", t_pending_phone),
    ("correction_email", t_correction_email),
    ("asks_about_field", t_asks_about_program), ("chitchat", t_chitchat),
]

# ---- EDGE_CASES (hand-authored hard cases, fixed) ------------------------
EDGE_CASES = [
    {"id": "edge_trap_chitchat", "scenario": "trap", "user_message": "I love hiking near Denver on weekends.",
     "expect": {"empty": True}},  # "Denver" must NOT be set as mailing_address
    {"id": "edge_bare_ambiguous", "scenario": "ambiguous", "user_message": "1999",
     "expect": {"empty": True}},  # no pending -> unplaceable -> CLARIFY, never a silent set
    {"id": "edge_deflection", "scenario": "deflect", "pending": "dob",
     "user_message": "Actually, what programs can I pick from?",
     "expect": {"choice": ["program"]}},  # must NOT bind to dob
    {"id": "edge_typed_choice", "scenario": "typed_choice", "pending": "enrollment_type",
     "user_message": "full time please", "expect": {"sets": {"enrollment_type": "full_time"}}},
    {"id": "edge_restraint_question", "scenario": "restraint", "pending": "country_citizenship",
     "user_message": "Can you tell me more about what documents I'll need later?",
     "expect": {"empty": True}},
    # confident attribution (cascade rule 1) must beat pending-by-type (rule 2):
    # a clear email must NOT be shoved into the pending phone slot.
    {"id": "edge_confident_over_pending", "scenario": "precedence", "pending": "phone",
     "user_message": "Oh hang on, my email is sam.lee@example.com.",
     "expect": {"sets": {"email": "sam.lee@example.com"}}},
    # value not in the option set -> validator match_options no-match -> CLARIFY,
    # never a bogus canonical set.
    {"id": "edge_value_not_in_options", "scenario": "no_match", "pending": "program",
     "user_message": "I want to study astrophysics.",
     "expect": {"empty": True}},
    # refusal / negation: must not invent a value from a decline.
    {"id": "edge_refusal", "scenario": "refusal", "pending": "phone",
     "user_message": "I'd rather not share my phone number right now.",
     "expect": {"empty": True}},
    # pending-bind + confident extra must coexist in one turn.
    {"id": "edge_answer_plus_extra", "scenario": "compound", "pending": "dob",
     "user_message": "March 3rd 1995 — and you can text me at (415) 555-0132.",
     "expect": {"sets": {"dob": "1995-03-03", "phone": "(415) 555-0132"}}},
    # inverse of trap_chitchat: a conversational wrapper must NOT suppress a real value.
    {"id": "edge_chitchat_with_value", "scenario": "wrapped_value",
     "user_message": "Sorry, typing in line at the store — anyway you can reach me at (212) 555-9981.",
     "expect": {"sets": {"phone": "(212) 555-9981"}}},
    # name over-attribution: a named third party is not the applicant. (No
    # referral/recommend cue — that would make how_heard=referral defensible.)
    {"id": "edge_third_party_name", "scenario": "third_party",
     "user_message": "My advisor, Dr. Patel, is traveling this week.",
     "expect": {"empty": True}},
    # large select (15 opts -> asked as free text): country name -> ISO-code canonical.
    {"id": "edge_freetext_country", "scenario": "freetext_select", "pending": "country_citizenship",
     "user_message": "I'm a citizen of South Korea.",
     "expect": {"sets": {"country_citizenship": "KR"}}},
    # no pending + no cue: clarify, don't bind. cascade rule 3 must NOT silently fire on dob.
    {"id": "edge_bare_date_no_cue", "scenario": "bare_date",
     "user_message": "August 10, 2000.",
     "expect": {"empty": True}},
]


def gen_eval_set(per_template: int = 8, seed: int = 0) -> list[dict]:
    rng = random.Random(seed)
    cases = []
    for name, fn in TEMPLATES:
        for i in range(per_template):
            p = personas.gen_persona(SCHEMA, rng)
            msg, expect = fn(p, rng)
            cases.append({
                "id": f"{name}-{i}", "scenario": name,
                "form_state": expect.pop("form_state", {}),
                "pending": expect.pop("pending", None),
                "conversation_history": [], "user_message": msg,
                "expect": expect,
            })
    for ec in EDGE_CASES:
        cases.append({"id": ec["id"], "scenario": ec["scenario"],
                      "form_state": ec.get("form_state", {}), "pending": ec.get("pending"),
                      "conversation_history": [], "user_message": ec["user_message"],
                      "expect": ec["expect"]})
    return cases


# ---- human-readable digest (kept in sync with the jsonl on every write) ---

_WHY = {
    "edge_trap_chitchat": '"Denver" must NOT be grabbed as mailing_address',
    "edge_bare_ambiguous": "no pending → unplaceable number → clarify, never a silent set",
    "edge_deflection": "user pivots to a question mid-pending → must NOT bind answer to dob",
    "edge_typed_choice": "typed answer to a button field → map to canonical value",
    "edge_restraint_question": "question while pending → answer it, extract nothing",
    "edge_confident_over_pending": "cascade rule 1 (confident) beats rule 2 — email must NOT fill pending phone slot",
    "edge_value_not_in_options": "not an offered program → match no-match → clarify, never a bogus set",
    "edge_refusal": "refusal/negation → must not invent a value",
    "edge_answer_plus_extra": "pending-bind (dob) + confident extra (phone) must coexist in one turn",
    "edge_chitchat_with_value": "inverse of trap — conversational wrapper must NOT suppress a real value",
    "edge_third_party_name": "a named third party (advisor) is not the applicant",
    "edge_freetext_country": "large select asked as free text → country name → ISO-code match (labels are bare codes)",
    "edge_bare_date_no_cue": "no pending + no cue → clarify; cascade rule 3 must NOT silently bind dob",
}


def _fmt_expect(e) -> str:
    parts = []
    if e.get("sets"):
        parts.append("sets " + ", ".join(f"`{k}`={v!r}" for k, v in e["sets"].items()))
    if e.get("choice"):
        parts.append("offer choice for " + ", ".join(f"`{c}`" for c in e["choice"]))
    if e.get("empty"):
        parts.append("**no field set** (clarify / chit-chat)")
    return "; ".join(parts) or "—"


def _setup(c) -> str:
    s = []
    if c["form_state"]:
        s.append("filled: " + ", ".join(f"`{k}`={v!r}" for k, v in c["form_state"].items()))
    if c["pending"]:
        s.append(f"pending: `{c['pending']}`")
    return "<br>".join(s) or "empty form"


def write_md(cases: list[dict], path: str):
    tmpl, edges = {}, []            # tmpl keeps first-seen scenario order
    for c in cases:
        if c["id"].startswith("edge_"):
            edges.append(c)
        else:
            tmpl.setdefault(c["scenario"], []).append(c)

    out = ["# M3a eval set — case review\n",
           f"Frozen extractor eval. **{len(cases)} cases** ({len(tmpl)} template types ×N + "
           f"{len(edges)} edge cases). Each is scored extract → validate → compose against the "
           "expected result. Generated by `eval_set.py` — do not edit by hand.\n",
           "Columns: **setup** = form/pending before the turn; **user says** = the message; "
           "**expected** = what the harness should do.\n",
           "\n## Templates (auto-generated from random personas)\nShowing 2 of the N per type.\n",
           "\n| type | setup | user says | expected |\n|---|---|---|---|\n"]
    for scn, cs in tmpl.items():
        for c in cs[:2]:
            out.append(f"| `{scn}` | {_setup(c)} | {c['user_message'].replace('|', chr(92)+'|')} "
                       f"| {_fmt_expect(c['expect'])} |\n")
    out.append("\n## Edge cases (hand-authored hard cases — fixed)\n"
               "\n| id | setup | user says | expected | why it's hard |\n|---|---|---|---|---|\n")
    for c in edges:
        out.append(f"| `{c['id']}` | {_setup(c)} | {c['user_message'].replace('|', chr(92)+'|')} "
                   f"| {_fmt_expect(c['expect'])} | {_WHY.get(c['id'], '')} |\n")
    with open(path, "w") as f:
        f.write("".join(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--per-template", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="tuning/v2/eval/eval_set.jsonl")
    args = ap.parse_args()

    if args.preview:
        print("=== TEMPLATES (instantiated once for preview) ===")
        rng = random.Random(7)
        for name, fn in TEMPLATES:
            p = personas.gen_persona(SCHEMA, rng)
            msg, expect = fn(p, dict_rng := random.Random(7))
            print(f"\n[{name}]\n  msg: {msg!r}\n  expect: {expect}")
        print("\n=== EDGE CASES (hand-authored) ===")
        for ec in EDGE_CASES:
            print(f"\n[{ec['id']}] pending={ec.get('pending')}\n  msg: {ec['user_message']!r}\n  expect: {ec['expect']}")
        cases = gen_eval_set(args.per_template, args.seed)
        print(f"\n=== set size: {len(cases)} cases ({len(TEMPLATES)} templates × {args.per_template} + {len(EDGE_CASES)} edge cases) ===")
        return

    import os
    cases = gen_eval_set(args.per_template, args.seed)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        for c in cases:
            f.write(json.dumps(c) + "\n")
    md = os.path.join(os.path.dirname(args.out), "cases.md")
    write_md(cases, md)
    print(f"wrote {len(cases)} cases to {args.out} and digest to {md}")


if __name__ == "__main__":
    main()
