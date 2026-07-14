"""Deterministic smoke — the doc-18.1 scenarios with stubbed extractor output.

Runs pre-step -> validate -> compose (no model) and asserts the ACTIONS for each
scenario. The model calls (extract / respond) are covered by the live teacher
smoke in chunk 3. Run from repo root:  python3 -m tuning.v2.smoke_deterministic
"""
from __future__ import annotations

from .schema import load_schema
from .state import TurnState, Pending, CONFIRM_SUBMIT, queue
from . import prestep
from .validator import validate
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


def main():
    for fn in [s1_volunteered, s2_elliptical, s4_button_event, s5_ambiguous_select,
               s6_asks_about_field, s7_deflection, s8_chitchat, s12_save,
               s13_premature_submit, s14_terminal, s15_validation_error,
               s16_bulk_bare, s16b_unplaceable, s17_large_select_text,
               s18a_bare_date_pending_binds, s18b_bare_date_no_pending_clarifies,
               s18c_cued_date_sets, s18d_bare_number_no_pending]:
        print(f"\n{fn.__name__}")
        fn()
    passed = sum(1 for _, c, _ in _results if c)
    print(f"\n=== {passed}/{len(_results)} checks passed ===")
    return 0 if passed == len(_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
