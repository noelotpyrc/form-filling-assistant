"""Time DSPy Evaluate with the Kimi judge at num_threads=1 vs num_threads=4
on a small slice of val cases. Confirms parallelism works end-to-end without
errors (race conditions in metric, concurrent OpenRouter calls, concurrent
MLX inference, etc.) before committing to a long full-budget run.

Run from repo root:
  JUDGE_BACKEND=openrouter \\
  python/.venv/bin/python -u tuning/gepa/test_num_threads.py --n-cases 4
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO / "tuning" / "dspy"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / ".env")

import _litellm_executor_fix  # noqa: E402, F401  (apply LiteLLM executor resilience patch)
import dspy  # noqa: E402
from optimize_prompt import FormAssistant  # noqa: E402
from optimize import load_examples, stratified_sample, make_metric  # noqa: E402
from tuning.harness.pipeline import configure_lm, DEFAULT_LM_MODEL  # noqa: E402
from tuning.harness.preflight import SCHEMA_PATH  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--student-port", type=int, default=8100)
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL)
    ap.add_argument("--n-cases", type=int, default=4,
                    help="How many val cases to evaluate in each timing run")
    ap.add_argument("--threads-low", type=int, default=1)
    ap.add_argument("--threads-high", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--train-size", type=int, default=486)
    ap.add_argument("--val-size", type=int, default=122)
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY not set")

    configure_lm(
        api_base=f"http://localhost:{args.student_port}/v1",
        model=args.student_model,
    )
    form_schema = json.loads(Path(SCHEMA_PATH).read_text())
    examples = load_examples(form_schema)
    rng = random.Random(args.seed)
    rng.shuffle(examples)
    train_set = stratified_sample(examples, args.train_size, seed=args.seed)
    train_ids = {id(ex) for ex in train_set}
    remaining = [ex for ex in examples if id(ex) not in train_ids]
    val_set = stratified_sample(remaining, args.val_size, seed=args.seed + 1)
    devset = val_set[: args.n_cases]
    print(f"Devset size: {len(devset)}")
    print(f"Judge backend: {os.getenv('JUDGE_BACKEND', 'openai')}")
    print(f"OpenRouter model: {os.getenv('JUDGE_OPENROUTER_MODEL', 'moonshotai/kimi-k2.6')}")
    print(f"N ensemble: {os.getenv('JUDGE_OPENROUTER_N', '3')}\n")

    metric = make_metric(use_judge=True)
    program = FormAssistant()

    def run_eval(n_threads: int):
        ev = dspy.Evaluate(
            devset=devset,
            metric=metric,
            num_threads=n_threads,
            display_progress=False,
            display_table=False,
            return_all_scores=True,
            provide_traceback=True,
        )
        t0 = time.time()
        result = ev(program)
        dt = time.time() - t0
        # result.results is a list of (example, prediction, score) tuples
        scores = [r[2] for r in result.results]
        avg = sum(scores) / len(scores) if scores else 0.0
        return dt, avg, scores

    for n_threads in [args.threads_low, args.threads_high]:
        print(f"── num_threads={n_threads} ──")
        try:
            dt, avg, scores = run_eval(n_threads)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            continue
        print(f"  wall: {dt:.1f}s  avg_score: {avg:.4f}")
        print(f"  per-case scores: {[round(s, 3) for s in scores]}\n")


if __name__ == "__main__":
    main()
