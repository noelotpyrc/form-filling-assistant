# Doc 9 — Scenario Simulator

Uses an LLM ("LLM U") to simulate realistic user behavior in multi-turn form-filling conversations. LLM U interacts with the form-filling assistant (LLM A) in a live loop — choosing intents, picking from a constrained action space, and generating natural language messages — producing session logs usable as training data for fine-tuning.

## Concepts

**Persona** — A flat data blob keyed by field_id. Contains all the "answers" a fake user would give. One persona can be used across multiple forms (shared fields like `full_name`, `email` get reused).

```typescript
interface Persona {
  name: string;                         // "Jane Smith"
  data: Record<string, unknown>;        // { full_name: "Jane Smith", dob: "1998-05-15", ... }
  groupData: Record<string, unknown[]>; // { degrees: [{ institution: "MIT", ... }], jobs: [...] }
  files: Record<string, PersonaFile>;   // { transcript: { path: "fixtures/transcript.pdf", size_mb: 2.1 }, ... }
}
```

## User Action Types

Defined by what the UI actually lets users do. There are 5 interaction types:

### 1. Send Message (proactive)

The user types free text in the chat input and optionally attaches files. This is the only **proactive** action — the user initiates it without the model prompting them. All the variation in user behavior lives here as options on this single action type:

| Option | Values | Example |
|--------|--------|---------|
| **delivery** | `batch` · `incremental` | All fields at once vs. one at a time |
| **completeness** | `full` · `partial` · `skip` | All fields, some fields, or "skip this section" |
| **intent** | `provide_info` · `correct` · `revisit` · `ask_question` | New data, fix a mistake, go back, or ask about a field |
| **verbosity** | `terse` · `verbose` | "Jane Smith, 1998-05-15" vs. "My name is Jane Smith, I was born on May 15th 1998" |
| **attachments** | `none` · `correct_file` · `wrong_type` · `oversized` | No file, valid file, wrong format (jpg instead of pdf), exceeds size limit |

### 2. Select Choice (reactive)

The model sends `ask_choice` with options. The user clicks one. The simulator needs a policy: which option to pick.

| Option | Values |
|--------|--------|
| **selection** | `preferred` (match from persona) · `first` · `random` |

### 3. Fill Fields (reactive)

The model sends `show_fields` with a form card. The user fills in the inputs and clicks "Send answers." The simulator needs a policy: what values to enter.

| Option | Values |
|--------|--------|
| **completeness** | `full` (fill all) · `partial` (leave some blank) |
| **accuracy** | `correct` (from persona) · `typo` (introduce errors for later correction) |

### 4. Upload File (reactive)

The model requests a document (transcript, resume, insurance card). The user attaches a file. This can also happen alongside a send_message (the user types text and attaches a file in one go).

| Option | Values |
|--------|--------|
| **action** | `upload` (provide the file) · `skip` (ignore and send a message instead) |
| **file_quality** | `correct` (right type/size) · `wrong_type` (e.g. jpg instead of pdf) · `oversized` (exceeds max_size_mb) |

### 5. Click Button (reactive)

The model sends `show_button` with `save_draft` or `submit`. The user clicks it.

| Option | Values |
|--------|--------|
| **action** | `click` (always click) · `ignore` (skip and send a message instead) |

## Message Rendering

LLM U generates natural language messages directly — no programmatic templates. The behavior profile and persona data guide LLM U's style (terse vs verbose, formal vs casual, etc.). The U→A adapter converts LLM U's structured `UserAction` output into the format LLM A expects:

- **`message`**: Passed through as-is to LLM A as a chat message.
- **`message` + `file`**: Adapter wraps the file content: `[File: transcript.pdf]\n{extracted text}\n[End of transcript.pdf]\n\nHere's my transcript.`
- **`select_choice`**: Adapter converts to `[system] User selected option: "label"`.
- **`fill_fields`**: Adapter converts to `FieldEdit` — silent state mutation, no model call.
- **`click_button`**: Runner auto-handles — injects click event + API response event.

## Simulation Architecture

The simulator is a live interactive loop with an adapter layer between two LLM sessions. LLM U (user simulator) and LLM A (form-filling assistant) never see each other's raw formats — the adapter translates each side's output into what the other would naturally receive.

```
LLM U                     Adapter                      LLM A
(user simulator)          (the "app")                  (form assistant)
                    ┌───────────────────┐
  sees ◀────────────┤  A→U: render LLM  │◀──────────── produces
  "what's on        │  A output as user  │              raw text +
   my screen"       │  screen view       │              actions
                    │                    │
  produces ────────▶│  U→A: convert LLM  │──────────▶  receives
  structured        │  U action to app   │              chat message /
  action output     │  format for LLM A  │              system event
                    └───────────────────┘
```

### A→U Adapter: Rendering the user's screen

Takes LLM A's raw output (text + parsed actions) and form state, renders a text representation of what the user would see on their screen. This is the only input LLM U receives each turn.

**Always visible (every turn):**

```
## Assistant Message
Great, I've saved your personal information. Let's move on to education.
Can you tell me about your undergraduate degree?

## Form Panel
Overall progress: 7/30 required fields (23%)
- Personal Information: 5/5 ✓
- Program Selection: 2/2 ✓
- Education: 0/4
- Work Experience: 0/3
- Test Scores: 0/3
- Documents: 0/2 files
- References: 0/3
- Additional Info: 0/1
```

**Conditionally visible (based on LLM A's actions):**

| LLM A action | What user sees | Rendered as |
|---|---|---|
| `ask_choice` | Clickable option buttons | `Choice buttons: ["Computer Science (MS)", "Data Science (MS)", "Business Admin (MBA)"]` |
| `show_fields` | Section expanded with empty input fields | `Form section "Education" is open with fields: institution, degree_type, gpa, graduation_date` |
| `show_button` | Save/submit button | `Button available: "Save Draft"` or `Button available: "Submit Application"` |
| `show_preview` | Summary card with field/value pairs | `Preview card: Personal Info — Name: Jane Smith, Email: jane@example.com; Education — ...` |
| `set_fields` | Progress counters update (user sees the effect, not the values) | Reflected in form panel counts |

**Not rendered (user doesn't see):**
- Raw `set_fields` field values — user sees counter changes, not the data
- System prompt internals
- Raw form state object

### U→A Adapter: Converting user actions to app format

Implemented in `simulator/user-action.ts`. Converts LLM U's structured `UserAction` output into the per-turn dynamic input for LLM A. The adapter handles two things that change per turn: the user message and the form state. The loop controller handles static parts (system prompt template, session management via `--resume`).

```typescript
function convertUserActionToAppInput(
  userAction: UserAction,
  formState: Record<string, unknown>,  // current form state (not mutated)
): ConvertedAction
```

| LLM U output | `userMessage` | `formState` |
|---|---|---|
| `{ action: 'message', text: '...' }` | Chat message string (as-is) | Passed through unchanged |
| `{ action: 'message', text: '...', file: { filename, content } }` | `[File: name]\n{content}\n[End of name]\n\ntext` | Passed through unchanged |
| `{ action: 'select_choice', label: "Bachelor's" }` | `[system] User selected option: "Bachelor's"` | Passed through unchanged |
| `{ action: 'fill_fields', fields: { gpa: '3.85' } }` | `null` — no message to LLM A | Updated with field edits applied |
| `{ action: 'click_button' }` | `null` — loop controller injects click event | Passed through unchanged |
| `{ action: 'stop' }` | `null` — terminates the loop | Passed through unchanged |

The adapter does NOT own system prompt construction — `SystemPrompt.build()` in the web app already handles that, baking form schema + current form state into the system prompt. The controller calls `SystemPrompt.build()` with the adapter's returned `formState`.

#### Form state delta inference

Between consecutive `form_state_snapshot` entries in a session log, field changes fall into two categories:
- **Model-explained**: Changes from `set_fields` in the preceding `model_output`
- **User-initiated**: All other changes — the user proactively edited form fields

The demo (`demo-u2a.ts`) computes this delta to derive `fill_fields` actions that LLM U should produce. A single turn can yield multiple actions (e.g., `fill_fields` + `message` when the user edits fields AND sends a message).

### LLM U's structured output

LLM U produces a ranked list of candidate actions per turn via `askJson()` with a JSON schema. The controller picks rank-1 and resolves any file references. File keys in LLM U output (e.g. `"degrees.0.transcript"`) are resolved to `FileAttachment { filename, content }` from persona data by the controller.

```typescript
interface FileAttachment {
  filename: string;  // "Resume.pdf"
  content: string;   // pre-extracted text content
}

interface UserAction {
  action: 'message' | 'select_choice' | 'fill_fields' | 'click_button' | 'stop';
  text?: string;                    // free text message
  file?: FileAttachment;            // file to attach (message action only)
  label?: string;                   // selected choice label
  fields?: Record<string, unknown>; // field edits to apply
}

interface ConvertedAction {
  userMessage: string | null;          // message for LLM A, or null
  formState: Record<string, unknown>;  // updated form state snapshot
  stop: boolean;                       // whether to end the session
}
```

### LLM U's inputs

LLM U is treated as a human user. It only knows:
1. **What's on screen** — the A→U rendered view (chat + form panel + interactive elements)
2. **Its own personal data** — the persona blob (name, GPA, work history, etc.)
3. **Its own personality** — the behavior profile (impatient, thorough, confused, etc.)

LLM U does NOT have access to raw form state, system prompts, or LLM A's internal action format.

### LLM sessions

Both LLM A and LLM U are Claude sessions managed via `ClaudeAgent` (the `@form-filling-assistant/claude-agent` package, which wraps the `claude` CLI).

**LLM A** — a persistent `ClaudeAgent` interactive session (`runInteractive()`). A single CLI process stays alive for the entire simulation. Supports two prompt modes:
- **Default mode**: The full prompt (static instructions + form schema + dynamic form state + user message) is re-sent as the user message each turn. Simple but expensive — the ~20K static instructions accumulate in context every turn.
- **Split-prompt mode** (`--split-prompt`): Static instructions (format rules, action types, form schema, behavior guidelines) are set once via `systemPrompt` on the constructor. Only the dynamic form state + user message are sent per turn via `session.send()`. **5x cheaper** for LLM A ($0.18/turn vs $0.99/turn) with identical field completion quality. The static prompt is ~20K chars that never change between turns.

External tools disabled (`tools: ''`) since LLM A outputs text+actions, not MCP tool calls.

**LLM U** — a persistent `ClaudeAgent` interactive session (`runInteractive()`). System prompt (persona + behavior profile + action catalog + output format rules) is set once on the constructor and lives in session memory. Each turn, the rendered screen view is sent via `session.send()`; LLM U responds with ranked candidates as JSON. External tools disabled (`tools: ''`).

Both use persistent processes to avoid CLI re-spawn overhead on every turn. Previously, each turn spawned a new `claude` CLI process (LLM A via the web-app server, LLM U via `agent.run()` with `--resume`), adding 5–20s of startup/session-hydration latency per turn. With `runInteractive()`, turn 2+ latency dropped to 5–7s for LLM U (sonnet, default) and 4–8s for LLM A (sonnet). The web-app server is no longer needed for CLI simulation.

LLM U output per turn:

```json
{
  "candidates": [
    {
      "rank": 1,
      "intent": "provide_info",
      "reasoning": "The assistant is asking for personal info and I have all the data ready",
      "actions": [{ "action": "message", "text": "Jane Smith, 1998-05-15, US citizen, jane@email.com" }]
    },
    {
      "rank": 2,
      "intent": "fill_presented_fields",
      "reasoning": "The form fields are open, I could fill them directly",
      "actions": [{ "action": "fill_fields", "fields": { "full_name": "Jane Smith", "dob": "1998-05-15" } }]
    },
    {
      "rank": 3,
      "intent": "ask_question",
      "reasoning": "I could ask what format they want for the date",
      "actions": [{ "action": "message", "text": "What format should the date be in?" }]
    }
  ]
}
```

The controller picks a candidate based on the sampling mode: greedy (always rank-1), weighted (70/20/10 distribution across top 3), or uniform (random). Sampling mode is selectable in the sim UI.

### The loop

```
  ┌──────────────────────────────────────────────────┐
  │                                                   │
  ▼                                                   │
┌──────────────┐    ┌──────────────┐    ┌───────────┐│
│ A→U Adapter   │───▶│ LLM U        │───▶│ U→A       ││
│ render screen │    │ (interactive │    │ Adapter   ││
│ view          │    │  session)    │    │ (runner)  ││
└──────────────┘    └──────────────┘    └─────┬─────┘│
                                              │      │
                                              ▼      │
                                        ┌───────────┐│
                                        │ LLM A      ││
                                        │ (interactive│├──▶ session.jsonl
                                        │  session)  ││
                                        └─────┬─────┘│
                                              │      │
                                              └──────┘
```

The loop terminates when:
- LLM U outputs `{ action: 'stop' }` → session ends
- Max turns reached (configurable safety limit)
- LLM A completes a `submit` flow
- Stuck loop detected — same intent repeated 3+ times in a row (controller forces stop)

### Behavior profiles

Behavior profiles are separate prompt files that define LLM U's personality. They're injected into LLM U's system prompt.

```
packages/integration-tests/src/e2e/simulator/profiles/
  thorough.md        — fills everything, asks clarifying questions, reviews before submitting
  impatient.md       — skips optional sections, terse answers, submits ASAP
  confused.md        — asks lots of questions, provides partial info, needs guidance
  corrector.md       — gives wrong info initially, then corrects after review
  returning.md       — has a saved draft, reviews filled data, corrects 1-2 things, fills gaps, submits
```

The `returning` profile is special: when detected, the simulator auto-generates a partial draft via `draft-generator.ts` (randomly fills ~50% of sections using persona data) and injects it into the initial form state. Turn 0 includes a `[system] Draft restored. N fields previously filled.` message so LLM A knows to pick up where the user left off. File fields are always left empty (files don't persist in drafts).

### Pipeline

```bash
# Run one simulated session
npm run e2e:sim -- --form northfield --persona jane --profile thorough

# Run N sessions across all combinations
npm run e2e:sim -- --runs 3

# Reproducible run with seed
npm run e2e:sim -- --form northfield --persona jane --profile impatient --seed 42
```

Each run produces a session-format JSONL file (same format as the web app's session logger and the replay tool), directly usable as training data.

## Runner Action Support

The E2E runner (`run-scenario.ts`) processes a queue of `QueuedAction` items. Each action is either a string (chat message or system event that triggers a model turn) or a structured object (silent state mutation).

```typescript
type FieldEdit = { type: 'field_edit'; fields: Record<string, unknown> };
type QueuedAction = string | FieldEdit;
```

### Supported user action types

| User Action | Queue Representation | Triggers Model? | State Change |
|---|---|---|---|
| **Chat message** | `"Hi, I'd like to apply..."` | Yes | — |
| **Chat + file attachment** | `"[File: name]\n{text}\n[End of name]\n\nMessage"` | Yes | — |
| **Select choice** (reactive) | `[system] User selected option: "label"` | Yes | — |
| **Click Save Draft** (reactive) | Runner auto-injects: `[system] User clicked: Save Draft` then `[system] Draft saved successfully.` | Yes (2 turns) | — |
| **Click Submit** (reactive) | Runner auto-injects: `[system] User clicked: Submit` then `[system] Submission saved. Reference: APP-...` | Yes (2 turns) | — |
| **Edit form field** | `{ type: 'field_edit', fields: { phone: '+1-555-0199' } }` | No (skip to next) | `formValues` updated |
| **Login + draft restore** | `scenario.initialFormValues` pre-loads state; first message is returning-user prompt | Yes (first turn) | `formValues` pre-loaded |

### Scenario interface

```typescript
interface Scenario {
  name: string;
  formJsonFile: string;
  preferredValues: Set<string>;  // for auto-selecting ask_choice options
  actions: QueuedAction[];       // message strings + field edits
  email?: string;                // simulated login email
  initialFormValues?: Record<string, unknown>;  // pre-loaded draft state
}
```

### 4 built-in scenarios

- `northfield` — New user, full CS application flow (Jane Smith)
- `northfield-returning` — Returning user with draft restore, file upload, field edit
- `westbrook` — AI research program (Alex Chen)
- `patient` — Patient intake (Maria Garcia)

## Session Replay Tool

The replay tool (`replay-session.ts`) reads an existing session log, replays the same user inputs against the live API, and produces two output files for comparison and training data.

### Usage

```bash
# Auto-detect form from session content
npm run replay -- mock_data/session-log.jsonl

# Specify form explicitly
npm run replay -- mock_data/session-log.jsonl --form packages/mock-masters/form.json
```

### How it works

1. Parses the session log JSONL and extracts turn pairs (model_input + model_output)
2. Auto-detects which form was used (northfield/westbrook/patient) from session content
3. For each turn, reconstructs the system prompt using the **original** session's form state (not replay's), so the model sees identical context
4. Sends the user message to the live API and collects the replay response
5. Compares original vs replay action types per turn

### Output

Two files are written to `e2e-logs/`:

| File | Format | Purpose |
|---|---|---|
| `replay-<id>-<ts>.json` | JSON | Side-by-side comparison (original vs replay per turn) |
| `replay-<id>-<ts>.jsonl` | JSONL | Session-format log matching the dev interface format — usable as training data |

The session JSONL emits the same entry types as the web app's session logger:
- `session_start` — form metadata and replay source info
- `user_message` — the input sent to the model
- `model_input` — includes `form_state_snapshot` at that turn
- `model_output` — includes `raw_text`, `parsed_actions`, `duration_ms`, `cost_usd`
- `form_state_update` — field deltas from `set_fields` actions

## Session Replay Page (`/replay.html`)

A browser-based visual debugger for JSONL session logs. Load a log file produced by the CLI simulator and replay the full three-actor interaction as an interactive chat transcript with detailed turn-by-turn inspection.

### Layout

Two-panel layout:
- **Chat panel** (left): LLM A messages as assistant bubbles with action badges (`set_fields`, `ask_choice`, etc.) and choice buttons. LLM U selected actions as user bubbles showing intent and action summary. System messages for state updates and session end.
- **Inspector panel** (right, dark theme): Turn-by-turn collapsible sections showing LLM U candidates (ranked, selected highlighted), action plans, state deltas, screen views, and raw JSON. Summary stats in footer: turns, fields filled, costs, duration, models.

### Features

- **File loading**: Drag-and-drop or file picker for `.jsonl` files. Client-side only — no server calls.
- **Turn navigation**: ◀ ▶ buttons and ← → keyboard shortcuts step through turns.
- **Cross-linking**: Click a turn in the inspector to scroll/highlight in chat, and vice versa.
- **Collapsible debug sections**: Candidates, action plans, state deltas, screen views, raw JSON — all collapsed by default for large sessions.
- **Summary stats**: Total turns, fields filled, LLM A/U costs, duration, end reason, models used.

### Usage

1. Start the web-app server (or have it already running)
2. Open `http://localhost:3004/replay.html`
3. Drop a JSONL file from `packages/integration-tests/e2e-logs/` or use the Load button

## Simulation Demo Page (`/sim.html`)

A browser-based UI for running and visualizing simulation loops interactively. Useful for demoing, sanity-checking simulation behavior, and debugging LLM U's decision-making.

### Architecture

The sim page orchestrates the full LLM A ↔ LLM U loop from the browser:

```
Browser (sim.html)
  ├── Calls POST /api/generate for LLM A (SSE stream)
  ├── Calls POST /api/generate-json for LLM U (structured JSON, session-resumed)
  ├── Uses sim-adapters.js (browser port of view-renderer + user-action converter)
  ├── Renders three panels: chat, form progress, LLM U candidates
  └── Logs to IndexedDB via Logger.js (sessions appear in /dev.html)
```

### Server Endpoints

3 sim-specific lazy-loaded endpoints plus the shared `/api/generate-json`. Sim endpoints cross-import from `packages/integration-tests/src/e2e/simulator/` on first hit:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/generate-json` | Shared: structured JSON generation with session resume (used for LLM U) |
| `GET /api/sim/config` | Available personas, profiles, forms for the sim UI |
| `POST /api/sim/llm-u-prompt` | Build LLM U system prompt from persona + profile |
| `POST /api/sim/resolve-file` | Resolve a file key from persona data to filename + content |

### Browser Adapters (`sim-adapters.js`)

A browser-side IIFE module (`var SimAdapters = ...`) porting the TypeScript adapters to plain JS:

- `SimAdapters.renderScreenView(assistantText, actions, formMeta, formValues)` — A→U adapter
- `SimAdapters.convertUserAction(userAction, formState)` — U→A adapter (legacy single-action)
- `SimAdapters.processActions(actions, formState, availableButton)` — Multi-action processor: converts ALL actions from a candidate into an execution plan `{ stop, fieldEdits, messages, clickButton }`
- `SimAdapters.buildLlmAMessage(messages)` — Combines plan messages into a single string for LLM A, with file content prepended

These are direct ports of `view-renderer.ts` and `user-action.ts`, including group field counting, conditional field visibility, and section progress computation.

### Features

- **Three-panel layout**: Chat (left), form progress with section bars (middle), cumulative LLM U candidates log (right)
- **Controls bar**: Form, persona, profile, model (Haiku/Sonnet), effort (low/medium/high), output mode (structured/streaming), sampling (greedy/weighted/uniform)
- **Multi-action handling**: `processActions()` converts ALL actions from a candidate into an execution plan. Handles combos like `select_choice` + `message`, `fill_fields` + `message`, `click_button` + `message`. The plan separates field edits (applied silently), messages (sent to LLM A), button clicks (special 2-turn flow), and stop signals.
- **Output modes**: "Structured" uses `--json-schema` via `/api/generate-json` (guaranteed valid JSON, but non-streaming). "Streaming" uses `/api/generate` with prompt-based JSON format (streams tokens, parses JSON after completion, handles markdown fences).
- **Session resume**: Both LLM A and LLM U reuse sessions across turns via `--resume`. First call is a cold start; subsequent calls pass the session ID for context continuity.
- **Stuck detection**: Requires same intent AND same screen hash (first 200 chars) for 3+ consecutive turns before flagging as stuck
- **Detailed logging**: JSONL export includes `session_start` (with model/effort/output/sampling config), `middleman_to_llm_u` (screen view + session ID), `llm_u` (candidates + selection), `middleman_plan` (processActions output), `middleman_to_llm_a` (combined message), `llm_a` (response + cost), `user_action` (selected actions + form state), `llm_u_error` (error + context), `session_end` (totals)
- **IndexedDB integration**: Sessions logged with `[SIM]` prefix so they appear in `/dev.html` Session Inspector

### Known Issues / TODO

1. ~~**LLM U latency**~~ **FIXED** — LLM U now resumes the same session across turns via `--resume` (same pattern as LLM A). First turn is cold start; subsequent turns reuse the session. The `/api/generate-json` endpoint accepts a `resume` param and returns `sessionId` for the next call. Added streaming output mode as an alternative to `--json-schema` to reduce latency (structured output blocks until complete; streaming returns tokens incrementally).
2. ~~**Candidate sampling**~~ **FIXED** — Added sampling mode dropdown (greedy / weighted / uniform). Greedy always picks rank-1. Weighted uses 70/20/10 distribution across top 3 candidates. Uniform picks randomly. The debug panel shows which candidate was selected and why.
3. ~~**Turn limit / auto-stop**~~ **FIXED** — MAX_TURNS = 30 safety limit added. Sessions auto-stop when the limit is reached.
4. ~~**Multi-action handling**~~ **FIXED** — `processActions()` in sim-adapters.js handles all action combos in a single pass. Produces an execution plan with `{ stop, fieldEdits, messages, clickButton }`. The sim loop applies field edits silently, sends combined messages to LLM A, and handles button clicks via a special 2-turn flow. Tested with 40+ unit tests in `sim-action-processor.test.ts`.
5. ~~**LLM U speed**~~ **FIXED** — Switched both LLM A and LLM U from per-turn CLI spawning (`agent.run()` + `--resume`) to persistent interactive sessions (`agent.runInteractive()`). A single CLI process stays alive for the entire simulation, eliminating 5–20s of process spawn + session hydration overhead per turn. LLM U (haiku) now runs in 2–7s/turn, LLM A (sonnet) in 4–8s/turn. Also disabled external tools (`tools: ''`) for both agents since neither uses MCP tool calls. The web-app server is no longer needed for simulation.
6. ~~**LLM A never uses `show_fields`**~~ **FIXED** — Added two proactive actions to LLM U's action catalog: `review_progress` ("show me what's been filled / what's left") and `inspect_section` ("show me the Education section"). These give LLM U reasons to ask for form visibility, which naturally triggers LLM A to respond with `show_fields` or `show_preview`. Especially relevant for the returning-user scenario where reviewing a saved draft is natural.
7. ~~**LLM U doesn't proactively upload files**~~ **FIXED** — The view renderer now generates state-aware nudges injected into the screen view at specific moments. A generic file upload tip ("You can upload documents anytime — the assistant can extract info automatically") appears at turn 3 and every 5th turn. Section review nudges appear at section completion boundaries. Progress check nudges appear around the halfway point. Nudges are throttled (max 1 per turn) to avoid nagging. The nudges are generic (the app doesn't know what files the user has) — matching real app behavior. Tested: LLM U uploaded files at turn 6 in a thorough-profile run.
8. ~~**CLI simulator logging insufficient for training data**~~ **FIXED** — The CLI runner (`simulate.ts`) now implements the full replayable session log format with 8 entry types: `state_init`, `llm_a_input`, `llm_a_output`, `state_update`, `llm_u_input`, `llm_u_output`, `action_plan`, `session_end`. All three actors (LLM U, Middleman, LLM A) are captured. Typed interfaces in `session-log.ts`. See [Replayable Session Log Format](#replayable-session-log-format).
9. ~~**CLI simulator missing sim.html features**~~ **FIXED** — Multi-action handling via `processActions()`, persistent interactive sessions, sampling modes (`--sampling greedy|weighted|uniform`), and `--effort low|medium|high` flag all ported from sim.html to the CLI simulator. Feature parity achieved.
10. **Only 3 hardcoded personas** — Jane, Alex, Maria are manually defined in `personas.ts`. Training data generation needs dozens or hundreds of diverse personas (different demographics, education backgrounds, international students, non-traditional applicants, edge cases). Needs a persona generator that can programmatically create personas from a form schema — likely using an LLM to produce realistic, varied persona data.
11. ~~**LLM A cost grows linearly per turn**~~ **MITIGATED** — Added `--split-prompt` mode that splits the system prompt into static instructions (set once on the ClaudeAgent constructor) and dynamic state (sent per turn). LLM A cost dropped from ~$20/session to ~$4/session (5x reduction). Per-turn cost grows from $0.01 to $0.39 instead of $0.11 to $2.17. The flag is opt-in for backward compatibility. The remaining cost growth comes from accumulated conversation context in the interactive session — further reduction would require conversation summarization or context windowing.
12. ~~**LLM U JSON parse errors**~~ **FIXED** — LLM U occasionally returns plain text instead of valid JSON (especially with haiku or effort=low). Added silent retry: on parse failure, resend the same screen view. No artificial correction prompts injected — the retry is identical to the original request. Max 2 retries before failing the turn.
13. ~~**Impatient profile produces unrealistic data dumps**~~ **FIXED** — Rewrote the impatient behavior profile. Previously told LLM U to "batch everything" and "dump as much as you can in one message," producing unrealistic comma-separated data dumps. New profile emphasizes: answer only what's asked (one question, one answer), use files to skip manual entry (savvy efficiency), terse but natural language. Tested: sessions went from 7-turn data-dump-and-quit to 26-turn natural Q&A flow with proactive file upload.

## Replayable Session Log Format

The simulation log should be a replayable timeline of the full three-actor flow: LLM U ↔ Middleman (state) ↔ LLM A. Given just the JSONL, you can reconstruct the entire session — scrubbing through a timeline of message exchanges and state changes across all three actors.

### Data model

```
LLM U                    Middleman (State)              LLM A
─────                    ─────────────────              ─────
                         state_init
                                                        ← llm_a_input
                                                        → llm_a_output
                         state_update (from LLM A)
llm_u_input →
← llm_u_output
                         action_plan
                         state_update (from LLM U)
                                                        ← llm_a_input
                                                        → llm_a_output
                         state_update (from LLM A)
llm_u_input →
...
```

### Entry types

| Entry | Actor | Contains |
|-------|-------|----------|
| `state_init` | Middleman | Form schema, initial formValues, persona, profile, session config (model, effort, sampling) |
| `llm_a_input` | LLM A | System prompt + user message (what LLM A received) |
| `llm_a_output` | LLM A | Raw text, parsed actions, sessionId, cost, duration |
| `state_update` | Middleman | Source (llm_a / llm_u / button), delta, full formValues snapshot |
| `llm_u_input` | LLM U | Screen view text (what LLM U saw) |
| `llm_u_output` | LLM U | All candidates, selected rank + intent, sampling mode used |
| `action_plan` | Middleman | Selected candidate → execution plan (messages, fieldEdits, clickButton, stop) |

Each turn produces a predictable sequence: `llm_u_input → llm_u_output → action_plan → [state_update] → llm_a_input → llm_a_output → [state_update]`. A replay tool can render this as a three-column timeline.

## File Structure

```
packages/integration-tests/src/e2e/
  run-scenario.ts          — runner (takes QueuedAction[], runs turns, logs)
  replay-session.ts        — replay tool (session log → comparison + training JSONL)
  simulator/
    simulate.ts            — loop controller: starts LLM U + LLM A sessions, wires adapters
    session-log.ts         — typed entry interfaces + SessionLogger for replayable JSONL format
    action-processor.ts    — TS port of processActions() + buildLlmAMessage() (multi-action handling)
    draft-generator.ts     — generates realistic partial drafts for returning-user simulations
    user-action.ts         — U→A adapter: UserAction + formState → ConvertedAction
    view-renderer.ts       — A→U adapter: LLM A output + form state → user screen text
    action-catalog.ts      — 20 atomic user actions (11 reactive + 9 proactive) for LLM U prompt
    llm-u-prompt.ts        — LLM U system prompt builder (persona + profile + catalog + output format + rules)
    demo-u2a.ts            — demo: replays session log through U→A adapter, shows form state deltas
    demo-a2u.ts            — demo: replays session log through A→U adapter, shows screen views
    demo-llm-u.ts          — demo: replays session through LLM U prompt, shows ranked candidates
    personas.ts            — persona definitions (3 personas: jane, alex, maria)
    profiles/              — behavior profile prompt files (.md)
packages/integration-tests/src/
  simulator-adapters.test.ts — 34 unit tests (20 A→U + 14 U→A)
  sim-action-processor.test.ts — 36 unit tests for processActions() and buildLlmAMessage() (JS version)
  action-processor.test.ts — 31 unit tests for processActions() and buildLlmAMessage() (TS version)
packages/web-app/public/
  sim.html                 — simulation demo page (browser-driven LLM A ↔ LLM U loop)
  replay.html              — session replay page (visual JSONL log debugger)
  js/sim-adapters.js       — browser port of view-renderer + user-action converter
```

## Persona Data

3 pre-built personas that cover different form domains:

1. **Jane Smith** — US grad school applicant (CS, MIT undergrad, Google work experience)
2. **Alex Chen** — International AI researcher (Stanford, DeepMind, publications)
3. **Maria Garcia** — Medical patient (insured, hypertension, medications)

Each persona's `data` map covers all field_ids across all 3 forms. Shared fields (name, email, dob, phone, address) are consistent per persona. Form-specific fields (GPA, insurance, medications) filled per persona's "story."

## Usage

```bash
# Run one simulated session
npm run e2e:sim -- --form northfield --persona jane --profile thorough

# Run N sessions across all combinations
npm run e2e:sim -- --runs 3

# Reproducible run with seed
npm run e2e:sim -- --form northfield --persona jane --profile impatient --seed 42

# Use a different model for LLM U
npm run e2e:sim -- --form northfield --persona jane --profile impatient --llm-u-model sonnet

# Weighted sampling + low effort (faster, more diverse training data)
npm run e2e:sim -- --form northfield --persona jane --profile thorough --sampling weighted --effort low

# Split-prompt mode (5x cheaper LLM A — static instructions set once, only dynamic state per turn)
npm run e2e:sim -- --form northfield --persona jane --profile thorough --split-prompt

# Replay an existing session log against live API
npm run replay -- mock_data/session-log.jsonl

# Demo: see what LLM U candidates look like for recorded session turns
npm run demo:llm-u -- 3 --persona jane --profile impatient --model haiku
npm run demo:llm-u -- --turns 1-5

# Demo: see A→U screen rendering for recorded session
npm run demo:a2u

# Demo: see U→A action inference from recorded session (form state deltas)
npm run demo:u2a
```
