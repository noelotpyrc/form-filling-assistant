"""Claude Code headless judge — stateless, confidence-score, N=3 ensemble.

For each (case, prediction), runs N parallel `claude -p` subprocess calls
and averages the per-item confidence scores element-wise. The user prompt
mirrors what the SFT model sees (build_context output + user_message) so
the judge evaluates the assistant on the same information the model received.

Design (locked in 2026-05-14):
  - Uniform system prompt (judge role + scoring scale + output format)
  - User prompt: case_id + MODEL INPUT block (build_context) + GOLD + PREDICTED
                 + flat numbered rubric from get_rubric_for_case(case)
  - One judge call per case — multi-tag rubric items handled in a single call
  - N parallel stateless calls per case → element-wise average → list[float]
  - Confidence scores in [0, 1] (not binary yes/no)
  - Subscription auth (no --bare, no API key)

Env knobs:
  CLAUDE_BIN              — path to claude binary (default: "claude")
  JUDGE_CLAUDE_TIMEOUT    — subprocess timeout in seconds (default: 180)
  JUDGE_CLAUDE_N          — ensemble size per decision (default: 3)
  JUDGE_CLAUDE_MODEL      — claude model name (default: claude-opus-4-7)
  JUDGE_CLAUDE_EFFORT     — effort level (default: medium)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))

from rubrics import get_rubric_for_case  # noqa: E402
from tuning.harness.pipeline import build_context  # noqa: E402
from tuning.harness.preflight import SCHEMA_PATH  # noqa: E402

CLAUDE_BIN = os.getenv("CLAUDE_BIN", "claude")
TIMEOUT_SEC = int(os.getenv("JUDGE_CLAUDE_TIMEOUT", "180"))
N_ENSEMBLE = int(os.getenv("JUDGE_CLAUDE_N", "3"))
MODEL = os.getenv("JUDGE_CLAUDE_MODEL", "claude-opus-4-7")
EFFORT = os.getenv("JUDGE_CLAUDE_EFFORT", "medium")


# ─────────────────────────────────────────────────────────────────────────
# Schema (lazy-loaded once)
# ─────────────────────────────────────────────────────────────────────────

_FORM_SCHEMA: dict | None = None


def _get_schema() -> dict:
    global _FORM_SCHEMA
    if _FORM_SCHEMA is None:
        _FORM_SCHEMA = json.loads(Path(SCHEMA_PATH).read_text())
    return _FORM_SCHEMA


# ─────────────────────────────────────────────────────────────────────────
# Prompt templates
# ─────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an LLM judge evaluating a form-filling assistant's turn output.

The assistant produces FIVE module outputs that together define each turn (any of which can be empty in a given turn):
  - action flags (5 booleans: has_new_data, needs_choice, wants_review, wants_save, wants_submit)
  - response_text (conversational reply)
  - field updates (field_ids + field_values, parallel arrays — empty when no fields are being committed)
  - multiple-choice (question + options — empty unless needs_choice is true)
  - review summary (summary_title + summary_content — empty unless wants_review is true)

You judge the PREDICTED turn. The GOLD turn is one reference for correct behavior — phrasing can differ and still be correct.

For each numbered rubric item, return a CONFIDENCE SCORE in [0, 1]:
  1.0  = rubric clearly satisfied
  0.75 = mostly satisfied, minor concerns
  0.5  = genuinely ambiguous / partial credit
  0.25 = mostly violated, with some merit
  0.0  = rubric clearly violated
Use the full [0, 1] range — don't snap to only 0 or 1.

Reply with ONLY a JSON array of floats, length = number of rubric items, in order. No prose, no markdown fence, no explanation."""


USER_PROMPT_TEMPLATE = """case_id: {case_id}

────── MODEL INPUT (verbatim — what the assistant received) ──────
context:
{model_context}

user_message:
{user_message}

────── GOLD TURN (reference) ──────
{gold_block}

────── PREDICTED TURN (judge this) ──────
{predicted_block}

────── RUBRIC ──────
{rubric_block}

Reply with a JSON array of {n_items} floats in [0, 1] (use full range). JSON array only."""


def _fmt_turn(p: dict) -> str:
    flags = p.get("flags") or {
        f: p.get(f, False) for f in
        ["has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit"]
    }
    flag_str = " ".join(f"{k}={bool(v)}" for k, v in flags.items())
    fids = p.get("field_ids") or []
    fvals = p.get("field_values") or []
    field_lines = "\n".join(f"  {fid} = {fv!r}" for fid, fv in zip(fids, fvals)) or "  (none)"
    out = [
        f"flags:    {flag_str}",
        f"response_text: {p.get('response_text', '')!r}",
        f"field updates ({len(fids)}):",
        field_lines,
    ]
    q = p.get("question") or ""
    opts = p.get("options") or []
    if q or opts:
        out.append(f"question: {q!r}")
        out.append(f"options:  {opts}")
    st = p.get("summary_title") or ""
    sc = p.get("summary_content") or ""
    if st or sc:
        out.append(f"review:   '{st}' — {sc!r}")
    return "\n".join(out)


def build_user_prompt(case: dict, predicted: dict, rubric_items: list[dict]) -> str:
    """Render the per-case user prompt — exactly mirrors the SFT model input.

    `build_context` already applies the legacy `---actions---` strip and the
    history_window=6 + per-turn truncation, so the judge sees what the model
    saw, no more, no less.
    """
    inp = case["input"]
    ctx = build_context(
        _get_schema(),
        inp.get("form_state", {}),
        inp.get("conversation_history", []),
    )
    rubric_block = "\n".join(
        f"{i+1}. {it['id']} — {it['ask']}" for i, it in enumerate(rubric_items)
    )
    return USER_PROMPT_TEMPLATE.format(
        case_id=case["test_id"],
        model_context=ctx,
        user_message=inp["user_message"],
        gold_block=_fmt_turn(case["correct_answer"]),
        predicted_block=_fmt_turn(predicted),
        rubric_block=rubric_block,
        n_items=len(rubric_items),
    )


# ─────────────────────────────────────────────────────────────────────────
# Subprocess + parsing
# ─────────────────────────────────────────────────────────────────────────

def _parse_floats(text: str, expected_n: int) -> list[float]:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
        t = t.rstrip("`").strip()
    arr = json.loads(t)
    if not isinstance(arr, list) or len(arr) != expected_n:
        raise ValueError(
            f"expected JSON array of {expected_n} floats, got {arr!r}"
        )
    out: list[float] = []
    for x in arr:
        f = float(x)
        if not (0.0 <= f <= 1.0):
            raise ValueError(f"score {f} out of [0, 1]")
        out.append(f)
    return out


def _one_call(user_prompt: str, expected_n: int) -> list[float]:
    cmd = [
        CLAUDE_BIN, "-p", user_prompt,
        "--system-prompt", SYSTEM_PROMPT,
        "--tools", "",
        "--model", MODEL,
        "--effort", EFFORT,
        "--output-format", "json",
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=TIMEOUT_SEC, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude failed (rc={proc.returncode}): "
            f"stderr={proc.stderr[:300]!r}"
        )
    data = json.loads(proc.stdout)
    return _parse_floats(data.get("result") or "", expected_n)


# ─────────────────────────────────────────────────────────────────────────
# Public API — matches the judge_case signature in judge.py's dispatch
# ─────────────────────────────────────────────────────────────────────────

def judge_case(case: dict, predicted: dict, rubric_items: list[dict],
               model: str | None = None) -> list[float]:
    """Score a case — N=3 parallel stateless calls, element-wise average.

    Returns list[float] of length len(rubric_items), each in [0, 1].
    """
    if not rubric_items:
        return []
    user_prompt = build_user_prompt(case, predicted, rubric_items)
    n = N_ENSEMBLE
    results: list[list[float] | None] = [None] * n
    errors: list[BaseException | None] = [None] * n

    def _worker(i: int):
        try:
            results[i] = _one_call(user_prompt, len(rubric_items))
        except BaseException as e:  # noqa: BLE001
            errors[i] = e

    threads = [threading.Thread(target=_worker, args=(i,), daemon=True) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if any(e is not None for e in errors):
        raise next(e for e in errors if e is not None)

    valid = [r for r in results if r is not None]
    item_count = len(rubric_items)
    return [sum(r[i] for r in valid) / len(valid) for i in range(item_count)]


# ─────────────────────────────────────────────────────────────────────────
# CLI smoke
# ─────────────────────────────────────────────────────────────────────────

def _cli():
    import argparse
    from dotenv import load_dotenv
    load_dotenv(REPO / ".env")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", default="seed-P3-ex3")
    ap.add_argument("--mode", choices=["gold", "fabricated"], default="gold")
    args = ap.parse_args()

    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    case = next(s for s in seeds if s["test_id"] == args.seed)
    rubric = get_rubric_for_case(case)
    if args.mode == "gold":
        predicted = dict(case["correct_answer"])
    else:
        predicted = {
            "flags": {"has_new_data": True, "needs_choice": False, "wants_review": False,
                      "wants_save": False, "wants_submit": False},
            "response_text": "Got it, saved your DOB as 1995-01-04.",
            "field_ids": ["dob"], "field_values": ["1995-01-04"],
            "question": "", "options": [], "summary_title": "", "summary_content": "",
        }
    print(f"Seed: {args.seed}  mode: {args.mode}  N={N_ENSEMBLE}  model={MODEL}  effort={EFFORT}")
    scores = judge_case(case, predicted, rubric)
    print(f"Scores: {[round(s, 3) for s in scores]}")
    for it, s in zip(rubric, scores):
        mark = "✓" if s >= 0.999 else ("✗" if s <= 0.001 else f"~{s:.2f}")
        print(f"  {mark} [{it['weight']}] {it['id']}")


if __name__ == "__main__":
    _cli()
