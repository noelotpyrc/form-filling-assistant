# GEPA Optimization Trials

## Setup

- **Student LM**: Qwen3.5-0.8B-4bit via MLX (localhost:8082)
- **Reflection LM**: GPT-5 via OpenAI API
- **Dataset**: 300 test cases from simulation JSONL logs (210 train / 90 val)
- **Intent distribution**: gather 147, clarify 54, converse 49, close 29, review 21
- **Architecture**: 5-module decomposition (IntentDecider → TextResponder → DataExtractor → ChoiceBuilder → ReviewBuilder)
- **MLflow experiment ID**: 584096502307395351

---

## Earlier MLflow runs (context unknown)

MLflow runs exist from before this tracking started. Listed here for reference only — context and config details are not verified.

| Run ID | MLflow name | Metric logged |
|--------|-------------|---------------|
| `6e242eff` | eval_0 | 56.12 |
| `e7ce7a8c` | eval_1 | 76.67 |
| `eb212b6f` | eval_2 | 48.75 |
| `bb1ff772` | merciful-zebra-33 | 56.12 → 76.67 → 48.75 (3 checkpoints) |

---

## Trial 2 — 2025-03-25 (current, stopped at 34%)

**Config changes from Trial 1**:
- IntentDecider and TextResponder switched from `ChainOfThought` → `Predict` (fix for reasoning blowup)
- try/except fallbacks added around all modules (to prevent process crashes)
- Context trimmed: history 6→3 messages, 300→150 chars, form_state values truncated to 50 chars
- `max_tokens=512` on student LM
- Over-extraction feedback added to DataExtractor metric
- Temperature: 0.0

**Baseline**: 0.386 (10-example sample)

```
[0] intent=converse score=0.38 | user: [system] User selected option: "Type it in manually"
[1] intent=converse score=0.38 | user: [File: jane-transcript.pdf]
[2] intent=clarify score=0.22 | user: No disability accommodations needed...
[3] intent=close  score=0.27 | user: [system] User selected option: "Yes"
[4] intent=clarify score=0.30 | user: Before saving — the progress bar shows...
[5] intent=converse score=0.38 | user: Oh okay that makes sense...
[6] intent=close  score=0.27 | user: [system] User selected option: "No"
[7] intent=converse score=0.38 | user: [system] User selected option: "Full-time"
[8] intent=converse score=0.93 | user: The panel is showing recommendations...
[9] intent=converse score=0.38 | user: Oh, I should probably add those...
```

**Observation**: Model defaults to `converse` for most inputs. Only [8] scored well (0.93).

**GEPA progress** (36 iterations, ~2 hours, 985/2895 rollouts):

| Metric | Value |
|--------|-------|
| Baseline avg | 0.386 |
| Best program score (trainset subsample) | 0.521 |
| Best valset score | 0.521 |
| Valset pareto front aggregate | 0.656 (iter 33) |

**Score plateau**: Best score stuck at 0.521 from iteration 16 onward (no improvement in 20 iterations).

**Key issue**: "No valid reflective examples found for data_extractor" / "No valid predictions found for any module" on nearly every iteration. GEPA could not perform guided reflection — only random mutations.

**Root cause identified**:
1. Our `try/except` around module calls intercepted `AdapterParseError` before DSPy's `bootstrap_trace_data` could catch it and record `FailedPrediction` in the trace. Without trace entries, GEPA's `make_reflective_dataset()` found nothing to reflect on.
2. `add_format_failure_as_feedback` defaults to `False` — even if failures were traced, GEPA would filter them out instead of showing the reflection LM what went wrong.

**Action**: Stopped run. Will fix both issues for Trial 3.

---

## Trial 3 — Planned

**Changes**:
1. Remove try/except around module calls — let `AdapterParseError` propagate to DSPy's `patched_forward()` which converts it to `FailedPrediction` with raw text preserved in trace
2. Set `add_format_failure_as_feedback=True` in GEPA constructor — reflection LM sees malformed output + expected format → generates better instructions
3. Consider bumping temperature from 0.0 to 0.1–0.2 for diversity during optimization

**Expected outcome**: GEPA can now perform guided reflection on format failures, which should improve structured output compliance and break through the 0.521 plateau.

---

## Known Issues

1. **Truncation warnings** (`max_tokens=None`): DataExtractor sometimes generates huge JSON dumps (entire form state). The `max_tokens=512` limit helps but warnings still appear occasionally. DSPy retries and succeeds.
2. **Temperature 0.0**: Fully deterministic — may cause repetition loops and limit GEPA's ability to explore diverse outputs during optimization.
3. **3-example subsample for iteration evals**: GEPA uses tiny subsamples per iteration for speed, which makes per-iteration scores noisy.
4. **Conditional module execution**: DataExtractor/ChoiceBuilder/ReviewBuilder only run for certain intents. If the small model mispredicts intent (e.g., always `converse`), those modules never get called or traced.
