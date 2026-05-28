# Local SFT Harness

Phase 1 of doc-12 Experiment 10 (E2E harness), now with the deterministic-helpers and probe-runner additions from Experiment 11.

Runs the SFT-v2 model end-to-end via the existing web app so we can manually drive real form-filling sessions and capture failure modes — plus a programmatic probe runner that drives the same harness against scripted scenarios for batch evaluation.

## Architecture

```
Browser (?backend=local)
   │
   ▼ POST /api/generate-local
Web app (packages/web-app)  — thin proxy
   │
   ▼ POST /api/generate
Harness (this dir, port 8200)
   │  • build_context (schema + form_state + history)
   │  •   ↳ optionally augmented with deterministic state summary + group-index hints
   │  • FormAssistant.forward()  (5-module DSPy pipeline)
   │  • compose → text + ---actions--- block
   │  •   ↳ schema-validated + type-coerced via state_check
   │  • append logs/session-*.jsonl + logs/session-*.lm-calls.jsonl
   │
   ▼ HTTP (DSPy ChatAdapter)
mlx_vlm.server  (port 8100)  — serves SFT-v2 fp16
```

## What you need running

1. **mlx_vlm.server on :8100** serving SFT-v2:
   ```sh
   ./scripts/serve-models.sh qwen-sft     # or directly:
   uv run python -m mlx_vlm server \
     --model ~/work/models/qwen35-08b-dspy-format-v2-mlx \
     --port 8100
   ```

2. **Persistence-server on :3005** (only needed for save/submit; harness still
   starts without it):
   ```sh
   cd packages/persistence-server && npm run dev
   ```

3. **Harness on :8200** (this dir):
   ```sh
   cd <repo-root>
   /path/to/python/.venv/bin/uvicorn tuning.harness.serve:app --port 8200
   ```

4. **Web app on :3004**:
   ```sh
   npx tsx packages/web-app/src/index.ts
   ```

## Use it (interactive)

Open http://localhost:3004/?backend=local in a browser. The choice is
persisted to localStorage, so subsequent visits stay on the local backend.
To switch back to Claude: http://localhost:3004/?backend=claude (or clear
the `chat_backend` localStorage entry).

The chat works exactly as with Claude — type a message, see a response, see
the form panel update. Session traces land in `logs/session-{id}.jsonl` (and
`*.lm-calls.jsonl` for the per-module HTTP transcript) in the same schema
the production agent uses.

## Use it (batch / probes)

Run scripted scenarios against the harness with `probe_runner.py`. Probes
live in `tuning/harness/probes/P*.md` (12 phases × 5 probes = 60 scenarios
covering session opening, multi-entity groups, file uploads, status checks,
adversarial inputs, etc.).

```sh
# Run all probes (60 × 2 temps = 120 model calls, ~10 min)
/path/to/.venv/bin/python tuning/harness/probe_runner.py

# Just one phase
/path/to/.venv/bin/python tuning/harness/probe_runner.py P3

# Multiple phases
/path/to/.venv/bin/python tuning/harness/probe_runner.py P5 P8

# Custom temperatures (one run per temp)
/path/to/.venv/bin/python tuning/harness/probe_runner.py P5 --temps 0.0 0.7

# Turn on doc-16 #3/#5 deterministic context augmentation
/path/to/.venv/bin/python tuning/harness/probe_runner.py P5 P8 --augment-state
```

Results land in `tuning/harness/probes/runs/P*.md` — same probe content
with per-run module outputs + composed final response appended after each
probe block. Source files in `probes/` are never modified.

## Endpoints exposed

| Path | Method | Purpose |
|---|---|---|
| `POST /api/generate` | POST | Run one turn through the SFT pipeline. Returns SSE (text, done, error events). |
| `POST /api/save-draft` | POST | Persist current form state via persistence-server. |
| `POST /api/submit` | POST | Submit form state via persistence-server. |
| `GET /health` | GET | Liveness check; reports LM/persistence reachability. |

`POST /api/generate` request body:
```jsonc
{
  "session_id": "string (browser-generated)",
  "user_message": "string",
  "form_state": { "<field_id>": "<value>", ... },
  "form_schema": { /* parsed form JSON */ },
  "conversation_history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ],
  "temperature": 0.0,         // optional; overrides the LM's configured default per-call
  "augment_state": false      // optional; turns on doc-16 #3/#5 deterministic enrichment
}
```

Response is SSE matching the existing web-app `/api/generate` contract:
```
event: text  data: {"text": "<response_text>"}
event: text  data: {"text": "\n\n---actions---\n```json\n[...]\n```"}
event: done  data: {"session_id": "...", "duration_ms": N, "cost_usd": 0.0}
```

The browser's existing `action-parser.js` parses the `---actions---` block
and applies the actions to the form panel — no separate action plane needed.

## Module layout

| File | Responsibility |
|---|---|
| `serve.py` | FastAPI app exposing the endpoints above. Configures DSPy LM at startup. Wraps the pipeline in a thread executor so the 5-call serial chain doesn't block the event loop. Sets/clears the per-session ContextVar so dspy_logger.HarnessLogger writes events to the right `lm-calls.jsonl`. |
| `pipeline.py` | Configures `dspy.LM` to point at mlx_vlm; wraps `FormAssistant.forward()` from `tuning/dspy/optimize_prompt.py`. Builds the context string (schema + form_state + last-6-turn history with file-aware truncation). Per-call temperature override via `dspy.context()`. Optional state augmentation via `state_check`. |
| `composer.py` | Turns a 5-module Prediction into the legacy `text + ---actions--- + JSON` format. Now also runs `state_check.validate_against_schema` per `set_fields` entry — drops unknown fields, snaps select labels to canonical values, coerces types (bool/list/number). Returns the dropped list separately so callers can log what got rejected. |
| `state_check.py` | Deterministic helpers (no LLM calls) for the doc-16 CANNOT #3 / #5 / #6 / #7 fixes: `compute_state_summary` (humanized filled/missing for context augmentation), `compute_group_indices` (current entries + next index), `coerce_value` (bool/list/number type coercion), `validate_against_schema` (enum check, label-to-value snap, drop unknowns). Schema-aware; handles dotted/dashed field-id notation. |
| `lifecycle.py` | Talks to `packages/persistence-server` for save_draft / submit_final. Two POST helpers. |
| `logger.py` | Append-only JSONL session logger matching the existing schema in `logs/session-*.jsonl`. Per-turn events: `user_message`, `model_input`, `model_output` (with `module_outputs` field — additive but useful), `form_state_update`, `error`. |
| `dspy_logger.py` | DSPy `BaseCallback` subclass that writes per-module / per-LM-call events to `logs/session-{id}.lm-calls.jsonl`. Captures the raw ChatAdapter messages going in and the raw model response coming back, plus any AdapterParseError exceptions. Critical for debugging when DSPy silently swallows a parse failure. Bound per-session via a `ContextVar` set in `serve.py`. |
| `probe_runner.py` | Reads `probes/P*.md`, parses each probe's `form_state` / `conversation_history` / `user_message`, POSTs to the harness one or more times (per-temperature), captures the response, writes a sibling result file under `probes/runs/` with per-run module outputs and composed response appended to each probe block. Handles cross-probe `form_state` references via `same as PX-exY` shorthand. |

## Probes layout

```
tuning/harness/probes/
├── P1-session-opening.md          (5 probes: brand-new, returning, off-topic, generic Q, start-over)
├── P2-closed-set-selection.md     (5: word-pick, 6th-option, off-schema, waffle, mind-change)
├── P3-personal-info.md            (5: self-correction, partial dump, format Q, voice-to-text, refusal)
├── P4-single-entity-group.md      (5: bulk degree, piecemeal, sub-field Q, single job, sparse recommender)
├── P5-multi-entity-group.md       (5: 2 degrees, append job, 3 recommenders, remove, edit-by-index)
├── P6-conditional-fields.md       (5: prior_application_year, TOEFL, citizenship change, funding, conditional)
├── P7-file-uploads.md             (5: transcript, SOP, replace, deferral, mis-assignment correction)
├── P8-mid-flow-status.md          (5: what-do-I-have, what's-left, show-section, are-we-done, recall-value)
├── P9-save-and-resume.md          (5: direct save, indirect, mind-change, button-click, returning recap)
├── P10-pre-submission-review.md   (5: full review, edit-via-review, what's-left-to-submit, wrap-up, file recall)
├── P11-submission.md              (5: direct submit, hesitation, confirm event, premature, post-submit)
├── P12-adversarial.md             (5: haiku off-topic, frustrated, sarcasm, prompt-injection, terse)
└── runs/                           # populated by probe_runner.py; not under source control
```

## Configuration (env vars)

```sh
LM_URL=http://localhost:8100/v1                                    # mlx_vlm endpoint
LM_MODEL=./models/qwen35-08b-dspy-format-v2-mlx    # served model name
PERSISTENCE_URL=http://localhost:3005                              # persistence-server
LOG_DIR=/path/to/logs                                              # session JSONL output (defaults to repo logs/)
HARNESS_URL=http://localhost:8200                                  # used by web-app proxy
```

## Session log artifacts

Per session you get **two** JSONL files in `LOG_DIR`:

- `session-{id}.jsonl` — high-level turn-by-turn record
  - `user_message` — what the user typed
  - `model_input` — context length + form_state snapshot
  - `model_output` — composed text + parsed_actions + module_outputs (5 modules' raw structured outputs) + duration
  - `form_state_update` — fields applied to the form panel
  - `error` — any failure or composer-rejection event

- `session-{id}.lm-calls.jsonl` — per-module / per-LM-call HTTP transcript
  - `module_start` / `module_end` per `dspy.Predict` call (with module name + inputs/outputs)
  - `lm_start` / `lm_end` per HTTP call to mlx_vlm (with raw messages + raw response)
  - `adapter_parse_start` / `adapter_parse_end` per ChatAdapter parse (catches AdapterParseError silently-swallowed cases)

Use the second one when you want to see exactly what the model saw and emitted; use the first for high-level turn navigation.

## Out of scope (Phase 1)

- Vault tools (`vault_*`)
- `validate_fields`, `discover_form` (we use the static schema the browser sends)
- `wants_submit` handling — model has zero training supervision (see doc-12 Experiment 9 audit)
- Token-level streaming — faked via two SSE chunks since the 5-module pipeline is serial
- Multi-form support — northfield only
- File uploads work for **content extraction** (browser inlines `[File: name]<text>[End of name]` into the user_message and the model reads it) but the model often skips the canonical "assign filename to file field" step (see doc-15 R7)

## Smoke tests

Each module is independently runnable:

```sh
uv run python tuning/harness/pipeline.py     # exercises full pipeline against :8100
uv run python tuning/harness/composer.py     # composes a fake Prediction
uv run python tuning/harness/state_check.py  # — (no __main__ yet; import + call helpers)
```

End-to-end:
```sh
curl -sN -X POST http://localhost:8200/api/generate \
  -H 'Content-Type: application/json' \
  -d @example_request.json
```

Or the structured probe runner (recommended once probes are authored):
```sh
/path/to/.venv/bin/python tuning/harness/probe_runner.py P1 --temps 0.0
```
