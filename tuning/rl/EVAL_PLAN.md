# GRPO Evaluation Plan

## Goal

Produce a defensible, reproducible evaluation of the GRPO-trained DataExtractor against:
1. **SFT baseline** — establishes whether GRPO helped at all over the starting point
2. **Training-time reward curves** — verifies held-out generalization vs. training-set overfitting
3. **Across checkpoints** — identifies the best checkpoint (not necessarily the last)

Scope is **limited to the DataExtractor module**. Full-pipeline evaluation (intent, responder, etc.) happens *after* we run GEPA on top of the chosen GRPO model.

---

## What we have

| Resource | Location | Notes |
|---|---|---|
| Base model | `mlx-community/Qwen3.5-0.8B-4bit` (HF cache) | served on :8082 via mlx_vlm |
| SFT LoRA | `~/work/models/qwen35-08b-dspy-format-lora/` | format-compliant starting point |
| SFT merged | `~/work/models/qwen35-08b-dspy-format-mlx/` (1.6GB fp16) | served on :8084 via mlx_vlm |
| GRPO checkpoints | Modal Volume `grpo-checkpoints/grpo_outputs/checkpoint-{300,600,900,1200,1500,1800}/` | adapter + optimizer state |
| GRPO final LoRA | Modal Volume `grpo-extractor-lora/` | currently checkpoint-1800 |
| GRPO merged | Modal Volume `grpo-extractor-merged/` | currently checkpoint-1800 merged |
| Training data | `tuning/rl/grpo_extractor_mutated.jsonl` (41,767 examples) | seed=42 |
| Data generator | `tuning/rl/gen_grpo_data.py` | supports `--seed` |
| Reward functions | `tuning/rl/train_grpo_modal.py` lines 159-239 | format, accuracy, hallucination |
| Existing eval harness | `tuning/sft/compare_models.py` | server-based, reusable |

---

## Design decisions

### 1. Test set — reuse SFT's `tuning/data/test-cases.jsonl` (300 cases)

**Decision: reuse the 300-case SFT test set as-is. Do not generate new synthetic data.**

Rationale:
- **Cross-experiment consistency** — same test set already used for SFT eval and future GEPA runs; enables direct comparison
- **Better realism than synthetic** — cases include real `form_state_before` and `conversation_history`; `gen_grpo_data.py` produces flat synthetic prompts
- **Natural coverage of both positive and hallucination scenarios**:
  - **151 positive cases** (`set_fields` action): expected extraction, measures accuracy
  - **86 non-extractor cases** where extractor should return empty: measures hallucination
  - **63 other cases** (show_preview, show_fields, etc.): extractor still runs, should stay empty
- Training used the GRPO mutated set (41K examples, seed=42), which has zero overlap with the SFT test set by construction
- Sample size of 300 is sufficient to distinguish 8 models

**Format note**: SFT test cases have different schema than GRPO training data. `eval_grpo.py` will:
1. Load test cases
2. Build DSPy ChatAdapter-formatted prompts using `build_context()` and `DataExtractorSignature` (reuse from `compare_models.py`)
3. Extract ground truth from `expected_fields_set` (for positive cases) or empty list (for others)

**No new synthetic data**. `gen_grpo_data.py` remains for *training* data only.

### 2. Checkpoints to evaluate

Fixed sweep:
- **base** — raw `Qwen3.5-0.8B-4bit`
- **SFT** — `qwen35-08b-dspy-format-mlx`
- **GRPO-300, 600, 900, 1200, 1500, 1800** — all 6 GRPO checkpoints

Total: **8 models × 300 examples = 2,400 inferences**

### 3. Metrics

**Primary task metrics** (computed per example, aggregated):

| Metric | Definition | Why it matters |
|---|---|---|
| `format_ok` | Has `[[ ## field_ids ## ]]`, `[[ ## field_values ## ]]`, `[[ ## completed ## ]]`, and parses | Basic sanity |
| `field_id_precision` | `\|GT ∩ Pred\| / \|Pred\|` | Over-extraction (hallucination risk) |
| `field_id_recall` | `\|GT ∩ Pred\| / \|GT\|` | Under-extraction (missing info) |
| `field_id_f1` | Harmonic mean of precision/recall | Overall ID accuracy |
| `value_exact_match` | Fraction of matched IDs where value matches GT | Extraction accuracy |
| `hallucination_rate` | Fraction of Pred IDs not in form schema | Schema adherence |
| `empty_correct` | When GT is empty, did model return empty? | Avoid false extractions |
| `avg_completion_length` | Mean chars in output | Detect mode collapse / rambling |

**Secondary (reference)**:
- `training_reward_equivalent` — re-run the exact training reward functions on held-out predictions for apples-to-apples comparison with training curves
- `latency_ms` — per-request time

### 4. Execution environment

**Decision: run locally.**

Measured baseline (10 examples on SFT mlx_vlm on M1 Pro):
- Avg **2.5 s/request**
- 300 examples ≈ **12 min/checkpoint**
- 8 checkpoints × 300 examples ≈ **~100 min total inference** (sequential)
- Plus ~5-10 min model swap overhead per checkpoint ≈ **+60 min**
- **Expected total: 2.5-3 hours**

Tradeoff vs. Modal:
- Local: free, same environment we'll ship in, but slow
- Modal L4: ~$2, ~30 min total, but extra setup + cost + not representative of deployment

Local wins. If we need to iterate (add metrics, re-run), 3-4 hours is acceptable.

### 5. Model serving strategy

Each checkpoint served via `mlx_vlm.server` using the **merged model** (not LoRA + base), because:
- Avoids per-request adapter loading overhead
- mlx_vlm handles merged models directly
- Matches how we'd deploy in production

**Download pipeline** (one-time):
```bash
# Per checkpoint: download merged model from Modal, rename
modal volume get grpo-checkpoints grpo_outputs/checkpoint-300/ /tmp/ckpt-300/
# (need to merge locally OR get the already-merged version if it was saved)
```

**Problem**: only `checkpoint-1800` has a pre-merged version on the volume. For 300/600/900/1200/1500 we need to either:
- **(a)** Merge locally after download — requires loading base model + LoRA + merge step
- **(b)** Add a one-off Modal job that merges all 6 checkpoints and saves them to the volume
- **(c)** Serve each checkpoint as LoRA + base via a different server setup (not mlx_vlm's strength)

**Choice: (b)** — one Modal job loops over all 6 checkpoints, merges each, saves to volume at `merged/checkpoint-{N}/`. Then bulk-download all.

### 6. Eval harness design

New script: `tuning/rl/eval_grpo.py`

Reuse from `compare_models.py`:
- Server calling pattern (`call_model(url, messages)`)
- Format analysis (`FIELD_MARKER_RE`, etc.)

New logic:
- Load test set from `grpo_eval_set.jsonl` (prompts already formatted, no DSPy adapter needed)
- Compute the 8 primary metrics above per example
- Aggregate by checkpoint
- Output:
  - `eval_results_{checkpoint}.jsonl` — per-example predictions + scores
  - `eval_summary.csv` — one row per checkpoint with all metrics
  - `eval_learning_curve.png` — held-out metric vs. training step, with training reward overlaid

**CLI**:
```bash
uv run python tuning/rl/eval_grpo.py \
    --eval-set tuning/rl/grpo_eval_set.jsonl \
    --url http://localhost:8084/v1/chat/completions \
    --model-path ~/work/models/grpo-ckpt-1500-mlx \
    --checkpoint-name grpo-1500 \
    --output tuning/rl/eval_results/
```

Then a meta-runner iterates over all 8 servers/models.

### 7. Validation & sanity checks

Before trusting the numbers:
- Re-run SFT eval on a small slice and compare to existing `compare_models.py` SFT numbers (should be very close on overlapping metric: format_ok ~99.3%)
- Run 10 examples on the base model first to confirm it fails at the expected rates (<1% format_ok, per SFT eval findings)
- Manually inspect 5-10 predictions per checkpoint to spot-check anything weird (e.g., mode collapse = very short outputs, reward hacking = bizarre field picks)

---

## Execution plan (ordered steps)

1. **Modal merge job** — one-off: loop over 6 checkpoints, merge each, save to volume (~30 min on L4)
2. **Download merged models** — pull all 6 GRPO merged models locally (~10-20 min depending on bandwidth)
3. **Write `eval_grpo.py`** — reuse `compare_models.py` patterns (signatures, build_context, format analysis)
4. **Dry-run on SFT + 10 examples** — validate metrics against existing SFT eval numbers (format_ok should be ~99.3% to confirm harness is correct)
5. **Full eval sweep** — 8 checkpoints × 300 examples (~2.5-3 hours)
6. **Generate report** — `eval_summary.csv`, `eval_learning_curve.png`, `eval_report.md`
7. **Identify best checkpoint** — pick by combined held-out metric (not training reward)
8. **Document findings** — update `docs/doc-12-tuning-journal.md` Experiment 7

---

## Sampling config

- **Temperature**: `0` (greedy, deterministic). Matches how we'll deploy. Training used T=1.0 with `num_generations=4` for RL variance; that's a training-only requirement, not relevant to eval.
- **Max tokens**: 512 (same as training).
- **Schema coverage**: training used one form schema (`masters-northfield.json`). Generalization to new schemas is out of scope for this round.

---

## Deliverables

- `tuning/rl/eval_grpo.py` — eval harness (reuses `tuning/data/test-cases.jsonl`)
- `tuning/rl/eval_results/` — per-checkpoint predictions + metrics
- `tuning/rl/eval_summary.csv` — comparison table
- `tuning/rl/eval_learning_curve.png` — held-out metrics vs. training step
- Update to `docs/doc-12-tuning-journal.md` Experiment 7 with final results
