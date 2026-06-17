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
from pathlib import Path

import dspy
from .claude_lm import ClaudeLM, CLAUDE_BIN
from .schema import load_schema, Schema
from .state import TurnState, CONFIRM_SUBMIT
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
}


def claude_p(system: str, user: str, timeout: int = 120) -> str:
    cmd = [CLAUDE_BIN, "-p", user, "--model", SIM_USER_MODEL,
           "--output-format", "json", "--system-prompt", system]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"LLM U claude failed rc={proc.returncode}: {proc.stderr[:300]}")
    return json.loads(proc.stdout).get("result", "")


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


def render_screen(pred) -> str:
    scr = f"Assistant said:\n{pred.text}"
    for a in pred.actions:
        if a["type"] == "ask_choice":
            scr += "\n\nButtons on screen: " + ", ".join(f'"{o["label"]}"' for o in a["options"])
        elif a["type"] == "show_button":
            scr += f'\n\n[A "{a["button"]}" button is shown.]'
    return scr


U_SYS = """You are role-playing a person filling out an online application by chatting with an assistant. Stay in character; never break role.

YOUR information (use it to answer; phrase naturally in your own words, don't dump raw values):
{persona}

Your style: {style} — {style_desc}.

You'll see the assistant's latest message and any on-screen buttons. Respond in ONE short turn.
This turn specifically: {directive}

Reply with ONLY a JSON object, one of:
{{"action": "message", "text": "<what you type>"}}
{{"action": "select", "label": "<exact on-screen button label>"}}
{{"action": "stop"}}   (only if the application is submitted/finished)"""


def llm_u(schema, persona, style, screen, directive) -> dict:
    sys = U_SYS.format(persona=render_persona(schema, persona), style=style,
                       style_desc=STYLE_DESC[style], directive=DIRECTIVES[directive])
    return _parse_action(claude_p(sys, screen))


def _module_of(call: dict) -> str:
    sysmsg = call["messages"][0]["content"] if call.get("messages") else ""
    return "responder" if "conversational reply" in sysmsg else "extractor"


def run_session(agent, lm, schema, scenario: str, seed: int, max_turns: int = 24) -> dict:
    rng = random.Random(seed)
    persona = personas.gen_persona(schema, rng)
    style = personas.gen_style(rng)
    policy = SCENARIOS[scenario]
    state = TurnState(schema=schema, form_state={})
    history: list[dict] = []
    records: list[dict] = []
    transcript: list[dict] = []
    user_msg = ""          # turn 0 kickoff: assistant greets
    u_turn = 0

    for turn in range(max_turns):
        prev = len(lm.history)
        pred = agent(state=state, user_message=user_msg, history=history)
        for call in lm.history[prev:]:
            records.append({"session": seed, "scenario": scenario, "turn": turn,
                            "module": _module_of(call), "messages": call["messages"],
                            "completion": call["outputs"][0] if call.get("outputs") else ""})
        if user_msg:
            history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": pred.text})
        transcript.append({"turn": turn, "user": user_msg, "assistant": pred.text,
                           "actions": [a["type"] for a in pred.actions]})

        if state.pending and state.pending.target == CONFIRM_SUBMIT:
            break

        directive = policy.get(u_turn, "answer")
        action = llm_u(schema, persona, style, render_screen(pred), directive)
        u_turn += 1
        kind = action.get("action", "message")
        if kind == "stop":
            break
        elif kind == "select":
            user_msg = f'[system] User selected option: "{action.get("label", "")}"'
        else:
            user_msg = action.get("text", "").strip()
            if not user_msg:
                break

    return {"scenario": scenario, "seed": seed, "style": style, "turns": turn + 1,
            "persona": persona, "filled": dict(state.form_state),
            "records": records, "transcript": transcript}


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
        json.dump({k: s[k] for k in ("scenario", "seed", "style", "turns", "persona", "filled", "transcript")},
                  open(out / f"transcript-{seed}-{scenario}.json", "w"), indent=2)
        summaries.append(f"  {scenario:10} seed={seed} turns={s['turns']:2} "
                         f"filled={len(s['filled'])} records={len(s['records'])}")
    train_f.close()

    print("\n=== sessions ===")
    print("\n".join(summaries))
    print(f"\ntraining examples: {n_ext} extractor + {n_resp} responder = {n_ext + n_resp}")
    print(f"written to {out}/")


if __name__ == "__main__":
    main()
