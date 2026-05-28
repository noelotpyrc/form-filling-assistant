# Local Model Form Assistant

## What
AI-assisted patient intake form filling that runs entirely in-browser using a fine-tuned small local model (Qwen 3.5 0.8B via transformers.js).

## Strategy
Build on the existing Form Filling Assistant (`~/work/form-filling-assistant`) which already has chat UI, Claude CLI integration, form panel, and MCP tool calling. Evolve it in two tracks:

1. **Enhance the frontend** with generative UI (inline interactive components in chat + dynamic form panel)
2. **Collect conversation traces** during Claude-powered usage as fine-tuning data
3. **Fine-tune Qwen 3.5 0.8B** on those traces
4. **Swap to local model** running in-browser via transformers.js

## Phases

### Phase 1: Generative UI Enhancement
Evolve the existing web-app to support generative UI — the AI renders interactive form components inline in chat messages, not just in the side panel. Make the experience more conversational and less "fill out this form."

### Phase 2: Training Data Collection
Instrument the app to log full conversation traces (messages, tool calls, form state) as JSONL. Every Claude-powered session produces fine-tuning data.

### Phase 3: Model Fine-tuning
Fine-tune Qwen 3.5 0.8B on collected traces. Focus on: conversational quality, tool call generation, field value extraction from natural language.

### Phase 4: Local Model Integration
Load the fine-tuned model in-browser via transformers.js. Replace the Claude backend. The app becomes fully client-side with optional server persistence for draft checkpointing.
