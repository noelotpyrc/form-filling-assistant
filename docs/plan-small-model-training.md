# Plan: Small Model Training Pipeline

## Overview

Build a pipeline to fine-tune small open-source models on synthetic training data from our simulation logs, targeting two deployment paths:

- **Track 1**: SmolLM2-360M → fine-tune → ONNX export → browser inference via transformers.js
- **Track 2**: Qwen 0.8B–4B → fine-tune → serve locally via MLX on Mac

Both tracks share the same training data, format, and evaluation criteria. Track 2 is the faster path (larger model, likely better results). Track 1 is the ambitious path (fully in-browser, no server).

## Prerequisites

- [x] Simulation logs exist (doc-9 JSONL format with `llm_a_input` + `llm_a_output` pairs)
- [x] Auto-scorer exists (5 criteria: text, delimiter, JSON, action types, field extraction)
- [x] Model test infrastructure exists (`model-test.html` + CLI script)
- [ ] Sufficient training data generated (need 5–25 simulation runs → 100–500 examples)
- [ ] 32GB Mac available for browser testing of 0.5B+ models

## Phase 0: Training Data Preparation

**Goal**: Convert simulation JSONL logs into fine-tuning format.

### Tasks

1. **Build data conversion script** — Read session JSONL, extract `llm_a_input` + `llm_a_output` pairs, output chat-format JSONL:
   ```json
   {"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
   ```
2. **Generate sufficient training data** — Run 10–20 simulation sessions across personas/profiles. Target: 300+ training examples.
3. **Quality filter** — Only keep turns where Claude's output passes all 5 scoring criteria. Reject malformed outputs.
4. **Curriculum sort** — Order examples by complexity: greeting → single field → multi-field → choices → file handling → error recovery.
5. **Train/eval split** — 80/20 split. Ensure eval set covers all complexity levels.

**Output**: `training-data/sft-train.jsonl`, `training-data/sft-eval.jsonl`

**Dependency**: Need more simulation runs. Current logs may not have enough volume.

## Phase 1: SFT with LoRA

**Goal**: Teach the model our `text + ---actions--- + JSON` format.

### Track 2 (primary — faster path)

1. **Install MLX LM** on Mac: `pip install mlx-lm`
2. **Download base model**: `mlx_lm.convert --hf-path Qwen/Qwen3-0.6B-Instruct` (start with 0.6B, scale to 4B if needed)
3. **Fine-tune with MLX LoRA**:
   ```bash
   mlx_lm.lora --model <converted_model> --data training-data/ --train --iters 500 --batch-size 2
   ```
4. **Evaluate**: Run all 5 test cases against fine-tuned model, compare pass rates vs base model
5. **Serve**: `mlx_lm.server --model <model> --adapter-path <lora_adapter>` — OpenAI-compatible API on localhost
6. **Integrate**: Point web app at localhost API instead of Claude

### Track 1 (secondary — depends on Track 2 results)

1. **Fine-tune SmolLM2-360M** — Use Unsloth (cloud GPU) or MLX LoRA (Mac, slower)
2. **Merge LoRA**: `model.merge_and_unload()` → save merged model
3. **Export to ONNX**: `optimum-cli export onnx --model <merged> --task text-generation`
4. **Quantize**: `python -m scripts.convert --quantize` (q4f16 for WebGPU)
5. **Test in browser**: Load via transformers.js on `model-test.html`
6. **Integrate**: Add transformers.js to web app, replace Claude API calls

### Success criteria

- **Minimum**: >60% of test cases pass (format compliance)
- **Good**: >80% pass rate + correct field extraction on simple cases
- **Great**: >90% pass rate + correct field extraction on all cases

## Phase 2: Refinement (after Phase 1 shows promise)

### Option A: Rejection Sampling + SimPO

1. Generate 10 completions per eval input from the fine-tuned student model
2. Score each with auto-scorer
3. Build preference pairs: passing outputs (chosen) vs failing outputs (rejected)
4. Run SimPO/ORPO training (single-stage, no separate SFT needed)

### Option B: DSPy GEPA (Track 2 only)

1. Define our task as a DSPy program (system prompt → model → parse actions)
2. Define metric using auto-scorer
3. Run GEPA optimizer to evolve the system prompt
4. Evaluate: does optimized prompt + base model match fine-tuned model quality?

### Option C: Constrained Decoding (Track 2 only)

1. Define GBNF grammar for `text + ---actions--- + JSON array`
2. Apply at inference time via MLX/llama.cpp
3. This guarantees format compliance — model only needs to get content right

## Phase 3: GRPO/RAFT (only if Phase 2 insufficient)

1. Define reward function from auto-scorer (5 criteria → scalar reward)
2. Run GRPO: generate N completions, rank by reward, optimize policy
3. Or simpler RAFT: generate, filter top-k by reward, SFT on filtered set

## Decision Points

| After | Evaluate | Decision |
|-------|----------|----------|
| Phase 0 | Enough training data? | If <100 examples, run more simulations first |
| Phase 1 Track 2 | Qwen 0.6B fine-tuned pass rate | If >80%, proceed to Track 1. If <60%, try Qwen 4B instead. |
| Phase 1 Track 1 | SmolLM2-360M fine-tuned pass rate | If <50%, abandon Track 1 — model too small. Focus on Track 2. |
| Phase 2 | Pass rate improvement | If >90%, ship it. If <80%, proceed to Phase 3. |

## Framework Choices

| Component | Choice | Reason |
|-----------|--------|--------|
| Fine-tuning (Mac) | MLX LoRA | Native Apple Silicon, handles both training and serving |
| Fine-tuning (cloud) | Unsloth | 2x faster, 80% less VRAM, free Colab support |
| Serving (Track 2) | MLX LM server | OpenAI-compatible API, runs on Mac |
| Browser inference (Track 1) | transformers.js | Only viable option for in-browser LLM |
| ONNX export | optimum-cli | HuggingFace standard tool |
| Prompt optimization | DSPy GEPA | Uses error traces, not just scalar rewards |
| Constrained decoding | llama.cpp GBNF or XGrammar | Fast, low overhead |

## Estimated Timeline

| Phase | Effort | Dependency |
|-------|--------|-----------|
| Phase 0: Data prep | 1–2 days | Need simulation runs |
| Phase 1 Track 2: MLX fine-tune | 2–3 days | Phase 0 |
| Phase 1 Track 1: ONNX export | 1–2 days | Phase 1 Track 2 results |
| Phase 2: Refinement | 2–3 days | Phase 1 |
| Phase 3: GRPO (if needed) | 2–3 days | Phase 2 |

## Open Questions

1. **System prompt in training data**: Should we include the full system prompt in every training example, or use a compressed version? Full prompt = model learns to follow it. Compressed = smaller context, more room for conversation.
2. **Multi-turn vs single-turn training**: Each example is one turn. Should we also train on multi-turn sequences (consecutive turns from the same session) to teach conversation flow?
3. **Qwen3 `<think>` tokens**: Should we strip `<think>` blocks from training data (teach model to skip reasoning), or keep them (model learns to reason then respond)? Stripping saves tokens but may hurt quality.
4. **How many simulation runs**: 10 runs × 25 turns = 250 examples. Is that enough? Literature suggests 100–500 for SFT on small models. May need 20+ runs.
