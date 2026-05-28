# Doc 13: SFT Diagnosis (Qwen3.5-0.8B Format-SFT)

> **Status — superseded for the current model.** This doc diagnoses an earlier SFT checkpoint that used a single categorical `intent` (gather / clarify / converse / close / review). The current model (`qwen35-08b-dspy-format-lora-v2`) uses a different action-router architecture (5 independent boolean flags). For up-to-date per-module diagnosis on the current model, see [doc-12 Experiment 9](doc-12-tuning-journal.md#experiment-9-sft-v2--binary-flag-action-router). This document is preserved as the historical snapshot of the categorical-intent SFT diagnosis.

Per-module evaluation of the format-SFT checkpoint on the full 300-case test set. This document records what SFT does well, what it does poorly, and how to reproduce the numbers from scratch.

Scope: **diagnosis only**. How to fix the weaknesses (further SFT, GRPO reward design, prompt changes, etc.) is not covered here — those decisions are still open.

---

## TL;DR

- Overall format compliance is essentially solved: **98.9%** of module outputs parse cleanly.
- The dominant pipeline failure mode is **intent routing**, not format and not module content. Router accuracy is **70.0%** with a strong "converse" bias; the `review` intent is effectively broken (4.8%).
- Downstream modules — when they are routed to at all — produce correct content at very high rates (text 100%, choice 100%, review-builder 89%).
- DataExtractor format is 85.0% loose / 77.3% strict; the gap is dominated by fabrication on cases whose ground truth is empty (separate issue from format learning).

---

## Checkpoint under test

| | |
|---|---|
| Model | Qwen3.5-0.8B + Format-SFT LoRA |
| MLX path | `~/work/models/qwen35-08b-dspy-format-mlx` |
| Source experiments | doc-12, Experiment 2 (Format SFT) |
| Test set | `tuning/data/test-cases.jsonl` (n = 300) |
| Eval script | `tuning/rl/eval_modules.py` |
| Server | `mlx_vlm.server` on `localhost:8089` |

---

## Test set composition

300 cases drawn from simulation logs. Gold-intent distribution (assigned by `infer_intent()` in `tuning/dspy/optimize_prompt.py`):

| Gold intent | Cases | Share |
|---|---|---|
| gather | 147 | 49.0% |
| clarify | 54 | 18.0% |
| converse | 49 | 16.3% |
| close | 29 | 9.7% |
| review | 21 | 7.0% |

Per-case routing fans out to one router call (`intent_decider`) plus the action-specific module:

| Module | Calls in this run |
|---|---|
| intent_decider | 300 (always) |
| data_extractor | 300 (run separately via `eval_grpo.py`) |
| text_responder | 49 |
| choice_builder | 54 |
| review_builder | 46 |

---

## Headline results

### Per-module summary (SFT, n = 300, 449 module calls excluding data_extractor)

| Module | n | format_ok | content / accuracy | Notes |
|---|---|---|---|---|
| intent_decider | 300 | **100.0%** | **70.0%** routing accuracy | converse-biased |
| text_responder | 49 | 100.0% | 100.0% | avg response length 343 chars |
| choice_builder | 54 | 100.0% | 100.0% | avg 3.3 options |
| review_builder | 46 | 89.1% | 89.1% | avg content length 1412 chars |
| **Overall format_ok** | — | **98.9%** | — | weighted across 449 calls |
| data_extractor | 300 | 85.0% loose / 77.3% strict | (see below) | run separately, see `preds_sft.jsonl` |

`format_ok` definitions per module:

- `intent_decider`: has `[[ ## completed ## ]]` marker AND predicted intent ∈ `{gather, converse, clarify, close, review}`.
- `text_responder`: `completed` marker AND `response_text` marker present.
- `choice_builder`: `completed` marker AND non-empty question AND parseable options list.
- `review_builder`: `completed` marker AND non-empty `title` AND non-empty `content`.
- `data_extractor` (loose): both list markers present (markers-only).
- `data_extractor` (strict): markers-only criterion AND `field_names` and `values` lists have equal length.

### intent_decider per-class accuracy

| Gold intent | Correct | Acc |
|---|---|---|
| gather | 127 / 147 | 86.4% |
| converse | 43 / 49 | 87.8% |
| close | 15 / 29 | 51.7% |
| clarify | 24 / 54 | 44.4% |
| **review** | **1 / 21** | **4.8%** |

### intent_decider top confusions (90 mistakes total)

| Gold → Pred | Count |
|---|---|
| review → converse | 19 |
| clarify → converse | 19 |
| close → converse | 13 |
| gather → clarify | 12 |
| clarify → gather | 9 |
| gather → converse | 6 |
| converse → gather | 3 |
| converse → clarify | 2 |
| gather → close | 2 |
| clarify → close | 2 |
| review → close | 1 |
| converse → close | 1 |
| close → clarify | 1 |

The pattern is a "converse pull": when in doubt, the router predicts `converse`, which silently routes the turn through `text_responder` and bypasses extraction / choice / review entirely. The format envelope still parses, so the failure is invisible to format-only metrics.

### data_extractor (from earlier `eval_grpo.py` run on the same 300 cases)

- Loose format_ok (markers present): **85.0%**
- Strict format_ok (markers + equal-length lists): **77.3%**
- Failure mode: fabrication on inputs whose ground truth is empty/refusal — the model invents field names and values (e.g., the `"Maria Garcia"` + DOB case in `preds_sft.jsonl`). Mismatched list lengths are mostly a downstream symptom of this fabrication, not a separate format-learning failure.

---

## What SFT learned well

1. **Output envelope across all five module signatures.** Marker emission, the `[[ ## completed ## ]]` closer, and field ordering parse cleanly at ≥89% on the worst module and 100% on three of the five.
2. **Pure extraction (gather) and pure conversation (converse).** Both clear 86–88% routing accuracy and produce correct downstream content when routed.
3. **Choice and text content quality.** When routing puts a turn into `text_responder` or `choice_builder`, the produced content is correct in 100% of sampled cases. The downstream modules are not the bottleneck.
4. **review_builder format.** Journal previously claimed 75%; the full n=46 run shows 89.1%, better than reported.

## What SFT did not learn (or learned wrong)

1. **`review` intent is effectively broken.** 1/21 = 4.8%. 19/21 review turns are misclassified as `converse`. Examples include "Draft restored. 15 fields previously filled" and "recommendation letters still shows 0/4 — is that expected?" — turns that need the structured review path but get a freeform reply instead.
2. **`clarify` and `close` are at coin-flip accuracy.** clarify 44.4%, close 51.7%. Both lose primarily to `converse`. The router does not reliably distinguish "user is asking a meta question" or "user is signaling submit/save" from "user is chatting."
3. **`gather → clarify` over-asking.** 12 cases where the user provided enough information to extract but the router asked for clarification instead. This is a more conservative failure mode than fabrication but still drops throughput.
4. **DataExtractor fabrication on empty inputs.** Format learning succeeded for non-empty cases; the model has not learned that "no extractable data → emit empty lists." Instead it invents field/value pairs.
5. **review_builder format edges.** 5 / 46 cases miss the non-empty title+content check. Smallest of the issues, but real.

---

## Reproducing the diagnosis

All commands assume cwd = `python/` so `uv run` picks the right venv (the `python/` directory holds the `uv` project that has `mlx_vlm`, `dspy`, etc. installed).

### 1. Start the SFT model server

```bash
cd <repo-root>/python
uv run python -m mlx_vlm.server \
  --model "$HOME/work/models/qwen35-08b-dspy-format-mlx" \
  --port 8089 \
  > /tmp/eval-modules-sft-8089.log 2>&1 &
echo $! > /tmp/eval-modules-sft-8089.pid
```

Wait until `/tmp/eval-modules-sft-8089.log` shows the server is listening.

### 2. Run the per-module eval (modules other than data_extractor)

```bash
cd <repo-root>/python
uv run python ../tuning/rl/eval_modules.py \
  --url http://localhost:8089/v1/chat/completions \
  --model-path "$HOME/work/models/qwen35-08b-dspy-format-mlx" \
  --checkpoint-name sft \
  --output ../tuning/rl/eval_results/ \
  --skip-modules data_extractor
```

Expected runtime on a Mac with mlx_vlm: ~15 min (449 calls × ~1.7s/call).

Outputs:

- `tuning/rl/eval_results/preds_modules_sft.jsonl` — one row per module call (test_id, module, user_message, raw_output, latency, metrics).
- `tuning/rl/eval_results/summary_modules_sft.json` — per-module aggregates.

`--skip-modules data_extractor` is used because we already have a 300-case DataExtractor prediction file from the prior `eval_grpo.py` run; rerunning would be redundant.

### 3. (Optional) Re-run DataExtractor only

```bash
cd <repo-root>/python
uv run python ../tuning/rl/eval_grpo.py \
  --url http://localhost:8089/v1/chat/completions \
  --model-path "$HOME/work/models/qwen35-08b-dspy-format-mlx" \
  --checkpoint-name sft \
  --output ../tuning/rl/eval_results/
```

Output: `tuning/rl/eval_results/preds_sft.jsonl` and `summary_sft.json`.

### 4. Stop the server when done

```bash
kill $(cat /tmp/eval-modules-sft-8089.pid)
rm /tmp/eval-modules-sft-8089.pid
```

### 5. Reproduce the intent confusion table

```bash
cd <repo-root>/python
uv run python - <<'PY'
import json
from collections import Counter, defaultdict

correct = defaultdict(int)
total = defaultdict(int)
mistakes = []

path = "../tuning/rl/eval_results/preds_modules_sft.jsonl"
with open(path) as f:
    for line in f:
        r = json.loads(line)
        if r.get("module") != "intent_decider":
            continue
        m = r["metrics"]
        gold, pred = m["gold_intent"], m["pred_intent"]
        total[gold] += 1
        if gold == pred:
            correct[gold] += 1
        else:
            mistakes.append((gold, pred))

print("Per-gold-intent accuracy:")
for g in sorted(total):
    print(f"  {g:>10s}: {correct[g]:>3}/{total[g]:<3} = {100*correct[g]/total[g]:5.1f}%")

print("\nConfusion (gold -> pred):")
for (g, p), v in Counter(mistakes).most_common():
    print(f"  {g:>10s} -> {p:>10s}: {v}")
PY
```

---

## File index

| Artifact | Path |
|---|---|
| Eval script (5 modules) | `tuning/rl/eval_modules.py` |
| Eval script (DataExtractor only) | `tuning/rl/eval_grpo.py` |
| Test cases | `tuning/data/test-cases.jsonl` |
| DSPy signatures + `infer_intent()` | `tuning/dspy/optimize_prompt.py` |
| SFT per-module predictions | `tuning/rl/eval_results/preds_modules_sft.jsonl` |
| SFT per-module summary | `tuning/rl/eval_results/summary_modules_sft.json` |
| SFT DataExtractor predictions | `tuning/rl/eval_results/preds_sft.jsonl` |
| SFT DataExtractor summary | `tuning/rl/eval_results/summary_sft.json` |
| Smoke run (n=30, all modules) | `tuning/rl/eval_results/preds_modules_sft-smoke30.jsonl` |
| Smoke run (n=30, no extractor) | `tuning/rl/eval_results/preds_modules_sft-smoke30-no-extractor.jsonl` |

---

## Reconciliation with doc-12 journal

Earlier per-module numbers in doc-12 (Experiment 3 area) came from `tuning/sft/compare_models.py`, which prints aggregates but does **not** persist raw predictions, so they are not directly reproducible from saved files. Where the new run differs:

| Module | doc-12 claim | This run | Note |
|---|---|---|---|
| intent_decider | 100% (format) | 100% format / 70% accuracy | doc-12 reported format only; routing accuracy was not split out. |
| data_extractor | 99.3% format | 85.0% loose / 77.3% strict | doc-12 used loose (markers only) on a 151-case positive subset; this run uses the full 300, with strict adding the equal-length constraint. The 85% loose vs 99.3% loose gap is the empty-GT cases on which SFT fabricates. |
| choice_builder | 100% | 100% | matches |
| review_builder | 75% | 89.1% | better than reported |
| text_responder | not measured | 100% format / 100% content | new — `compare_models.py` did not test this module. |
