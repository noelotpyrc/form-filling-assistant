# Doc 11: Small Model Research — Browser Inference

## Goal

Replace Claude (cloud API) with a small open-source model running **entirely in the browser** via transformers.js + WebGPU. The model must play the LLM A role: read the system prompt, converse with the user, and emit `text + ---actions--- + JSON` output.

## Constraints

- **Runtime**: Browser only. No server. transformers.js + WebGPU (ONNX format).
- **Download size**: Under ~1.5GB (q4f16 quantized) for reasonable first-load experience.
- **Context window**: Our system prompt (~10KB) + form schema (~17KB) + conversation = ~7K+ tokens before the first user message. Model must handle this.
- **Output format**: Must produce `text + ---actions--- + JSON` matching our existing action parser. No tool_use protocol — raw text output only.
- **Latency**: Usable at ≥10 tok/s for conversational feel.
- **Memory**: Must run in browser on a 16GB Mac (unified memory, shared between CPU and GPU). Models ≥0.5B overflow the WebGPU/WASM buffer on 16GB machines. 32GB machines can run 0.5B–0.6B models.

## Test Results Summary

| Model | Params | Loads (16GB)? | Loads (32GB)? | Follows format? | Notes |
|-------|--------|--------------|--------------|----------------|-------|
| SmolLM2-135M | 135M | ✅ WebGPU | ✅ | ❌ Ignores prompt entirely | Produces generic filler text. Too small. |
| SmolLM2-360M | 360M | ✅ WebGPU | ✅ | ❌ Acknowledges form, no actions | Understands context but can't produce structured output. Potentially fine-tunable. |
| Qwen2.5-0.5B | 0.5B | ❌ Buffer overflow | 🔲 Untested | 🔲 Untested | WebGPU + WASM both fail on 16GB. Needs 32GB machine. |
| Qwen3-0.6B | 0.6B | ❌ Buffer overflow | 🔲 Untested | ✅ All checks pass (CLI) | Follows `text + ---actions--- + JSON` format with zero fine-tuning. Needs 32GB for browser. |

### Key finding: 0.6B is the minimum for instruction-following

The floor for following our structured output format (without fine-tuning) is between 360M and 600M parameters:
- **135M**: Ignores system prompt completely — outputs random conversational filler
- **360M**: Acknowledges form context but cannot produce `---actions---` delimiter or JSON actions
- **600M (Qwen3)**: Successfully produces `text + ---actions--- + JSON` with valid action types

### Key finding: 16GB Mac browser memory is the bottleneck

On a 16GB Mac (unified memory), WebGPU and WASM both fail to allocate buffers for models ≥0.5B:
- Qwen3-0.6B (`q4`): `failed to allocate a buffer of size 919096585` (WASM)
- Qwen2.5-0.5B (`q4f16`): `Failed to execute 'createBuffer' on 'GPUDevice': Value is outside the 'unsigned long long' value range` (WebGPU)
- SmolLM2-360M (`q4f16`): Loads and runs fine on WebGPU

A **32GB Mac** should handle 0.5B–0.6B models comfortably.

## Model Candidates

### Tested

| Model | Params | ONNX ID | Download | Context | Status |
|-------|--------|---------|----------|---------|--------|
| SmolLM2-135M | 135M | `HuggingFaceTB/SmolLM2-135M-Instruct` | ~100MB | 8K | ❌ Too small for instruction-following |
| SmolLM2-360M | 360M | `HuggingFaceTB/SmolLM2-360M-Instruct` | ~250MB | 8K | ❌ Raw fails, but potentially fine-tunable |
| Qwen2.5-0.5B | 0.5B | `onnx-community/Qwen2.5-0.5B-Instruct` | ~350MB | 32K | 🔲 Needs 32GB machine for browser test |
| Qwen3-0.6B | 0.6B | `onnx-community/Qwen3-0.6B-ONNX` | ~400MB | 32K | ✅ CLI passes, needs 32GB for browser |

### Not tested

| Model | Params | Status | Notes |
|-------|--------|--------|-------|
| Llama-3.2-1B-Instruct | 1B | ✅ ONNX available | Too big for 16GB browser. Proven WebGPU demo on larger machines (~10 tok/s). |
| Gemma-3n-E2B | 5B (2B effective) | ⚠️ ONNX broken | Open issue [#1383](https://github.com/huggingface/transformers.js/issues/1383). Novel architecture — only 2B VRAM. Worth watching. |
| Phi-3-mini-4k | 3.8B | ✅ ONNX available | Too big for browser on most machines. |

## Detailed Test Results

### Qwen3-0.6B — CLI (Node.js WASM)

**Greeting test: ALL 5 SCORES PASS** ✅

| Score | Result |
|-------|--------|
| Has text output | ✅ Pass |
| Has `---actions---` delimiter | ✅ Pass |
| Valid JSON actions (1) | ✅ Pass |
| All action types valid | ✅ Pass |
| Conversational text (1762 chars) | ✅ Pass |

**Observations:**
- Model understood the system prompt and produced valid `text + ---actions--- + JSON` format
- Qwen3 has built-in `<think>` reasoning — consumes ~500 tokens before the actual response. With 256 max tokens, the model spent all tokens thinking. **1024 max tokens** needed.
- WASM inference: ~2 tok/s (259s for 1024 tokens). WebGPU expected: 15–30 tok/s.
- System prompt used: compact (~20K chars), which strips file handling, system events, and verbose examples

### SmolLM2-135M — Browser (WebGPU q4f16)

**Simple answer test ("Jane Smith"): FAIL** ❌

Output (257 chars):
```
You can. Just choose the fields you want to fill and fill them in with set_fields.
Here's an example of what you can use.
I'm sorry for the misunderstanding, it seems I can not answer the specific user.
Do you have any specific fields you want to fill out?
```

- No `---actions---` delimiter
- No field extraction from user input
- Generic, vague text — model essentially ignored the system prompt
- Token callback count: 0 (streaming callbacks didn't fire)
- Generation time: ~14s on Node WASM, near-instant on browser WebGPU

### SmolLM2-360M — Browser (WebGPU q4f16)

**Simple answer test ("Jane Smith"): FAIL** ❌ (but better)

Output (386 chars):
```
The user has provided you with a description of their current form. To assist you better,
I would like to know more about their current form. What information can you provide about
their current form, such as their field values, their field types (e.g. text, email, etc.),
and any relevant details they have entered so far?
```

- No `---actions---` delimiter
- No field extraction
- **Acknowledges form context** — mentions "field values", "field types", "current form"
- Confused about its role (talks about user in third person)
- Improvement over 135M: understands the domain, just can't produce structured output

## System Prompt Sizes

Three prompt tiers for testing:

| Mode | Size | Content | Use case |
|------|------|---------|----------|
| **Minimal** | ~2K chars | Format instructions + field list, no schema | Testing if model can follow format at all |
| **Compact** | ~20K chars | Format + schema + section order, no examples/file handling | CLI tests, browser tests on small models |
| **Full** | ~30K chars | Production system prompt from `system-prompt.js` | Production use with capable models |

The compact prompt (used in CLI tests) strips: file handling instructions, system events, show_fields/show_preview/show_button examples, and verbose behavior guidelines.

## Browser Memory Requirements

On Mac with unified memory (shared CPU+GPU):

| Model size | q4f16 download | Runtime memory (est.) | 16GB Mac | 32GB Mac |
|-----------|---------------|----------------------|----------|----------|
| 135M | ~100MB | ~300MB | ✅ | ✅ |
| 360M | ~250MB | ~600MB | ✅ | ✅ |
| 0.5B | ~350MB | ~900MB | ❌ | ✅ (expected) |
| 0.6B | ~400MB | ~1GB | ❌ | ✅ (expected) |
| 1B | ~700MB | ~1.5GB | ❌ | ⚠️ Tight |

Note: Runtime memory includes weights + KV cache + activations. The KV cache grows with input length — our ~5K token system prompt contributes significantly.

## Training Methods: Comprehensive Comparison

Our task: teach a small model to produce `text + ---actions--- + JSON` using synthetic training data generated by Claude (the "teacher"). This section surveys all viable methods.

### 1. Supervised Fine-Tuning (SFT)

The baseline approach. Train directly on (input, output) pairs from simulation logs.

**How it works**: Each `llm_a_input` + `llm_a_output` from our JSONL logs becomes a training example. The model learns to predict the teacher's output given the same input.

**Variants:**

| Method | Description | Pros | Cons |
|--------|-------------|------|------|
| **Full fine-tune** | Update all model weights | Best quality for small models (360M–0.6B are small enough) | Needs more VRAM, can't share base weights |
| **LoRA** | Low-rank adapters, freeze base weights | 99%+ parameter reduction, fast, composable | Slightly lower quality than full |
| **QLoRA** | LoRA on quantized base model | Even less VRAM (can train 0.6B on 8GB GPU) | Quantization adds noise |

**Best for**: Our primary approach. Start here.

### 2. Rejection Sampling Fine-Tuning (RFT / RAFT)

Generate multiple outputs per input, filter to keep only correct ones, then SFT on the filtered set.

**How it works**: For each training input, generate N completions from the student model. Score each using our existing auto-scorer (has delimiter? valid JSON? correct action types?). Keep only passing outputs. Fine-tune on those.

**Why it matters for us**: Our scoring criteria are programmatic (not subjective), making rejection sampling straightforward. Recent research (2025) shows RAFT yields competitive performance with GRPO and PPO while being much simpler.

**Best for**: Phase 2 — after initial SFT, use rejection sampling to refine the model's output quality.

### 3. Knowledge Distillation

Train the student to match the teacher's behavior more deeply than just input-output pairs.

**Variants:**

| Method | Description | Applicability |
|--------|-------------|---------------|
| **Standard KD** (logit matching) | Match teacher's token probability distributions | Requires teacher logits — not available from Claude API |
| **Sequence-level KD** | Train on teacher's generated sequences | ✅ This is effectively what our SFT does |
| **Chain-of-Thought distillation** | Include teacher's reasoning in training data | Could use Qwen3's `<think>` traces as training signal |
| **Curriculum distillation** | Progress from easy to hard examples | ✅ Applicable — start with simple turns (greeting, single field), progress to multi-field extraction |

**Pedagogically-inspired approach** (2025 paper): A three-stage pipeline — Knowledge Identifier (find what student doesn't know), Organizer (build progressive curriculum), Adapter (generate data matched to student's level). Relevant because our test cases already range from trivial (greeting) to hard (multi-field extraction).

**Best for**: Improving data efficiency. Curriculum ordering of our training data (simple turns first, complex turns later) is low-hanging fruit.

### 4. Preference Optimization (DPO / SimPO / ORPO)

Train the model to prefer good outputs over bad ones, using pairs of (chosen, rejected) examples.

| Method | Description | Needs reference model? | Notes |
|--------|-------------|----------------------|-------|
| **DPO** | Direct Preference Optimization | Yes | Standard approach. Needs SFT first. |
| **SimPO** | Simple PO with reference-free reward | No | Simpler than DPO, competitive performance. State-of-the-art for <10B models (Gemma-2-9B-it-SimPO). |
| **ORPO** | Odds Ratio PO | No | Combines SFT + preference in one stage. No separate SFT needed. |
| **KTO** | Kahneman-Tversky Optimization | No | Works with unpaired data (just good or bad, not paired). |

**How to build preference pairs for our task:**
- **Chosen**: Teacher (Claude) outputs that pass all 5 scoring criteria
- **Rejected**: Student model's outputs that fail (missing delimiter, invalid JSON, wrong action types)
- Can also use teacher outputs vs deliberately degraded outputs (remove delimiter, corrupt JSON)

**Best for**: Phase 2 — after SFT gets the model close, preference optimization sharpens format compliance.

### 5. Reinforcement Learning (GRPO / PPO)

Optimize the model using reward signals rather than supervised examples.

| Method | Description | Notes |
|--------|-------------|-------|
| **PPO** | Proximal Policy Optimization | Classic RLHF. Heavy (needs reward model + value model). Overkill for our task. |
| **GRPO** | Group Relative Policy Optimization | DeepSeek's method. Simpler than PPO — no value model. Samples multiple responses, ranks by reward, optimizes. |
| **RAFT** | Reward-ranked fine-tuning | Simplest RL-adjacent method. Generate, score, train on top-k. Competitive with GRPO/PPO (2025 finding). |

**Reward function for our task**: Our auto-scorer (5 criteria) can serve directly as the reward function:
1. Has text? (+0.2)
2. Has `---actions---`? (+0.2)
3. Valid JSON? (+0.2)
4. Correct action types? (+0.2)
5. Correct field extraction? (+0.2)

**Best for**: When SFT + preference optimization plateau. GRPO or RAFT could push format compliance from 80% → 95%.

### 6. Constrained Decoding (inference-time, no training)

Force valid output structure at generation time by masking invalid tokens.

| Framework | Speed | Approach | Notes |
|-----------|-------|----------|-------|
| **Outlines** | Moderate | FSM from JSON schema | Complex schemas can be slow to compile (40s–10min) |
| **XGrammar** | Fast | CFG with FSM-level perf | Up to 100x faster than traditional grammar methods |
| **llguidance** | Very fast | ~50μs/token | Guidance-ai's engine. Negligible overhead. |
| **llama.cpp GBNF** | Fast | Grammar specification | Built into llama.cpp. Works with MLX via external tools. |

**How it applies**: Define a grammar that enforces `text + ---actions--- + [JSON array]`. The model can only generate tokens that match this pattern.

**Key insight**: This doesn't improve the model's understanding — it just forces the output shape. A model that would generate garbage still generates garbage, but in valid JSON format. Best combined with fine-tuning.

**Best for**: Track 2 (API serving via MLX/llama.cpp). Ensures 100% format compliance at inference time. Not available for transformers.js (Track 1).

### Method Comparison Summary

| Method | Training needed? | Data requirement | Complexity | Expected impact | Phase |
|--------|-----------------|-----------------|------------|----------------|-------|
| **SFT (LoRA)** | Yes | 100–500 examples | Low | High — teaches format | 1 |
| **Rejection sampling** | Yes | Generated from student | Low | Medium — filters quality | 2 |
| **Curriculum ordering** | No (data reordering) | Same data, sorted | Low | Low-Medium — improves efficiency | 1 |
| **DPO/SimPO** | Yes | Preference pairs | Medium | Medium — sharpens compliance | 2 |
| **GRPO/RAFT** | Yes | Reward function | Medium-High | Medium-High — pushes last 20% | 3 |
| **Constrained decoding** | No | None | Low | High for format, zero for quality | Any (Track 2 only) |

### Recommended Pipeline

```
Step 0: Extract atomic training data from simulation sessions
Step 1: Serve SmolLM2-360M + Qwen 0.8B via MLX locally
Step 2: Test both models raw — baseline evaluation
Step 3: DSPy prompt optimization on both models (GEPA/MIPROv2)
Step 4: Decide SFT necessity per model
Step 5: SFT with Unsloth on Google Colab (if needed)
Step 6: Deploy — ONNX for browser (Track 1), MLX for local API (Track 2)
Step 7: Preference optimization — DPO/SimPO/GRPO (if needed)
```

**Step 0** — Extract all LLM A turns from simulation JSONL logs into atomic training records (user_message, assistant_output, form_state, conversation_history, metadata). Run quality stats and filter broken sessions.

**Step 1** — Serve both candidate models locally via MLX (`mlx_lm.server` — OpenAI-compatible API). Both SmolLM2-360M and Qwen 0.8B run on Mac with unified memory.

**Step 2** — Feed our system prompt + test cases to raw (untuned) models. Evaluate format compliance, action accuracy. This sets the baseline for each model.

**Step 3** — Use DSPy (GEPA or MIPROv2) to optimize the system prompt for each model. DSPy calls the local MLX server, evaluates against our ground truth data, and evolves the prompt. No Claude API needed — we already have expected outputs from simulation logs.

**Step 4** — If the optimized prompt produces good results → skip SFT, deploy with optimized prompt. If not → proceed to SFT, using the optimized prompt as the system prompt in training examples.

**Step 5** — Fine-tune with LoRA via Unsloth on Google Colab (free T4 GPU). Export to HuggingFace format.

**Step 6** — Convert trained model to deployment format:
- Track 1 (browser): HuggingFace → ONNX → transformers.js
- Track 2 (local API): HuggingFace → MLX → `mlx_lm.server`

**Step 7** — If format compliance plateaus, apply preference optimization (DPO/SimPO with chosen/rejected pairs) or RL (GRPO/RAFT with auto-scorer as reward). Constrained decoding at inference time (Track 2 only) as a final safety net.

## Prompt Tuning Pipeline (Claude — for training data quality)

Before fine-tuning small models, we should optimize the Claude system prompt to produce better training data. Claude already follows instructions and outputs structured data perfectly — the tuning target is **behavioral quality**: when to batch fields, conversation tone, section transitions, error handling, etc.

### Iterative tuning loop

```
Run simulation → Review in /replay.html → Identify behavioral issues
    → Edit system prompt → Re-run simulation → Compare metrics
```

### What to tune (behavioral, not format)

| Aspect | Example issue | Prompt fix |
|--------|--------------|------------|
| **Fields per turn** | Asks one field at a time (slow) | "Batch related fields together when possible" |
| **Tone** | Too formal / too verbose | Adjust personality guidelines |
| **Section transitions** | Abrupt jumps between sections | "Summarize completed section before moving on" |
| **Error handling** | Confused by ambiguous input | Add examples of graceful clarification |
| **Choice presentation** | Always uses ask_choice even when unnecessary | Refine rules for when to use each action type |

### Quantitative metrics (from simulation logs)

- **Fields per turn** — higher is more efficient
- **Turns to complete** — lower is better
- **Action type distribution** — healthy mix of set_fields, ask_choice, show_fields
- **User satisfaction proxy** — LLM U stop reason (completed vs stuck vs max_turns)

These metrics can be computed directly from the JSONL logs. A comparison script would load two session logs and show the deltas.

### Why not DSPy/GEPA for this?

DSPy requires a direct LLM API (OpenAI-compatible or Anthropic SDK). Our setup uses a Claude CLI wrapper (`ClaudeAgent`), which spawns `claude` CLI processes — not compatible with DSPy's LM interface without a custom adapter. The manual iteration loop is simpler, faster to set up, and gives us direct control over what we're optimizing.

## Fine-Tuning Frameworks

| Framework | Type | GPU needed | Mac support | ONNX export | Best for |
|-----------|------|-----------|-------------|-------------|----------|
| **Unsloth** | LoRA/QLoRA trainer | NVIDIA (CUDA) | ❌ | Via HF export | Fast training, low VRAM. 2x speed, 80% less VRAM. Best for single-GPU training. |
| **MLX LoRA** | LoRA trainer + serving | Apple Silicon | ✅ Native | ❌ (MLX format) | Mac-native. Fine-tune AND serve on same machine. Track 2 primary choice. |
| **LLaMA-Factory** | All-in-one (SFT/DPO/PPO/ORPO) | NVIDIA or Apple | ✅ Via MLX backend | Via HF export | Web UI, most training methods supported, 100+ models. Good for experimentation. |
| **Axolotl** | Config-driven trainer | NVIDIA (CUDA) | ❌ | Via HF export | Multi-GPU, production pipelines. Overkill for our scale. |
| **TRL** | HuggingFace trainer library | NVIDIA or CPU | Partial | Via HF export | Official HF. Supports SFT, DPO, GRPO, KTO. Most ecosystem support. |
| **Torchtune** | PyTorch-native trainer | NVIDIA or MPS | ✅ (MPS) | Via HF export | Deep customization. Meta's official tool. |

### Framework recommendation for our setup (Mac)

**Track 1 (SmolLM2-360M → browser):**
1. Fine-tune with **Unsloth** or **TRL** on a cloud GPU (Colab/Lambda/etc.) or locally with **MLX LoRA**
2. Merge LoRA adapter into base model
3. Export to ONNX: `python -m scripts.convert --quantize --model_id <merged_model>`
4. Deploy via transformers.js in browser

**Track 2 (Qwen 0.8B–4B → local API):**
1. Fine-tune with **MLX LoRA** directly on Mac (native, no cloud needed)
2. Serve with **MLX LM server** (`mlx_lm.server` — OpenAI-compatible API on localhost)
3. Optionally add constrained decoding via grammar/outlines integration

### ONNX Export Pipeline (Track 1)

```
Base model (HuggingFace)
  → Fine-tune with LoRA (Unsloth/TRL/MLX)
  → Merge adapter into base: model.merge_and_unload()
  → Export to ONNX: optimum-cli export onnx --model <merged> --task text-generation
  → Quantize: python -m scripts.convert --quantize (q4f16 for WebGPU)
  → Upload to HuggingFace or serve locally
  → Load in browser via transformers.js
```

Note: LoRA adapters cannot be loaded separately in transformers.js — they must be merged into the base model before ONNX export.

## Training Data Preparation

Our simulation logs (doc-9) are the training data source. Each session JSONL contains turn-by-turn exchanges.

### Format conversion needed

From session log entry pairs:
```json
{"type": "llm_a_input", "turn": 5, "user_message": "Jane Smith, born May 15 1998"}
{"type": "llm_a_output", "turn": 5, "raw_text": "Great, I'll record your name and date of birth.\n\n---actions---\n```json\n[{\"type\": \"set_fields\", ...}]\n```"}
```

To training format (chat-style):
```json
{
  "messages": [
    {"role": "system", "content": "<system prompt>"},
    {"role": "user", "content": "Jane Smith, born May 15 1998"},
    {"role": "assistant", "content": "Great, I'll record your name and date of birth.\n\n---actions---\n```json\n[{\"type\": \"set_fields\", ...}]\n```"}
  ]
}
```

### Data quantity estimate

- 1 simulation session = 20–30 turns = 20–30 training examples
- Need ~100–500 high-quality examples for SFT on small models
- **5–25 simulation runs** should produce enough data
- Quality > quantity: filter to only turns where Claude produced valid output (rejection sampling on teacher data)

### Curriculum ordering

Sort training examples by complexity:
1. **Easy**: Greeting (no user data), simple acknowledgments
2. **Medium**: Single-field extraction ("Jane Smith" → set full_name)
3. **Hard**: Multi-field extraction, choice selection, file handling
4. **Hardest**: Error recovery, clarification requests, section transitions

## Next Steps: Two Parallel Tracks

### Track 1: Browser-native (transformers.js + SmolLM2-360M)

**Goal**: Fully in-browser inference — no server, no API, zero cloud dependency.

- **Model**: SmolLM2-360M (fits in 16GB browser, ~250MB download)
- **Status**: Loads and runs, but doesn't follow our output format without fine-tuning
- **Path**: Fine-tune on simulation logs → export to ONNX → integrate with web app via transformers.js
- **Risk**: 360M params may not have enough capacity even after fine-tuning
- **Conditional**: Don't integrate transformers.js into web app until fine-tuned model shows promising results

### Track 2: Local API (MLX + Qwen 0.8B–4B)

**Goal**: Local model served as API on Mac. Browser calls `http://localhost`. No cloud API, but requires a running local process.

- **Models**: Qwen3.5-0.8B (small, fast) or Qwen3.5-4B (better quality, still local)
- **Serving**: MLX (Apple's ML framework, optimized for Apple Silicon unified memory). Preferable over Ollama for Mac — better memory efficiency and supports LoRA fine-tuning natively.
- **Path**: Serve base model via MLX → test raw → fine-tune if needed → optionally add thin harness
- **Advantage**: Larger models (4B) likely follow our format without fine-tuning. Fine-tuning improves consistency.

### Shared work across both tracks

#### 1. Fine-tuning framework research

| Framework | Type | Notes |
|-----------|------|-------|
| **Unsloth** | LoRA/QLoRA fine-tuning | Direct weight training. Fast (2x speedup claimed). Supports SmolLM2, Qwen. Popular for small model fine-tuning. |
| **MLX LoRA** | Native Mac fine-tuning | Apple's own LoRA implementation. Runs directly on Apple Silicon. Could handle both Track 2 serving AND fine-tuning on the same machine. |
| **TRL** | HuggingFace trainer | Official HF library. Supports SFT, DPO, RLHF. Most ecosystem support. |

**Research needed**: Which framework best handles our use case (structured output fine-tuning on small models, with ONNX export for Track 1)?

#### 2. Agentic harness research (Track 2 only)

For the local API path, the question is what combination of harness + fine-tuning:

| Approach | Fine-tuning | Harness | Complexity | Expected quality |
|----------|------------|---------|------------|-----------------|
| Raw fine-tuned model | ✅ | None | Low | Good if fine-tuning works |
| Fine-tuned + thin harness | ✅ | JSON repair + retry | Low-Medium | Better reliability |
| Base model + full harness | ❌ | Agent loop, tool routing | High | Unknown — depends on model size |
| Fine-tuned + full harness | ✅ | Agent loop, tool routing | High | Best quality, most complex |

Also: **grammar-constrained decoding** (supported by llama.cpp, vLLM) can force valid JSON output at inference time without fine-tuning. MLX may support this via `outlines` or similar libraries. Worth investigating.

#### 3. Training data preparation

Both tracks use the same training data from simulation logs (doc-9):
- Each `llm_a_input` + `llm_a_output` pair = one training example
- System prompt + user message → expected text + actions
- 20–30 turns per session × multiple sessions = hundreds of examples
- Need a script to convert JSONL session logs to fine-tuning format (instruction/response pairs)

### Decision points

1. **After fine-tuning SmolLM2-360M**: If format compliance is poor (<50% pass rate), deprioritize Track 1 and focus on Track 2.
2. **After testing Qwen 4B raw on MLX**: If it follows our format without fine-tuning, Track 2 becomes the fast path — fine-tuning is optional polish.
3. **After comparing both tracks**: Choose primary deployment model. Can support both (browser for low-end, API for high-quality) if both work.

## MLX Eval Results (raw, no fine-tuning)

Tested 4 models served via MLX (`mlx_lm.server`) against 90 test cases sampled from simulation logs. Each test case sends the full system prompt + conversation history + user message, then scores the model output against Claude's ground truth.

### Overall comparison

| Metric | SmolLM2-360M | Qwen2.5-0.5B | Qwen3.5-0.8B | Qwen3.5-4B |
|--------|-------------|-------------|-------------|-------------|
| **Avg format score** | 0.68 | 0.64 | 0.92 | 0.85 |
| **Delimiter when expected** | 37/77 (48%) | 44/77 (57%) | **75/77 (97%)** | 66/77 (86%) |
| **Correctly omits delimiter** | 3/13 (23%) | 5/13 (38%) | 4/13 (31%) | **9/13 (69%)** |
| **Valid JSON** | 47% | 41% | **84%** | 69% |
| **Action type match** | 28% | 20% | 28% | **40%** |
| **Field recall** | 0.04 | 0.07 | 0.44 | **0.62** |
| **Field precision** | 0.04 | 0.06 | 0.38 | **0.63** |
| **Avg speed** | 4.3s | **3.2s** | 6.8s | 36.9s |

### Key findings

1. **Qwen3.5-0.8B has the best format compliance** (97% delimiter rate when actions are expected). It's the most reliable at following the `text + ---actions--- + JSON` pattern. However, it over-triggers — produces actions when it shouldn't (31% correct omission vs 4B's 69%).

2. **Qwen3.5-4B has the best task understanding** (40% action type match, 0.62 field recall, 0.63 field precision). It's smarter about when to produce actions and extracts fields more accurately. Format compliance is slightly lower (86% delimiter when expected) — SFT would fix this easily.

3. **The 4B "format gap" is misleading.** The raw format score (0.85 vs 0.92) favors 0.8B because 0.8B always produces delimiter (even when wrong), while 4B correctly omits it when no actions are needed. On cases where actions ARE expected, 0.8B is only 11% better at producing the delimiter (97% vs 86%).

4. **SmolLM2-360M and Qwen2.5-0.5B are not viable without SFT.** Both have <50% delimiter rate and near-zero field accuracy. They understand the domain slightly but can't follow the structured output format.

### Recommendation

- **Primary target**: Qwen3.5-0.8B — best format compliance, fast (6.8s), good enough quality for DSPy prompt optimization + light SFT
- **High-quality target**: Qwen3.5-4B — best understanding, needs SFT for format reliability, 5x slower
- **Experiment**: Fine-tune 4B → task-aware pruning → see if we get 4B quality at ~1-2B speed
- **Skip**: SmolLM2-360M and Qwen2.5-0.5B (unless SFT dramatically improves them)

## Tuning Experiments Summary

Detailed experiment logs are in **[doc-12-tuning-journal.md](doc-12-tuning-journal.md)**. Per-module evaluation of the format-SFT checkpoint (n=300) is in **[doc-13-sft-diagnosis.md](doc-13-sft-diagnosis.md)**.

### DSPy GEPA Prompt Optimization (Experiment 1)

Tested GEPA on Qwen3.5-0.8B with 5-module decomposition (IntentDecider → TextResponder → DataExtractor → ChoiceBuilder → ReviewBuilder). GPT-5 as reflection LM.

- **Result**: 0.131 → 0.548 (4.2x improvement), plateaued at iteration 13
- **Key finding**: Format compliance is the bottleneck, not prompt quality. Qwen 0.8B can't reliably produce DSPy's structured output markers (`[[ ## field ## ]]`). GEPA can improve prompts but can't fix the model's limited instruction-following capability.
- **Lesson**: Teach format first (SFT or constrained decoding), optimize content last (GEPA).

### Revised tuning pipeline

```
Step 1: Format SFT — teach model DSPy structured output format (200-500 examples, MLX LoRA)
Step 2: Constrained decoding — Outlines/GBNF as safety net for 100% format compliance
Step 3: Task SFT — fine-tune on form-filling data from simulation logs
Step 4: GEPA — optimize per-module prompts on the format-competent model
```

## Constrained Decoding for Small Models

The most promising approach for fixing format compliance. Instead of hoping the model outputs valid structured data, **constrain it at the token level** during generation.

### Frameworks

| Framework | Speed | How it works | Apple Silicon | Notes |
|-----------|-------|-------------|---------------|-------|
| **Outlines** | ⭐⭐ | FSM from JSON schema/regex/Pydantic | ✅ Native | 98% schema adherence. Provider-agnostic (works with MLX, transformers, llama.cpp). Most flexible. |
| **llama.cpp GBNF** | ⭐⭐⭐ | BNF grammar specification | ✅ Native | Built into llama.cpp. JSON schema → grammar auto-conversion. Smaller models benefit MORE from constraints. |
| **SGLang** | ⭐⭐⭐ | Compressed finite-state machines | Experimental | 2.5x throughput over alternatives. Best for scaling. |
| **Guidance** | ⭐⭐ | Earley's algorithm, interleaved Python control | ✅ | ~50μs overhead per token. Can mix Python logic with constrained generation. |

### Outlines example (most relevant for us)

```python
import outlines

# Constrain intent to exact enum — eliminates "gather" (with quotes) parse failures
generator = outlines.generate.choice(model, ["gather", "converse", "clarify", "close", "review"])

# Constrain field extraction to valid JSON
from pydantic import BaseModel
class FieldExtraction(BaseModel):
    field_ids: list[str]
    field_values: list[str]
generator = outlines.generate.json(model, FieldExtraction)
```

### llama.cpp GBNF example

```
# Grammar for our intent output
root ::= intent
intent ::= "gather" | "converse" | "clarify" | "close" | "review"
```

### Key research findings

- Small models (1-4B) are **more sensitive** to format constraints than large models — constrained decoding helps them disproportionately
- JSON significantly outperforms YAML/XML in parseability for small models
- Constrained decoding doesn't improve model **understanding** — it forces valid structure on whatever the model generates. Best combined with fine-tuning or prompt optimization.
- Grammar compilation can be slow for complex schemas (40s–10min with Outlines), but our schemas are simple

### Integration plan

Two options to try:

1. **Outlines + MLX**: Wrap our MLX server with Outlines constraints for each DSPy module's output schema. This can be done at the DSPy adapter level or as a post-processing layer.
2. **llama.cpp GBNF**: Switch from MLX server to llama.cpp server with GBNF grammars. Native Apple Silicon support, built-in grammar constraints.

Both approaches can layer under DSPy — constrained decoding handles format, GEPA handles content quality.

## SFT for Structured Output

Research shows SFT is transformative for small models: **~0% to 88.9% schema accuracy** with just 200-500 training examples.

### Training data for format SFT

We need training data specifically for teaching DSPy's structured output format, separate from our task-level SFT data.

**Source 1: GEPA failure cases** — Every `AdapterParseError` from our GEPA runs contains the raw model output and the expected format. Convert to training pairs:
```json
{
  "input": "<DSPy prompt with format instructions>",
  "expected": "[[ ## intent ## ]]\ngather",
  "actual_failure": "\"gather\""
}
```

**Source 2: Synthetic format examples** — Generate (input, correctly-formatted-output) pairs for each module signature:
- IntentDecider: 50 examples of `[[ ## intent ## ]]\n{gather|converse|clarify|close|review}`
- DataExtractor: 50 examples of `[[ ## field_ids ## ]]\n["field1", "field2"]\n[[ ## field_values ## ]]\n["val1", "val2"]`
- TextResponder: 50 examples of `[[ ## response_text ## ]]\nHere is your response text.`

**Source 3: Simulation logs** — Our existing atomic training data, reformatted to DSPy's expected output structure.

### Plan

1. **Collect format failures** from GEPA runs as negative examples
2. **Generate synthetic format-correct examples** for each module signature
3. **SFT with MLX LoRA** on the format training data (separate from task SFT)
4. **Re-run GEPA** with the format-tuned model — expect higher baseline and more successful reflections
5. **Task SFT** on simulation logs for content quality (if needed after GEPA)

## Research Notes

### Task-aware structured pruning (lobotomization)

Fine-tune the 4B model on our task, then measure which attention heads / MLP neurons actually activate during form-filling. Prune the heads/neurons that never fire, producing a smaller task-specific model. Pipeline:

```
SFT on 4B → profile activations on our test cases → rank heads/neurons by importance
  → prune bottom N% → light SFT to recover quality → repeat until quality degrades
```

This is a later optimization — requires the fine-tuned 4B model first (Step 5).

### Qwen3.5-4B inference optimization on M1 Pro 16GB

Key bottleneck: memory bandwidth on Apple Silicon, not compute. Model weights (~2.5GB at 4-bit) fit fine; the KV cache and serving overhead are the real constraints.

**vllm-mlx** — Drop-in replacement for mlx_lm.server. OpenAI-compatible API, continuous batching (4.3x throughput at 16 concurrent), content-based prefix caching (up to 28x speedup on repeated prompts). 21-87% faster than llama.cpp across configs. `pip install vllm-mlx`. Benchmarks on M4 Max; M1 Pro will be slower but relative advantage holds. [GitHub](https://github.com/waybarrios/vllm-mlx)

**KV cache quantization** — mlx_lm supports `--kv-bits N` (4 or 8) and `--kv-group-size`. Uniform 4-bit is dangerous (PPL can spike to 507). Better: use **mlx-optiq** for per-layer mixed-precision KV quantization. Pre-quantized models exist: `mlx-community/Qwen3.5-4B-OptiQ-4bit`. Saves ~57% memory at 16K context. Server support via PRs #934/#941 (may not be merged yet).

**Prompt prefix caching** — mlx_lm supports `make_prompt_cache` API. ~5.8x speedup on TTFT. **Caveat**: broken for Qwen3.5 specifically — hybrid architecture (attention + Mamba layers) has non-trimmable recurrent state ([issue #980](https://github.com/ml-explore/mlx-lm/issues/980)). vllm-mlx may handle this differently.

**Speculative decoding** — MLX supports `--draft-model`. Qwen3.5-0.8B as draft for 4B is viable (same tokenizer). Expect ~1.3-1.5x speedup on M1 Pro. Not supported with batched inference — single-request only.

**Practical recipe for our setup**:
1. Serve via vllm-mlx (batching + prefix caching)
2. Use OptiQ-4bit model variant (mixed-precision KV cache)
3. Set `--max-kv-size 2048` to cap memory
4. Speculative decoding with 0.8B draft for single-user scenarios

### Community insights on small model workflows

From practitioners using Qwen3.5-4B locally:
- Model needs ~1-2K tokens of context to produce good output
- **Outlines** for constrained decoding — hijacks logit processing to guarantee structured output (JSON schemas, Pydantic models, enums, CFGs). Works at inference time, no training needed.
- Small models (0.8B) are "immensely LoRA finetuneable" for local training
- If RL baseline reward is below 20%, skip RL and do SFT with synthetic data first — matches our GEPA finding (13.1% baseline)
- Recommended order: constrained decoding → SFT → RL/prompt optimization

### TurboQuant: KV cache compression (Google Research, 2025)

[TurboQuant](https://arxiv.org/abs/2504.19874) compresses the KV cache to 3-bit precision with zero accuracy loss, achieving 6x memory reduction and 8x attention speedup. Uses two techniques:
- **PolarQuant**: Converts vectors to polar coordinates for efficient quantization (no data normalization overhead)
- **QJL** (Quantized Johnson-Lindenstrauss): 1-bit error correction using dimensionality reduction

**Relevance to us**: The main reason Qwen3.5-4B can't run in 16GB browser is KV cache growth with our long system prompt (~5K tokens). Model weights (q4 ~2.5GB) fit fine — it's the KV cache (~1.5GB at FP16) that overflows. TurboQuant could reduce KV cache to ~250MB, making 4B viable on 16GB.

**Status**: Research-only (papers, no open-source code). Would need implementation for MLX or transformers.js. Worth watching for community adoption. MLX may add KV cache quantization as a feature.

### Flash-MoE: SSD-streaming for large MoE models

[Flash-MoE](https://github.com/danveloper/flash-moe) runs Qwen3.5-397B (512 experts, 4 active per token) on a 48GB MacBook by streaming expert weights from SSD at 4.4 tok/s. Not directly applicable to our dense models (0.8B, 4B), but validates the concept that models use only a fraction of their capacity per token — the basis for our pruning approach.

## Test Infrastructure

### Browser test page: `/model-test.html`

Interactive page with configurable options:
- **Model**: SmolLM2-360M, Qwen2.5-0.5B, Qwen3-0.6B, SmolLM2-135M
- **Backend**: WebGPU + q4f16 (fast) or WASM + q4 (safe fallback)
- **Prompt mode**: Minimal (~2K), Compact (~20K), Full (~30K)
- **Max tokens**: 64–2048 (default 1024)
- **5 test cases**: Greeting, Simple answer, Multi-info, Choice, Question
- **Auto-scoring**: Format compliance badges (pass/partial/fail)
- **Console logging**: Full debug output with `[model-test]` prefix

### CLI test script

```bash
# Available models: smollm-360, qwen25, qwen3, smollm-135
npm run model-test -- --model qwen3 --test greeting --max-tokens 1024
npm run model-test -- --model smollm-360 --max-tokens 512
npm run model-test -- --model all --max-tokens 1024
```

## File Structure

```
tuning/
  scripts/
    extract.py             — extract atomic training data from sims/*.jsonl
    sample.py              — sample balanced test cases from atomic data
  eval/
    run_eval.py            — run models against test cases, score results
    results/               — per-model eval output (JSONL)
  data/
    atomic.jsonl           — extracted turns from all simulations
    test-cases.jsonl       — sampled eval cases (balanced by category)
  sft/                     — Unsloth training scripts/configs (future)
  dspy/
    optimize_prompt.py     — DSPy GEPA 5-module pipeline (IntentDecider, TextResponder, DataExtractor, ChoiceBuilder, ReviewBuilder)
packages/web-app/public/
  model-test.html          — browser test page (WebGPU/WASM, interactive)
packages/integration-tests/src/e2e/model-test/
  test-small-models.ts     — CLI test script (WASM, automated)
scripts/
  serve-models.sh          — start MLX model servers (SmolLM2, Qwen)
  batch-sim.sh             — run all persona × profile simulation combos
python/
  pyproject.toml           — ML dependencies (mlx-lm)
docs/
  doc-11-small-model-research.md  — this document
```
