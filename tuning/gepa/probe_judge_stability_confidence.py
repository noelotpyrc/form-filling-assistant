"""Probe: Claude headless judge with CONFIDENCE SCORES instead of yes/no.

Tests the hypothesis that asking the judge to return floats in [0,1] yields
STABLE continuous scores across runs even when yes/no would flip. If a
borderline item consistently returns ~0.55 instead of randomly snapping
between 0.0 and 1.0, the eval-level variance should drop dramatically.

Same 5 cases, 5 runs each, stateless Claude headless (Opus 4.7, effort=medium).
Reports per-item score stdev across runs (granular stability) and per-case
weighted-score stdev (overall stability).

Run from repo root:
  python tuning/gepa/probe_judge_stability_confidence.py
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
from judge_claude_headless import _build_case_prompt, LEGACY_TAG  # noqa: E402
from probe_judge_stability import fabricated_pred  # noqa: E402

CLAUDE_BIN = os.getenv("CLAUDE_BIN", "claude")
TIMEOUT_SEC = 240
RUNS_PER_CASE = 5
MODEL = "claude-opus-4-7"
EFFORT = "medium"


def specialist_system_prompt_confidence(tag: str) -> str:
    universal_block = "\n".join(
        f"{i+1}. {it['id']} — {it['ask']}" for i, it in enumerate(UNIVERSAL_GOOD)
    )
    if tag == LEGACY_TAG:
        spec = "These are legacy cases — apply the universal criteria carefully."
    else:
        c = CATEGORY_BAD[tag]
        spec = f"{c['id']} — {c['ask']}"
    return (
        "You are a specialist LLM judge for a form-filling assistant. For each "
        "numbered rubric item, return a CONFIDENCE SCORE in [0, 1] capturing "
        "how strongly the prediction satisfies that item:\n"
        "  1.0  = rubric clearly satisfied (definite yes)\n"
        "  0.75 = mostly satisfied, minor concerns\n"
        "  0.5  = genuinely ambiguous / partial credit\n"
        "  0.25 = mostly violated, with some merit\n"
        "  0.0  = rubric clearly violated (definite no)\n"
        "Use the full [0,1] range — don't snap to only 0 or 1.\n"
        "\n"
        "UNIVERSAL CRITERIA (apply to every case):\n"
        f"{universal_block}\n"
        "\n"
        f"YOUR SPECIALTY ({tag}):\n"
        f"{spec}\n"
        "\n"
        "Reply with ONLY a JSON array of floats, one per rubric item, in order. "
        "No prose, no markdown fence, no explanation."
    )


def case_prompt_confidence(case: dict, predicted: dict, rubric_items: list[dict]) -> str:
    """Same body as judge_claude_headless._build_case_prompt but ends with a
    request for floats instead of yes/no.
    """
    base = _build_case_prompt(case, predicted, rubric_items)
    # _build_case_prompt ends with a yes/no instruction; replace it.
    base = re.sub(
        r'Reply with a JSON array of length \d+, .*?JSON array only\.\s*$',
        f'Reply with a JSON array of {len(rubric_items)} floats in [0, 1] '
        f'(use the full range — do NOT snap to only 0 or 1). JSON array only.',
        base.rstrip(),
        flags=re.DOTALL,
    )
    return base


def _parse_floats(text: str, expected_n: int) -> list[float]:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
        t = t.rstrip("`").strip()
    arr = json.loads(t)
    if not isinstance(arr, list) or len(arr) != expected_n:
        raise ValueError(f"expected array of len {expected_n}, got {arr!r}")
    out: list[float] = []
    for x in arr:
        f = float(x)
        if not (0.0 <= f <= 1.0):
            raise ValueError(f"score {f} out of [0,1]")
        out.append(f)
    return out


def stateless_judge_confidence(case: dict, predicted: dict, rubric_items: list[dict],
                               tag: str) -> tuple[list[float], dict]:
    system_prompt = specialist_system_prompt_confidence(tag)
    case_prompt = case_prompt_confidence(case, predicted, rubric_items)
    cmd = [
        CLAUDE_BIN, "-p", case_prompt,
        "--system-prompt", system_prompt,
        "--tools", "",
        "--model", MODEL,
        "--effort", EFFORT,
        "--output-format", "json",
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=TIMEOUT_SEC, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude failed (rc={proc.returncode}): stderr={proc.stderr[:300]!r}")
    data = json.loads(proc.stdout)
    scores = _parse_floats(data.get("result") or "", len(rubric_items))
    return scores, data


def weighted_score_float(rubric: list[dict], item_scores: list[float]) -> float:
    total_w = sum(it["weight"] for it in rubric) or 1.0
    earned = sum(it["weight"] * s for it, s in zip(rubric, item_scores))
    return earned / total_w


def run_case(label: str, case: dict, mode: str, tag: str):
    rubric = get_rubric_for_case(case)
    if mode == "gold":
        predicted = dict(case["correct_answer"])
    else:
        predicted = fabricated_pred()
    print(f"\n━━━ {label} — case={case['test_id']}  mode={mode}  tag={tag}  items={len(rubric)} ━━━")
    rows: list[list[float]] = []
    scores: list[float] = []
    durs: list[float] = []
    for r in range(RUNS_PER_CASE):
        try:
            item_scores, data = stateless_judge_confidence(case, predicted, rubric, tag)
        except Exception as e:
            print(f"  run {r+1}: ERROR {type(e).__name__}: {str(e)[:120]}")
            continue
        ws = weighted_score_float(rubric, item_scores)
        rows.append(item_scores)
        scores.append(ws)
        durs.append(data.get("duration_ms", 0) / 1000)
        compact = "[" + ",".join(f"{s:.2f}" for s in item_scores) + "]"
        print(f"  run {r+1}: {compact}  ws={ws:.3f}  dur={durs[-1]:.1f}s")
    if not rows:
        print("  ** all runs failed")
        return
    # Per-item stdev across runs
    item_stdevs = []
    for i in range(len(rubric)):
        col = [r[i] for r in rows]
        item_stdevs.append(statistics.stdev(col) if len(col) > 1 else 0.0)
    print(f"  per-item σ: [{', '.join(f'{s:.3f}' for s in item_stdevs)}]")
    print(f"  max per-item σ: {max(item_stdevs):.3f}   "
          f"mean per-item σ: {statistics.mean(item_stdevs):.3f}")
    if len(scores) > 1:
        print(f"  weighted score: mean={statistics.mean(scores):.3f}  "
              f"stdev={statistics.stdev(scores):.4f}  "
              f"range=[{min(scores):.3f}, {max(scores):.3f}]")


def main():
    print(f"Config: model={MODEL}, effort={EFFORT}, runs/case={RUNS_PER_CASE}, "
          f"output=confidence floats in [0,1]")
    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    eval_cases = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]
    by_id = {s["test_id"]: s for s in seeds}
    eval_by_id = {c["test_id"]: c for c in eval_cases}

    plan = [
        ("single-tag GOLD",       "seed-P3-ex3", by_id,      "gold",        "#4_commits_regardless"),
        ("single-tag FABRICATED", "seed-P3-ex3", by_id,      "fabricated",  "#4_commits_regardless"),
        ("multi-tag #4 side",     "seed-P1-ex1", by_id,      "fabricated",  "#4_commits_regardless"),
        ("multi-tag #8 side",     "seed-P1-ex1", by_id,      "fabricated",  "#8_training_data_hallucination"),
    ]
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
