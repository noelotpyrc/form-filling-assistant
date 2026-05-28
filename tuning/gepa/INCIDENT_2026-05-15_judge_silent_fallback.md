# Incident — Silent judge-failure fallback inflated GEPA candidate scores

**Date:** 2026-05-15
**Affected artifacts:**
- `tuning/gepa/results/baseline_sft_v2_claude_conf_n3.json` (precalc_baseline.py @ 2026-05-14 15:10)
- `tuning/gepa/results/run_full_claude_judge_20260514_1617/gepa_state.bin` (optimize.py @ 2026-05-14 16:17–20:56)
- `tuning/gepa/results/eval_candidate2_fresh.json` (eval_candidate.py @ 2026-05-14 21:50)

**Outcome:** Candidate 2 was selected by GEPA as a winner with a reported +0.087 val-set lift over baseline. Subsequent fresh-eval reported +0.061 lift. Both numbers were largely artifacts of a silent failure path in the metric; the actual candidate effect (measured under a working judge on a deterministic re-run) is roughly zero or slightly negative.

## Symptom

- `eval_candidate2_fresh.json` showed several cases at score 0.85–1.0 that, on a deterministic-pred re-run with a working judge, cluster tightly around 0.10–0.50 (M=10 trials, σ ≤ 0.02).
- Example: `legacy-single_field_239` — stored 0.854, today's M=10 cluster mean 0.457 ± 0.017 (23σ off).
- No `error` rows or `score: 0.0` rows in any artifact, so the failures left no upstream signature.

## Root cause

`tuning/gepa/metric.py` (lines 402–413, before fix) caught judge exceptions silently:

```python
try:
    answers = judge_case(case, pred, rubric)
except Exception as e:
    # Judge failure shouldn't crash the metric; record as a failed
    # informational check and proceed with programmatic-only score.
    checks.append(CheckResult(
        name="judge_error",
        passed=False,
        detail=f"judge call failed: {e}",
    ))
    weights.append(0.0)  # don't weight a system error
    return _aggregate_text(checks, weights)
```

When `judge_case` raised (e.g., `claude -p` exited non-zero or returned a usage-limit message that failed to parse as a JSON float list), the metric:
1. Appended an `informational` check with weight 0 (does not surface).
2. Returned the score with only the programmatic text_responder check (`no_persona_leak`, weight 0.5, trivially passes on most cases → score 1.0).

With module weights `text_responder: 0.55` (vs other modules summing to 0.45), a silent failure inflates the composite by approximately `0.55 × (1.0 − true_text_responder_score)`. On cases where the true judge would give text_responder ~0.1–0.3, the silent path lifts the case score by 0.4–0.5.

## Evidence

| test_id | yest score | today M=10 mean | σ | observed Δ | predicted if silent failure: 0.55·(1−judged) |
|---|---|---|---|---|---|
| legacy-single_field_239 | 0.854 | 0.457 | 0.017 | +0.40 | ≈ +0.40 |
| legacy-ask_choice_only_23 | 0.911 | 0.475 | 0.012 | +0.44 | ≈ +0.45 |
| legacy-question_no_actions_227 | 0.611 | 0.139 | 0.009 | +0.47 | ≈ +0.50 |

Across the full 122-case val set, baseline_sft_v2 → val_subscores[2] showed mean Δ = +0.085 (matches GEPA's reported lift). On the 112 cases where baseline and candidate preds are byte-identical (verified by `gen_cand_preds.py`), today's same-script-run re-scoring with working judge shows mean Δ = −0.001 ± 0.015 (σ). So the apparent +0.085 lift is mostly the silent-failure inflation accumulated across cases where the judge failed during yesterday's runs.

The user's `/loop` message from 2026-05-14 17:27 PT — "You're out of extra usage · resets 7:20pm (America/New_York)" — confirms a Claude Code usage limit was hit during the GEPA run window (16:17–20:56 PT). The headless judge calls would have failed at that point. Without the silent fallback, GEPA's compile loop would have halted with a visible error; with the fallback, candidate 2's score got inflated by the fraction of its evaluation calls that hit the limit.

## Why per-case judge variance was the wrong explanation

Earlier in the investigation, the inter-run drift on byte-identical preds was hypothesized to be judge run-to-run variance. Directly measured within-run per-case σ (M=10 trials per case, same script run, same env):

| test_id | within-run σ | spread |
|---|---|---|
| legacy-single_field_239 | 0.017 | 0.066 |
| legacy-ask_choice_only_23 | 0.012 | 0.038 |
| legacy-question_no_actions_227 | 0.009 | 0.026 |
| legacy-single_field_265 | 0.000 | 0.000 |
| legacy-choice_selection_75 | 0.002 | 0.005 |

The drift was 20–50× larger than the within-run σ. Working-judge variance alone could not explain it. The asymmetric magnitude (drift always pushes scores upward by ~0.4–0.5, never the reverse) is the fingerprint of the 0.55-weight fallback.

## Fix

1. `tuning/gepa/judge.py:judge_case` now wraps both backends in a 3-attempt retry-with-backoff loop (5s, 15s). After 3 failures, the exception propagates.
2. `tuning/gepa/metric.py:score_text_responder` removes the silent `except Exception` around `judge_case`. Judge failures now propagate up through `score_case → metric → eval loop`, terminating the run.
3. `eval_candidate.py` and `precalc_baseline.py` already write a row-level `error` field on exception; with the fix, that field now actually captures judge failures instead of being permanently `null`.

## Rule going forward

- **Never let the judge fail silently.** The judge is the primary signal for text_responder, which is the highest-weight module. A failed judge call means the case is unscored — full stop. Errors should surface immediately so the operator can pause, wait for the usage window to reset, and resume.
- **Verify with M=10 trials** when investigating any inter-run drift that exceeds within-run σ × 3. If you see drift much larger than measured within-run noise, suspect failure-path inflation before suspecting model drift.

## Files modified by this incident

- `tuning/gepa/metric.py` — removed silent except in `score_text_responder` (around line 402–413).
- `tuning/gepa/judge.py` — added retry loop in `judge_case`.
- `tuning/gepa/eval_candidate.py` — already persists preds + env (added 2026-05-15 morning).
- `tuning/gepa/precalc_baseline.py` — same.
