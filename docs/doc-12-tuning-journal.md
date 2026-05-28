# Doc 12: Tuning Journal

Detailed experiment log for teaching small models (Qwen3.5-0.8B, 4B) to produce structured output for our form-filling assistant. Each experiment records config, results, and lessons learned.

## Tuning Pipeline (revised order)

```
Step 1: Format SFT — teach model to output DSPy structured format
Step 2: Constrained decoding — enforce valid structure at token level (Outlines/GBNF)
Step 3: Task SFT — fine-tune on form-filling task data from simulation logs
Step 4: GEPA prompt optimization — optimize per-module prompts on a format-competent model
```

GEPA was originally tried first (before format SFT). It proved the approach works but hit a hard ceiling because the model couldn't produce valid structured output. Lesson: teach format first, optimize content last.

## Experiment 1: DSPy GEPA — Prompt Optimization (Qwen3.5-0.8B)

### Setup

- **Student LM**: Qwen3.5-0.8B-4bit via MLX (localhost:8082)
- **Reflection LM**: GPT-5 (OpenAI API, temperature=1.0)
- **Framework**: DSPy GEPA (Guided Evolution of Prompt Architecture)
- **Test data**: 300 examples from simulation logs (210 train, 90 val)
- **Intent distribution**: gather 49%, clarify 18%, converse 16%, close 10%, review 7%
- **Metric**: Combined score — intent accuracy (0.3), text quality (0.15), field extraction F1 (0.3), choice accuracy (0.15), review accuracy (0.1)
- **5-module decomposition**: IntentDecider → TextResponder → DataExtractor → ChoiceBuilder → ReviewBuilder

### Trial 2: Predict modules, try/except fallbacks

- **Date**: 2026-03-25
- **Config**: `ChainOfThought` → `Predict` for IntentDecider and TextResponder. Try/except around each module call with fallback defaults.
- **Baseline**: 0.386 (format failures get partial credit from fallback values)
- **Best score**: 0.521 at iteration 13 (34% complete, ~1.5 hours)
- **Reflection success**: 0 out of 60 attempts. "No valid reflective examples" on every iteration.
- **Root cause**: Try/except wrappers prevented DSPy from recording trace entries for failed module calls. Without traces, GEPA's `make_reflective_dataset()` found no valid predictions to reflect on. All improvement came from random mutations only.
- **Stopped at**: 34% (1h50m). Score plateaued at 0.521.
- **Lesson**: Don't catch errors that DSPy needs to see. Let `AdapterParseError` propagate so `FailedPrediction` gets recorded in the trace.

### Trial 3: Let AdapterParseError propagate + format failure feedback

- **Date**: 2026-03-25
- **Config changes from Trial 2**:
  - Removed try/except around module calls
  - Added `add_format_failure_as_feedback=True` to GEPA constructor
  - Increased `reflection_minibatch_size=10` (default 3 too small for 5 conditional modules — with 3 random samples and 5 intents, 87%^3 = 66% chance of missing any given module)
- **Baseline**: 0.131 (format failures now score 0 instead of getting partial credit)
- **Best score**: 0.548 at iteration 13 (4.2x improvement over baseline)

#### Score progression

| Iteration | Best Valset Score | Event |
|-----------|------------------|-------|
| 0 | 0.131 | Baseline (9/10 examples fail with AdapterParseError) |
| 2 | 0.387 | After intent_decider + text_responder prompt improvements |
| 4 | 0.421 | After data_extractor prompt |
| 9 | 0.424 | After review_builder prompt |
| 12 | 0.498 | After improved text_responder prompt |
| 13 | 0.548 | After merged programs 3+4. Best score achieved. |
| 14-23 | 0.548 | Plateau — 10 new prompts proposed, none improved best score |
| 23 | 0.548 | **Stopped** at 43% (52 min). No improvement for 27 min. |

#### GEPA-proposed prompt improvements

All 5 modules received reflective prompt improvements:

- **intent_decider**: "You are classifying the assistant's next-turn intent in an in-progress form-filling conversation. Return exactly one of: gather, converse, clarify, close, review."
- **text_responder**: "You are a conversational form-filling assistant. Your goal is to acknowledge what the user said, be helpful and concise, and guide them smoothly through completing the form."
- **data_extractor**: "You are a form-field extractor. Your only job is to read the provided context and the latest user_message, extract any form field values the user explicitly provided in that message, and output them in the exact structure below. Do not include any explanations or extra text."
- **choice_builder**: "You are generating a single multiple-choice question to collect the next needed piece of information for the Northfield University Graduate Application form. Only generate a multiple-choice question when the next missing field is actually a choice-type (select, multi_select, or boolean). Do not fabricate choices for free-text, numbers, dates, files, or descriptive fields."
- **review_builder**: "Task: Generate a form progress summary for the user."

#### Common failure modes observed

1. **Intent with quotes**: Model outputs `"gather"` instead of `gather` → DSPy JSONAdapter parse failure
2. **Free-form text**: TextResponder generates conversational text without `[[ ## response_text ## ]]` wrapper → DSPy can't find the output field
3. **Type errors**: DataExtractor outputs `False` (bool) in a `list[str]` field → Pydantic validation error
4. **Runaway repetition**: Model fills entire context with repeated text → truncation (`finish_reason='length'`)
5. **Over-extraction**: DataExtractor dumps all known fields from context instead of just current user message fields

#### DSPy signature matching issue

Debug logging revealed why reflections fail intermittently:

```
traj[0] no match for choice_builder (sig=SignatureMeta), trace has: ['SignatureMeta', 'SignatureMeta']
```

`signature.equals()` (line 224 of `gepa_utils.py`) compares instructions:
```python
trace_instances = [t for t in trace if t[0].signature.equals(module.signature)]
```

But `equals()` checks `cls.instructions != other.instructions` (line 475 of `signature.py`). Since GEPA **mutates instructions** during optimization, traces recorded with old instructions don't match modules with new instructions. This is likely a DSPy design issue — traces from iteration N can't match modules after iteration N+1's mutation.

**Impact**: Reflections work in early iterations (before significant instruction divergence) but fail more often as optimization progresses. This may partly explain the plateau.

### Conclusion

GEPA works for prompt optimization (4.2x improvement), but hit a hard ceiling at 0.548 imposed by Qwen 0.8B's format compliance. The model cannot reliably produce DSPy's structured output markers. No amount of prompt optimization can fix a model that can't follow the output format.

**What we got**:
- Optimized prompt instructions for all 5 modules
- Clear evidence that format compliance (not prompt quality) is the bottleneck
- A reusable metric framework (300 test cases, combined scoring)
- Understanding of DSPy GEPA's internals (trace matching, reflection pipeline)

**What to do next**: Teach format first (SFT or constrained decoding), then re-run GEPA on a format-competent model.

---

## Experiment 2: Format SFT

Teach Qwen 0.8B to produce DSPy's structured output format via supervised fine-tuning.

### Setup

- **Date**: 2026-03-27
- **Framework**: Unsloth + `FastVisionModel` (Qwen3.5 is a VLM architecture) on Colab T4
- **Base model**: `unsloth/Qwen3.5-0.8B` (full precision, no 4-bit)
- **LoRA config**: r=16, alpha=16, language layers only (`finetune_vision_layers=False`)
- **Training data**: `format_train.jsonl` — 3,997 examples (3,597 train / 400 val)
  - intent_decider: 1,499, text_responder: 1,434, data_extractor: 578, choice_builder: 386, review_builder: 100
  - Generated using DSPy's ChatAdapter to guarantee format correctness
- **Training**: 3 epochs, batch=2, grad_accum=4 (effective batch 8), lr=2e-4 cosine, max_length=16384
- **Trainable params**: 10.8M / 863M (1.25%)
- **Notebook**: `tuning/sft/sft_format_qwen35_08b.ipynb`

### Results

- **Eval loss**: 0.0463
- **Training time**: ~6.4 hours on Tesla T4, 95.4% VRAM usage (13.9 / 14.6 GB)
- **Format compliance**: Sanity check shows correct `[[ ## field ## ]]` delimiters and `[[ ## completed ## ]]` markers
- **Artifacts**: LoRA adapter (41MB) + merged safetensors (1.6GB) + GGUF Q8_0 (774MB) downloaded to `~/work/models/`

### Sanity check observations

- Intent decider: correct format, produced `converse` (debatable — could be `gather`)
- Data extractor: correct format, but hallucinated ~16 fields when only 2 were in the user message (over-extraction). Output also truncated due to `max_new_tokens=128` limit in test cell.
- These are quick sanity checks, not a proper eval — need to run the full metric framework to assess actual quality.

### Colab notes

- Used **Pro account** — free tier can't complete the full training without extra credits
- Used a keep-alive hack to prevent Colab from disconnecting during the 6+ hour run
- **TODO**: Mount Google Drive for input data and output artifacts — enables safe storage and training resumption if disconnected

### Full eval: compare_models.py (300 test cases)

Ran side-by-side comparison of original 0.8B vs SFT model on 300 test cases from `test-cases.jsonl`.

|  | Original | SFT |
|---|---|---|
| Format OK (all fields + completed) | 108/300 (36%) | 298/300 (99.3%) |
| Has `[[ ## completed ## ]]` | 110/300 | 298/300 |
| Intent accuracy | 39/91 (43%) | 73/91 (80%) |
| Avg latency | 2.1s | 1.5s |

Per-module format compliance:

| Module | Original | SFT |
|---|---|---|
| intent_decider | 72/91 (79%) | 91/91 (100%) |
| data_extractor | 1/151 (0.7%) | 150/151 (99.3%) |
| choice_builder | 34/54 (63%) | 54/54 (100%) |
| review_builder | 1/4 (25%) | 3/4 (75%) |

### Sanity check: content quality (sanity_check.py)

12 diverse prompts across intent/extractor/text_responder modules. All 12 produced valid format. Content findings:

- **Intent**: 3/5 correct — misses `clarify` (predicted `gather`) and `review` (predicted `converse`)
- **Extractor**: hallucination problem — ignores actual user message, outputs memorized field patterns with fabricated values (e.g. user says "Sarah Johnson" but model outputs "Alex Chen")
- **Text responder**: good quality — natural, varied, contextually relevant
- **Repetition**: 10/12 unique outputs (2 duplicates are identical short intent outputs, expected)

---

## Experiment 3: GEPA on SFT model (Qwen3.5-0.8B)

### Setup

- **Date**: 2026-03-31
- **Student LM**: SFT fine-tuned Qwen3.5-0.8B via mlx_vlm (localhost:8084)
- **Reflection LM**: GPT-5 (OpenAI API)
- **Budget**: light (2,895 rollouts)

### Results

- **Baseline**: 0.827 (82.7%) — 6x higher than pre-SFT Trial 3 baseline (0.131)
- **Full valset score**: 0.7285 (iteration 0) — never improved across 9 iterations
- **Stopped at**: iteration 9, ~38 min. No prompt changes accepted.
- **GEPA proposed** detailed prompts (especially a 7K-char text_responder prompt) but none beat the subsample baseline.

### Why it plateaued

The SFT model has near-perfect format compliance, so GEPA reflections work. But the bottleneck shifted to **content quality**, specifically data extraction:

1. **Extractor hallucination** — 0.8B model ignores user input and outputs memorized field patterns. No prompt can fix this.
2. **Extractor weight** — 25% of the combined metric. With extractor scores near 0 on many examples, the ceiling is ~75%.
3. **Intent at ~80%** — limited room to improve the 30% weight component.

### Conclusion

GEPA + SFT on 0.8B has reached its ceiling. Format compliance is solved (99.3%), but the model is too small for accurate data extraction. Next step: try Qwen3.5-4B which should have better instruction following and extraction capability.

---

## Experiment 4: Constrained Decoding (skipped)

Skipping for now — SFT achieved 99.3% format compliance, making constrained decoding unnecessary.

---

## Experiment 5: Task SFT (planned)

Force valid structure at token level during generation.

### Options

1. **Outlines + MLX** — Pydantic/regex constraints per module
2. **llama.cpp GBNF** — BNF grammar, switch serving layer

### Expected outcome

Eliminates format failures entirely (100% valid structure). Content quality inside the structure depends on model capability — may be garbage in valid JSON. Best combined with SFT or GEPA.

---

## Experiment 4: Task SFT (planned)

Fine-tune on actual form-filling task data from simulation logs. Model learns both format AND content.

### Training data

- Source: `tuning/data/atomic.jsonl` — extracted turns from simulation sessions
- Format: chat-style messages (system + user + assistant)
- Size: ~500-1500 examples from 20-50 simulation sessions

---

## Experiment 6: GRPO Training Data Preparation

Built the training dataset for GRPO reinforcement learning on the format-SFT model, targeting `DataExtractor` only.

### Scripts (no notebook)

| Script | Purpose | Output |
|---|---|---|
| `tuning/rl/gen_grpo_data.py` | Purely programmatic generator. Builds `(prompt, ground_truth_ids, ground_truth_values)` triples using the DSPy ChatAdapter over `masters-northfield.json`, with random form states, value generators (names, dates, scores, addresses), and variations for single/multi-field, choice, and file-upload cases. | `tuning/rl/grpo_extractor_data.jsonl` (3,000 examples) |
| `tuning/rl/mutate_extractor_data.py` | Loads 578 real `data_extractor` examples from SFT training data and asks a cheap LLM to rewrite each one under many synthetic user profiles, preserving the original `field_ids` / `field_values` structure. The `haiku_mutation` source label and `call_haiku` function name are legacy — the script was originally written against Claude Haiku but the current dataset was generated with a different model (see the `model=` argument inside the script). | (contributes `haiku_mutation` rows to the combined file below) |

### Final dataset

`tuning/rl/grpo_extractor_mutated.jsonl` — **41,767 examples** used for all GRPO runs.

Source distribution:

| Source | Count | Share |
|---|---|---|
| `haiku_mutation` (LLM rewrites — legacy label) | 29,622 | 71% |
| `programmatic_option` | 11,107 | 27% |
| `programmatic_file` | 1,038 | 2% |

Each row has `{prompt, ground_truth_ids, ground_truth_values, source}`. The dataset was used wholesale — no explicit train/val split at this stage; evaluation uses the separate 300-case test set from `tuning/data/test-cases.jsonl`.

---

## Experiment 7: GRPO on Format-SFT Model (Qwen3.5-0.8B)

GRPO reinforcement learning to improve DataExtractor accuracy, starting from the format-SFT LoRA.

### 7a. Training

#### Initial local attempt and Unsloth

- Initial approach lived in `tuning/rl/grpo_extractor_qwen35_08b.ipynb`, a Colab/notebook-style flow using **vanilla HuggingFace + TRL + PEFT with BitsAndBytes QLoRA** (explicitly no Unsloth). CPU smoke tests in `debug_grpo_cpu.py` and `test_notebook_cpu.py` validated that the reward functions, data loader, and `GRPOTrainer` loop all run end-to-end before committing to GPU.
- Unsloth was considered but not used for GRPO. The reason recorded at the time was that Unsloth had unresolved issues with the Qwen3.5 hybrid architecture (attention + Mamba layers). **We did not save logs of a specific Unsloth-GRPO failure** — this was a forward-looking avoidance based on the broader Qwen3.5 hybrid issues also seen in mlx_lm prompt caching (see doc-11). If we revisit Unsloth for a future run, we should re-test and record actual errors.
- A further gotcha from the notebook: the SFT LoRA was trained on `Qwen3_5ForConditionalGeneration` (the VLM class, via Unsloth's FastVisionModel). Loading it with `AutoModelForCausalLM` silently mismatches layer nesting and the adapter fails to apply. The notebook and Modal script both load the VLM class explicitly to avoid this.

#### Migration to Modal

Local/Colab GRPO was slow and memory-constrained. We moved actual training to **Modal** with a persistent volume for checkpoints.

- Script: `tuning/rl/train_grpo_modal.py`
- App: `grpo-extractor-qwen35-08b` on Modal
- GPU: **L4** (24 GB VRAM), 6 h timeout per run
- Volume: `grpo-checkpoints` (Modal Volume, mounted at `/vol`)
- Image: `python:3.11` + `torch>=2.5`, `transformers==5.5.4`, `trl==1.1.0`, `peft==0.19.0`, `accelerate==1.13.0`, `bitsandbytes>=0.45`, `datasets>=4.0`
- Modal usage followed `tuning/modal_guide.md` (see project root).

#### Reward functions (`train_grpo_modal.py` module-level)

| Reward | Range | What it rewards |
|---|---|---|
| `format_reward_func` | 0 to +2 | +1 when all three markers present (`[[ ## field_ids ## ]]`, `[[ ## field_values ## ]]`, `[[ ## completed ## ]]`); additional +1 when parsed `field_ids` is non-empty AND `len(field_ids) == len(field_values)`. |
| `accuracy_reward_func` | 0 to +3 | If GT is empty: +1.5 for predicting empty, else 0. If GT is non-empty: `1.5 × id_F1` + `1.5 × (correct_values / |GT|)`. |
| `hallucination_penalty_func` | 0 to −2 | −0.5 per predicted `field_id` that is not in the set of valid IDs parseable from the prompt, capped at −2.0. |

Theoretical max total reward ≈ **+5.0**; lower bound ≈ **−2.0**.

> Known bias (logged here for future reward redesign): the second +1 in `format_reward_func` only triggers when `field_ids` is **non-empty**. Combined with `accuracy_reward_func` giving +1.5 only when GT is empty AND pred is empty, the net signal leans toward "emit something" over "emit nothing." This aligns with what we later saw in eval (empty-correct rate collapsing).

#### Hyperparameters (`GRPOConfig`)

- `num_generations=4`, `per_device_train_batch_size=1`, `gradient_accumulation_steps=4` (effective batch 4)
- `max_completion_length=512`
- `learning_rate=5e-6`, `adam_beta1=0.9`, `adam_beta2=0.99`, `weight_decay=0.1`
- `warmup_ratio=0.1`, `lr_scheduler_type="cosine"`, `max_grad_norm=0.1`
- `optim="adamw_8bit"`, `bf16=True`
- `save_steps=100`, `logging_steps=1`, `log_completions=True`

#### Training runs

Five Modal runs, all resuming on the same `grpo-checkpoints` volume. Logs in `tuning/rl/grpo_training_run{1..5}.log`; per-step metrics in `grpo_log_history_{600,900,1500,1800}steps.json`.

| Run | `max_steps` | Mode | Log file |
|---|---|---|---|
| 1 | 300 | fresh from SFT LoRA | `grpo_training_run1.log` |
| 2 | 300 | `--use-grpo-lora` (continue from previous GRPO LoRA) | `grpo_training_run2.log` |
| 3 | 900 | `--resume` from HF checkpoint | `grpo_training_run3.log` |
| 4 | 1500 | `--resume` | `grpo_training_run4.log` |
| 5 | 1800 | `--resume` | `grpo_training_run5.log` |

Training reward trajectory (per-step reward values from saved log histories, step range `[1, max_steps]`):

| History file | Entries | Min reward | Max reward | Final step reward |
|---|---|---|---|---|
| `grpo_log_history_600steps.json` | 600 | −0.60 | 5.00 | 3.125 |
| `grpo_log_history_900steps.json` | 900 | −0.60 | 5.00 | 3.500 |
| `grpo_log_history_1500steps.json` | 1500 | −0.60 | 5.00 | 4.625 |
| `grpo_log_history_1800steps.json` | 1800 | −0.60 | 5.00 | 1.571 |

Training reward rose from near 0 toward ~4.6 through step 1500, then regressed at 1800 (final-step value 1.57) — suggesting the policy wandered off a high-reward basin late in the run.

Training curves saved as `grpo_training_{600,900,1500,1800}steps.png`.

#### Checkpoint merging

Checkpoints from training are QLoRA adapters over a **4-bit** quantized base. Merging them into the same 4-bit base introduces rounding errors, so merging is done separately by `tuning/rl/merge_checkpoints_modal.py` using an **fp16** base, producing standalone models under `merged/checkpoint-{N}/` on the volume. These are then converted to MLX for local Mac eval. Log: `merge_job.log`.

### 7b. Evaluation

#### Scripts

| Script | Where | Notes |
|---|---|---|
| `tuning/rl/eval_grpo.py` | Local Mac | DataExtractor-only evaluator against an `mlx_vlm.server`. Saves `preds_{name}.jsonl` + `summary_{name}.json` under `tuning/rl/eval_results/`. |
| `tuning/rl/eval_grpo_modal.py` | Modal | Same metrics, but loads base + (optional) LoRA adapter on a remote GPU so multiple checkpoints can be scored without re-downloading the base. |
| `tuning/rl/eval_sweep.sh` | Local | Driver that launched sweeps across checkpoints. |

#### Test set

`tuning/data/test-cases.jsonl` (n=300), split into `num_positive=151` (non-empty gold extraction) and `num_negative=149` (gold is empty — model should refuse).

#### Headline results

All numbers from `summary_{checkpoint}.json` in `tuning/rl/eval_results/`.

| Checkpoint | format_ok | pos F1 | pos value_match | neg empty_correct | pos halluc | avg completion (chars) |
|---|---|---|---|---|---|---|
| base (Qwen3.5-0.8B 4-bit) | 0.7% | 0.001 | 0.0% | 97.3% | 0.6% | 743 |
| sft (format-SFT) | 77.3% | 0.883 | 84.0% | 0.7% | 0.2% | 421 |
| grpo-300 | 74.3% | 0.813 | 73.2% | 24.2% | 0.9% | 1,867 |
| grpo-900 | 84.0% | 0.845 | 78.8% | 0.7% | 0.1% | 1,840 |
| grpo-1500 | 96.3% | 0.795 | 71.4% | 0.0% | 0.7% | 1,943 |
| grpo-1800 | 97.0% | 0.799 | 71.8% | 0.0% | 0.7% | 1,939 |

#### Observations

1. **Format compliance improved** substantially (77.3% → 97.0%) — this was the main thing GRPO moved. The reward signal for format was clearly learned.
2. **Positive F1 regressed** (0.88 → 0.80) and **value_match regressed** (84.0% → 71.8%) vs SFT. GRPO traded some content accuracy for format compliance.
3. **Empty-correct collapsed** (SFT 0.7% → grpo-1800 0.0%, after briefly touching 24.2% at step 300). GRPO actively drove the model further from emitting empty lists, consistent with the reward-function bias noted above.
4. **Avg completion length ballooned** (421 → 1,939 chars, ~4.6×). The model became more verbose despite `max_completion_length=512` — suggesting the generations are hitting the length cap frequently.
5. **1800 steps is not obviously better than 1500** on any metric — final training reward also regressed at 1800 (3.125 → 1.571 between step 1500 and 1800 log snapshots). We did not select a "best" checkpoint; downstream work should consider grpo-1500 as the strongest candidate.

#### Artifacts in `tuning/rl/eval_results/`

- `preds_base.jsonl` / `summary_base.json`
- `preds_sft.jsonl` / `summary_sft.json`
- `preds_grpo-300.jsonl` / `summary_grpo-300.json`
- `preds_grpo-900.jsonl` / `summary_grpo-900.json`
- `preds_grpo-1500.jsonl` / `summary_grpo-1500.json`
- `preds_grpo-1800.jsonl` / `summary_grpo-1800.json`

Per-module evaluation of the SFT baseline (intent_decider routing, text_responder, choice_builder, review_builder) was done later and is documented in [doc-13-sft-diagnosis.md](doc-13-sft-diagnosis.md).

---

## Experiment 8: GEPA on format-competent model (planned)

Re-run GEPA prompt optimization after Experiments 2-3 fix format compliance. Expect:
- Higher baseline (format failures no longer score 0)
- More successful reflections (valid traces for all modules)
- Higher ceiling (GEPA can focus on content quality instead of fighting format)

Also try on Qwen3.5-4B — larger model likely has better format compliance out of the box.

---

## Experiment 9: SFT v2 — Binary-flag Action Router

### Setup

- **Date**: 2026-04-29
- **Model**: Qwen3.5-0.8B → `qwen35-08b-dspy-format-lora-v2` (LoRA on fp16 base, then merged to fp16 standalone for mlx_vlm serving)
- **Architecture change**: `ActionRouterSignature` switched from a single categorical `intent` (gather / clarify / converse / close / review) to **5 independent boolean flags**:
  - `has_new_data` — user provided new field values to extract
  - `needs_choice` — multi-choice question should be presented
  - `wants_review` — progress-summary card should be shown
  - `wants_save` — Save Draft button should be offered
  - `wants_submit` — Submit Application button should be offered

  Each flag fires independently — a single turn can combine extraction + choice + save offer. Other modules (`text_responder`, `data_extractor`, `choice_builder`, `review_builder`) gate on these flags.
- **Training**: Same Modal SFT pipeline as Experiment 2, on an L4 with fp16 base. Training data regenerated by `tuning/sft/gen_format_data.py` with the new `infer_route()` definition.
- **Inference serving**: `mlx_vlm.server` on `localhost:8100` over the merged fp16 model.

### Eval refactor (mid-experiment)

After v2 was trained, the evaluation script `tuning/sft/compare_models.py` was rebuilt to fix two long-standing problems:

1. **Re-running inference for every analysis.** The old script computed scores from in-memory tallies and printed aggregates only — inspecting any failure mode required re-running the model.
2. **Implicit assumptions in gold derivation** that turned out to be wrong (see audit below).

The script now has two subcommands sharing scoring code:

| Stage | Subcommand | Behavior |
|---|---|---|
| 1 | `compare_models.py infer ...` | Runs models against test cases, writes per-case JSONL with raw outputs + gold labels. Only stage that touches a server. |
| 2 | `compare_models.py report --in *.jsonl [--failures]` | Reads JSONL, recomputes every metric, emits aggregate + per-bucket failure examples. No model calls. |

This guarantees aggregate stats are reproducible from stored predictions and that iterating on metrics or failure analysis is free (no inference cost).

### Gold-label audit

Triggered by an apparent contradiction during failure-mode review: a "gold False" `wants_save` for a case where the user literally said "save the draft." Three issues found, only the first is fully fixed:

1. **`parsed_actions` was dropped from `test-cases.jsonl`** by `tuning/scripts/sample.py` when the test set was built from `atomic.jsonl`. But `infer_route()` in the eval still read `parsed_actions` to derive `wants_save` / `wants_submit` button intents. Result: both flags' gold was always `False` regardless of case content. **Fixed** by parsing the JSON action block in `expected_output` as the canonical source.
2. **`wants_submit` has zero positive cases** in either training (1442 atomic turns) or eval (300 test cases). The simulator never produced a submit button — its button vocabulary is `{save_draft}` only. The previously reported 100% accuracy was structurally trivial: gold and pred were both always False. Beyond the eval bug, the model has had **zero training supervision** on this flag. **Not fixed**: requires regenerating simulator data with submit-flow scenarios.
3. **`wants_review` lumps `show_preview` (progress card) and `show_fields` (highlight section)** under one flag in both training and eval. Internally consistent, but the two are semantically distinct UI affordances. Borderline; not fixed.

The eval also gained per-flag pos/neg confusion breakdown (TP/FN, TN/FP) so zero-positive flags are no longer hidden behind 100% accuracy averaging.

### Headline numbers — initial (pre-audit) eval

Looked excellent at first read:

```
                          Original          SFT-v2
Format OK                  126/600          598/600  (99.7%)

Action-router per-flag accuracy:
  has_new_data            147/300          263/300  (87.7%)
  needs_choice            181/300          237/300  (79.0%)
  wants_review            212/300          271/300  (90.3%)
  wants_save              222/300          279/300  (93.0%)
  wants_submit            224/300          300/300  (100.0%)

Content accuracy:
  data_extractor F1       0.000            0.965
  choice_builder F1       0.016            0.454
  review_builder coverage 1.000            1.000
  text_responder ok       0.451            1.000
```

Format compliance hit ~100% across all 5 modules — solving the same gap Experiment 2 chased. But the high `wants_*` flag numbers were inflated by Bug #1 + Bug #2.

### Headline numbers — post-fix (300 cases, true behavior)

After re-deriving gold from `expected_output` and exposing pos/neg recall:

```
flag           pos-recall (gold True → pred True)   neg-recall (gold False → pred False)
has_new_data   131/148 = 89%                        132/152 = 87%
needs_choice    40/96  = 42%   ← under-fires        197/204 = 97%
wants_review    16/43  = 37%   ← under-fires        255/257 = 99%
wants_save      17/30  = 57%   ← under-fires        266/270 = 99%
wants_submit     —/0   N/A                          300/300 = 100%
```

Content metrics unchanged (they don't depend on the gold-route fix):

```
data_extractor (n=148): ID F1 0.965 / exact-set 0.899 / value-match 0.816
choice_builder (n=59):  option F1 0.454 / exact-set 0.356 / question present 1.000
review_builder (n=22):  coverage 1.000 / title present 1.000 / content present 1.000
text_responder (n=71):  non-empty 1.000 / no format leak 1.000 / ok 1.000
```

### Observations

1. **Format compliance: solved.** 99.7% across all modules. Same lesson as Experiment 2; transfers cleanly to the new architecture.
2. **The model is systematically conservative on routing.** Headline accuracy looked high because gold is mostly negative — neg-recall is excellent (96–100%), but pos-recall on the under-fired flags is 36–57%. Previous metric design hid this.
3. **`has_new_data` is the only balanced flag** (89% pos / 87% neg). It's also the only flag with a high positive base rate in training (40%). Suggests the false-negative bias on the others is a low-base-rate / class-imbalance artifact, not a fundamental capability gap.
4. **`choice_builder` option F1 of 0.45 is real** — not a metric artifact. Many gold/pred mismatches are still semantically reasonable paraphrases (e.g., the model proposes a 2-option question where gold has 3 options but the missing third is an orthogonal alternative). Needs qualitative review before assuming the model is "wrong."
5. **`data_extractor` value-match 0.82 reflects an SFT-data formatting habit.** Failures are dominated by Python-stringification (`"True"` instead of `true`, `"['a','b']"` instead of `["a","b"]`). Likely fixable by cleaning training data, not RL.
6. **`wants_submit` is structurally untestable today.** Both training and eval have zero positive cases. To validate any improvement here we'd first need new simulator data covering submit-flow scenarios.

### Files

| Artifact | Path |
|---|---|
| Eval script (refactored) | `tuning/sft/compare_models.py` |
| LoRA → fp16 merge | `tuning/sft/merge_lora_modal.py` |
| SFT training (new arch) | `tuning/sft/train_sft_format_modal.py` |
| Training data generator | `tuning/sft/gen_format_data.py` |
| Predictions JSONL (300 cases) | `/tmp/preds_v2_full.jsonl` |
| Report output | `/tmp/report_v2_full.txt` |

---

## Experiment 10: E2E harness — plug SFT-v2 into the web app (planned)

**Date**: 2026-04-29

### Motivation

After Experiments 1–9 we've been iterating in a closed loop: synthetic data → SFT → synthetic eval → repeat. Two compounding sources of error make this loop slow:

- The synthetic data itself has known issues (see [doc-14](doc-14-training-data-issues.md)).
- The eval has had silent measurement bugs (Experiment 9 audit).

We have not yet driven the model in production conditions. The eval is a regression net, not a development driver. Real failures are likely to come from:

- Real form schemas (not just `masters-northfield.json`)
- Multi-turn drift (eval is single-turn-isolated; real sessions accumulate context)
- Real user inputs (typos, tangents, file pastes, partial recovery, "wait — let me redo that")
- UI integration — does `set_fields` actually populate? Do buttons render? Does Save Draft persist?
- Capability gaps the model has no representation for (file upload, vault tools, validate_fields)

### Plan

Build `tuning/harness/` — a standalone Python HTTP service that:

- Exposes the same SSE contract as the web app's existing `/api/generate` endpoint (text events + done)
- Receives structured per-turn data (`session_id`, `user_message`, `form_state`, `form_schema`, `conversation_history`) so it remains form-agnostic
- Runs the 5-module DSPy pipeline (`FormAssistant.forward()` from `tuning/dspy/optimize_prompt.py`) against `http://localhost:8100` (mlx_vlm serving SFT-v2)
- Composes module outputs into the legacy `text + ---actions--- + JSON` format that `packages/web-app/public/js/action-parser.js` already parses
- Handles non-conversational lifecycle (`save_draft` / `submit_final`) by talking directly to `packages/persistence-server` (`POST /api/drafts`, `POST /api/submissions`)
- Logs per-turn traces to `logs/session-{id}.jsonl` matching the existing schema, plus an additive `module_outputs` field for per-module debugging

Web-app changes (minimal):
- New `/api/generate-local` proxy route in `packages/web-app/src/index.ts`
- New `LocalSFTProvider` browser provider in `packages/web-app/public/js/chat-provider.js`
- `?backend=local` URL param toggle, persisted to localStorage; default stays Claude

### Out of scope

- Vault tools (`vault_*`)
- File uploads, `validate_fields`, `discover_form` (we use the static `masters-northfield.json` schema)
- `wants_submit` handling (model has zero training supervision — see Experiment 9 audit)
- Token-level streaming (faked via two SSE chunks since the 5-module pipeline is serial)
- Multi-form support — northfield only

### Success criteria

A working chat session in the web UI driven by SFT-v2, with full session traces captured for each turn. Manual testing reveals real failure modes; subsequent work targets only those.

### Files (planned)

```
tuning/harness/
├── serve.py        # FastAPI; POST /api/generate (SSE)
├── pipeline.py     # FormAssistant + dspy.LM @ :8100
├── composer.py     # Prediction → text + ---actions--- block
├── lifecycle.py    # save_draft / submit_final → persistence-server
├── logger.py       # session JSONL writer
└── README.md
```

Estimated size: ~400 LOC Python, ~50 LOC TypeScript additions on the web-app side.

### Phasing

**Phase 1**: build and wire up; confirm the toggle works and one round-trip turn produces a sane response in the chat UI.

**Phase 2**: defer until Phase 1 surfaces real failures. Don't pre-spec the next round of training or eval changes.

---

## Experiment 11: Phase-1 harness shipment, programmatic probes, deterministic helpers

**Date**: 2026-04-29 → 2026-05-06

This experiment covers everything between "Experiment 10 was planned" and "we're ready to start GEPA." Three distinct workstreams happened in series:

1. **Phase 1 harness** — actually shipped what Experiment 10 sketched
2. **Programmatic probes** — replaced manual click-test-and-eyeball with an automated probe sweep
3. **Deterministic helpers** — added the cheapest interventions for the failure modes the probes surfaced (doc-16 #3 / #5 / #6 / #7 mappings)

Plus two cross-cutting docs landed during this period: `doc-15-real-app-issues.md` (the running R-issue log) and `doc-16-model-capabilities.md` (the CAN / CANNOT / NOT-SURE behavior framework).

### 11A — Phase 1 harness shipment

Built the architecture sketched in Experiment 10. Files now live:

```
tuning/harness/
├── serve.py          # FastAPI; POST /api/generate (SSE), /api/save-draft, /api/submit, /health
├── pipeline.py       # build_context + run_turn; configures dspy.LM @ :8100; per-call temp override
├── composer.py       # Prediction → text + ---actions--- block; schema validation + type coercion
├── lifecycle.py      # save_draft / submit_final → persistence-server
├── logger.py         # session JSONL writer (matches existing schema + additive module_outputs)
├── dspy_logger.py    # DSPy BaseCallback → per-module / per-LM-call transcript JSONL
└── README.md
```

Web-app changes:
- New `/api/generate-local` proxy route in `packages/web-app/src/index.ts`
- New `LocalSFTProvider` in `chat-provider.js` with structured-context support
- `?backend=local` URL toggle, persisted to localStorage
- Backend-aware kickoff message (the R4 fix in doc-15) — embeds known state in plain assistant voice instead of letting the model fall back to vault patterns

End-to-end verified: browser → `/api/generate-local` → harness `/api/generate` → 5-module pipeline → composed SSE response, with full session traces at `logs/session-{id}.jsonl` and per-LM-call transcripts at `logs/session-{id}.lm-calls.jsonl`.

### 11B — Real-app issue log (doc-15)

Manual interactive testing through the harness produced a stream of distinct failure modes, logged as R-issues with deterministic root-cause attribution where possible:

| ID | Severity | Status | One-liner |
|---|---|---|---|
| R1 | blocker | fixed (composer) | `ask_choice` options shape mismatch — clicks returned "undefined" |
| R2 | painful | deferred (model fix) | `needs_choice` false-negative when text_responder asks a question |
| R3 | painful | deferred (model fix) | choice_builder hallucinated "Medical Assistant" — not in schema |
| R4 | painful | fixed (kickoff prompt) | Vault-talk + missing first-turn choices on brand-new applicants |
| R5 | painful | deferred (model fix) | text_responder produces empty reply while data_extractor silently fills 17 fields |
| R6 | painful | deferred (training data) | data_extractor structural errors on resume (employer/title swap, hallucinated funding) |
| R7 | blocker (file UX) | deferred (model fix) | Uploaded file not assigned to its file field |
| R8 | painful | fixed (harness) | Conversation history truncated to 300 chars, file content lost after one turn |
| R9 | blocker | fixed (harness) | `select` options truncated at `[:5]` — silently wrong values when user picks 6th option |
| R10 | painful | deferred (model fix) | `has_new_data` false-negative on bare-statement identity ("Let Sea is my full name") |
| R11 | painful | deferred (model fix) | text_responder hallucinates form state (claims fields empty when filled) |
| R12 | **blocker** | deferred (training data) | Training-data persona leakage ("Alex Chen" surfaces on a fresh session) |
| R13 | painful | deferred (model fix) | Data_extractor fabricates field values from conversational filler |

Of the 13, 4 were fully fixed at the harness/composer layer (R1, R4, R8, R9). The remaining 9 are model-behavior issues — split across calibration (GEPA-tunable), training data (R6, R12), and architectural (R5, R7).

### 11C — Programmatic probe framework

Manual testing was producing one session at a time and saturating attention. To get coverage of the full conversation surface, decomposed the form-filling flow into 12 phases and authored 5 scenarios per phase (60 total probes), each with realistic 4–6-turn conversation history:

```
P1  session opening              P7  file uploads
P2  closed-set selection         P8  mid-flow status
P3  free-text personal info      P9  save & resume
P4  single-entity group          P10 pre-submission review
P5  multi-entity group           P11 submission
P6  conditional fields           P12 adversarial
```

Each probe lives in `tuning/harness/probes/P*.md` as a structured markdown block with `form_state`, `conversation_history` (last 6 turns, file-aware sized), and `user_message`. The runner (`probe_runner.py`) parses the markdown, POSTs to the harness twice per probe (once at temperature=0.0 for determinism, once at 0.7 for variability check), and writes results into sibling files at `probes/runs/P*.md` — same probe blocks with per-run module outputs and composed responses appended.

#### Cross-cutting finding from probes

**temp=0.7 amplifies hallucination, not creativity.** Across nearly every probe, the higher-temperature run was *worse* than temp=0 — fabricated field values, made-up dialogue, hallucinated returning-user state. The model at temp=0 is already at the edge of its capability; sampling alternatives moves it into degenerate regions. Implication for downstream optimization: any technique that explores via temp>0 (DSPy GEPA's default mode, RL rollouts) is sampling a distribution that includes more hallucinations. Either the search must run at temp=0 or the reward must heavily penalize hallucinations.

#### Probes also helped catch a design issue
Architectural fact made explicit during this work: every module is a one-shot `dspy.Predict` from `(context, user_message)`. No cross-module piping, no agent loop. The "text-action seam" (R5, etc.) lives at this seam.

### 11D — Deterministic helpers (`state_check.py` + composer integration)

After consolidating all 13 R-issues + 60 probes into a behavior framework (doc-16: CAN / CANNOT / NOT-SURE), 4 of the 8 CANNOTs lent themselves to deterministic Python:

- **#3 cross-check two states** — `compute_state_summary(schema, form_state)` produces a humanized "Already provided: ... | Still needed: ..." string for context augmentation
- **#5 group-field index management** — `compute_group_indices(schema, form_state)` produces "Academic Degrees: 1 entry; next would be entry 2"
- **#6 inconsistent value serialization** — `coerce_value(field_def, raw)` for boolean / list / number type-fixing; runs unconditionally on every set_fields entry
- **#7 wrong field/value (clear cases)** — `validate_against_schema(schema, field_id, value)` drops unknown field_ids, snaps select labels to canonical values ("Computer Science (MS)" → "cs"), drops out-of-enum values; returns a `dropped` list for logging

#3 and #5 are exposed via `augment_state=True` request flag (off by default; small distribution-shift risk). #6 and #7 are always on in the composer (no model-facing change).

#### A/B finding (P5 + P8 with augment_state on vs off)

Modest but real wins where the model can read the enrichment:

| | Helped | No effect | Still broken |
|---|---|---|---|
| #3 (P8 status) | ex2 (what's left), ex4 t=0.7 (listed values accurately) | ex3 (still no recap) | ex1, ex5 (vault leakage persists) |
| #5 (P5 indices) | ex3 (correctly used recommenders.0/1) | ex1, ex2 (still wrong index for "before X" phrasing) | ex4, ex5 (no remove/edit action vocabulary) |

Augmentation produced clear wins in 3 of 8 cases, no regression anywhere. Doesn't fix:
- vault hallucination (training-data prior survives explicit context)
- text-action disconnect (different architectural seam)
- actions that the model doesn't have vocabulary for (remove entry, edit by index)

#### Composer scope discovered narrower than initially claimed

The schema validator catches enum violations and unknown field_ids — but **cannot catch free-text mutations** (model wrote `bain_companies` for `jobs.0.employer` when user said "Bain & Company"; the field is `text` type, no enum to validate against). For text/textarea/email/phone/file fields, anything the model emits passes through. This is recorded as "GEPA candidate" rather than a deterministic-helper target.

### Observations / lessons

1. **Most R-issues are model-behavior, not harness gaps.** 4 of 13 fixed at harness/composer; the rest need model-side intervention (training data, RL, GEPA, or architectural changes). The harness is now a stable measurement instrument; the next gains are in the model.
2. **Training-data leakage is the hardest residual issue.** R12 (persona memorization) survives explicit kickoff prompting (R4 only partially mitigates). No deterministic fix; only retraining or model scale can address it.
3. **Probe coverage > manual sessions for breadth, manual > probes for depth.** The probes surfaced systematic patterns across the 60 scenarios; manual sessions caught nuanced single-incidence failures (R12 was first observed manually). Both are needed.
4. **The text-action disconnect (R5) is architectural, not calibration.** Fixing it cleanly requires a reconciliation step that sees all 5 module outputs together — which is a new module + new training data, deferred for v3 SFT.
5. **`compare_models.py` synthetic eval missed most R-issues.** It only measures action-flag accuracy and per-module content; it doesn't simulate multi-turn drift, file uploads, returning-user kickoffs, or conversation-vibe failures. The probe sweep is now the more informative quality signal.

### Files

| Artifact | Path |
|---|---|
| Harness | `tuning/harness/{serve,pipeline,composer,lifecycle,logger,dspy_logger,state_check}.py` |
| Probes (source) | `tuning/harness/probes/P*.md` (12 files, 60 probes) |
| Probes (results) | `tuning/harness/probes/runs/P*.md` (regenerated by `probe_runner.py`) |
| Probe runner | `tuning/harness/probe_runner.py` |
| Real-app issues log | `docs/doc-15-real-app-issues.md` |
| Behavior framework | `docs/doc-16-model-capabilities.md` |
| Web-app integration | `packages/web-app/src/index.ts` (`/api/generate-local`), `packages/web-app/public/js/chat-provider.js` (`LocalSFTProvider`), `packages/web-app/public/index.html` (kickoff redesign) |

### What's next

1. **GEPA** — first prompt-tuning pass on the SFT model. Targets from doc-16 NOT-SURE #2 ("follow prompt to adjust behavior"): action_router calibration (R2/R10), text_responder grounding (R11/R5), data_extractor schema-faithfulness (R7's file-assignment step, R6's structural errors). Reward design needs to penalize the failure patterns identified in doc-15 — especially #4 (commits to output regardless) and #8 (training-persona names enumerable from `personas.ts`).

2. **v3 SFT planning** — for issues that don't yield to GEPA (R5 architectural, R12 memorization, possibly R6 structural). Likely requires: a reconciliation module, broader persona pool with redacted identifiers, possibly a context-format change for #3/#5.

3. **RL** — only after GEPA evidence shows whether prompt tuning closes enough of the calibration issues to justify weight updates.

GEPA is up next.

---

## Experiment 12: GEPA pilot v1 — eval set, hybrid metric, invalidated pilot, hygiene rule

**Date**: 2026-05-08 → 2026-05-10

Built the GEPA infrastructure and ran two pilots against the SFT v2 model.
Both pilots produced invalid score deltas because the experimental harness
silently diverged from the production reference. The valuable output of
this experiment is the methodology fix, not the pilot numbers.

### 12A — Eval set construction

- **28 base seeds** at `tuning/gepa/seeds.jsonl`, hand-authored. Each pairs
  an input scenario with the ideal `correct_answer` (5 flags +
  response_text + field_ids/values + question/options + summary). Seeds
  cover CANNOTs #1, #2, #3, #4, #5, #7, #8 from doc-16.
- **280 variations** at `tuning/gepa/eval_cases.jsonl`, 10 per seed,
  generated via `claude` CLI headless (Sonnet) preserving each seed's
  scenario archetype.
- **300 legacy cases** converted from `tuning/data/test-cases.jsonl` via
  `import_legacy.py`, mapping the old `set_fields/ask_choice/show_preview`
  action format to the new (input + correct_answer) shape. Tagged
  `source=legacy-{category}`.
- Total: 608 cases.

### 12B — Hybrid metric

`tuning/gepa/metric.py` scores cases as a weighted sum across the 5
modules, renormalized per case so a "format clarification" case (only
router + text active) isn't diluted by inactive-module weights.

- Programmatic checks: action_router 5-flag exact match,
  data_extractor F1 + value match, choice_builder/review_builder
  presence, persona-leak regex (context-aware: skipped when persona
  appears in input).
- Judge: `judge.py` calls GPT-5 once per case with all rubric items
  batched. `rubrics.py` defines ~60 per-seed yes/no items + a baseline
  "intent matches reference."
- Cost: ~$0.005/case at GPT-5 prices (~$3 per full-eval pass over 608
  cases).

### 12C — Pilot v1 (invalidated)

Two pilots ran on 2026-05-09/10:

| Pilot | Setup | Result |
|---|---|---|
| 1 (judge ON, small) | train=15, val=20, max_metric_calls=250 | "0.301 → 0.466 (+54%)" |
| 2 (judge ON, full) | train=486, val=122, max_metric_calls=4000 | "0.512 → 0.581 (+13%)" |

These numbers were attributed to GEPA's prompt mutations. They were not.
On inspection, the optimized program's outputs on a known anchor
(P1-ex3 from a real probe log) **did not match the production system's
output** for the same input. Comparing configs revealed three silent
divergences in the GEPA harness vs the production harness
(`tuning/harness/pipeline.py`):

1. **`max_tokens=512` was missing** — the model rambled, dumping ~12
   fabricated fields per turn instead of stopping cleanly.
2. **`cache=False` was missing** — DSPy's response cache may have
   replayed stale outputs across iterations.
3. **`load_form_context()` truncated select options to `[:5]`**, hiding
   "Mechanical Engineering (MS)" from the model.

Plus a fourth issue: `mlx_vlm.server` silently routes any requested
model name to the loaded weights but **applies a different chat template
based on the requested name**. The harness was using
`./models/qwen35-08b-dspy-format-v2-mlx` (correct
template), and a copy-pasted `--student-model` default in the GEPA
script was `mlx-community/Qwen3.5-0.8B-4bit` — same weights, wrong
template, off-distribution prompts.

GEPA's ~+13% lift was the optimized prompts compensating for these
configuration bugs in the experimental harness, not improvements to
the SFT model's actual behavior. Re-running the optimized program with
the correct config showed it does not match the gains the metric
reported.

### 12D — Hygiene rule and machinery

The fix for this class of bug is a process rule, not a code change to
GEPA. Codified in `CLAUDE.md` > Experiment hygiene:

> For any experimental task whose value comes from comparing "after"
> against "before": name the anchor explicitly, reproduce the anchor
> before running the experiment, block the costly run on the smoke test.

Implemented as:
- `tuning/harness/preflight.py::assert_anchor_match()` — runs the
  configured pipeline against a recorded fixture and aborts on diff.
- `tuning/harness/calibrate.py` — captures a model's expected output on
  the canonical input as a per-model fixture (`anchor_p1_ex3_<label>.json`).
- `tuning/harness/fixtures/anchor_p1_ex3_sft_v2.json` — SFT v2's
  verified P1-ex3 output, sourced from a live probe log.
- All four GEPA entry points (`optimize.py`, `compare_outputs.py`,
  `inspect_outputs.py`, `eval_program.py`) refactored to use harness's
  `configure_lm` + `build_context` and run `assert_anchor_match()` at
  startup.
- `tuning/dspy/optimize_prompt.py::main()` and `load_form_context()`
  marked deprecated to prevent the old buggy patterns from being
  copy-pasted again.

### Observations / lessons

1. **Score lift without anchor verification is meaningless.** Both pilot
   runs had clean-looking metrics curves, accepted-vs-rejected mutation
   ratios, and Pareto-front growth. Nothing in the run output flagged
   the harness divergence — only manual inspection of one optimized
   prediction against a probe log surfaced it. Hygiene rule made
   permanent.
2. **MLX server's `/v1/models` endpoint is misleading.** It lists
   registry-available names, not the actually-loaded weights. POSTing
   any of those names succeeds but applies a different chat template to
   the same loaded weights. Documented in `pipeline.py` so the next
   reader doesn't fall in.
3. **Defaults inherited blindly are silent landmines.** The wrong
   `--student-model` default in `gepa/optimize.py` came from
   copy-pasting `tuning/dspy/optimize_prompt.py` (which itself was
   wrong). Single-entry-point LM config — every script imports
   `configure_lm` from `harness/pipeline.py` — makes this class of
   divergence impossible-by-construction.
4. **Anchors must be model-specific.** The anchor's job is to detect
   harness divergence, not legitimate model differences. Calibrating
   per model means future "compare model A vs model B" experiments
   work cleanly: each side passes its own anchor first, then the metric
   diff between them is meaningful.

### What's next

- **Re-run GEPA pilot under correct config.** Same eval set, same
  metric, same budget — but with the canonical harness LM + anchor
  preflight gate. Expectation: smaller delta than the invalid +13%,
  closer to the model's actual prompt-followability ceiling on the
  hard CANNOTs.
- **If the real delta is small**, GEPA-on-SFT-v2 has hit its ceiling.
  Next moves are RL or a v3 SFT round — the same pattern doc-12
  Experiment 4 found at the GEPA ceiling on the format-untrained
  base model, just shifted up to the format-competent SFT model.
- **Pilot artifacts from 12C are intentionally not committed.** They
  document an invalid experiment; keeping them would imply the numbers
  are real. The methodology fix (12D + the hygiene commit on `main`)
  is the asset.
