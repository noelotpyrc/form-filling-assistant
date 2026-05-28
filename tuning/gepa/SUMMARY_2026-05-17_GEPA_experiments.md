# GEPA experiments summary (2026-05-14 → 2026-05-17)

Result: across **9 GEPA runs** with **5 different judges** and **3 different teachers**, the SFT-v2 student shows at most **+0.005 val lift** over baseline that survives noise/calibration scrutiny. GEPA does not produce a meaningful prompt-side improvement on this student + eval combo.

This doc records what we tried, what we learned about the infrastructure, and why GEPA isn't moving the needle here.

## TL;DR conclusions

1. **GEPA does not yield meaningful prompt-side lifts on SFT-v2 for this 122-case val set.** The best validated lift across all runs is on the order of judge noise (σ ≈ 0.01–0.02 per case, σ_mean ≈ 0.002 across 122 cases). Any putative gain of +0.005 or smaller is indistinguishable from re-evaluation noise.

2. **The SFT-v2 student does not faithfully follow mutated prompts.** When GEPA proposes longer or substantively different prompts, the student either (a) produces output the DSPy adapter cannot parse → `failure_score=0` cases or (b) ignores the new instructions and produces nearly the baseline output. Of 122 val cases, only ~8% had byte-different predictions between baseline and any GEPA-mutated candidate.

3. **Infrastructure now solid.** Silent failure modes (judge fallback, num_threads incompatibility, etc.) were identified and fixed. Future prompt-optimization experiments can use this framework reliably.

## Why we stopped

Per-case judge variance (σ ≈ 0.01–0.06 depending on judge) is comparable in magnitude to any GEPA-found "improvement" (≤ +0.005). With ~8% of val cases byte-different and the rest indistinguishable from baseline, no proposed mutation has shown a real signal that survives re-evaluation. Spending more budget on more iterations would explore deeper but is unlikely to break through this ceiling.

The bottleneck is the **student's prompt-following capacity**, not GEPA. SFT-v2 was trained on a specific output distribution; GEPA's proposed mutations don't shift it far from that distribution because the model can't comply with the new instructions in detail.

## Recommended next steps (not done here)

- **SFT another generation** with examples that include the desired mutated-prompt behavior. Then re-run GEPA on top of the new SFT model — there may be more headroom when the student can actually follow new instructions.
- **Tighten the eval set's signal-to-noise**: if cases scoring near 0.5–0.7 dominate the noise band, restructure rubrics to give cleaner pass/fail decisions where they matter.
- **Try in-context-learning instead of GEPA** — measure the SFT model's behavior with few-shot examples of the target behavior, no prompt mutation.

## Run-by-run log

### Run 1 — 2026-05-14 16:17 (CONTAMINATED — pre-fix)

- **Config**: claude_headless judge (opus-4-7, N=3), deepseek-v4-flash teacher, max=2000, val=122
- **Result**: 9 candidates, reported best cand 2 val 0.9137 → "+0.087 lift" was the headline
- **What went wrong**: Discovered on 2026-05-15 that `metric.py` had a silent `except Exception` around `judge_case` that fell back to programmatic-only scoring. With `text_responder` weight 0.55 and a trivial persona-leak check (weight 0.5), silent judge failures inflated case scores by ≈ 0.55 × (1.0 − true_judge_score). Confirmed via M=10 within-run trials: cases stored at 0.85 actually cluster around 0.45 under a working judge.
- **Documented in**: `INCIDENT_2026-05-15_judge_silent_fallback.md`
- **Status**: Discarded. Artifacts retained at `results/run_full_claude_judge_20260514_1617/`.

### Run 2 — 2026-05-15 16:24 (post-fix, halted by Claude Code usage)

- **Config**: claude_headless judge + deepseek teacher, with silent-fallback fix + retry-then-halt + pred persistence
- **Result**: 3 iterations completed, best cand 2 (text_responder mut) val 0.8337 (+0.0055 over baseline 0.8282)
- **Halt cause**: Claude Code subscription's "extra usage" limit hit at iter 3
- **Artifacts**: `results/run_full_claude_judge_20260515_1545/`

### Run 3 — 2026-05-15 20:04 (resume of Run 2)

- **Result**: Iter 4–8, 4 more candidates added (all worse than cand 2 from Run 2). Halted at iter 9 by usage limit again.
- **Best overall**: still cand 2 at 0.8337
- **Artifacts**: Same dir as Run 2 (`gepa_state.bin` updated).

### Run 4 — 2026-05-16 09:08 (clean restart from cand 2)

- **Config**: `--start-from-state` + `--start-from-candidate 2` (so cand 2 from Run 2 becomes the new baseline). Same judge/teacher.
- **Result**: Iter 1 found further action_router refinement (val 0.8350). Iter 3 merge action_router + text_responder → **val 0.8388** (best of this thread).
- **Halt cause**: Claude Code usage limit again at iter 5
- **Cumulative lift over original SFT baseline (0.828)**: ≈ +0.011 (but inflated by judge variance — see infrastructure notes)
- **Artifacts**: `results/run_full_claude_judge_20260516_0908_fromcand2/`

### Run 5 — 2026-05-16 16:47 (DeepSeek both sides)

- **Config**: deepseek-v4-flash judge + deepseek-v4-flash teacher, num_threads=4 (with LiteLLM executor patch — see infra notes)
- **Result**: 24 iterations, best val = baseline 0.7917. **No improvement found.**
  - 7 candidates added (all worse than baseline by 0.005–0.015)
  - 13 skipped at subsample, 2 reflection-failed, 1 merge-skipped, 1 halt
- **Halt cause**: First `JudgeRetriesExhausted` from DeepSeek empty responses at iter 24
- **Why no improvement**: DeepSeek judge variance σ ≈ 0.025–0.047 per case + DeepSeek teacher proposing prompts the SFT model can't faithfully follow
- **Artifacts**: `results/run_full_deepseek_20260516_1647/`

### Run 6 — 2026-05-17 08:14 (DeepSeek judge + Sonnet teacher, v1)

- **Halt cause**: `JudgeRetriesExhausted` during iter-0 baseline eval, before any GEPA iteration started. DeepSeek's malformed-JSON rate was high enough that all 3 retries also failed.
- **Discarded; led to the partial-ensemble fix below.**

### Run 7 — 2026-05-17 09:36 (DeepSeek + Sonnet, v2, partial-ensemble fix)

- **Config**: Same as Run 6 + judge tolerates N-of-N partial-ensemble (only halt if ALL N=3 calls fail)
- **Result**: Still hit halt at iter 0 baseline eval as DeepSeek had a sustained reliability dip (3 retries × 3 calls each all empty)
- **User halted**: "DeepSeek is unusable" — moved on
- **Artifacts**: `results/run_full_deepseek_judge_sonnet_teacher_20260517_0936_v2/`

### Run 8 — 2026-05-17 12:03 (Tencent judge + Sonnet teacher)

- **Pre-run check**: Tencent/hy3-preview variance test (5 cases × 10 trials) showed σ ≈ 0.02–0.06, 0 errors over 150 calls — looked viable
- **Live result**: Halted at baseline case 13 by `JudgeRetriesExhausted`. Tencent's failure rate jumped from ~0% in the variance test to ~10% under real load.
- **Artifacts**: `results/run_full_tencent_judge_sonnet_teacher_20260517_1203/`

### Run 9 — 2026-05-17 15:05 (GPT-5 judge + Sonnet teacher) — **FINAL**

- **Config**: gpt-5 via OpenAI API (judge), claude-sonnet-4.6 via OpenRouter (teacher), num_threads=4, partial-ensemble tolerant, halt-on-judge-failure
- **Pre-run variance**: GPT-5 σ ≈ 0.01–0.06, 0 errors over 150 calls
- **Result**: **Run completed full budget cleanly** (2000 metric calls, 24 iterations, ~7h45m, ~$50 OpenRouter cost)
  - Baseline val: 0.8172 (GPT-5 calibration; matches Claude headless's 0.8282 within calibration drift)
  - **Best candidate**: cand 13 (choice_builder mut on cand 12), val 0.8196 — **+0.0024 over baseline**
  - 13 candidates added, most worse than baseline; the +0.0024 winner barely separates from noise
- **Post-optimization re-eval of cand 13**: 0.815 — slightly below the original baseline 0.822, well within judge re-eval variance (per-case σ ≈ 0.02, σ_mean across 122 ≈ 0.002, so 0.005–0.010 shifts on re-eval are expected)
- **Artifacts**: `results/run_full_gpt5_judge_sonnet_teacher_20260517_1505/`, `gepa-pilot-20260517T224854.json`, `summary-20260517T224854.json`

## Judge variance reference table

5 fixed val cases (`legacy-single_field_239`, `legacy-ask_choice_only_23`, `legacy-question_no_actions_227`, `legacy-single_field_265`, `legacy-choice_selection_75`), M=10 trials each, same script-run, N=3 ensemble. Predictions byte-identical across all judges (from `paired_preds_cand2.json`).

| Judge | Within-run σ range | Wall (5×10 trials × N=3) | Reliability (live runs) |
|---|---|---|---|
| claude_headless (opus-4-7) | 0.000 – 0.017 | ~5 min | high; subscription usage limits |
| moonshotai/kimi-k2.6 | 0.000 – 0.012 (1 case) | ~33 min/case | unknown — too slow/expensive for full run |
| deepseek/deepseek-v4-flash | 0.000 – 0.047 | ~21 min | low — high malformed-JSON rate in production |
| tencent/hy3-preview | 0.000 – 0.060 | ~68 min | brittle — works in test, fails under live load |
| **gpt-5** (OpenAI direct) | 0.000 – 0.062 | ~12 min | **high — full run completed cleanly** |

Variance test artifacts: `judge_variance_5x10_*.json`.

## Infrastructure work product

Code changes made during this experiment (still in place):

- **`judge.py`**: Added `JudgeRetriesExhausted` class, 3-attempt retry-with-backoff in `judge_case`, dispatch for `JUDGE_BACKEND=claude_headless` and `JUDGE_BACKEND=openrouter`. Configurable backoff and max-attempts via env.
- **`judge_claude_headless.py`**: N=3 parallel subprocess calls, element-wise mean, confidence-score rubric design.
- **`judge_openrouter.py`**: N=3 parallel OpenAI-client calls (works against any OpenAI-compatible endpoint — used for OpenRouter and direct OpenAI). Partial-ensemble tolerant (averages over the N calls that succeed; only raises when all N fail). Env-configurable temperature so GPT-5 (which only accepts default 1.0) works alongside others.
- **`metric.py`**: Removed silent `except Exception` around `judge_case`. Added `pred_to_flat_dict` and `capture_judge_env` helpers for persisting predictions inline with scores. `score_text_responder` now propagates judge failures.
- **`optimize.py`**: 
  - Added `--num-threads` (DSPy parallelism for val/subsample eval).
  - Added `--start-from-state`/`--start-from-candidate` (clean restart from a prior candidate as the new baseline).
  - Added halt-on-judge-failure wrapper (`make_metric_with_halt`): catches `JudgeRetriesExhausted`, touches `gepa.stop` so DSPy's `FileStopper` halts at the next iteration boundary, short-circuits subsequent calls so we don't burn cost while waiting for the halt to register.
  - Removed silent try/except in baseline + post-eval loops (no more swallowed errors).
  - Schema v2 output: `env` + `config` + per-row `pred` + `halt_state` + `start_from` blocks.
- **`eval_candidate.py` / `precalc_baseline.py`**: Same schema v2 changes — persist preds inline with scores, env block, partial-save on judge failure.
- **`_litellm_executor_fix.py`**: Resilient wrapper around LiteLLM's module-level `ThreadPoolExecutor` to fix `cannot schedule new futures after shutdown` errors under `num_threads > 1` with Python 3.13 + DSPy 3.1.3 + LiteLLM 1.82.6.

Inspection / diagnostic scripts (kept for future reuse):

- **`sanity_check_baseline.py`** — verifies stored baseline preds match fresh re-inference (student determinism check)
- **`gen_cand_preds.py`** — re-runs candidate inference on full val_set, persists preds (deterministic, no judge)
- **`score_differing.py`** — scores only byte-different baseline/cand pred pairs with composite metric
- **`pick_from_scored.py`** — picks boost/regression examples from scored paired-preds output
- **`measure_judge_variance.py`** — per-case M-trial variance measurement (the cross-judge reference table above)
- **`verify_judge_drift.py`** — same-run scoring of byte-identical pairs to characterize within-run vs across-run variance
- **`test_num_threads.py`** — timing harness for num_threads parallelism

## Related docs in this directory

- `INCIDENT_2026-05-15_judge_silent_fallback.md` — root cause of the +0.087 "lift" in Run 1
- `HANDOFF_20260511.md` — earlier handoff (pre-incident, partially outdated)
