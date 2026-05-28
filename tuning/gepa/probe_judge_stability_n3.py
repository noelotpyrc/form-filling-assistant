"""Probe: N=3 ensemble stateless Claude-headless judge — does majority-vote
of 3 parallel calls produce stable scores across independent trials?

Each "judge decision" is N=3 parallel stateless calls (Opus 4.7, effort=medium),
element-wise majority-voted → one list[bool]. Then we run 5 such decisions
per case to test if the consolidated answers are stable.

Locks in: model=claude-opus-4-7, effort=medium.

Run from repo root:
  python tuning/gepa/probe_judge_stability_n3.py
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / ".env")

from rubrics import get_rubric_for_case  # noqa: E402
from judge_claude_headless import _build_case_prompt, _parse_yesno, LEGACY_TAG  # noqa: E402
from probe_judge_stability import specialist_system_prompt, fabricated_pred, weighted_score  # noqa: E402

CLAUDE_BIN = os.getenv("CLAUDE_BIN", "claude")
TIMEOUT_SEC = 240
N_ENSEMBLE = 3
TRIALS_PER_CASE = 5
MODEL = "claude-opus-4-7"
EFFORT = "medium"


def stateless_judge_one(case: dict, predicted: dict, rubric_items: list[dict],
                        tag: str) -> tuple[list[bool], float]:
    """One stateless judge call. Returns (yes/no list, duration_seconds)."""
    system_prompt = specialist_system_prompt(tag)
    case_prompt = _build_case_prompt(case, predicted, rubric_items)
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
        raise RuntimeError(f"claude failed (rc={proc.returncode}): "
                           f"stderr={proc.stderr[:300]!r}")
    data = json.loads(proc.stdout)
    answers = _parse_yesno(data.get("result") or "", len(rubric_items))
    dur = data.get("duration_ms", 0) / 1000
    return answers, dur


def ensembled_judge(case: dict, predicted: dict, rubric_items: list[dict],
                    tag: str, n: int = N_ENSEMBLE) -> tuple[list[bool], list[list[bool]], list[float]]:
    """N parallel stateless calls + element-wise majority vote.

    Returns (majority_answers, per_call_answers, per_call_durations).
    """
    results: list[list[bool] | None] = [None] * n
    durations: list[float] = [0.0] * n
    errors: list[BaseException | None] = [None] * n

    def _worker(i: int):
        try:
            results[i], durations[i] = stateless_judge_one(case, predicted, rubric_items, tag)
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
    majority: list[bool] = []
    for i in range(item_count):
        yes_count = sum(1 for r in valid if r[i])
        majority.append(yes_count > len(valid) / 2)
    return majority, [r or [] for r in results], durations


def run_case(label: str, case: dict, mode: str, tag: str,
             trials: int = TRIALS_PER_CASE):
    rubric = get_rubric_for_case(case)
    if mode == "gold":
        predicted = dict(case["correct_answer"])
    else:
        predicted = fabricated_pred()
    print(f"\n━━━ {label} — case={case['test_id']}  mode={mode}  tag={tag}  items={len(rubric)} ━━━")

    trial_majorities: list[list[bool]] = []
    trial_scores: list[float] = []
    trial_durs: list[float] = []
    inter_call_flips_per_trial: list[int] = []

    for t in range(trials):
        try:
            majority, per_call, durs = ensembled_judge(case, predicted, rubric, tag)
        except Exception as e:
            print(f"  trial {t+1}: ERROR {type(e).__name__}: {e}")
            continue
        score = weighted_score(rubric, majority)
        trial_majorities.append(majority)
        trial_scores.append(score)
        trial_durs.append(max(durs))
        # Within-trial disagreement: how many items had a non-unanimous N=3 vote
        within = 0
        details = []
        for i in range(len(rubric)):
            col = [r[i] for r in per_call]
            yes = sum(col)
            if yes != 0 and yes != len(col):
                within += 1
                details.append(f"item{i+1}({yes}/{len(col)})")
        inter_call_flips_per_trial.append(within)
        m_str = "".join("Y" if a else "n" for a in majority)
        details_str = f"  splits=[{','.join(details)}]" if details else ""
        print(f"  trial {t+1}: maj=[{m_str}]  score={score:.3f}  "
              f"par_dur={trial_durs[-1]:.1f}s  splits={within}/{len(rubric)}{details_str}")

    if not trial_majorities:
        print("  ** all trials failed")
        return

    # Across-trial flip count (after majority vote)
    cross_flips = []
    for i in range(len(rubric)):
        col = [m[i] for m in trial_majorities]
        cross_flips.append(0 if (all(col) or not any(col)) else sum(1 for v in col if v != col[0]))
    cross_flip_total = sum(1 for f in cross_flips if f > 0)
    print(f"  cross-trial flips (after N=3 maj-vote): {cross_flips}  "
          f"({cross_flip_total}/{len(cross_flips)} items disagreed across {trials} trials)")
    print(f"  within-trial split count avg: {statistics.mean(inter_call_flips_per_trial):.1f} items/trial")
    if len(trial_scores) > 1:
        print(f"  score after maj-vote: mean={statistics.mean(trial_scores):.3f}  "
              f"stdev={statistics.stdev(trial_scores):.4f}  "
              f"range=[{min(trial_scores):.3f}, {max(trial_scores):.3f}]")


def main():
    print(f"Config: N={N_ENSEMBLE} ensemble, {TRIALS_PER_CASE} trials/case, "
          f"model={MODEL}, effort={EFFORT}")

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
