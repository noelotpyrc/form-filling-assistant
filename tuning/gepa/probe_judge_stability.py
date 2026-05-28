"""Probe: stateless Claude-headless judge — does the same case produce stable
scores across independent calls?

Each call:
  claude -p "<case prompt>" --system-prompt "<specialist intro>" \\
         --tools "" --output-format json
No --resume, no session reuse. Each call is independent.

Run 5 times per case for K=4 cases, then report per-item flip rate and
per-case weighted-score variance.

Usage:
  python tuning/gepa/probe_judge_stability.py
"""

from __future__ import annotations

import json
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / ".env")

from rubrics import UNIVERSAL_GOOD, CATEGORY_BAD, get_rubric_for_case  # noqa: E402
from judge_claude_headless import _build_case_prompt, _parse_yesno, LEGACY_TAG  # noqa: E402

CLAUDE_BIN = os.getenv("CLAUDE_BIN", "claude")
TIMEOUT_SEC = 180
RUNS_PER_CASE = 5


# Same intro shape as judge_claude_headless._specialist_intro but with the
# explicit instruction at the *end*, since here it's a system prompt.
def specialist_system_prompt(tag: str) -> str:
    universal_block = "\n".join(
        f"{i+1}. {it['id']} — {it['ask']}" for i, it in enumerate(UNIVERSAL_GOOD)
    )
    if tag == LEGACY_TAG:
        spec = "These are legacy cases — apply the universal criteria carefully."
    else:
        c = CATEGORY_BAD[tag]
        spec = f"{c['id']} — {c['ask']}"
    return (
        "You are a specialist LLM judge for a form-filling assistant. You "
        "score predictions against numbered rubric items and reply with "
        "ONLY a JSON array of yes/no strings — one per item, in order. No "
        "prose, no markdown fence, no explanation.\n"
        "\n"
        "UNIVERSAL CRITERIA (apply to every case):\n"
        f"{universal_block}\n"
        "\n"
        f"YOUR SPECIALTY ({tag}):\n"
        f"{spec}\n"
        "\n"
        "Reply ONLY with a JSON array of yes/no strings of length matching "
        "the numbered rubric items in the user prompt."
    )


def stateless_judge(case: dict, predicted: dict, rubric_items: list[dict],
                    tag: str) -> tuple[list[bool], dict]:
    """One stateless judge call. Returns (yes/no list, full JSON output)."""
    system_prompt = specialist_system_prompt(tag)
    case_prompt = _build_case_prompt(case, predicted, rubric_items)
    cmd = [
        CLAUDE_BIN, "-p", case_prompt,
        "--system-prompt", system_prompt,
        "--tools", "",
        "--output-format", "json",
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=TIMEOUT_SEC, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude failed (rc={proc.returncode}): "
            f"stderr={proc.stderr[:400]!r}"
        )
    data = json.loads(proc.stdout)
    answers = _parse_yesno(data.get("result") or "", len(rubric_items))
    return answers, data


def fabricated_pred() -> dict:
    return {
        "flags": {"has_new_data": True, "needs_choice": False, "wants_review": False,
                  "wants_save": False, "wants_submit": False},
        "response_text": "Got it, saved your DOB as 1995-01-04.",
        "field_ids": ["dob"], "field_values": ["1995-01-04"],
        "question": "", "options": [], "summary_title": "", "summary_content": "",
    }


def weighted_score(rubric: list[dict], answers: list[bool]) -> float:
    total_w = sum(it["weight"] for it in rubric) or 1.0
    earned = sum(it["weight"] for it, a in zip(rubric, answers) if a)
    return earned / total_w


def run_case(label: str, case: dict, mode: str, tag: str, runs: int = RUNS_PER_CASE):
    rubric = get_rubric_for_case(case)
    if mode == "gold":
        predicted = dict(case["correct_answer"])
    else:
        predicted = fabricated_pred()
    print(f"\n━━━ {label} — case={case['test_id']}  mode={mode}  tag={tag}  items={len(rubric)} ━━━")
    rows: list[list[bool]] = []
    scores: list[float] = []
    durations: list[float] = []
    for r in range(runs):
        try:
            answers, data = stateless_judge(case, predicted, rubric, tag)
        except Exception as e:
            print(f"  run {r+1}: ERROR {type(e).__name__}: {e}")
            continue
        score = weighted_score(rubric, answers)
        rows.append(answers)
        scores.append(score)
        durations.append(data.get("duration_ms", 0) / 1000)
        joined = "".join("Y" if a else "n" for a in answers)
        print(f"  run {r+1}: [{joined}] score={score:.3f}  dur={durations[-1]:.1f}s")
    if not rows:
        print("  ** all runs failed")
        return
    # Per-item flip count
    flips = []
    for i in range(len(rubric)):
        col = [r[i] for r in rows]
        unanimous = all(col) or not any(col)
        flips.append(0 if unanimous else sum(1 for v in col if v != col[0]))
    flip_total = sum(1 for f in flips if f > 0)
    print(f"  per-item flips (0 = stable): {flips}   ({flip_total}/{len(flips)} items disagreed)")
    if len(scores) > 1:
        print(f"  score: mean={statistics.mean(scores):.3f}  stdev={statistics.stdev(scores):.4f}  "
              f"range=[{min(scores):.3f}, {max(scores):.3f}]")


def main():
    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    eval_cases = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]

    by_id = {s["test_id"]: s for s in seeds}
    eval_by_id = {c["test_id"]: c for c in eval_cases}

    plan = [
        # (label, test_id, source_dict, mode, tag)
        ("single-tag GOLD",      "seed-P3-ex3", by_id,      "gold",        "#4_commits_regardless"),
        ("single-tag FABRICATED","seed-P3-ex3", by_id,      "fabricated",  "#4_commits_regardless"),
        ("multi-tag #4 side",    "seed-P1-ex1", by_id,      "fabricated",  "#4_commits_regardless"),
        ("multi-tag #8 side",    "seed-P1-ex1", by_id,      "fabricated",  "#8_training_data_hallucination"),
    ]
    # Optional: probe a legacy + variation if available
    legacy_ids = [c["test_id"] for c in eval_cases
                  if c["test_id"].startswith("legacy-") and not (c.get("cannot_targets") or [])]
    if legacy_ids:
        plan.append(("legacy GOLD", legacy_ids[0], eval_by_id, "gold", LEGACY_TAG))

    for label, tid, src, mode, tag in plan:
        case = src.get(tid)
        if not case:
            print(f"\n** SKIP — {tid} not found")
            continue
        run_case(label, case, mode, tag)

    print("\nDone.")


if __name__ == "__main__":
    main()
