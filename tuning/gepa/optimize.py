"""GEPA pilot — joint optimization of FormAssistant's 5 module prompts
against the new eval cases (28 seeds + 280 variations + 300 legacy).

Wires:
  - DSPy FormAssistant (signatures from tuning/dspy/optimize_prompt.py)
  - Our new metric (tuning/gepa/metric.py) — programmatic + judge rubric
  - Bounded budget (auto={light,medium,heavy} from DSPy)

Pilot defaults: small train/val sample, light budget, judge OFF (programmatic
only, fast & free) — flip with --judge to run the real metric.

Run from repo root:
  python/.venv/bin/python tuning/gepa/optimize.py --student-port 8100 --judge \
      --budget light --train-size 30 --val-size 30
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import random
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO_ROOT / "tuning" / "dspy"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

# Patch LiteLLM's module-level executor BEFORE dspy/litellm gets used in
# parallel threaded contexts. Without this, num_threads > 1 causes silent
# failures (executor gets shut down, then subsequent calls raise). See
# tuning/gepa/_litellm_executor_fix.py for details.
import _litellm_executor_fix  # noqa: E402, F401

import dspy  # noqa: E402

# Reuse the FormAssistant module + signatures.
from optimize_prompt import FormAssistant  # noqa: E402

# Use the harness's canonical context builder + LM config — never duplicate.
# See CLAUDE.md > Experiment hygiene.
from tuning.harness.pipeline import build_context, configure_lm, get_agent, DEFAULT_LM_MODEL  # noqa: E402
from tuning.harness.preflight import (  # noqa: E402
    assert_anchor_match, assert_anchors_match,
    DEFAULT_ANCHOR, DEFAULT_ANCHORS, SCHEMA_PATH,
)

import metric as gepa_metric  # noqa: E402
from judge import JudgeRetriesExhausted  # noqa: E402

SEEDS_PATH = Path(__file__).parent / "seeds.jsonl"
EVAL_PATH = Path(__file__).parent / "eval_cases.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"


# ─────────────────────────────────────────────────────────────────────────
# Build DSPy Examples from our case format
# ─────────────────────────────────────────────────────────────────────────

def case_to_example(case: dict, form_schema: dict) -> dspy.Example:
    """Convert one eval case → DSPy Example.

    Uses harness's `build_context` so the prompt format matches production
    (and matches the SFT model's training distribution).
    """
    inp = case["input"]
    ctx = build_context(form_schema, inp.get("form_state", {}), inp.get("conversation_history", []))
    return dspy.Example(
        context=ctx,
        user_message=inp["user_message"],
        case=case,  # carry the full case for the metric
    ).with_inputs("context", "user_message")


def load_examples(form_schema: dict) -> list[dspy.Example]:
    seeds = [json.loads(l) for l in open(SEEDS_PATH)]
    cases = [json.loads(l) for l in open(EVAL_PATH)]
    all_cases = seeds + cases
    return [case_to_example(c, form_schema) for c in all_cases]


def stratified_sample(examples: list[dspy.Example], n: int, seed: int = 42) -> list[dspy.Example]:
    """Sample n examples, stratified by source so all CANNOTs are present."""
    by_source: dict[str, list] = {}
    for ex in examples:
        s = ex.case["source"]
        by_source.setdefault(s, []).append(ex)
    rng = random.Random(seed)
    sources = list(by_source.keys())
    rng.shuffle(sources)
    out: list = []
    # Round-robin pick one from each source until we have n
    while len(out) < n and any(by_source[s] for s in sources):
        for s in sources:
            if not by_source[s]:
                continue
            out.append(by_source[s].pop())
            if len(out) >= n:
                break
    return out


# ─────────────────────────────────────────────────────────────────────────
# Metric wrapper: pre-bind judge on/off
# ─────────────────────────────────────────────────────────────────────────

def make_metric(use_judge: bool):
    def m(gold, pred, trace=None, pred_name=None, pred_trace=None):
        case = gold.case if hasattr(gold, "case") else gold
        pred_dict = gepa_metric._extract_pred(pred)
        result = gepa_metric.score_case(case, pred_dict, use_judge=use_judge)
        if pred_name is None:
            return result["score"]
        return dspy.Prediction(score=result["score"], feedback=result["feedback"])
    return m


# Shared state for the halt-on-judge-failure wrapper. DSPy's GEPA compile()
# runs the metric inside threads with raise_on_error=False; raising from our
# metric would just be swallowed and converted to failure_score. Instead we
# touch the gepa.stop file (FileStopper picks it up at the next iteration
# boundary) and short-circuit subsequent calls so we don't waste minutes on
# retry-then-fail for every remaining case.
# See: tuning/gepa/INCIDENT_2026-05-15_judge_silent_fallback.md
_HALT_STATE: dict = {"stop_file": None, "halted": False, "first_error": None}


def make_metric_with_halt(use_judge: bool, failure_score: float = 0.0):
    """Wrap make_metric so a JudgeRetriesExhausted touches gepa.stop and
    short-circuits subsequent calls instead of letting DSPy silently
    substitute failure_score for judge failures.
    """
    inner = make_metric(use_judge=use_judge)

    def m(gold, pred, trace=None, pred_name=None, pred_trace=None):
        # Short-circuit: once halt is requested, don't bother invoking judge
        # on remaining cases (each would burn ~20s of retry backoff).
        if _HALT_STATE["halted"]:
            if pred_name is None:
                return failure_score
            return dspy.Prediction(score=failure_score, feedback="halt_requested")
        try:
            return inner(gold, pred, trace=trace, pred_name=pred_name, pred_trace=pred_trace)
        except JudgeRetriesExhausted as e:
            _HALT_STATE["halted"] = True
            _HALT_STATE["first_error"] = str(e)
            stop_file = _HALT_STATE.get("stop_file")
            if stop_file:
                try:
                    Path(stop_file).touch()
                    sys.stderr.write(
                        f"\n[optimize] JudgeRetriesExhausted — touched {stop_file} "
                        f"for graceful halt. GEPA will stop at the next iteration "
                        f"boundary. Cause: {e}\n"
                    )
                except Exception as touch_err:
                    sys.stderr.write(
                        f"\n[optimize] JudgeRetriesExhausted but could not touch "
                        f"stop file ({touch_err}). Run will continue with failure "
                        f"scores until you halt it manually. Cause: {e}\n"
                    )
            else:
                sys.stderr.write(
                    f"\n[optimize] JudgeRetriesExhausted with no stop_file "
                    f"configured (no --log-dir). Run will continue with failure "
                    f"scores. Cause: {e}\n"
                )
            sys.stderr.flush()
            if pred_name is None:
                return failure_score
            return dspy.Prediction(score=failure_score, feedback="judge_retries_exhausted")
    return m


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-port", type=int, default=8100,
                    help="MLX server port (8100 = SFT v2)")
    ap.add_argument("--student-model", default=DEFAULT_LM_MODEL,
                    help="Model path/name as registered with the MLX server. "
                         "Default = harness DEFAULT_LM_MODEL (SFT v2). When pointing "
                         "at a different model, also pass --anchor matching it.")
    ap.add_argument("--anchor", default=None,
                    help="Single anchor fixture path. If unset, preflight runs "
                         "the full DEFAULT_ANCHORS list (covers multiple "
                         "scenarios). Use this to point at a specific anchor "
                         "when testing a different --student-model.")
    ap.add_argument("--reflection-model", default="gpt-5",
                    help="Model used by GEPA for prompt mutation. If the "
                         "value contains a '/', it's passed to dspy.LM as-is "
                         "(LiteLLM provider/model, e.g. "
                         "'openrouter/deepseek/deepseek-v4-flash'). "
                         "Otherwise 'openai/' is prepended.")
    ap.add_argument("--reflection-base-url", default=None,
                    help="Optional api_base for the reflection model. "
                         "Needed only when the provider in --reflection-model "
                         "doesn't auto-resolve via LiteLLM env vars.")
    ap.add_argument("--budget", default="light", choices=["light", "medium", "heavy"],
                    help="DSPy auto-budget preset. Ignored if --max-metric-calls is set.")
    ap.add_argument("--max-metric-calls", type=int, default=None,
                    help="Hard cap on metric calls. Overrides --budget when set.")
    ap.add_argument("--train-size", type=int, default=30)
    ap.add_argument("--val-size", type=int, default=30)
    ap.add_argument("--judge", action="store_true",
                    help="Enable LLM judge in metric (cost: ~$0.005/case/eval)")
    ap.add_argument("--baseline-only", action="store_true",
                    help="Run only the baseline eval, skip GEPA")
    ap.add_argument("--baseline-from", default=None,
                    help="Path to a JSON produced by precalc_baseline.py. "
                         "If set, skips the pre-GEPA baseline loop and uses "
                         "the precomputed baseline_avg + per-case scores. "
                         "The JSON's val test_ids must match the current "
                         "val_set (same --seed, --train-size, --val-size).")
    ap.add_argument("--log-dir", default=None,
                    help="GEPA log/checkpoint directory. If it exists, GEPA resumes "
                         "from the last saved state. Required for fault tolerance.")
    ap.add_argument("--skip-preflight", action="store_true",
                    help="Skip the anchor preflight smoke test. Use only for "
                         "debugging — production runs must pass preflight.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--num-threads", type=int, default=1,
                    help="DSPy Evaluate/ParallelExecutor thread count for val + "
                         "subsample eval. Default 1 (sequential). With slower "
                         "judges (Kimi), use 4 to parallelize.")
    ap.add_argument("--start-from-state", default=None,
                    help="Path to a gepa_state.bin from a prior run. When set with "
                         "--start-from-candidate, applies that candidate's per-module "
                         "instructions to the initial FormAssistant before GEPA sees "
                         "it. GEPA then treats the enhanced program as its iter-0 "
                         "baseline. Must use a NEW --log-dir (don't overlay an "
                         "existing run's state).")
    ap.add_argument("--start-from-candidate", type=int, default=None,
                    help="Candidate index within --start-from-state to use as the "
                         "starting program. Required if --start-from-state is set.")
    args = ap.parse_args()

    # --start-from-state / --start-from-candidate validation
    if (args.start_from_state is None) != (args.start_from_candidate is None):
        sys.exit("--start-from-state and --start-from-candidate must be set together")
    if args.start_from_state and args.log_dir and Path(args.log_dir).exists() \
            and (Path(args.log_dir) / "gepa_state.bin").exists():
        sys.exit(
            f"--log-dir {args.log_dir} already contains gepa_state.bin. "
            f"Refusing to mix --start-from-state injection with DSPy auto-resume "
            f"from an existing state. Use a new --log-dir."
        )

    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY not set")

    # Set the halt stop_file path early — baseline eval can also hit
    # JudgeRetriesExhausted, and we want the metric wrapper to be able to
    # touch gepa.stop even if the eventual GEPA compile never starts.
    if args.log_dir is not None:
        _HALT_STATE["stop_file"] = str(Path(args.log_dir).resolve() / "gepa.stop")

    # ── Configure the student LM via the harness's canonical config ──
    # (max_tokens=512, cache=False, applied to whatever --student-model is).
    configure_lm(
        api_base=f"http://localhost:{args.student_port}/v1",
        model=args.student_model,
    )

    # Pass-through full LiteLLM model id when the user supplies one (contains
    # '/'), e.g. 'openrouter/deepseek/deepseek-v4-flash'. Otherwise prepend
    # 'openai/' to preserve legacy 'gpt-5' shorthand.
    reflection_model_id = (
        args.reflection_model if "/" in args.reflection_model
        else f"openai/{args.reflection_model}"
    )
    reflection_lm_kwargs: dict = dict(temperature=1.0, max_tokens=32000)
    if args.reflection_base_url:
        reflection_lm_kwargs["api_base"] = args.reflection_base_url
    reflection_lm = dspy.LM(reflection_model_id, **reflection_lm_kwargs)

    # ── Preflight: prove the harness reproduces the model's anchor(s) ──
    # See CLAUDE.md > Experiment hygiene.
    if not args.skip_preflight:
        if args.anchor:
            assert_anchor_match(args.anchor)
        else:
            assert_anchors_match()

    # Load form_schema once for case→example construction.
    form_schema = json.loads(Path(SCHEMA_PATH).read_text())

    # Load + sample
    print("Loading eval cases...")
    examples = load_examples(form_schema)
    print(f"  Total: {len(examples)} cases")

    rng = random.Random(args.seed)
    rng.shuffle(examples)
    train_set = stratified_sample(examples, args.train_size, seed=args.seed)
    train_ids = {id(ex) for ex in train_set}
    remaining = [ex for ex in examples if id(ex) not in train_ids]
    val_set = stratified_sample(remaining, args.val_size, seed=args.seed + 1)

    print(f"  Train: {len(train_set)}  Val: {len(val_set)}")
    print(f"  Train CANNOTs: {sorted({c for ex in train_set for c in (ex.case.get('cannot_targets') or ['(legacy)'])})}")

    # Use halt-on-judge-failure wrapper. Subsequent calls short-circuit
    # after the first JudgeRetriesExhausted, and we touch gepa.stop so the
    # FileStopper halts the run cleanly at the next iteration boundary.
    metric = make_metric_with_halt(use_judge=args.judge, failure_score=0.0)
    judge_label = os.getenv("JUDGE_MODEL", "gpt-5")
    print(f"  Judge: {'ON (' + judge_label + ')' if args.judge else 'OFF (programmatic only)'}")
    print(f"  Judge backend: {os.getenv('JUDGE_BACKEND', 'openai')}")

    # Fresh FormAssistant for GEPA to mutate — the harness's get_agent()
    # singleton is reserved for the preflight check / production reads only.
    program = FormAssistant()

    # ── Optional: apply a prior candidate's prompts as the starting program ──
    start_from_info: dict | None = None
    if args.start_from_state and args.start_from_candidate is not None:
        state_path = Path(args.start_from_state)
        if not state_path.exists():
            sys.exit(f"--start-from-state path not found: {state_path}")
        src_state = pickle.load(open(state_path, "rb"))
        src_candidates = src_state["program_candidates"]
        idx = args.start_from_candidate
        if idx < 0 or idx >= len(src_candidates):
            sys.exit(f"--start-from-candidate {idx} out of range [0, {len(src_candidates)-1}]")
        src_prompts = src_candidates[idx]
        src_baseline = src_candidates[0]
        mutated_modules = [m for m in src_prompts if src_prompts[m] != src_baseline[m]]
        # Verify every module in src_prompts maps to an attribute on the program
        unknown = [m for m in src_prompts if not hasattr(program, m)]
        if unknown:
            sys.exit(
                f"--start-from-state references modules not on FormAssistant: {unknown}. "
                f"Aborting to avoid silent prompt drop."
            )
        print(f"\n── Starting program: candidate {idx} from {state_path} ──")
        print(f"  Modules mutated vs that state's baseline: {mutated_modules}")
        # Apply each module's instructions (this includes both mutated and
        # baseline-identical modules — we set them all so the starting program
        # is exactly that candidate, no implicit fallback to FormAssistant defaults).
        applied = []
        for module_name, instructions in src_prompts.items():
            module = getattr(program, module_name)
            module.signature = module.signature.with_instructions(instructions)
            applied.append((module_name, len(instructions)))
        print(f"  Applied {len(applied)} modules. Sizes:")
        for name, sz in applied:
            mark = " (mutated)" if name in mutated_modules else ""
            print(f"    {name:18s} {sz:>6} chars{mark}")
        start_from_info = {
            "state_path": str(state_path),
            "candidate_index": idx,
            "modules_mutated_vs_source_baseline": mutated_modules,
        }

    # ── Baseline eval ──
    if args.baseline_from:
        if args.baseline_only:
            sys.exit("--baseline-from and --baseline-only are mutually exclusive")
        print(f"\n── Baseline (precomputed from {args.baseline_from}) ──")
        bp = json.loads(Path(args.baseline_from).read_text())
        loaded_ids = [r["test_id"] for r in bp["scores"]]
        current_ids = [ex.case["test_id"] for ex in val_set]
        if loaded_ids != current_ids:
            sys.exit(
                f"Baseline val_set mismatch — precomputed has {len(loaded_ids)} "
                f"cases, current has {len(current_ids)}. First diff: "
                f"loaded[0]={loaded_ids[0] if loaded_ids else None!r} "
                f"vs current[0]={current_ids[0] if current_ids else None!r}. "
                f"Re-run precalc_baseline.py with matching --seed/--train-size/--val-size."
            )
        baseline_avg = float(bp["baseline_avg"])
        print(f"  Loaded {len(loaded_ids)} per-case scores")
        print(f"  Baseline avg: {baseline_avg:.4f}")
    else:
        print("\n── Baseline eval ──")
        # No silent try/except — judge failures must halt the run.
        # (judge.judge_case retries internally; if it still fails, propagate.)
        # See: tuning/gepa/INCIDENT_2026-05-15_judge_silent_fallback.md
        baseline_scores: list[float] = []
        for i, ex in enumerate(val_set):
            pred = program(context=ex.context, user_message=ex.user_message)
            score = metric(ex, pred)
            baseline_scores.append(float(score))
            tid = ex.case["test_id"]
            print(f"  [{i:2d}] {tid:35s} score={score:.3f}")
            if _HALT_STATE["halted"]:
                sys.exit(
                    f"\n[optimize] Halting before GEPA compile — judge failure detected "
                    f"during baseline eval. Cause: {_HALT_STATE['first_error']}"
                )
        baseline_avg = sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0.0
        print(f"\n  Baseline avg: {baseline_avg:.3f}")

        if args.baseline_only:
            return

    # ── GEPA ──
    print(f"\n── GEPA (budget={args.budget}, joint optimization of all 5 modules) ──")
    print(f"  Student:    SFT v2 (canonical) @ localhost:{args.student_port}")
    print(f"  Reflection: {reflection_model_id}")

    gepa_kwargs = dict(
        metric=metric,
        reflection_lm=reflection_lm,
        track_stats=True,
        add_format_failure_as_feedback=True,
        failure_score=0.0,
        reflection_minibatch_size=10,
        num_threads=args.num_threads,
    )
    log_path: Path | None = None
    if args.log_dir is not None:
        log_path = Path(args.log_dir).resolve()
        log_path.mkdir(parents=True, exist_ok=True)
        gepa_kwargs["log_dir"] = str(log_path)
        # Wire the gepa.stop path so the metric wrapper can create it on
        # JudgeRetriesExhausted, triggering DSPy GEPA's built-in FileStopper.
        _HALT_STATE["stop_file"] = str(log_path / "gepa.stop")
        print(f"  Log/checkpoint dir: {log_path}")
        print(f"    (touch {log_path}/gepa.stop for graceful halt)")
    else:
        print(
            "  [warn] --log-dir not set → JudgeRetriesExhausted cannot auto-halt "
            "the run via gepa.stop. The run will continue with failure scores; "
            "you'll need to interrupt manually."
        )
    if args.max_metric_calls is not None:
        gepa_kwargs["max_metric_calls"] = args.max_metric_calls
        print(f"  Budget: max_metric_calls={args.max_metric_calls} (--budget ignored)")
    else:
        gepa_kwargs["auto"] = args.budget
        print(f"  Budget: auto={args.budget}")
    optimizer = dspy.GEPA(**gepa_kwargs)
    optimized = optimizer.compile(program, trainset=train_set, valset=val_set)

    # ── Post eval ──
    print("\n── Post-optimization eval ──")
    # No silent try/except — judge failures must halt the run.
    # If halt was set during compile, skip the post-eval entirely.
    if _HALT_STATE["halted"]:
        print(
            f"  Skipped: judge halt was triggered during compile "
            f"(cause: {_HALT_STATE['first_error']})"
        )
        opt_avg = 0.0
    else:
        opt_scores: list[float] = []
        for i, ex in enumerate(val_set):
            pred = optimized(context=ex.context, user_message=ex.user_message)
            score = metric(ex, pred)
            opt_scores.append(float(score))
            if _HALT_STATE["halted"]:
                sys.exit(
                    f"\n[optimize] Halting during post-eval — judge failure. "
                    f"Cause: {_HALT_STATE['first_error']}"
                )
        opt_avg = sum(opt_scores) / len(opt_scores) if opt_scores else 0.0
    print(f"  Optimized avg: {opt_avg:.3f}")
    print(f"  Improvement:   {opt_avg - baseline_avg:+.3f}")

    # Save
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    program_path = RESULTS_DIR / f"gepa-pilot-{ts}.json"
    optimized.save(str(program_path))
    summary = {
        "schema_version": "2",
        "timestamp": ts,
        "budget": args.budget,
        "max_metric_calls": args.max_metric_calls,
        "train_size": len(train_set),
        "val_size": len(val_set),
        "judge": args.judge,
        "baseline_avg": baseline_avg,
        "optimized_avg": opt_avg,
        "improvement": opt_avg - baseline_avg,
        "env": gepa_metric.capture_judge_env(),
        "config": {
            "student_port": args.student_port,
            "student_model": args.student_model,
            "reflection_model": reflection_model_id,
            "reflection_base_url": args.reflection_base_url,
            "seed": args.seed,
            "log_dir": str(log_path) if log_path else None,
            "baseline_from": args.baseline_from,
        },
        "halt_state": {
            "halted": _HALT_STATE["halted"],
            "first_error": _HALT_STATE["first_error"],
            "stop_file": _HALT_STATE["stop_file"],
        },
        "start_from": start_from_info,
    }
    summary_path = RESULTS_DIR / f"summary-{ts}.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\n  Saved: {program_path}\n         {summary_path}")


if __name__ == "__main__":
    main()
