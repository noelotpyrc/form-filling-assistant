"""M3b probe — multi-turn behavioural probe of the HYBRID system.

The hybrid = student extractor (StudentLM on a local MLX server) + nemotron
responder (OpenRouterLM), wired per-predictor via assign_lms(). Each probe session
runs one SCENARIO through sim.run_session() (the LLM-U loop), then an offline
assertion layer inspects the transcript / final form_state / persona and produces
one {name, pass, detail} record per behavioural check. The per-scenario assertions
roll up into a P1..P12 product-requirement coverage matrix.

Run (needs a live student server + OPENROUTER_API_KEY):
  tuning/v2/.venv/bin/python -m tuning.v2.probe --port 8101 \
      --student-model /path/to/student --scenarios all --seeds 2 --run m3b_hybrid

Offline self-test (no network, no model):
  tuning/v2/.venv/bin/python -m tuning.v2.probe --selftest

Outputs (<out> default tuning/v2/probe_runs/<run>/):
  report.json     per-session assertion results + latency stats + P-matrix
  sessions.jsonl  full run_session returns (incl. transcripts)
  transcript-<seed>-<scenario>.md  plain-text transcript, per FAILING session
"""
from __future__ import annotations
import argparse
import json
import random
import re
import statistics
import sys
from pathlib import Path

from .schema import load_schema, Schema
from .state import TurnState, CONFIRM_SUBMIT, queue, is_active
from . import persona as personas
from .sim import run_session, SCENARIOS, DIRECTIVES
from .validator import coerce, value_supported, _norm   # _norm re-exported (stress_invent, datagen)

PROBE_DIR = Path(__file__).resolve().parent / "probe_runs"

# The first ~6 required fields, in agenda order, that the "resume" scenario
# pre-fills from the persona before picking up mid-form (ids verified against
# schema.py walk order: program section then personal section).
RESUME_PREFILL = ["program", "start_term", "enrollment_type",
                  "prior_application", "full_name", "dob"]


# ======================================================================
# small helpers over a transcript entry (enriched by sim.run_session)
# ======================================================================

def _details(entry: dict) -> list:
    return entry.get("action_details") or []


def _turn_sets(entry: dict) -> list[tuple]:
    """(field_id, value) pairs recorded by set_fields actions on this turn."""
    out = []
    for a in _details(entry):
        if a.get("type") == "set_fields":
            for f in a.get("fields", []):
                out.append((f["field_id"], f.get("value")))
    return out


def _has_type(entry: dict, atype: str) -> bool:
    return any(a.get("type") == atype for a in _details(entry))


def _has_button(entry: dict, kind: str) -> bool:
    return any(a.get("type") == "show_button" and a.get("button") == kind
              for a in _details(entry))


def _ask_choice_fields(entry: dict) -> list[str]:
    """The field labels an ask_choice was shown for this turn (question is 'Label?')."""
    return [a.get("question", "").rstrip("?")
            for a in _details(entry) if a.get("type") == "ask_choice"]


def _all_set_values(transcript: list, from_turn: int = 0) -> list:
    vals = []
    for e in transcript:
        if e["turn"] >= from_turn:
            vals += [v for _fid, v in _turn_sets(e)]
    return vals


def _turn_for_uindex(transcript: list, u_index: int) -> dict | None:
    """The transcript entry carrying the USER message produced under directive
    u_turn == u_index. A directive at u_turn=k is applied to the screen shown at
    turn k, and the user's reply becomes the `user` field of turn k+1."""
    idx = u_index + 1
    return transcript[idx] if 0 <= idx < len(transcript) else None


# ======================================================================
# per-field canonicalisation for value comparison
# ======================================================================

def _canon(schema: Schema, fid: str, value):
    """Canonicalise a value for equality comparison, using the same coercion the
    validator uses where possible (dates -> YYYY-MM-DD, phone -> digits, email ->
    lowercased, choices/booleans -> option value as-is, text -> alnum-normalised)."""
    f = schema.field(fid)
    if f is None:
        return _norm(value)
    if f.is_multi:
        vals = value if isinstance(value, list) else [value]
        return frozenset(_norm(v) for v in vals)
    if f.is_choice:
        return value            # option value (or bool) on both sides
    if f.type == "date":
        ok, c = coerce(str(value), f)
        return c if ok else _norm(value)
    if f.type == "phone":
        return re.sub(r"\D", "", str(value))
    if f.type == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return _norm(value)
    if f.type == "email":
        return str(value).strip().lower()
    return _norm(value)         # text / textarea


# ======================================================================
# utterance support — what values the session may legitimately draw from
# ======================================================================

# A user's utterances (what they actually typed, [system] events excluded), the
# persona sheet, and — for choices — the schema option labels/values, together form
# the "utterance support set". A set value is INVENTED when it traces to none of
# them. Choices/booleans reach the schema-option bridge (a stored ISO value like
# 'KR' is supported iff the user typed its label 'South Korea'); their persona
# mismatches are left to values_match_persona.

# _norm / date-span finding / the per-type support rules now live in validator.py — the
# probe, stress_invent, datagen and the validator's own provenance gate share ONE
# implementation (`validator.value_supported`); this module re-exports the names its
# consumers already import.


def _session_utterances(session) -> list[str]:
    """Raw user-typed messages (not '[system]' events) across the session."""
    return [e["user"] for e in session["transcript"]
            if e.get("user") and not e["user"].startswith("[system]")]


def _date_in_utterances(iso: str, f, utterances: list[str]) -> bool:
    """True iff some date-like span in an utterance coerces to the same ISO value."""
    return any(value_supported(f, iso, u) for u in utterances)


def _choice_supported(f, value, norm_utts: list[str]) -> bool:
    """A choice/boolean value is utterance-supported iff, for every selected option,
    that option's label or value string appears (normalised) in some utterance —
    the schema-option bridge from a stored value back to what the user typed."""
    vals = value if isinstance(value, list) else [value]
    for v in vals:
        strs = {_norm(v)}
        for ov, ol in f.options:
            if ov == v or _norm(ov) == _norm(v):
                strs |= {_norm(ov), _norm(ol)}
        strs = {s for s in strs if s}
        if not any(any(s in nu for s in strs) for nu in norm_utts):
            return False
    return True


def _value_supported(schema, fid, value, utterances, persona) -> bool:
    """Is `value` traceable to the user's utterances (or the persona)? Type-aware.
    Used to classify a persona-mismatch as sim_infidelity (supported) vs an
    invention / transcription corruption (unsupported)."""
    f = schema.field(fid)
    if fid in persona and _canon(schema, fid, value) == _canon(schema, fid, persona[fid]):
        return True
    norm_utts = [_norm(u) for u in utterances]
    if f is None or f.type == "number":
        # number is unchecked in validator.value_supported (semantic value space);
        # here it is still compared as text, as it always was.
        return any(_norm(value) in nu for nu in norm_utts)
    if f.is_choice:
        return _choice_supported(f, value, norm_utts)
    if f.type == "phone" and not re.sub(r"\D", "", str(value)):
        return False                       # no digits -> nothing to trace
    return any(value_supported(f, value, u) for u in utterances)


def _persona_supported(f, value, pv) -> bool:
    """The persona sheet is part of the support set: a value the SIM was told to say
    counts as supported even when the utterance rendered it differently."""
    if f.type == "email":
        return str(value).lower() == str(pv).lower()
    if f.type == "phone":
        return re.sub(r"\D", "", str(value)) in re.sub(r"\D", "", str(pv))
    if f.type == "date":
        ok, c = coerce(str(pv), f)
        return (c if ok else str(pv)) == str(value)
    return _norm(value) in _norm(pv)       # text / textarea


def _invention_check(schema, fid, value, utterances, persona):
    """True (supported) / False (invented) / None (unchecked) for one set value.
    email/phone/free-text/date are checked deterministically — via the SHARED
    `validator.value_supported`, the same test the validator's provenance gate runs
    per turn — plus the persona escape hatch. Choices, booleans, numbers and
    multi_selects are 'unchecked' (their value space is the schema, not free text —
    a persona mismatch there is caught by values_match_persona)."""
    f = schema.field(fid)
    if f is None or f.is_choice or f.type == "number":
        return None
    if f.type == "phone" and not re.sub(r"\D", "", str(value)):
        return None                        # no digits -> nothing to check
    if f.type in ("text", "textarea") and not _norm(value):
        return None                        # no comparable content
    pv = persona.get(fid)
    if pv is not None and _persona_supported(f, value, pv):
        return True
    return any(value_supported(f, value, u) for u in utterances)


# ======================================================================
# assertions — each returns {name, pass, detail}
# pass is True / False / "N/A" (N/A = not applicable to this scenario)
# ======================================================================

def _res(name, ok, detail=""):
    return {"name": name, "pass": ok, "detail": detail}


def a_opening_shape(schema, session):
    """1. turn-0 reply exists, non-empty, and turn-0 actions include ask_choice for
    the program field. Skipped for resume (it opens mid-form with a greeting)."""
    if session["scenario"] == "resume":
        return _res("opening_shape", "N/A", "resume opens mid-form")
    t = session["transcript"][0]
    prog_label = schema.field("program").label
    asked_prog = prog_label in _ask_choice_fields(t)
    ok = bool(t.get("assistant", "").strip()) and "ask_choice" in t["actions"] and asked_prog
    return _res("opening_shape", ok,
                f"assistant='{t.get('assistant','')[:40]}' actions={t['actions']} asked_program={asked_prog}")


def a_terminal_reached(schema, session):
    """2. session ended via CONFIRM_SUBMIT (not max_turns); the session's actions
    include a show_preview and a submit button somewhere."""
    tr = session["transcript"]
    last = tr[-1]
    ended_confirm = last.get("pending") == CONFIRM_SUBMIT
    hit_cap = session["turns"] >= session.get("max_turns", 24)
    saw_preview = any(_has_type(e, "show_preview") for e in tr)
    saw_submit = any(_has_button(e, "submit") for e in tr)
    ok = ended_confirm and not hit_cap and saw_preview and saw_submit
    return _res("terminal_reached", ok,
                f"end_confirm={ended_confirm} turns={session['turns']} preview={saw_preview} submit={saw_submit}")


def a_required_complete(schema, session):
    """3. every required field reachable given the final conditionals is filled."""
    final = session["filled"]
    missing = [f.field_id for f in schema.fields
               if f.required and is_active(f, final)
               and final.get(f.field_id) in (None, "", [])]
    return _res("required_complete", not missing, f"missing={missing}")


def a_values_match_persona(schema, session):
    """4. Every filled field present in the persona should match it canonically.
    A mismatch is now CLASSIFIED rather than always failing: if the filled value is
    still traceable to the user's utterances (or a schema option label the user
    typed), it is SIM INFIDELITY — the simulator (LLM-U) voiced a value off its
    persona sheet and the student extracted it faithfully; reported in detail, does
    NOT fail. Only mismatches with no utterance support — pure inventions or
    transcription corruptions (value differs from BOTH the persona and every
    utterance) — fail the assertion. Booleans have no free-text utterance form, so an
    off-persona boolean (e.g. has_work_experience) is unsupported and correctly
    fails here (no_invented_values leaves it 'unchecked')."""
    persona, final = session["persona"], session["filled"]
    utts = _session_utterances(session)
    fails, infidelity = [], []
    for fid, val in final.items():
        if fid not in persona:
            continue
        if _canon(schema, fid, persona[fid]) == _canon(schema, fid, val):
            continue
        rec = {"field": fid, "persona": persona[fid], "got": val}
        if _value_supported(schema, fid, val, utts, persona):
            infidelity.append(rec)
        else:
            fails.append(rec)
    detail = f"unsupported_mismatches={fails}"
    if infidelity:
        detail += f" sim_infidelity={infidelity}"
    return _res("values_match_persona", not fails, detail)


def a_no_invented_values(schema, session):
    """4b. No set_fields value may be invented: every value must trace to a user
    utterance (or the persona). Type-aware — email (lowercase substring), phone
    (digit run), free text (normalised substring), date (ISO equals a coerced date
    span). Choices/booleans/numbers/multi_selects are recorded 'unchecked:<field>'
    (their value space is the schema, not free text). Fails ONLY on clear
    inventions — e.g. the trap-1 email/phone the user never uttered."""
    utts = _session_utterances(session)
    persona = session.get("persona") or {}
    invented, unchecked = [], []
    for e in session["transcript"]:
        for fid, val in _turn_sets(e):
            verdict = _invention_check(schema, fid, val, utts, persona)
            if verdict is None:
                unchecked.append(fid)
            elif verdict is False:
                invented.append({"field": fid, "value": val})
    detail = f"invented={invented}"
    if unchecked:
        detail += f" unchecked={sorted(set(unchecked))}"
    return _res("no_invented_values", not invented, detail)


def a_conditional_consistency(schema, session):
    """5. conditional fields never set when their gate is off: gre_* need
    gre_taken==True; funding_type needs funding_interest==True; english_test_*
    need toefl_required==True."""
    final = session["filled"]
    def _filled(fid):
        return final.get(fid) not in (None, "", [])
    viol = []
    gates = {
        ("gre_taken", True): ["gre_verbal", "gre_quant", "gre_writing", "gre_date"],
        ("funding_interest", True): ["funding_type"],
        ("toefl_required", True): ["english_test_type", "english_test_score", "english_test_date"],
    }
    for (gate_fid, need), deps in gates.items():
        if final.get(gate_fid) is not need:
            for d in deps:
                if _filled(d):
                    viol.append(f"{d} set but {gate_fid}!={need}")
    return _res("conditional_consistency", not viol, f"violations={viol}")


def a_no_trap_bind(schema, session):
    """6. the trap story's city/year never land as a set value (trap scenario)."""
    if session["scenario"] != "trap":
        return _res("no_trap_bind", "N/A", "not a trap scenario")
    entry = _turn_for_uindex(session["transcript"], 2)  # trap directive at u_turn 2
    if entry is None:
        return _res("no_trap_bind", "N/A", "trap turn not reached")
    msg = entry.get("user", "")
    years = re.findall(r"\b(?:19|20)\d{2}\b", msg)
    # capitalised tokens are candidate city names (drop the leading sentence word)
    cities = re.findall(r"\b[A-Z][a-z]{2,}\b", msg)
    trap_tokens = set(years) | set(cities)
    later_vals = _all_set_values(session["transcript"], from_turn=entry["turn"])
    final_vals = list(session["filled"].values())
    bound = [t for t in trap_tokens
             if any(t in str(v) for v in later_vals) or any(t in str(v) for v in final_vals)]
    return _res("no_trap_bind", not bound, f"trap_tokens={sorted(trap_tokens)} bound={bound}")


def a_refusal_respected(schema, session):
    """7. at the refusal turn no value is invented for the refused field."""
    if session["scenario"] != "refusal":
        return _res("refusal_respected", "N/A", "not a refusal scenario")
    tr = session["transcript"]
    asked_entry = tr[3] if len(tr) > 3 else None   # screen shown at u_turn 3
    refusal_entry = _turn_for_uindex(tr, 3)         # the refusing reply
    if refusal_entry is None:
        return _res("refusal_respected", "N/A", "refusal turn not reached")
    refused = asked_entry.get("pending") if asked_entry else None
    set_here = dict(_turn_sets(refusal_entry))
    invented = refused in set_here
    filled_later = session["filled"].get(refused) not in (None, "", []) if refused else False
    return _res("refusal_respected", not invented,
                f"refused={refused} invented_at_turn={invented} filled_eventually={filled_later}")


def a_invalid_flow(schema, session):
    """8. a malformed value never lands in form_state; a clarify/re-ask follows;
    the field ends correctly filled (invalid scenario). N/A when the pending field
    is plain text — a malformed value only makes sense for date/phone/email/number."""
    if session["scenario"] != "invalid":
        return _res("invalid_flow", "N/A", "not an invalid scenario")
    tr = session["transcript"]
    asked_entry = tr[4] if len(tr) > 4 else None    # screen shown at u_turn 4
    bad_entry = _turn_for_uindex(tr, 4)             # the malformed reply
    if bad_entry is None or asked_entry is None:
        return _res("invalid_flow", "N/A", "invalid turn not reached")
    field = asked_entry.get("pending")
    f = schema.field(field) if field else None
    if f is None or f.type not in ("date", "phone", "email", "number"):
        return _res("invalid_flow", "N/A", f"pending field '{field}' not malformable")
    bad_val = bad_entry.get("user", "")
    # (a) malformed value must not be recorded on this turn
    set_here = dict(_turn_sets(bad_entry))
    not_set = field not in set_here
    # (b) still pending (a clarify / re-ask keeps the field open this turn)
    still_pending = bad_entry.get("pending") == field
    # (c) the field ends correctly filled
    final_val = session["filled"].get(field)
    ends_filled = final_val not in (None, "", [])
    ok = not_set and still_pending and ends_filled
    return _res("invalid_flow", ok,
                f"field={field} bad='{bad_val[:30]}' not_set={not_set} "
                f"still_pending={still_pending} ends_filled={ends_filled}")


def a_status_no_sets(schema, session):
    """9. the status-question turn records nothing (status scenario). Bonus detail:
    whether a preview fired (deterministic when the phrasing hits wants_review)."""
    if session["scenario"] != "status":
        return _res("status_no_sets", "N/A", "not a status scenario")
    entry = _turn_for_uindex(session["transcript"], 2)  # status directive at u_turn 2
    if entry is None:
        return _res("status_no_sets", "N/A", "status turn not reached")
    sets = _turn_sets(entry)
    preview = _has_type(entry, "show_preview")
    return _res("status_no_sets", not sets, f"sets={sets} show_preview={preview}")


def a_save_button(schema, session):
    """10. a save_draft button appears at the save turn (save scenario)."""
    if session["scenario"] != "save":
        return _res("save_button", "N/A", "not a save scenario")
    entry = _turn_for_uindex(session["transcript"], 3)  # save directive at u_turn 3
    if entry is None:
        return _res("save_button", "N/A", "save turn not reached")
    ok = _has_button(entry, "save_draft")
    return _res("save_button", ok, f"actions={entry['actions']}")


def a_premature_blocked(schema, session):
    """11. a submit intent while incomplete shows NO submit button that turn, and
    the session still completes later (premature scenario)."""
    if session["scenario"] != "premature":
        return _res("premature_blocked", "N/A", "not a premature scenario")
    entry = _turn_for_uindex(session["transcript"], 1)  # premature at u_turn 1
    if entry is None:
        return _res("premature_blocked", "N/A", "premature turn not reached")
    no_submit = not _has_button(entry, "submit")
    completed = session["transcript"][-1].get("pending") == CONFIRM_SUBMIT
    return _res("premature_blocked", no_submit and completed,
                f"no_submit_that_turn={no_submit} completed_later={completed}")


ASSERTIONS = [a_opening_shape, a_terminal_reached, a_required_complete,
              a_values_match_persona, a_no_invented_values, a_conditional_consistency,
              a_no_trap_bind, a_refusal_respected, a_invalid_flow, a_status_no_sets,
              a_save_button, a_premature_blocked]


def run_assertions(schema, session) -> list[dict]:
    return [fn(schema, session) for fn in ASSERTIONS]


# ======================================================================
# P1..P12 coverage matrix (product requirements -> assertions)
# ======================================================================

def _by_name(results_by_session, name):
    """Flatten one assertion's result across all sessions -> list of pass values."""
    return [r["pass"] for res in results_by_session for r in res if r["name"] == name]


def _agg(pass_values):
    """Aggregate a list of True/False/'N/A' -> True (all real ones pass) / False
    (any real one fails) / 'N/A' (no real evidence)."""
    real = [p for p in pass_values if p != "N/A"]
    if not real:
        return "N/A"
    return all(bool(p) for p in real)


def _field_match_pass(schema, sessions, field_id, scenario=None):
    """True iff every session (optionally filtered to `scenario`) that filled
    `field_id` has it matching the persona canonically OR utterance-supported
    (sim infidelity — the U said a different value; the extraction was faithful).
    Takes schema explicitly — sessions reloaded from sessions.jsonl (resume path)
    have `_schema` stripped."""
    seen = False
    for s in sessions:
        if scenario and s["scenario"] != scenario:
            continue
        final, persona = s["filled"], s["persona"]
        if field_id in final and field_id in persona:
            seen = True
            if _canon(schema, field_id, persona[field_id]) \
               != _canon(schema, field_id, final[field_id]) \
               and not _value_supported(schema, field_id, final[field_id],
                                        _session_utterances(s), persona):
                return False
    return True if seen else "N/A"


def build_p_matrix(schema, sessions, results_by_session) -> dict:
    """Hard-coded product-requirement -> coverage mapping (M3b spec).

    P1  opening turn shape (greeting + first ask)
    P2  typed (non-button) answers still extract correctly
    P3  persona values captured accurately
    P4  address captured accurately
    P5  (out of v2 schema scope)  -- groups/repeated entries
    P6  conditional-field gating respected
    P7  (out of v2 schema scope)  -- file uploads
    P8  status / progress questions answered without corrupting state
    P9  save-draft + resume-mid-form
    P10 review/preview before submit
    P11 submit gating (blocked while incomplete; offered when complete)
    P12 off-topic / adversarial robustness (trap, refusal, invalid, chitchat, deflect)
    """
    # convenience: pass values per assertion across sessions
    opening = _by_name(results_by_session, "opening_shape")
    values = _by_name(results_by_session, "values_match_persona")
    invented = _by_name(results_by_session, "no_invented_values")
    cond = _by_name(results_by_session, "conditional_consistency")
    terminal = _by_name(results_by_session, "terminal_reached")
    status = _by_name(results_by_session, "status_no_sets")
    save = _by_name(results_by_session, "save_button")
    premature = _by_name(results_by_session, "premature_blocked")
    trap = _by_name(results_by_session, "no_trap_bind")
    refusal = _by_name(results_by_session, "refusal_respected")
    invalid = _by_name(results_by_session, "invalid_flow")

    # typed scenario: extraction accuracy on the typed-answer sessions (values +
    # no-invention, both scoped to the typed sessions)
    typed_vals = [p for s, res in zip(sessions, results_by_session)
                  if s["scenario"] == "typed"
                  for name in ("values_match_persona", "no_invented_values")
                  for p in [next((r["pass"] for r in res if r["name"] == name), "N/A")]]
    # resume scenario: does it reach terminal after picking up mid-form
    resume_term = [p for s, res in zip(sessions, results_by_session)
                   if s["scenario"] == "resume"
                   for p in [next((r["pass"] for r in res if r["name"] == "terminal_reached"), "N/A")]]

    return {
        "P1": {"covered_by": ["opening_shape"], "pass": _agg(opening)},
        "P2": {"covered_by": ["typed scenario", "values_match_persona", "no_invented_values"],
               "pass": _agg(typed_vals)},
        "P3": {"covered_by": ["values_match_persona", "no_invented_values"],
               "pass": _agg(values + invented)},
        # P4 stays address-scoped: an invented email/phone is a P3 signal, not an
        # entity-group one — session-level inventions live on P3 only.
        "P4": {"covered_by": ["values_match_persona (mailing_address)"],
               "pass": _field_match_pass(schema, sessions, "mailing_address")},
        "P5": {"covered_by": [], "pass": "N/A (out of v2 schema scope)"},
        "P6": {"covered_by": ["conditional_consistency"], "pass": _agg(cond)},
        "P7": {"covered_by": [], "pass": "N/A (out of v2 schema scope)"},
        "P8": {"covered_by": ["status scenario / status_no_sets"], "pass": _agg(status)},
        "P9": {"covered_by": ["save scenario / save_button", "resume scenario / terminal_reached"],
               "pass": _agg(save + resume_term)},
        "P10": {"covered_by": ["terminal_reached (show_preview)"], "pass": _agg(terminal)},
        "P11": {"covered_by": ["terminal_reached (submit)", "premature scenario / premature_blocked"],
                "pass": _agg(terminal + premature)},
        "P12": {"covered_by": ["trap/no_trap_bind", "refusal/refusal_respected",
                               "invalid/invalid_flow", "chitchat + deflect scenarios"],
                "pass": _agg(trap + refusal + invalid)},
    }


# ======================================================================
# session driver
# ======================================================================

def _build_resume_kwargs(schema, seed):
    """Deterministically preload the resume scenario's initial_state / pending /
    history from the SAME persona run_session will regenerate from `seed`."""
    rng = random.Random(seed)
    persona = personas.gen_persona(schema, rng)
    initial_state = {fid: persona[fid] for fid in RESUME_PREFILL if fid in persona}
    tmp = TurnState(schema=schema, form_state=dict(initial_state))
    q = queue(tmp)
    pending = q[0].field_id if q else None
    pf = schema.field(pending) if pending else None
    greeting = ("Welcome back! Let's pick up where you left off."
                + (f" Could you tell me your {pf.label}?" if pf else ""))
    history = [{"role": "assistant", "content": greeting}]
    return {"initial_state": initial_state, "initial_pending": pending,
            "initial_history": history}


def run_probe_session(agent, respond_lm, student_lm, schema, scenario, seed, max_turns=24):
    kwargs = {}
    if scenario == "resume":
        kwargs = _build_resume_kwargs(schema, seed)
    session = run_session(agent, respond_lm, schema, scenario, seed, max_turns=max_turns,
                          extra_lms=[student_lm], **kwargs)
    session["max_turns"] = max_turns
    session["_schema"] = schema   # stashed for _field_match_pass; stripped before write
    return session


# ======================================================================
# output
# ======================================================================

def _latency_stats(latencies: list[float]) -> dict:
    if not latencies:
        return {"p50": None, "p95": None, "max": None, "n": 0}
    s = sorted(latencies)
    def pct(p):
        return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]
    return {"p50": round(pct(0.50), 4), "p95": round(pct(0.95), 4),
            "max": round(max(s), 4), "n": len(s)}


def _session_latencies(session) -> list[float]:
    return [e.get("latency", 0.0) for e in session["transcript"]]


def _transcript_md(session) -> str:
    """Plain-text transcript reconstruction (parallels transcript_html.py)."""
    lines = [f"# {session['scenario']} seed={session['seed']} "
             f"style={session['style']} turns={session['turns']}", ""]
    for e in session["transcript"]:
        if e.get("user"):
            lines.append(f"**User:** {e['user']}")
        acts = ", ".join(e["actions"]) or "-"
        lines.append(f"**Assistant** (t{e['turn']}, actions: {acts}, "
                     f"pending: {e.get('pending')}): {e.get('assistant','')}")
        lines.append("")
    lines.append("## final form_state")
    lines.append("```json")
    lines.append(json.dumps(session["filled"], indent=2, ensure_ascii=False))
    lines.append("```")
    return "\n".join(lines)


def _print_summary(sessions, results_by_session, p_matrix, latency):
    print("\n=== scenario x seed grid (pass/total assertions, real only) ===")
    print(f"{'scenario':12} {'seed':>4}  {'pass/real':>10}  fails")
    for s, res in zip(sessions, results_by_session):
        real = [r for r in res if r["pass"] != "N/A"]
        npass = sum(1 for r in real if r["pass"])
        fails = [r["name"] for r in real if not r["pass"]]
        print(f"{s['scenario']:12} {s['seed']:>4}  {npass:>4}/{len(real):<5}  {', '.join(fails) or '-'}")
    print(f"\nlatency (per-turn, s): p50={latency['p50']} p95={latency['p95']} "
          f"max={latency['max']} n={latency['n']}")
    print("\n=== P-coverage matrix ===")
    for p in sorted(p_matrix, key=lambda k: int(k[1:])):
        print(f"  {p:4} {str(p_matrix[p]['pass']):>28}  <- {', '.join(p_matrix[p]['covered_by']) or '(none)'}")


def write_outputs(out: Path, sessions, results_by_session, p_matrix, run_name):
    out.mkdir(parents=True, exist_ok=True)
    all_lat = [l for s in sessions for l in _session_latencies(s)]
    latency = _latency_stats(all_lat)

    report = {
        "run": run_name,
        "scenarios": sorted({s["scenario"] for s in sessions}),
        "n_sessions": len(sessions),
        "latency": latency,
        "sessions": [],
        "p_matrix": p_matrix,
    }
    with open(out / "sessions.jsonl", "w") as jf:
        for s, res in zip(sessions, results_by_session):
            report["sessions"].append({
                "scenario": s["scenario"], "seed": s["seed"], "style": s["style"],
                "turns": s["turns"], "assertions": res,
                "latency": _latency_stats(_session_latencies(s)),
            })
            dump = {k: v for k, v in s.items() if k != "_schema"}
            jf.write(json.dumps(dump, default=str) + "\n")
            # transcript.md for any FAILING session
            if any(r["pass"] is False for r in res):
                (out / f"transcript-{s['seed']}-{s['scenario']}.md").write_text(_transcript_md(s))

    (out / "report.json").write_text(json.dumps(report, indent=2, default=str))
    return latency


# ======================================================================
# CLI
# ======================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8100, help="student MLX server port")
    ap.add_argument("--student-model", default=None, help="student model path/name (sent in body)")
    ap.add_argument("--scenarios", default="all", help="comma-list or 'all'")
    ap.add_argument("--seeds", type=int, default=2, help="run seeds 1..N per scenario")
    ap.add_argument("--run", default="m3b_hybrid")
    ap.add_argument("--out", default=None, help="output dir (default probe_runs/<run>/)")
    ap.add_argument("--max-turns", type=int, default=24)
    ap.add_argument("--selftest", action="store_true", help="offline self-test, no network")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    import dspy
    from .program import FormAssistant, assign_lms
    from .student_lm import StudentLM
    from .openrouter_lm import OpenRouterLM

    schema = load_schema()
    scenarios = list(SCENARIOS) if args.scenarios == "all" else args.scenarios.split(",")
    unknown = [s for s in scenarios if s not in SCENARIOS]
    if unknown:
        ap.error(f"unknown scenarios: {unknown}")

    out = Path(args.out) if args.out else PROBE_DIR / args.run
    out.mkdir(parents=True, exist_ok=True)

    # crash safety: each finished session is appended to sessions.jsonl at once,
    # and a re-run skips (scenario, seed) pairs already on disk — an interruption
    # costs one session, not the sweep. (datagen pilot1 lesson.)
    sessions, results_by_session, done = [], [], set()
    part = out / "sessions.jsonl"
    if part.exists():
        for line in open(part):
            s = json.loads(line)
            sessions.append(s)
            results_by_session.append(run_assertions(schema, s))
            done.add((s["scenario"], s["seed"]))
        if done:
            print(f"[probe] resuming: {len(done)} session(s) already on disk, skipping them", flush=True)

    for scenario in scenarios:
        for seed in range(1, args.seeds + 1):
            if (scenario, seed) in done:
                continue
            # fresh, demo-free program per session; per-predictor hybrid wiring
            student_lm = StudentLM(model=args.student_model or "student", port=args.port)
            respond_lm = OpenRouterLM()
            dspy.configure(lm=respond_lm)
            program = FormAssistant()
            assign_lms(program, extract_lm=student_lm, respond_lm=respond_lm)
            print(f"[probe] scenario={scenario} seed={seed} ...", flush=True)
            try:
                s = run_probe_session(program, respond_lm, student_lm, schema,
                                      scenario, seed, max_turns=args.max_turns)
            except Exception as e:
                print(f"  !! session failed: {type(e).__name__}: {str(e)[:160]}", flush=True)
                continue
            sessions.append(s)
            results_by_session.append(run_assertions(schema, s))
            with open(part, "a") as jf:   # persist immediately (crash safety)
                jf.write(json.dumps({k: v for k, v in s.items() if k != "_schema"},
                                    default=str) + "\n")

    if not sessions:
        print("no sessions completed", file=sys.stderr)
        sys.exit(1)

    p_matrix = build_p_matrix(schema, sessions, results_by_session)
    latency = write_outputs(out, sessions, results_by_session, p_matrix, args.run)
    _print_summary(sessions, results_by_session, p_matrix, latency)
    print(f"\nwritten to {out}/")


# ======================================================================
# offline self-test
# ======================================================================

def selftest():
    schema = load_schema()

    # 1) new DIRECTIVES / SCENARIOS keys exist
    for k in ("typed_answer", "status", "trap", "refusal", "invalid_value"):
        assert k in DIRECTIVES, f"missing directive {k}"
    for k in ("typed", "status", "trap", "refusal", "invalid", "resume"):
        assert k in SCENARIOS, f"missing scenario {k}"

    # ---- synthetic transcript builders -------------------------------
    def entry(turn, user="", assistant="ok", actions=None, pending=None):
        acts = actions or []
        return {"turn": turn, "user": user, "assistant": assistant,
                "actions": [a["type"] for a in acts], "action_details": acts,
                "pending": pending, "pending_held": False, "latency": 0.01}

    def set_action(*pairs):
        return {"type": "set_fields", "fields": [{"field_id": f, "value": v} for f, v in pairs]}

    def ask(label):
        return {"type": "ask_choice", "question": f"{label}?", "options": []}

    def button(kind):
        return {"type": "show_button", "button": kind}

    preview = {"type": "show_preview"}

    def session(scenario, transcript, filled, persona=None, turns=None, style="terse"):
        return {"scenario": scenario, "seed": 1, "style": style,
                "turns": turns if turns is not None else len(transcript),
                "persona": persona or {}, "filled": filled,
                "transcript": transcript, "records": [], "max_turns": 24,
                "_schema": schema}

    prog_label = schema.field("program").label

    # ---- 1. opening_shape: pass + fail + resume N/A ------------------
    p = session("straight", [entry(0, assistant="Hi!", actions=[ask(prog_label)], pending="program")], {})
    assert a_opening_shape(schema, p)["pass"] is True
    f = session("straight", [entry(0, assistant="", actions=[], pending=None)], {})
    assert a_opening_shape(schema, f)["pass"] is False
    r = session("resume", [entry(0, assistant="hi", actions=[], pending="dob")], {})
    assert a_opening_shape(schema, r)["pass"] == "N/A"

    # ---- 2. terminal_reached: pass + fail ---------------------------
    tr = [entry(0, actions=[ask(prog_label)], pending="program"),
          entry(1, actions=[preview, button("submit")], pending=CONFIRM_SUBMIT)]
    assert a_terminal_reached(schema, session("straight", tr, {}, turns=2))["pass"] is True
    tr2 = [entry(0, actions=[ask(prog_label)], pending="program")]  # never terminal
    assert a_terminal_reached(schema, session("straight", tr2, {}, turns=1))["pass"] is False

    # ---- 3. required_complete: pass + fail --------------------------
    full = {f.field_id: (True if f.type == "boolean" else "x")
            for f in schema.fields if f.required and is_active(f, {})}
    # is_active depends on values; recompute after seeding booleans (prior_application etc.)
    full = {}
    for f in schema.fields:
        if f.required and is_active(f, full):
            full[f.field_id] = True if f.type == "boolean" else "x"
    assert a_required_complete(schema, session("straight", [], full))["pass"] is True
    partial = dict(full); partial.pop("email", None)
    assert a_required_complete(schema, session("straight", [], partial))["pass"] is False

    # ---- 4. values_match_persona: pass + fail -----------------------
    persona = {"full_name": "Jane Doe", "email": "Jane@Example.com", "program": "cs",
               "dob": "1995-03-02", "phone": "(415) 555-0132"}
    match = {"full_name": "jane  doe", "email": "jane@example.com", "program": "cs",
             "dob": "March 2, 1995", "phone": "415-555-0132"}
    assert a_values_match_persona(schema, session("straight", [], match, persona))["pass"] is True
    mm = dict(match); mm["email"] = "someone@else.com"
    assert a_values_match_persona(schema, session("straight", [], mm, persona))["pass"] is False

    # ---- 4b. no_invented_values: pass + fail (hallucinated email) + choice unchecked
    niv_ok = [entry(0, actions=[ask(prog_label)], pending="program"),
              entry(1, user="my email is joe@work.com, phone (415) 555-2020, born 03/24/1996",
                    actions=[set_action(("email", "joe@work.com"), ("phone", "(415) 555-2020"),
                                        ("dob", "1996-03-24"))], pending="full_name")]
    assert a_no_invented_values(schema, session("straight", niv_ok, {"email": "joe@work.com"}))["pass"] is True
    niv_bad = [entry(0), entry(1, user="I moved to Austin in 2019, great city.",
                              actions=[set_action(("email", "ghost@nowhere.com"))], pending="dob")]
    rb = a_no_invented_values(schema, session("trap", niv_bad, {"email": "ghost@nowhere.com"}))
    assert rb["pass"] is False and "ghost@nowhere.com" in rb["detail"], rb
    niv_choice = [entry(0), entry(1, user="anything at all",
                                  actions=[set_action(("program", "cs"))], pending="dob")]
    rc = a_no_invented_values(schema, session("straight", niv_choice, {"program": "cs"}))
    assert rc["pass"] is True and "program" in rc["detail"], rc   # choice -> unchecked, never invented

    # ---- 4c. values_match_persona classification: sim_infidelity vs unsupported
    # off-persona choice value the user DID utter (its label) -> sim_infidelity (pass)
    inf_tr = [entry(0), entry(1, user="I've been living in South Korea for years now",
                              actions=[set_action(("country_citizenship", "KR"))], pending="dob")]
    ri = a_values_match_persona(schema, session("trap", inf_tr,
                                                {"country_citizenship": "KR"}, {"country_citizenship": "BR"}))
    assert ri["pass"] is True and "sim_infidelity" in ri["detail"], ri
    # off-persona boolean with no utterance support -> unsupported mismatch (fail)
    uns_tr = [entry(0), entry(1, user="let's keep going, next question please",
                              actions=[set_action(("has_work_experience", True))], pending="dob")]
    ru = a_values_match_persona(schema, session("refusal", uns_tr,
                                                {"has_work_experience": True}, {"has_work_experience": False}))
    assert ru["pass"] is False and "unsupported" in ru["detail"], ru

    # ---- 5. conditional_consistency: pass + fail --------------------
    ok_cond = {"funding_interest": False}
    assert a_conditional_consistency(schema, session("straight", [], ok_cond))["pass"] is True
    bad_cond = {"funding_interest": False, "funding_type": ["fellowship"]}
    assert a_conditional_consistency(schema, session("straight", [], bad_cond))["pass"] is False
    bad_gre = {"gre_taken": False, "gre_verbal": 160}
    assert a_conditional_consistency(schema, session("straight", [], bad_gre))["pass"] is False

    # ---- 6. no_trap_bind: pass + fail (trap at u_turn 2 -> tr idx 3) -
    trap_tr = [entry(0), entry(1), entry(2),
               entry(3, user="I moved to Austin in 2019, loved it.",
                     actions=[], pending="email")]
    assert a_no_trap_bind(schema, session("trap", trap_tr, {}))["pass"] is True
    trap_bad = [entry(0), entry(1), entry(2),
                entry(3, user="I moved to Austin in 2019.",
                      actions=[set_action(("mailing_address", "12 Austin Rd"))], pending="email")]
    assert a_no_trap_bind(schema, session("trap", trap_bad, {"mailing_address": "12 Austin Rd"}))["pass"] is False
    assert a_no_trap_bind(schema, session("straight", [], {}))["pass"] == "N/A"

    # ---- 7. refusal_respected: pass + fail (asked at idx3, reply idx4) -
    ref_ok = [entry(0), entry(1), entry(2), entry(3, assistant="phone?", pending="phone"),
              entry(4, user="rather not say", actions=[], pending="phone")]
    assert a_refusal_respected(schema, session("refusal", ref_ok, {}))["pass"] is True
    ref_bad = [entry(0), entry(1), entry(2), entry(3, assistant="phone?", pending="phone"),
               entry(4, user="rather not say",
                     actions=[set_action(("phone", "(000) 000-0000"))], pending="phone")]
    assert a_refusal_respected(schema, session("refusal", ref_bad, {}))["pass"] is False

    # ---- 8. invalid_flow: pass + fail + text N/A --------------------
    inv_ok = [entry(0), entry(1), entry(2), entry(3),
              entry(4, assistant="dob?", pending="dob"),
              entry(5, user="Feb 30, 1995", actions=[], pending="dob")]
    assert a_invalid_flow(schema, session("invalid", inv_ok, {"dob": "1995-02-28"}))["pass"] is True
    inv_bad = [entry(0), entry(1), entry(2), entry(3),
               entry(4, assistant="dob?", pending="dob"),
               entry(5, user="Feb 30, 1995",
                     actions=[set_action(("dob", "1995-02-30"))], pending=None)]
    assert a_invalid_flow(schema, session("invalid", inv_bad, {}))["pass"] is False
    inv_text = [entry(0), entry(1), entry(2), entry(3),
                entry(4, assistant="name?", pending="full_name"),
                entry(5, user="whatever", pending="full_name")]
    assert a_invalid_flow(schema, session("invalid", inv_text, {}))["pass"] == "N/A"

    # ---- 9. status_no_sets: pass + fail (status at u_turn 2 -> idx3) -
    st_ok = [entry(0), entry(1), entry(2),
             entry(3, user="how much is left?", actions=[preview], pending="email")]
    assert a_status_no_sets(schema, session("status", st_ok, {}))["pass"] is True
    st_bad = [entry(0), entry(1), entry(2),
              entry(3, user="how much is left?",
                    actions=[set_action(("email", "x@y.com"))], pending="email")]
    assert a_status_no_sets(schema, session("status", st_bad, {}))["pass"] is False

    # ---- 10. save_button: pass + fail (save at u_turn 3 -> idx4) -----
    sv_ok = [entry(0), entry(1), entry(2), entry(3),
             entry(4, user="save please", actions=[button("save_draft")], pending="email")]
    assert a_save_button(schema, session("save", sv_ok, {}))["pass"] is True
    sv_bad = [entry(0), entry(1), entry(2), entry(3),
              entry(4, user="save please", actions=[], pending="email")]
    assert a_save_button(schema, session("save", sv_bad, {}))["pass"] is False

    # ---- 11. premature_blocked: pass + fail (premature at u_turn 1 -> idx2)
    pm_ok = [entry(0), entry(1),
             entry(2, user="submit now!", actions=[button("save_draft")], pending="email"),
             entry(3, actions=[preview, button("submit")], pending=CONFIRM_SUBMIT)]
    assert a_premature_blocked(schema, session("premature", pm_ok, {}, turns=4))["pass"] is True
    pm_bad = [entry(0), entry(1),
              entry(2, user="submit now!", actions=[button("submit")], pending=CONFIRM_SUBMIT)]
    assert a_premature_blocked(schema, session("premature", pm_bad, {}, turns=3))["pass"] is False

    # ---- P-matrix builds over a mixed batch -------------------------
    batch = [session("straight", tr, full, persona, turns=2),
             session("typed", tr, match, persona, turns=2),
             session("trap", trap_tr, {}),
             session("resume", tr, full, persona, turns=2),
             session("save", sv_ok, {})]
    res = [run_assertions(schema, s) for s in batch]
    pm = build_p_matrix(schema, batch, res)
    assert sorted(pm, key=lambda k: int(k[1:])) == [f"P{i}" for i in range(1, 13)], pm
    assert pm["P5"]["pass"] == "N/A (out of v2 schema scope)"
    assert pm["P7"]["pass"] == "N/A (out of v2 schema scope)"

    # ---- run_session plumbing offline (fake agent + LMs, no network) -
    _selftest_run_session_plumbing(schema)

    print("selftest: all assertions passed (12 assertions x pass/fail branches incl. "
          "no_invented_values + sim_infidelity classification, P-matrix build, "
          "run_session plumbing)")


def _selftest_run_session_plumbing(schema):
    """Drive sim.run_session with a fake agent + fake LMs (no network): verifies
    initial_state preload, extra_lms record/cost slicing, and per-turn latency."""
    import types
    from .state import Pending

    class FakeLM:
        def __init__(self):
            self.history = []

    respond_lm, student_lm = FakeLM(), FakeLM()

    class FakeAgent:
        def __call__(self, state, user_message, history):
            # one extractor call (student) + one responder call (respond_lm)
            student_lm.history.append({"messages": [{"role": "system", "content": "Extract ..."}],
                                       "outputs": ["[]"], "cost": 0.0})
            respond_lm.history.append({"messages": [{"role": "system", "content": "conversational reply"}],
                                       "outputs": ["Hello!"], "cost": 0.002})
            state.pending = Pending(CONFIRM_SUBMIT)   # terminate after this turn
            return types.SimpleNamespace(
                text="Hello!",
                actions=[{"type": "ask_choice", "question": "Program of Interest?", "options": []}])

    s = run_session(FakeAgent(), respond_lm, schema, "resume", seed=1, max_turns=5,
                    initial_state={"program": "cs"}, initial_pending="start_term",
                    initial_history=[{"role": "assistant", "content": "Welcome back!"}],
                    extra_lms=[student_lm])
    assert s["turns"] == 1, s["turns"]
    mods = {r["module"] for r in s["records"]}
    assert mods == {"extractor", "responder"}, mods
    assert len(s["records"]) == 2, len(s["records"])
    assert "program" in s["filled"], s["filled"]                     # initial_state preloaded
    e0 = s["transcript"][0]
    assert "action_details" in e0 and "latency" in e0, e0
    assert e0["pending"] == CONFIRM_SUBMIT, e0
    assert s["teacher_cost"] >= 0.0


if __name__ == "__main__":
    main()
