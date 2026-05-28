# Doc 8: Architecture Overview — Web App UX

## 1. Purpose

An alternative UI for the form-filling assistant, designed for users who don't have access to Claude Chat or Claude Desktop. The web app provides a browser-based split-panel interface — chat on the left, form panel on the right.

Unlike the Claude Chat flow (Doc 1), the web app uses a **browser-centric architecture** where ALL application logic runs in the browser: system prompt building, action parsing, validation, vault storage, form state management, and logging. The server is a dumb CLI proxy with a single endpoint. This architecture is designed to enable a future swap to a local model (e.g., Qwen 3.5 0.8B via WASM/WebGPU) running entirely in the browser.

## 2. Components

### 2.1 Browser Application

The browser owns everything:

| Module | File | Purpose |
|--------|------|---------|
| System Prompt Builder | `public/js/system-prompt.js` | Builds dynamic system prompt per turn |
| Action Parser | `public/js/action-parser.js` | Parses `---actions---` delimiter + JSON from model output |
| Chat Provider | `public/js/chat-provider.js` | Pluggable LLM interface (currently `CLIProxyProvider`) |
| File Processor | `public/js/file-processor.js` | Reads files, extracts text from PDFs (see Doc 10) |
| Logger | `public/js/logger.js` | Structured JSONL logging to IndexedDB |
| Validation | `public/js/validation.js` | Schema-generic client-side field validation |
| Vault | `public/js/vault.js` | IndexedDB-based data storage for cross-session reuse |
| Form Metadata | `public/forms/*.json` | Static form schemas + instructions |
| Sim Adapters | `public/js/sim-adapters.js` | Browser port of view-renderer + user-action converter for sim demo |
| UI | `public/index.html` | Split-panel chat + form interface |
| Sim Demo | `public/sim.html` | Three-panel simulation visualization (chat, form progress, LLM U candidates) |

### 2.2 Web App Server (Dumb CLI Proxy)

A minimal Express server (`packages/web-app`, port 3004) with **6 endpoints** (2 core + 4 simulation):

```
# Core endpoints
GET  /api/config     → { preselectedForm: string | null }
POST /api/generate       { prompt, resume?, systemPrompt?, model?, effort? } → SSE stream
POST /api/generate-json  { prompt, systemPrompt?, model?, resume?, effort?, jsonSchema? } → structured JSON

# Simulation demo endpoints (lazy-loaded, only when sim pages are hit)
GET  /api/sim/config         → { personas, profiles, forms }
POST /api/sim/llm-u-prompt   { persona, profile } → { systemPrompt }
POST /api/sim/resolve-file   { persona, fileKey } → { filename, content }
```

The core server knows nothing about forms, actions, sessions, vault, or the application domain. It spawns Claude Code CLI via the `claude-agent` wrapper and streams raw text back. When `/api/generate` receives optional `systemPrompt`/`model`/`effort` params, it creates a one-off agent instead of using the default app agent — this enables LLM U streaming mode alongside LLM A. The simulation endpoints cross-import from `packages/integration-tests/src/e2e/simulator/` (lazy-loaded on first hit) and provide a browser-driven simulation loop. In the future, the core server is eliminated entirely when swapping to a local model.

**`--form` flag:** In production, each deployment serves one form (one form = one site). The server accepts a `--form <id>` CLI flag that locks the app to a single form:

```bash
npx tsx packages/web-app/src/index.ts --form masters-northfield
```

When `--form` is set, the browser auto-loads the form schema and shows a login screen (email input). After login, it checks the persistence server for a saved draft — if found, restores it and tells Claude the user is returning; otherwise starts a new conversation. Without `--form`, login is shown first, then the dev-only form selector.

### 2.3 Claude Agent Wrapper (`packages/claude-agent`)

A generic TypeScript wrapper around the Claude Code CLI headless mode. Used by the web app server to proxy prompts. See Doc 8 §5 below.

### 2.4 Persistence Server

A minimal Express server (`packages/persistence-server`, port 3005) with 3 endpoints for draft and submission persistence. No auth, no validation, schema-agnostic.

## 3. Component Interaction

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (owns ALL logic)                                       │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ SystemPrompt │  │ ActionParser │  │ ChatProvider           │  │
│  │ .build()     │  │ .parseActions│  │ .CLIProxyProvider      │  │
│  └──────┬───────┘  └──────┬───────┘  │ (future: LocalModel)  │  │
│         │                 │          └──────────┬─────────────┘  │
│         │  ┌──────────────┘                     │               │
│         │  │                                    │               │
│  ┌──────▼──▼────────────────────────────────────▼──────┐        │
│  │  index.html — UI + orchestration                     │        │
│  │  formValues, formSchema, claudeSessionId, Logger     │        │
│  └──────────┬──────────────────────────────┬───────────┘        │
│             │                              │                    │
│  ┌──────────▼──────┐           ┌───────────▼──────────┐         │
│  │ Validation.js   │           │ Vault (IndexedDB)    │         │
│  │ Logger (IDB)    │           │ Logger (IndexedDB)   │         │
│  └─────────────────┘           └──────────────────────┘         │
└────────────┬─────────────────────────────────┬──────────────────┘
             │ GET /api/config                 │ POST /api/drafts
             │ POST /api/generate              │ POST /api/submissions
             │ (SSE stream)                    │
             ▼                                 ▼
     ┌───────────────┐                 ┌─────────────────┐
     │ Web App Server│  stdio/JSON     │ Persistence     │
     │ (dumb proxy)  │◄──────────►     │ Server :3005    │
     │ port 3004     │  Claude CLI     └─────────────────┘
     └───────────────┘
```

## 4. Model Output: Text + Actions

The model outputs every response in a `text + actions` format. The **browser** parses this (not the server).

### Format

```
Your conversational text here...

---actions---
```json
[
  { "type": "set_fields", "fields": [{ "field_id": "full_name", "value": "John Smith" }] }
]
```
```

If there are no actions, the model just outputs text with no delimiter.

During streaming, text is displayed as plain text. On completion, the text portion is rendered as **markdown** using `marked.js` (bold, lists, tables, code blocks, etc.).

### Action Types

| Action | Purpose |
|--------|---------|
| `set_fields` | Set form field values. The form panel updates progress automatically. |
| `show_fields` | Focus a section in the form panel (collapses all others, expands the target). Used sparingly. |
| `ask_choice` | Render clickable option buttons in chat |
| `show_preview` | Render a structured summary card in chat |
| `show_button` | Show a `save_draft` or `submit` button |

### System Events (Frontend → Model)

The frontend sends feedback to the model as `[system]`-prefixed messages:
```
[system] Draft saved successfully.
[system] Validation error: email format invalid.
[system] User selected option: "Computer Science (MS)"
[system] User clicked: Save Draft
```

## 5. Agent Backend: Claude Agent Wrapper

Same `@form-filling-assistant/claude-agent` package as before. The web app server uses it as a dumb pipe via two modes:

```typescript
// Streaming text (LLM A, /api/generate)
const run = agent.run(prompt, { resume: resumeSessionId });
// Stream text events back to browser via SSE
// Return session_id, duration_ms, cost_usd in done event

// Structured JSON (/api/generate-json)
const { data, sessionId, costUsd, durationMs } = await agent.askJsonFull(prompt, schema);
// Returns structured output + session metadata for resume
```

The server does NOT parse actions, build system prompts, or maintain session state. It just proxies.

### Why text + actions (not MCP tool_use)?

The `text + actions` format is **model-agnostic**. Claude uses it via system prompt instructions; a fine-tuned local model (e.g., Qwen 3.5 0.8B) can be trained to produce the same format natively. Using Anthropic's `tool_use` protocol would create a format that doesn't transfer to local models.

## 6. Web App API

### `GET /api/config`

Returns app configuration. The browser fetches this on init to determine startup behavior.

**Response:** `{ preselectedForm: string | null }`

- If `preselectedForm` is set (via `--form` flag), the browser auto-loads that form and starts the conversation.
- If `null`, the browser shows the dev form selector.

### `POST /api/generate`

Request body: `{ prompt: string, resume?: string }`

**SSE event types:**

| Event | Payload | Description |
|---|---|---|
| `text` | `{ text }` | Raw text chunk from model (streamed) |
| `done` | `{ session_id, duration_ms, cost_usd }` | Turn complete, includes Claude CLI session ID |
| `error` | `{ message }` | Error occurred |

The browser sends the full prompt (system + user message), receives raw text, and handles all parsing/routing.

## 7. Persistence Server API

Three endpoints on port 3005. No auth, no validation, schema-agnostic.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/drafts` | Upsert draft `{ email, form_id, data }` → returns `{ draft_id, updated_at }` |
| `GET /api/drafts/:email` | Get saved draft → returns `{ draft_id, form_id, data, updated_at }` or 404 |
| `POST /api/submissions` | Save submission `{ email, form_id, data }` → returns `{ submission_id, reference_number, submitted_at }` |

## 8. Browser-Side Flow

### Per-turn flow (sendMessage → doGenerate)

1. **Build system prompt** — `SystemPrompt.build(formMeta, vaultSummary, formValues)` includes form schema, vault data, current state, and behavior guidelines (with interruption handling rules).
2. **Compose full prompt** — `systemPrompt + "\n\n---\n\nUser message: " + userMessage`
3. **Call chat provider** — `chatProvider.generate(fullPrompt, claudeSessionId)` → SSE stream
4. **Stream text to UI** — Display chunks in chat bubble. Stop at `---actions---` delimiter.
5. **Parse actions** — `ActionParser.parseActions(fullText)` → array of action objects
6. **Execute actions** — `handleAction(action)` for each (show_fields, set_fields, ask_choice, etc.)
7. **Capture session ID** — `claudeSessionId` from `done` event for multi-turn continuity
8. **Log everything** — `Logger.*()` writes to IndexedDB

### Chat Provider Abstraction

```javascript
// Current: CLIProxyProvider (server proxy)
const chatProvider = new ChatProvider.CLIProxyProvider('/api/generate');

// Future: LocalModelProvider (in-browser WASM/WebGPU)
// const chatProvider = new ChatProvider.LocalModelProvider(model);

// Future: APIProvider (direct API calls)
// const chatProvider = new ChatProvider.APIProvider(apiKey);
```

All providers share the same interface: `generate(fullPrompt, resumeSessionId?)` → controller with `onText`, `onDone`, `onError` callbacks.

## 9. Logging (IndexedDB)

Structured JSONL logging stored in IndexedDB for debugging and model training data.

**Database:** `form-filling-logs`
**Object store:** `entries` (autoIncrement key, indexes on `session_id`, `type`, `ts`)

### Log Entry Types

| Type | When | Key fields |
|------|------|------------|
| `session_start` | Form selected | `form_id`, `form_name` |
| `user_message` | User sends message | `message`, `role` |
| `model_input` | Before calling provider | `full_prompt_length`, `user_message`, `form_state_snapshot` |
| `model_output` | After response complete | `raw_text`, `parsed_actions`, `duration_ms`, `cost_usd` |
| `error` | Any error | `message`, `context` |
| `form_state_update` | Fields changed | `field_updates`, `source` |

### Session Inspector (`/dev.html`)

A standalone dev page at `/dev.html` for viewing session metadata and exporting logs. Completely separate from the chat app.

- **Session table** — lists all sessions with form name, start time, duration, entry count, model turns, and cost
- **Detail view** — click a row to expand all log entries with color-coded type badges
- **Per-session actions** — Export (JSONL) and Delete
- **Bulk actions** — Export All and Clear All

### Simulation Demo (`/sim.html`)

A standalone page for running and visualizing LLM A ↔ LLM U simulation loops interactively. Three-panel layout:

- **Chat panel** (left) — shows the LLM A conversation as it streams, including user messages injected by LLM U
- **Form progress panel** (middle) — live section-by-section progress bars updated as `set_fields` actions arrive
- **Debug panel** (right) — cumulative log of LLM U's ranked candidates per turn, with intent, reasoning, and actions

Controls: form selector, persona selector, behavior profile selector, LLM U model picker (haiku/sonnet/opus), Start/Stop/Export buttons. The simulation loop runs entirely in the browser — it calls `/api/generate` for LLM A (SSE) and `/api/generate-json` for LLM U (structured JSON). Sessions are logged to IndexedDB (with `[SIM]` prefix) so they appear in the Session Inspector. Export downloads a structured JSONL file with `session_start`, `llm_a`, `llm_u`, `user_action`, and `session_end` entries.

### DevTools Access

```javascript
Logger.listSessions()                    // list all session IDs
Logger.getSession(logSessionId)          // get all entries for a session
Logger.exportSession(logSessionId)       // JSONL string for download/training
Logger.deleteSession(sessionId)          // delete a single session
Logger.clearAll()                        // clear all logs
```

## 10. Vault (IndexedDB)

The browser-based vault stores form data in IndexedDB for cross-session reuse.

**Database:** `form-filling-vault`
**Object store:** `entries` (keyPath: `id`, indexes on `source_url`, `form_id`, `is_profile`)

**Functions:**
- `vaultList()` — metadata array (no full data)
- `vaultLoad(ids)` — full data for given IDs
- `vaultSave(entry)` — save new entry
- `vaultDelete(ids)` — delete entries
- `vaultSetProfile(opts)` — build/activate/clear a unified profile
- `vaultGetActiveProfile()` — get active profile
- `vaultBuildSummary()` — summary string for model context

On each turn, the vault summary is built in the browser and injected into the system prompt.

## 11. Form Panel Architecture

### Startup

- **Login screen**: Always shown first. User enters email, clicks Continue.
- **Draft check**: After login, browser calls `GET /api/drafts/{email}` on the persistence server. If a draft exists for the selected form, `formValues` is restored from it.
- **With `--form`**: Browser fetches `/api/config`, loads the form schema, shows login, then calls `selectForm()` with a hidden message (new user or returning user with draft).
- **Without `--form`** (dev mode): After login, shows form selector cards. User picks one.

### Section Accordion

The right panel displays a section-based accordion derived from the form schema. Each schema section becomes a collapsible row:

```
formContent
├── formTitle (sticky header) — form name
├── formOverallProgress — compact bar "X/Y required (Z%)"
└── sectionAccordion
    ├── section-row[data-section-id="personal"]
    │   ├── section-header (click to toggle)
    │   │   ├── chevron ▶ (rotates when expanded)
    │   │   ├── section-title "Personal Information"
    │   │   └── section-progress "3/7 fields"
    │   └── section-body (hidden when collapsed)
    │       ├── rendered fields (via renderField())
    │       └── section-actions → "Send answers" button
    ├── section-row[data-section-id="program"]
    │   └── ...
    └── ...
```

### Field Rendering

Fields are rendered **on section expand**, not via model actions. When the user clicks a section header to expand it, `ensureSectionFieldsRendered(sectionId)` creates all editable controls for that section's fields. This means:

1. Model emits `set_fields` → browser stores values in `formValues` and updates section progress counters. Fields are populated when the section is expanded.
2. Model emits `show_fields` → browser collapses all other sections and expands the target section. Used sparingly — only when the user asks to see where data is filled, or when the model needs the user to focus on a specific section.
3. `ask_choice` → clickable option buttons in chat (not in the panel).
4. `show_button` → save_draft / submit button in chat.

### Edit-in-place Flow

1. User expands a section → `ensureSectionFieldsRendered()` renders editable controls
2. User fills fields → clicks "Save" → `sendSectionAnswers()` collapses the section
3. Values are stored in `formValues` and included in `form_state_snapshot` on every model turn — no chat message sent
4. User can re-expand the section at any time to edit fields

### Section Progress

Per section: count required visible fields (skip conditionally hidden), count filled. Display as "X/Y fields". File fields count based on `formValues` presence. Group fields count required sub-fields × entries. Overall progress bar shows total across all sections.

### Non-Schema Notes

When the model sends `set_fields` with a `field_id` that doesn't exist in the schema (e.g., `prior_application_year` when only `prior_application` is a schema field), the value is stored as a per-section "Additional Info" note rather than being silently dropped. These notes appear at the bottom of the section body with formatted labels.

### File Fields

Shown inline within their section as a status line:
- Not uploaded: `📎 Transcript: use chat to upload`
- Uploaded: `✓ Transcript: uploaded`

### File Attachment — Model-Driven Assignment

When a user attaches a file via the chat 📎 button, the browser's `FileProcessor` extracts text (for PDFs/text files) and produces a `ProcessedFile`. The file is **not** auto-assigned to a form field — the browser cannot reliably determine whether a PDF is a resume, transcript, or statement of purpose.

Instead, when the message is sent, the model reads the extracted text, identifies the document type, and uses `ask_choice` to confirm with the user. After confirmation, the model uses `set_fields` to assign the file and extract data. The browser's `handleSetFields()` detects file-type fields and calls `assignFileToField()`, which looks up the file in `sentFiles` by filename and stores metadata in `formValues`. See Doc 10 for the full flow.

## 12. Session Management

- **No server-side sessions.** All state is in browser memory.
- `claudeSessionId` — Claude CLI session ID, round-tripped via `done` SSE events. Used for `--resume` in multi-turn.
- `logSessionId` — Browser-generated ID for logging. New per form selection.
- `formValues`, `formSchema`, `currentFormMeta` — all in JS variables.

## 13. Example Conversation Loop

```
Turn 1:
  Browser builds system prompt with form schema + vault summary
  Browser sends full prompt via chatProvider.generate()
  Model text: "Hi! Let's start with your personal details.
               What's your full name, email, and phone number?"
  Model actions: [] (no actions — user manages the form panel)
  → User can expand "Personal Information" section to see fields

Turn 2:
  User: "I'm John Smith, john@gmail.com, 555-1234"
  Browser rebuilds system prompt (includes current formValues)
  Model text: "Got it! I've filled in your details."
  Model actions: [{ type: "set_fields", fields: [
    { field_id: "full_name", value: "John Smith" },
    { field_id: "email", value: "john@gmail.com" },
    { field_id: "phone", value: "555-1234" }
  ]}]
  → Browser stores values, section progress updates to "3/7 fields"

Turn 3 (interruption):
  User: "Wait, what's the GRE?"
  Model text: "The GRE is a standardized test... Now, back to your details."
  Model actions: [] (no actions — just answered the question)
  → No form changes, conversation continues naturally

Turn 4 (user asks to see where data is):
  User: "Can you show me where my education info goes?"
  Model text: "Sure! I've expanded the Education section for you."
  Model actions: [{ type: "show_fields", section: "Education" }]
  → Browser collapses all other sections, expands Education
```

## 14. Key Differences from Claude Chat UX

| Aspect | Claude Chat (Doc 1) | Web App (this doc) |
|---|---|---|
| UI | Standard Claude chat interface | Split-panel: chat + form panel |
| Architecture | Server-heavy (MCP, mock servers) | Browser-centric (1 dumb proxy) |
| Form discovery | MCP `discover_form` tool | Static JSON files in browser |
| Validation | Server-side via MCP `validate_fields` | Client-side `validation.js` |
| Vault | File-based (`~/.form-filling-assistant/`) via MCP tools | IndexedDB in browser |
| Draft/Submit | Via MCP `submit_draft`/`submit_final` tools | Direct HTTP to persistence server |
| Model output | Standard tool_use/tool_result | Text + actions format |
| Form control | MCP tools (`show_fields`, `set_fields`) | Parsed actions from model output |
| System prompt | N/A (MCP provides context) | Built per-turn in browser JS |
| Action parsing | N/A (structured tool results) | Browser-side `ActionParser` |
| Logging | N/A | IndexedDB structured JSONL |
| Session state | Server in-memory | Browser JS variables |
| Server endpoints | 6 (sessions, form, vault, chat, etc.) | 6 (2 core + 4 simulation) |
| Requires mock servers | Yes (3 servers) | No (static JSON + persistence server) |
| Requires MCP server | Yes | No |
| Local model ready | No | Yes (swap ChatProvider) |

## 15. Related Documents

- **Doc 1: Architecture — Claude Chat UX** — The original Claude Chat-based flow (uses MCP + mock servers)
- **Doc 2: API Contract** — Generic website API endpoint specifications (for mock servers)
- **Doc 3: MCP Tool Server Spec** — Tool definitions (for Claude Chat flow)
- **Doc 7: Interactive Testing Guide** — Setup and testing instructions for both UIs
