"""Deterministic smoke — the doc-18.1 scenarios with stubbed extractor output.

Runs pre-step -> validate -> compose (no model) and asserts the ACTIONS for each
scenario. The model calls (extract / respond) are covered by the live teacher
smoke in chunk 3. Run from repo root:  python3 -m tuning.v2.smoke_deterministic
"""
from __future__ import annotations

import json
from pathlib import Path

from .schema import load_schema
from .state import TurnState, Pending, CONFIRM_SUBMIT, queue
from . import prestep
from .validator import validate, match_options, coerce, DROPPED
from .composer import compose

SCHEMA = load_schema()
_results = []


def run_turn(state, message, pairs):
    ps = prestep.run(message, state)
    # pass the message so validate() can apply the bare-value demotion (doc-18.1)
    outcomes = [] if ps.handled else validate(pairs, state, message)
    actions, directives = compose(state, ps, outcomes)
    return actions, directives


def types(actions):
    return [a["type"] for a in actions]


def opt_values(action):
    return [o["value"] for o in action["options"]]


def fids(set_action):
    return [f["field_id"] for f in set_action["fields"]]


def has_dir(directives, kind):
    return any(d[0] == kind for d in directives)


def check(name, cond, detail=""):
    _results.append((name, cond, detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))


def state_with(filled: dict, pending: str | None = None):
    s = TurnState(schema=SCHEMA, form_state=dict(filled))
    if pending:
        s.pending = Pending(pending)
    return s


# ---------------------------------------------------------------- scenarios

def s1_volunteered():
    s = state_with({})
    a, d = run_turn(s, "I'm Maria Garcia, my email's maria.g@gmail.com",
                    [{"field_id": "full_name", "value": "Maria Garcia"},
                     {"field_id": "email", "value": "maria.g@gmail.com"}])
    check("S1 set_fields(full_name,email)", "set_fields" in types(a) and
          set(fids(a[0])) == {"full_name", "email"})
    check("S1 agenda -> program is next (program-first section_order), shown as buttons",
          types(a) == ["set_fields", "ask_choice"] and s.pending.target == "program",
          f"types={types(a)} pending={s.pending}")


def s2_elliptical():
    s = state_with({"full_name": "Maria Garcia", "email": "maria.g@gmail.com"}, pending="dob")
    a, d = run_turn(s, "March 12, 1999", [{"field_id": None, "value": "March 12, 1999"}])
    check("S2 null date cascades -> set_fields(dob=ISO)",
          types(a)[0] == "set_fields" and a[0]["fields"][0] == {"field_id": "dob", "value": "1999-03-12"},
          str(a[0]["fields"]))
    # next REQUIRED after dob is country_citizenship (a select) — gender is optional
    check("S2 agenda -> next required (program) shown as buttons",
          types(a) == ["set_fields", "ask_choice"] and s.pending.target == "program",
          f"types={types(a)} pending={s.pending}")


def s4_button_event():
    s = state_with({"full_name": "M", "dob": "1999-03-12"}, pending="enrollment_type")
    a, d = run_turn(s, '[system] User selected option: "Full-time"', [])  # extractor skipped
    check("S4 system option -> set_fields(enrollment_type=full_time), no model",
          types(a)[0] == "set_fields" and a[0]["fields"][0] == {"field_id": "enrollment_type", "value": "full_time"},
          str(a[0]["fields"]))


def s21_unknown_option_label():
    # An off-schema `User selected option` label (e.g. a UI button leaking through as
    # an option event) must NEVER be written as a raw value (doc-18.1 prestep fix):
    # no set, pending stays open so the agenda's reask recovers.
    s = state_with({"full_name": "M"}, pending="prior_application")
    a, d = run_turn(s, '[system] User selected option: "Save Draft"', [])
    check("S21 unknown option label -> no set, prior_application unwritten, pending stays",
          not any(x["type"] == "set_fields" for x in a)
          and "prior_application" not in s.form_state
          and s.pending and s.pending.target == "prior_application",
          f"types={types(a)} filled={s.form_state} pending={s.pending}")


def s5_ambiguous_select():
    s = state_with({})
    a, d = run_turn(s, "I'm interested in a science program", [{"field_id": "program", "value": "science"}])
    check("S5 ambiguous select -> ask_choice(subset cs,data_science)",
          types(a) == ["ask_choice"] and set(opt_values(a[0])) == {"cs", "data_science"},
          str(opt_values(a[0])) if a and a[0]["type"] == "ask_choice" else types(a))


def s6_asks_about_field():
    s = state_with({})
    a, d = run_turn(s, "what programs do you have?", [{"field_id": "program", "value": ""}])
    check("S6 empty value -> ask_choice(all 6)",
          types(a) == ["ask_choice"] and len(a[0]["options"]) == 6,
          str(types(a)))


def s7_deflection():
    s = state_with({"full_name": "M"}, pending="dob")
    a, d = run_turn(s, "actually, what programs do you offer?", [{"field_id": "program", "value": ""}])
    check("S7 deflection -> ask_choice(program), pending switches to program",
          types(a) == ["ask_choice"] and s.pending.target == "program")
    check("S7 dob not force-filled, still queued",
          "dob" in [f.field_id for f in queue(s)] and "dob" not in s.form_state)


def s8_chitchat():
    s = state_with({"full_name": "M"}, pending="country_citizenship")
    a, d = run_turn(s, "ugh, so rainy today", [])  # restraint -> []
    check("S8 chitchat -> no actions (text only)", types(a) == [])
    check("S8 pending re-asserted in text only (no re-emitted choice)",
          has_dir(d, "reask_pending"))


def s12_save():
    s = state_with({"full_name": "M"}, pending="country_citizenship")
    a, d = run_turn(s, "let's save it, I'll come back later", [])
    check("S12 save -> show_button(save_draft), agenda paused",
          types(a) == ["show_button"] and a[0]["button"] == "save_draft")


def s13_premature_submit():
    s = state_with({"full_name": "M"}, pending="country_citizenship")
    a, d = run_turn(s, "just submit it already", [])
    check("S13 premature submit -> offers save_draft, no submit button, submit_blocked",
          any(x["type"] == "show_button" and x["button"] == "save_draft" for x in a)
          and not any(x["type"] == "show_button" and x["button"] == "submit" for x in a)
          and has_dir(d, "submit_blocked"), f"types={types(a)} dirs={[x[0] for x in d]}")


def _all_required_except(skip: str) -> dict:
    vals = {"select": None, "boolean": True, "date": "2000-01-01", "number": 1,
            "text": "x", "textarea": "x", "email": "x@y.com", "phone": "5550000"}
    out = {}
    for f in SCHEMA.fields:
        if not f.required or f.field_id == skip:
            continue
        out[f.field_id] = f.options[0][0] if f.is_choice else vals[f.type]
    return out


def s14_terminal():
    # fill every required field except the last (funding_interest), then answer it
    last = [f for f in SCHEMA.fields if f.required][-1]
    s = state_with(_all_required_except(last.field_id), pending=last.field_id)
    a, d = run_turn(s, "yes please", [{"field_id": last.field_id, "value": "yes"}])
    check("S14 last required -> terminal (set_fields, show_preview, show_button submit)",
          types(a) == ["set_fields", "show_preview", "show_button"] and a[-1]["button"] == "submit",
          str(types(a)))
    check("S14 pending -> confirm_submit", s.pending and s.pending.target == CONFIRM_SUBMIT)


def s15_validation_error():
    s = state_with(_all_required_except(None) if False else {"full_name": "M"})
    s.pending = Pending(CONFIRM_SUBMIT)
    a, d = run_turn(s, '[system] Validation error: "Fall 2026 enrollment is closed" (field: start_term)', [])
    check("S15 validation error -> text only (agenda held), fix directive",
          types(a) == [] and has_dir(d, "fix"))
    check("S15 re-pend errored field, held", s.pending.target == "start_term" and s.pending.held)


def s16_bulk_bare():
    s = state_with({"full_name": "Maria Garcia"}, pending="dob")
    a, d = run_turn(s, "Maria Garcia, March 12 1999, maria.g@gmail.com, 555-0142",
                    [{"field_id": "email", "value": "maria.g@gmail.com"},
                     {"field_id": "phone", "value": "555-0142"},
                     {"field_id": "full_name", "value": "Maria Garcia"},   # already filled -> CORRECTION
                     {"field_id": None, "value": "March 12 1999"}])        # unplaced -> cascade to dob
    check("S16 bulk: set_fields incl. cascaded dob + email + phone",
          types(a)[0] == "set_fields" and {"email", "phone", "dob"}.issubset(set(fids(a[0]))),
          str(fids(a[0])))


def s16b_unplaceable():
    s = state_with({})  # no pending; two text name fields unfilled
    a, d = run_turn(s, "Lee", [{"field_id": None, "value": "Lee"}])
    check("S16b unplaceable bare value -> CLARIFY, never silently set",
          not any(x["type"] == "set_fields" for x in a) and has_dir(d, "clarify"),
          f"types={types(a)} dirs={[x[0] for x in d]}")


def s17_large_select_text():
    # program-section + name filled; pending=dob; answering dob makes the next
    # required field country_citizenship (15 options) -> asked as TEXT, not buttons
    pre = {"program": "cs", "start_term": "fall_2026", "enrollment_type": "full_time",
           "prior_application": False, "full_name": "Maria"}
    s = state_with(pre, pending="dob")
    a, d = run_turn(s, "March 12, 1999", [{"field_id": None, "value": "March 12, 1999"}])
    check("S17 large select (15-country) asked as text, not buttons",
          "ask_choice" not in types(a) and s.pending.target == "country_citizenship",
          f"types={types(a)} pending={s.pending}")


# ---- large-select label enrichment (freetext_select) ----------------------
# The country selects carry human labels (US->United States, KR->South Korea, ...)
# so a free-typed country name option-matches to its ISO-code canonical value.

def s19_freetext_country():
    field = SCHEMA.field("country_citizenship")
    check("S19 match_options('South Korea') -> unique KR",
          [o[0] for o in match_options("South Korea", field)] == ["KR"],
          str(match_options("South Korea", field)))
    check("S19 match_options('korea') -> resolves via substring containment -> KR",
          [o[0] for o in match_options("korea", field)] == ["KR"],
          str(match_options("korea", field)))
    # full turn: pending=country_citizenship, extractor attributes the country name ->
    # validator option-matches it to the canonical ISO value KR.
    s = state_with({"full_name": "M"}, pending="country_citizenship")
    a, d = run_turn(s, "I'm a citizen of South Korea.",
                    [{"field_id": "country_citizenship", "value": "South Korea"}])
    check("S19 freetext country turn -> set_fields(country_citizenship=KR)",
          types(a)[0] == "set_fields" and {"field_id": "country_citizenship", "value": "KR"} in a[0]["fields"],
          str(a[0]["fields"]) if a and a[0]["type"] == "set_fields" else str(types(a)))


# ---- bare-value demotion policy (doc-18.1 "code owns placement") ----------
# A message that is ONLY a value (a lone date/number, no words) must not be bound
# from its type alone: validate() demotes every pair to {null, value} so placement
# runs through the binding cascade. These four cases pin the policy in the core.

def s18a_bare_date_pending_binds():
    # bare date + pending=dob: demotion -> cascade rule 2 (pending of matching type) binds dob
    s = state_with({"full_name": "Maria"}, pending="dob")
    a, d = run_turn(s, "August 10, 2000.", [{"field_id": "dob", "value": "2000-08-10"}])
    check("S18a bare date + pending=dob -> demoted, cascade binds pending dob",
          types(a)[0] == "set_fields" and a[0]["fields"][0] == {"field_id": "dob", "value": "2000-08-10"},
          str(a[0]["fields"]) if a and a[0]["type"] == "set_fields" else str(types(a)))


def s18b_bare_date_no_pending_clarifies():
    # NEW POLICY: bare date + no pending. Demoted; the cascade finds the value fits
    # several distinctive fields (dob/gre_date/english_test_date + phone digits) ->
    # not unique -> CLARIFY. The confident {dob} attribution is overridden in code.
    s = state_with({})
    a, d = run_turn(s, "August 10, 2000.", [{"field_id": "dob", "value": "2000-08-10"}])
    check("S18b bare date + no pending -> demoted, NO set, CLARIFY",
          not any(x["type"] == "set_fields" for x in a) and has_dir(d, "clarify"),
          f"types={types(a)} dirs={[x[0] for x in d]}")


def s18c_cued_date_sets():
    # regression: message has words ('I was born on ...') -> NOT bare -> guard does
    # not fire -> the attributed dob set stands.
    s = state_with({})
    a, d = run_turn(s, "I was born on August 10, 2000", [{"field_id": "dob", "value": "2000-08-10"}])
    check("S18c cued date ('I was born on ...') -> guard does not fire, dob set stands",
          types(a)[0] == "set_fields" and a[0]["fields"][0] == {"field_id": "dob", "value": "2000-08-10"},
          str(a[0]["fields"]) if a and a[0]["type"] == "set_fields" else str(types(a)))


def s18d_bare_number_no_pending():
    # bare number '1999' + no pending. Demoted. Cascade rule 3 finds NO candidate:
    # 1999 < prior_application_year.min (2000) and out of range for every other number
    # field, so no coercion succeeds -> not unique -> CLARIFY (not a silent set).
    s = state_with({})
    a, d = run_turn(s, "1999", [{"field_id": "prior_application_year", "value": "1999"}])
    check("S18d bare number 1999 + no pending -> demoted, no set, CLARIFY (out of every number range)",
          not any(x["type"] == "set_fields" for x in a) and has_dir(d, "clarify"),
          f"types={types(a)} dirs={[x[0] for x in d]}")


# ---- multi_select (funding_type) --------------------------------------------
# funding_type is type=multi_select: an explicit conjunction of exact options sets
# them ALL (value stored as a LIST); a single exact option is a one-element list;
# a category word matching >=2 labels ("assistantship") stays ambiguous -> buttons.

def s20a_multi_conjunction():
    s = state_with({"funding_interest": True}, pending="funding_type")
    a, d = run_turn(s, "fellowship and scholarship",
                    [{"field_id": "funding_type", "value": "fellowship and scholarship"}])
    check("S20a multi conjunction -> set_fields(funding_type=[fellowship,scholarship])",
          types(a)[0] == "set_fields" and
          a[0]["fields"][0] == {"field_id": "funding_type", "value": ["fellowship", "scholarship"]},
          str(a[0]["fields"]) if a and a[0]["type"] == "set_fields" else str(types(a)))


def s20b_multi_single():
    s = state_with({"funding_interest": True}, pending="funding_type")
    a, d = run_turn(s, "a fellowship would be great",
                    [{"field_id": "funding_type", "value": "fellowship"}])
    check("S20b multi single exact -> set_fields(funding_type=[fellowship]) (one-element list)",
          types(a)[0] == "set_fields" and
          a[0]["fields"][0] == {"field_id": "funding_type", "value": ["fellowship"]},
          str(a[0]["fields"]) if a and a[0]["type"] == "set_fields" else str(types(a)))


def s20c_multi_category():
    s = state_with({"funding_interest": True}, pending="funding_type")
    a, d = run_turn(s, "an assistantship, I think",
                    [{"field_id": "funding_type", "value": "assistantship"}])
    check("S20c multi category word ('assistantship') -> ask_choice(teaching,research)",
          types(a) == ["ask_choice"] and
          set(opt_values(a[0])) == {"teaching_assistantship", "research_assistantship"},
          str(opt_values(a[0])) if a and a[0]["type"] == "ask_choice" else str(types(a)))


# ---- SFT-era finalize (2026-08-02) --------------------------------------
# Three validator changes: the provenance gate (code owns provenance), the country
# alias table in match_options, and phone canonicalization in coerce.

def s22a_country_alias():
    res = SCHEMA.field("country_residence")
    check("S22a match_options('Britain') -> unique UK (alias table)",
          [o[0] for o in match_options("Britain", res)] == ["UK"],
          str(match_options("Britain", res)))
    check("S22a match_options('America') -> unique US (alias table)",
          [o[0] for o in match_options("America", res)] == ["US"],
          str(match_options("America", res)))
    check("S22a alias table is keyed by option value -> cannot fire on another field",
          match_options("America", SCHEMA.field("program")) == []
          and match_options("Britain", SCHEMA.field("how_heard")) == [],
          str(match_options("America", SCHEMA.field("program"))))
    s = state_with({"full_name": "M"}, pending="country_residence")
    a, d = run_turn(s, "I live in Britain these days.",
                    [{"field_id": "country_residence", "value": "Britain"}])
    check("S22a 'Britain' turn -> set_fields(country_residence=UK)",
          types(a)[0] == "set_fields" and {"field_id": "country_residence", "value": "UK"} in a[0]["fields"],
          str(a[0]["fields"]) if a and a[0]["type"] == "set_fields" else str(types(a)))
    s = state_with({"full_name": "M"}, pending="country_residence")
    a, d = run_turn(s, "I'm in America.",
                    [{"field_id": "country_residence", "value": "America"}])
    check("S22a 'America' turn -> set_fields(country_residence=US)",
          types(a)[0] == "set_fields" and {"field_id": "country_residence", "value": "US"} in a[0]["fields"],
          str(a[0]["fields"]) if a and a[0]["type"] == "set_fields" else str(types(a)))


def s22b_provenance_unsupported():
    # the recorded slice1b failure shape: a third-party mention, and the extractor
    # hands back PII that appears NOWHERE in the message. Nothing may be written.
    s = state_with({"full_name": "M"}, pending="email")
    a, d = run_turn(s, "Ravi Ali in my office went through this exact process and swore by it.",
                    [{"field_id": "email", "value": "ravi.ali14@example.com"},
                     {"field_id": "phone", "value": "(892) 555-1029"}])
    check("S22b invented email+phone -> nothing set, pending email untouched, reask fires",
          not any(x["type"] == "set_fields" for x in a)
          and "email" not in s.form_state and "phone" not in s.form_state
          and s.pending and s.pending.target == "email" and has_dir(d, "reask_pending"),
          f"types={types(a)} filled={s.form_state} pending={s.pending} dirs={[x[0] for x in d]}")
    # a value the message DOES carry still sets, same turn shape
    s = state_with({"full_name": "M"}, pending="email")
    a, d = run_turn(s, "my email is ravi.ali14@example.com",
                    [{"field_id": "email", "value": "ravi.ali14@example.com"}])
    check("S22b same email, present in the message -> set (gate is provenance, not a blocklist)",
          types(a)[0] == "set_fields" and s.form_state["email"] == "ravi.ali14@example.com",
          f"types={types(a)} filled={s.form_state}")


def s22c_phone_canonical():
    check("S22c coerce phone -> digits, '+' kept",
          coerce("(415) 782-3311", SCHEMA.field("phone")) == (True, "4157823311")
          and coerce("+49 30 901820", SCHEMA.field("phone")) == (True, "+4930901820"),
          str([coerce("(415) 782-3311", SCHEMA.field("phone")),
               coerce("+49 30 901820", SCHEMA.field("phone"))]))
    s = state_with({"full_name": "M"}, pending="phone")
    a, d = run_turn(s, "you can text me at (212) 555-9981",
                    [{"field_id": "phone", "value": "(212) 555-9981"}])
    check("S22c phone turn -> form stores '2125559981' (punctuation is not data)",
          types(a)[0] == "set_fields" and s.form_state.get("phone") == "2125559981",
          f"types={types(a)} filled={s.form_state}")


def s22d_date_support_is_coerce_span():
    # the ISO value is NOT a substring of "January 15, 1998" — support must be decided
    # by coercing the spans in the message, or every dated turn would be dropped.
    s = state_with({"full_name": "M"}, pending="dob")
    a, d = run_turn(s, "I was born January 15, 1998, in Lagos.",
                    [{"field_id": "dob", "value": "1998-01-15"}])
    check("S22d ISO dob + spelled-out date in the message -> supported, dob set",
          types(a)[0] == "set_fields" and s.form_state.get("dob") == "1998-01-15",
          f"types={types(a)} filled={s.form_state}")
    s = state_with({"full_name": "M"}, pending="dob")
    a, d = run_turn(s, "sure, go ahead.", [{"field_id": "dob", "value": "1998-01-15"}])
    check("S22d same ISO dob, no date anywhere in the message -> dropped, dob unwritten",
          not any(x["type"] == "set_fields" for x in a) and "dob" not in s.form_state
          and s.pending and s.pending.target == "dob",
          f"types={types(a)} filled={s.form_state} pending={s.pending}")


def s22e_date_support_covers_every_coerce_format():
    # v3 regression 2026-08-02: support was decided by a regex that did not know the
    # day-first "%d %b %Y" form `coerce` accepts, so 6 CORRECT dates were dropped.
    # Spans are now found by calling coerce over token windows — the two cannot drift.
    s = state_with({"full_name": "M"}, pending="dob")
    a, d = run_turn(s, "Go ahead and use 2 Feb 1993.", [{"field_id": "dob", "value": "1993-02-02"}])
    check("S22e day-first abbreviated month ('2 Feb 1993') -> supported, dob set",
          types(a)[0] == "set_fields" and s.form_state.get("dob") == "1993-02-02",
          f"types={types(a)} filled={s.form_state}")
    s = state_with({"full_name": "M", "dob": "1990-01-01"}, pending=None)
    a, d = run_turn(s, "change my birthday to 28 Sep 1995",
                    [{"field_id": "dob", "value": "1995-09-28"}])
    check("S22e correction to a day-first date -> supported, dob overwritten",
          any(x["type"] == "set_fields" for x in a) and s.form_state.get("dob") == "1995-09-28",
          f"types={types(a)} filled={s.form_state}")
    s = state_with({"full_name": "M"}, pending="dob")
    a, d = run_turn(s, "I was born 28 Sep 1995", [{"field_id": "dob", "value": "2025-09-28"}])
    check("S22e wrong year off the same message -> still dropped (the gate is not weakened)",
          not any(x["type"] == "set_fields" for x in a) and "dob" not in s.form_state,
          f"types={types(a)} filled={s.form_state}")


# ---- replay gate: the 25 recorded inventions from the slice1b sweep -------
# stress_runs/ is local (gitignored). Missing file -> loud skip, never a build break.

REPLAY = Path(__file__).resolve().parent / "stress_runs" / "slice1b" / "results.jsonl"
INVENTED_BUCKETS = {"from_corpus", "novel_in_format", "other_novel"}


def s23_replay_slice1b_inventions():
    if not REPLAY.exists():
        print(f"  !! SKIPPED replay gate — {REPLAY} not found (local, gitignored) !!")
        return
    n, survivors = 0, []
    for line in open(REPLAY):
        row = json.loads(line)
        for cl in row.get("classified") or []:
            if cl["bucket"] not in INVENTED_BUCKETS:
                continue
            n += 1
            outs = validate([{"field_id": cl["field_id"], "value": cl["value"]}],
                            TurnState(schema=SCHEMA, form_state={}), row["user_message"])
            if [o.kind for o in outs] != [DROPPED]:
                survivors.append((cl["field_id"], cl["value"], [o.kind for o in outs]))
    check(f"S23 replay: all {n} invented slice1b values DROPPED ({n - len(survivors)}/{n})",
          n == 25 and not survivors, f"n={n} survivors={survivors[:6]}")


def main():
    for fn in [s1_volunteered, s2_elliptical, s4_button_event, s21_unknown_option_label,
               s5_ambiguous_select,
               s6_asks_about_field, s7_deflection, s8_chitchat, s12_save,
               s13_premature_submit, s14_terminal, s15_validation_error,
               s16_bulk_bare, s16b_unplaceable, s17_large_select_text,
               s19_freetext_country,
               s18a_bare_date_pending_binds, s18b_bare_date_no_pending_clarifies,
               s18c_cued_date_sets, s18d_bare_number_no_pending,
               s20a_multi_conjunction, s20b_multi_single, s20c_multi_category,
               s22a_country_alias, s22b_provenance_unsupported, s22c_phone_canonical,
               s22d_date_support_is_coerce_span, s22e_date_support_covers_every_coerce_format,
               s23_replay_slice1b_inventions]:
        print(f"\n{fn.__name__}")
        fn()
    passed = sum(1 for _, c, _ in _results if c)
    print(f"\n=== {passed}/{len(_results)} checks passed ===")
    return 0 if passed == len(_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
