"""Live teacher smoke — runs FormAssistant with ClaudeLM (sonnet) on the
model-sensitive scenarios and checks the resulting actions. Complements the
deterministic smoke (which stubs the model). Costs ~2 teacher calls per turn.

Run from repo root:  tuning/v2/.venv/bin/python -m tuning.v2.smoke_teacher
"""
from __future__ import annotations
import json

import dspy
from .claude_lm import ClaudeLM
from .schema import load_schema
from .state import TurnState, Pending, queue
from .program import FormAssistant

SCHEMA = load_schema()
_results = []


def types(actions):
    return [a["type"] for a in actions]


def has_set(actions, fid=None):
    for a in actions:
        if a["type"] == "set_fields":
            if fid is None:
                return True
            return any(f["field_id"] == fid for f in a["fields"])
    return False


def ask_choice_for(actions):
    for a in actions:
        if a["type"] == "ask_choice":
            return a
    return None


def check(name, cond, got=""):
    _results.append((name, cond))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   got: {got}" if not cond else ""))


def run(state, msg, history=None):
    out = FA(state=state, user_message=msg, history=history or [])
    print(f"\n  user: {msg}")
    print(f"  actions: {types(out.actions)}")
    print(f"  text: {out.text[:140]}")
    return out


def s1_volunteered():
    print("\nS1 volunteered data")
    s = TurnState(schema=SCHEMA)
    o = run(s, "I'm Maria Garcia, email maria.g@gmail.com")
    check("S1 set_fields full_name+email", has_set(o.actions, "full_name") and has_set(o.actions, "email"),
          json.dumps(o.actions))


def s2_elliptical():
    print("\nS2 elliptical answer to pending")
    s = TurnState(schema=SCHEMA, form_state={"full_name": "Maria Garcia"})
    s.pending = Pending("dob")
    hist = [{"role": "assistant", "content": "What's your date of birth?"}]
    o = run(s, "March 12, 1999", hist)
    check("S2 dob set to ISO", s.form_state.get("dob") == "1999-03-12", str(s.form_state.get("dob")))


def s5_ambiguous():
    print("\nS5 ambiguous select")
    s = TurnState(schema=SCHEMA)
    o = run(s, "I'm interested in a science program")
    ac = ask_choice_for(o.actions)
    vals = {opt["value"] for opt in ac["options"]} if ac else set()
    check("S5 ask_choice narrowed to science programs", ac is not None and vals == {"cs", "data_science"}, str(vals))


def s6_asks_about_field():
    print("\nS6 asks about a field")
    s = TurnState(schema=SCHEMA)
    o = run(s, "what programs do you offer?")
    ac = ask_choice_for(o.actions)
    check("S6 ask_choice(program, all 6)", ac is not None and len(ac["options"]) == 6,
          str(len(ac["options"]) if ac else None))


def s8_chitchat():
    print("\nS8 chitchat (restraint)")
    s = TurnState(schema=SCHEMA, form_state={"full_name": "Maria"})
    s.pending = Pending("country_citizenship")
    hist = [{"role": "assistant", "content": "What's your country of citizenship?"}]
    o = run(s, "ugh, it's so rainy today", hist)
    check("S8 no set_fields (restraint)", not has_set(o.actions), json.dumps(o.actions))


def s12_save():
    print("\nS12 save request")
    s = TurnState(schema=SCHEMA, form_state={"full_name": "Maria"})
    s.pending = Pending("country_citizenship")
    o = run(s, "let's save and come back later")
    check("S12 show_button(save_draft)",
          any(a["type"] == "show_button" and a["button"] == "save_draft" for a in o.actions),
          json.dumps(o.actions))


def s13_premature_submit():
    print("\nS13 premature submit (incomplete)")
    s = TurnState(schema=SCHEMA, form_state={"full_name": "Maria"})
    s.pending = Pending("country_citizenship")
    o = run(s, "just submit it now")
    check("S13 no submit button (incomplete)",
          not any(a["type"] == "show_button" and a["button"] == "submit" for a in o.actions),
          json.dumps(o.actions))


def multiturn():
    print("\nMULTI-TURN pending threading")
    s = TurnState(schema=SCHEMA)
    hist = []
    o = run(s, "hi there!", hist)
    hist += [{"role": "user", "content": "hi there!"}, {"role": "assistant", "content": o.text}]
    p1 = s.pending.target if s.pending else None
    o = run(s, "Jordan Lee", hist)  # bare answer to whatever was asked
    check("MT bare answer bound to the pending field", p1 is not None and s.is_filled(p1), f"pending was {p1}, state={s.form_state}")


def main():
    global FA
    dspy.configure(lm=ClaudeLM())
    FA = FormAssistant()
    for fn in [s1_volunteered, s2_elliptical, s5_ambiguous, s6_asks_about_field,
               s8_chitchat, s12_save, s13_premature_submit, multiturn]:
        try:
            fn()
        except Exception as e:
            check(fn.__name__ + " (raised)", False, repr(e))
    passed = sum(1 for _, c in _results if c)
    print(f"\n=== {passed}/{len(_results)} teacher checks passed ===")
    return 0 if passed == len(_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
