"""M2 sim — in-process LLM U (claude -p) <-> FormAssistant.forward() (teacher).

Each turn the teacher runs the v2 DSPy program in-process, so we capture every
extractor/responder (messages, completion) pair from lm.history — that IS the
SFT training data (doc-18 §4/§5). LLM U is a lightweight claude -p call driven
by a programmatic persona (persona.py), a behavioral style, and a per-turn
scenario directive (the turn-type quotas).

Run:  tuning/v2/.venv/bin/python -m tuning.v2.sim --sessions 3 --scenario straight
Outputs (gitignored): tuning/v2/sims/<run>/train.jsonl + transcript-*.json
"""
from __future__ import annotations
import argparse
import json
import os
import random
import re
import subprocess
import time
from pathlib import Path

import dspy
from .claude_lm import ClaudeLM, CLAUDE_BIN
from .schema import load_schema, Schema
from .state import TurnState, Pending, CONFIRM_SUBMIT
from .context import _display
from .program import FormAssistant
from . import persona as personas

SIM_USER_MODEL = os.getenv("V2_SIM_USER_MODEL", "sonnet")
SIM_DIR = Path(__file__).resolve().parent / "sims"

STYLE_DESC = {
    "terse": "answers in as few words as possible",
    "chatty": "friendly and talkative, adds little asides",
    "unsure": "hesitant, sometimes asks for clarification",
    "impatient": "wants to finish fast, may push to skip ahead",
    "polite": "warm and courteous, full sentences",
}

DIRECTIVES = {
    "answer": "Answer the assistant's current question using YOUR information. If buttons are shown you may click the matching one (select) or just type your answer.",
    "deflect": "Do NOT answer the current question yet — instead ask the assistant about a DIFFERENT part of the application (e.g. what the options are for some field).",
    "chitchat": "Do NOT answer — make a brief, friendly OFF-TOPIC remark (small talk), nothing about the form.",
    "correct": "Answer the current question, but ALSO mention that one value you gave earlier was wrong and give the corrected value.",
    "bulk": "Volunteer SEVERAL pieces of your information at once in a single message, not just the one asked.",
    "save": "Say you'd like to save your progress and come back to finish later.",
    "premature_submit": "Insist on submitting the whole application right now.",
    # --- M3b probe additions (additive; do not change the above) ---
    "typed_answer": "Answer the assistant's CURRENT question by TYPING the option as free text — do NOT click any on-screen button. Use natural casing and your own words (e.g. type \"computer science\" rather than the exact button label).",
    "status": "Do NOT answer the current question. Instead, ask the assistant how much of the form is left — what still remains to be filled in.",
    "trap": "Do NOT answer the current question. Instead, tell a SHORT personal story that happens to mention a city and a year (for example, that you moved to Austin in 2019). This is just background chatter about your life — it is NOT information for the form and must not be recorded.",
    "refusal": "Politely DECLINE to provide the specific piece of information the assistant is currently asking for. Do not give the value or any substitute — just say you'd rather not share that right now.",
    "invalid_value": "Answer the current question, but give a PLAUSIBLE BUT MALFORMED value for its type — an impossible date, a phone number with too few digits, or an email missing its '@'. Present it as if it were your real value. (If the current field is plain text, just answer normally.)",
}

# A scenario maps (user-turn index) -> directive key. Default is "answer".
SCENARIOS = {
    "straight":  {},
    "bulk":      {0: "bulk"},
    "deflect":   {1: "deflect"},
    "chitchat":  {2: "chitchat"},
    "correct":   {2: "correct"},
    "save":      {3: "save"},
    "premature": {1: "premature_submit"},
    # --- M3b probe additions ---
    "typed":     {1: "typed_answer"},
    "status":    {2: "status"},
    "trap":      {2: "trap"},
    "refusal":   {3: "refusal"},
    # {4: invalid_value}; the following (u_turn 5) defaults to "answer", which the
    # U model uses to supply the corrected value naturally.
    "invalid":   {5: "invalid_value"},   # turn 5 asks dob (coercible) — turn 4 is full_name (text, nothing to reject)
    # empty schedule (all "answer"); the probe runner preloads an initial state so
    # the session resumes mid-form and continues to completion.
    "resume":    {},
}


def claude_p(system: str, user: str, timeout: int = 120) -> tuple[str, float]:
    cmd = [CLAUDE_BIN, "-p", user, "--model", SIM_USER_MODEL,
           "--output-format", "json", "--system-prompt", system]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"LLM U claude failed rc={proc.returncode}: {proc.stderr[:300]}")
    data = json.loads(proc.stdout)
    return data.get("result", ""), float(data.get("total_cost_usd") or 0.0)


def _parse_action(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {"action": "message", "text": raw.strip()}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"action": "message", "text": raw.strip()}


def render_persona(schema: Schema, persona: dict) -> str:
    return "\n".join(f"  {f.label}: {_display(schema, f.field_id, persona[f.field_id])}"
                     for f in schema.fields if f.field_id in persona)


# Human labels for the composer's action buttons (show_button). These are UI
# controls, NOT form-field options — clicking one is a `User clicked` event.
BUTTON_LABELS = {"save_draft": "Save Draft", "submit": "Submit"}


def shown_button_labels(pred) -> set[str]:
    """Lower-cased labels of the action BUTTONS on the current screen (save/submit),
    so the message builder can emit `User clicked` for them (vs `selected option`)."""
    return {BUTTON_LABELS.get(a["button"], a["button"]).lower()
            for a in pred.actions if a["type"] == "show_button"}


def render_screen(pred) -> str:
    scr = f"Assistant said:\n{pred.text}"
    for a in pred.actions:
        if a["type"] == "ask_choice":
            scr += "\n\nOption buttons on screen: " + ", ".join(f'"{o["label"]}"' for o in a["options"])
        elif a["type"] == "show_button":
            label = BUTTON_LABELS.get(a["button"], a["button"])
            scr += f'\n\nAction button on screen: "{label}" (a UI control, not a form option)'
    return scr


U_SYS = """You are role-playing a person filling out an online application by chatting with an assistant. Stay in character; never break role.

YOUR information (use it to answer; phrase naturally in your own words, don't dump raw values):
{persona}

USE EXACTLY the values from YOUR information above — emails, phone numbers, dates, addresses, names, and countries must be reproduced with their real value (you may reformat a date, but never change the value itself); never invent, paraphrase into a different value, or substitute a new one, and any asides or stories you tell must not contradict these facts.

Your style: {style} — {style_desc}.

You'll see the assistant's latest message and any on-screen buttons. Respond in ONE short turn.
This turn specifically: {directive}

Reply with ONLY a JSON object, one of:
{{"action": "message", "text": "<what you type>"}}
{{"action": "select", "label": "<exact on-screen button label>"}}
{{"action": "stop"}}   (only if the application is submitted/finished)"""


def llm_u(schema, persona, style, screen, directive) -> tuple[dict, float]:
    sys = U_SYS.format(persona=render_persona(schema, persona), style=style,
                       style_desc=STYLE_DESC[style], directive=DIRECTIVES[directive])
    text, cost = claude_p(sys, screen)
    return _parse_action(text), cost


def _module_of(call: dict) -> str:
    sysmsg = call["messages"][0]["content"] if call.get("messages") else ""
    return "responder" if "conversational reply" in sysmsg else "extractor"


def run_session(agent, lm, schema, scenario: str, seed: int, max_turns: int = 24,
                initial_state: dict | None = None, initial_pending: str | None = None,
                initial_history: list | None = None, extra_lms: list | None = None) -> dict:
    """LLM-U-driven session loop.

    initial_state / initial_pending / initial_history preload form_state, pending,
    and conversation history (used by the "resume" scenario). Backward compatible:
    omit them for a fresh session.

    extra_lms: additional LMs whose history is ALSO sliced per turn for records +
    cost (the hybrid probe passes [student_lm] while lm is the responder
    OpenRouterLM, so the student's extractor calls are captured too). When omitted,
    behaviour is identical to the single-lm original.

    Per-turn wall-clock latency: the agent() call is wrapped with time.monotonic and
    the elapsed seconds stored on each transcript entry ("latency"). This is
    per-TURN (one extract + one respond call), not per-extract-call — StudentLM does
    not record per-call timing in its history, so per-turn agent latency is used, as
    the M3b spec permits.
    """
    rng = random.Random(seed)
    persona = personas.gen_persona(schema, rng)
    style = personas.gen_style(rng)
    policy = SCENARIOS[scenario]
    state = TurnState(schema=schema, form_state=dict(initial_state or {}))
    if initial_pending:
        state.pending = Pending(initial_pending)
    history: list[dict] = list(initial_history or [])
    records: list[dict] = []
    transcript: list[dict] = []
    user_msg = ""          # turn 0 kickoff: assistant greets
    u_turn = 0
    teacher_cost = u_cost = 0.0
    sliced_lms = [lm] + list(extra_lms or [])

    for turn in range(max_turns):
        prevs = [len(x.history) for x in sliced_lms]
        t0 = time.monotonic()
        pred = agent(state=state, user_message=user_msg, history=history)
        latency = time.monotonic() - t0
        for x, prev in zip(sliced_lms, prevs):
            for call in x.history[prev:]:
                records.append({"session": seed, "scenario": scenario, "turn": turn,
                                "module": _module_of(call), "messages": call["messages"],
                                "completion": call["outputs"][0] if call.get("outputs") else ""})
            teacher_cost += sum((c.get("cost") or 0.0) for c in x.history[prev:])
        if user_msg:
            history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": pred.text})
        transcript.append({"turn": turn, "user": user_msg, "assistant": pred.text,
                           "actions": [a["type"] for a in pred.actions],
                           # additive: full action dicts + pending target + latency
                           # so the M3b probe assertion layer can inspect them.
                           "action_details": pred.actions,
                           "pending": (state.pending.target if state.pending else None),
                           "pending_held": bool(state.pending and state.pending.held),
                           "latency": round(latency, 4)})

        if state.pending and state.pending.target == CONFIRM_SUBMIT:
            break

        directive = policy.get(u_turn, "answer")
        buttons = shown_button_labels(pred)
        action, ucost = llm_u(schema, persona, style, render_screen(pred), directive)
        u_cost += ucost
        u_turn += 1
        kind = action.get("action", "message")
        if kind == "stop":
            break
        elif kind == "select":
            label = action.get("label", "").strip()
            # a save/submit ACTION button is a click event, not an option selection
            if label.lower() in buttons:
                user_msg = f"[system] User clicked: {label}"
            else:
                user_msg = f'[system] User selected option: "{label}"'
        else:
            user_msg = action.get("text", "").strip()
            if not user_msg:
                break

    return {"scenario": scenario, "seed": seed, "style": style, "turns": turn + 1,
            "persona": persona, "filled": dict(state.form_state),
            "records": records, "transcript": transcript,
            "cost_usd": teacher_cost + u_cost,
            "teacher_cost": round(teacher_cost, 4), "u_cost": round(u_cost, 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=3)
    ap.add_argument("--scenario", default="straight", help="one scenario, or 'all' to round-robin")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--run", default="dryrun")
    args = ap.parse_args()

    lm = ClaudeLM()
    dspy.configure(lm=lm)
    schema = load_schema()
    agent = FormAssistant()

    out = SIM_DIR / args.run
    out.mkdir(parents=True, exist_ok=True)
    scenarios = list(SCENARIOS) if args.scenario == "all" else [args.scenario]

    train_f = open(out / "train.jsonl", "w")
    summaries = []
    n_ext = n_resp = 0
    run_cost = 0.0
    n_ok = 0
    for i in range(args.sessions):
        scenario = scenarios[i % len(scenarios)]
        seed = args.seed + i
        print(f"[session {i+1}/{args.sessions}] scenario={scenario} seed={seed} ...", flush=True)
        try:
            s = run_session(agent, lm, schema, scenario, seed)
        except Exception as e:
            print(f"  !! session failed: {type(e).__name__}: {str(e)[:160]} — skipping", flush=True)
            continue
        for r in s["records"]:
            train_f.write(json.dumps(r) + "\n")
            n_ext += r["module"] == "extractor"
            n_resp += r["module"] == "responder"
        json.dump({k: s[k] for k in ("scenario", "seed", "style", "turns", "persona", "filled",
                                     "transcript", "cost_usd", "teacher_cost", "u_cost")},
                  open(out / f"transcript-{seed}-{scenario}.json", "w"), indent=2)
        run_cost += s["cost_usd"]
        n_ok += 1
        summaries.append(f"  {scenario:10} seed={seed} turns={s['turns']:2} "
                         f"filled={len(s['filled'])} records={len(s['records'])} "
                         f"${s['cost_usd']:.3f} (teacher ${s['teacher_cost']:.3f} + U ${s['u_cost']:.3f})")
    train_f.close()

    print("\n=== sessions ===")
    print("\n".join(summaries))
    print(f"\ntraining examples: {n_ext} extractor + {n_resp} responder = {n_ext + n_resp}")
    avg = run_cost / n_ok if n_ok else 0.0
    print(f"cost: ${run_cost:.2f} over {n_ok} sessions  (avg ${avg:.3f}/session)")
    print(f"  projected — 50 sessions ≈ ${avg*50:.0f} · 500 ≈ ${avg*500:.0f} · 2000 ≈ ${avg*2000:.0f}")
    print(f"written to {out}/")


if __name__ == "__main__":
    main()
