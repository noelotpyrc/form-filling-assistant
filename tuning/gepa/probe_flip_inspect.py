"""Inspect raw N=3 call outputs across 5 trials for seed-P3-ex3 fabricated.

Same prompt sent 15 times. Logs each call's per-item confidence floats so we
can see WHERE the judge changes its mind. Reproduces the trials from
probe_judge_stability_v4 with full visibility into the underlying samples.
"""

from __future__ import annotations

import json
import statistics
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / ".env")

from rubrics import get_rubric_for_case  # noqa: E402
from judge_claude_headless import build_user_prompt, _one_call  # noqa: E402
from probe_judge_stability_v4 import fabricated_pred  # noqa: E402

TRIALS = 5
N = 3

seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
case = next(s for s in seeds if s["test_id"] == "seed-P3-ex3")
rubric = get_rubric_for_case(case)
predicted = fabricated_pred()

user_prompt = build_user_prompt(case, predicted, rubric)
n_items = len(rubric)

print(f"Case: seed-P3-ex3 fabricated   rubric items ({n_items}):")
for i, it in enumerate(rubric):
    print(f"  {i+1}. {it['id']} (w={it['weight']})")
print()

all_call_results: list[list[list[float]]] = []  # [trial][call] = scores
for t in range(TRIALS):
    print(f"━━━ trial {t+1} ━━━")
    results: list[list[float] | None] = [None] * N

    def _worker(i: int):
        results[i] = _one_call(user_prompt, n_items)

    threads = [threading.Thread(target=_worker, args=(i,), daemon=True) for i in range(N)]
    for th in threads: th.start()
    for th in threads: th.join()
    valid = [r for r in results if r is not None]
    for i, r in enumerate(valid):
        compact = "[" + ",".join(f"{s:.2f}" for s in r) + "]"
        print(f"  call {i+1}: {compact}")
    avg = [sum(r[i] for r in valid) / len(valid) for i in range(n_items)]
    avg_compact = "[" + ",".join(f"{s:.2f}" for s in avg) + "]"
    print(f"  AVG:    {avg_compact}")
    all_call_results.append(valid)
    print()

print("=" * 72)
print("Per-item summary across all 15 underlying calls:")
print(f"{'#':>3} {'item':<32} {'mean':>6} {'σ':>6}  values per call")
flat = [[r[i] for trial in all_call_results for r in trial] for i in range(n_items)]
for i, it in enumerate(rubric):
    vals = flat[i]
    mn = statistics.mean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    print(f"{i+1:>3} {it['id']:<32} {mn:>6.3f} {sd:>6.3f}  {vals}")
