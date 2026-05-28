# Form-Filling Assistant

A proof-of-concept system where an AI assistant fills out web forms on behalf of users entirely through conversation. Users never touch the target website directly — the assistant discovers form structure, collects data conversationally, and submits completed forms.

## Two Ways to Use It

### 1. Claude Chat / Claude Desktop

Use Claude's native chat interface with MCP tools connected via `.mcp.json`. Requires the mock servers and MCP server to be running.

> "Help me fill out the masters application at http://localhost:3001"

See [Doc 1: Architecture — Claude Chat UX](docs/doc-1-architecture-claude-chat.md).

### 2. Web App

A browser-based UI with a split-panel layout: chat on the left, form panel on the right. Uses a **browser-centric architecture** where ALL logic (system prompt building, action parsing, validation, vault, logging) runs in the browser. The server is a 1-endpoint dumb CLI proxy. Designed for future swap to a local model running in-browser.

```bash
npm run dev:persist  # port 3005 (persistence server)
npm run dev:web      # port 3004, open http://localhost:3004
```

See [Doc 8: Architecture — Web App UX](docs/doc-8-architecture-web-app.md).

## Architecture

### Claude Chat Flow
```
User  <──chat──>  Claude  <──MCP tools──>  MCP Server  <──HTTP──>  Mock Servers
                                            16 tools               (3 servers)
```

### Web App Flow
```
Browser (ALL logic: system prompt, action parsing, validation, vault, logging)
    ↕ SSE (POST /api/generate — 1 endpoint)
Web App Server (port 3004, dumb CLI proxy) → Claude CLI (via claude-agent)
    ↕ HTTP
Persistence Server (port 3005, 3 endpoints)
```

## Packages

```
packages/
  shared/              Shared TypeScript types (JsonStore persistence)
  mcp-server/          MCP tool server (16 tools: 10 form-filling + 6 vault)
  mock-masters/        Northfield University, MS in CS (port 3001)
  mock-masters-b/      Westbrook Institute, Research MS in AI (port 3003)
  mock-patient/        Riverside Family Medical, Patient Intake (port 3002)
  claude-agent/        Generic Claude Code CLI wrapper (ClaudeAgent class)
  web-app/             Browser-based chat UI with form panel (port 3004)
  persistence-server/  Draft & submission persistence (port 3005)
  integration-tests/   97 tests across 4 test files
```

## Quick Start

### Claude Chat / Desktop Flow

```bash
npm install
npm run build

# Start mock servers (separate terminals)
npm run dev:masters      # port 3001
npm run dev:masters-b    # port 3003
npm run dev:patient      # port 3002

# Open project folder in Claude Chat/Desktop — .mcp.json auto-discovered
```

### Web App Flow

```bash
npm install
npm run build

# Start servers (separate terminals)
npm run dev:persist      # port 3005 (persistence server)
npm run dev:web          # port 3004

# Open http://localhost:3004 — select a form and start chatting
```

### Run Tests

```bash
npm run build
npm run test:integration    # 97 tests across 4 files
```

## MCP Tools (16 total, Claude Chat flow only)

### Form-Filling (10 tools)

| Tool | Purpose |
|------|---------|
| `discover_form` | Connect to website, get schema + instructions |
| `validate_fields` | Check field values against website constraints |
| `upload_file` | Upload documents (transcript, SOP, etc.) |
| `submit_draft` | Submit data as draft, get preview for review |
| `submit_final` | Commit the final submission |
| `get_session_status` | Check session state |
| `get_drafts` | Retrieve saved drafts from the website |
| `get_submissions` | Retrieve completed submissions from the website |
| `set_fields` | Set form field values in the web app's form panel |
| `show_fields` | Progressively reveal fields in the web app's form panel |

### Vault (6 tools)

| Tool | Purpose |
|------|---------|
| `vault_list` | List saved entries (metadata only) |
| `vault_load` | Load full data by entry ID |
| `vault_save` | Save form data for cross-site reuse |
| `vault_delete` | Delete vault entries |
| `vault_merge` | Merge entries from the same website (deep merge) |
| `vault_set_profile` | Build/activate/clear a unified cross-site profile |

## Web App Actions (5 types)

The web app uses a `text + actions` model output format instead of MCP tools:

| Action | Purpose |
|--------|---------|
| `set_fields` | Set field values + auto-show in form panel |
| `show_fields` | Reveal empty fields in the panel |
| `ask_choice` | Render clickable option buttons in chat |
| `show_preview` | Render a structured summary card in chat |
| `show_button` | Show save_draft or submit button |

## Key Features

### Cross-Site Data Reuse

Fill a form on Site A, save to vault, then reuse personal info, education, and work history when filling Site B. Claude loads vault entries, identifies overlapping fields, and pre-fills automatically.

- **Claude Chat flow**: File-based vault at `~/.form-filling-assistant/`, managed via MCP tools
- **Web App flow**: IndexedDB vault in the browser, managed via `vault.js`

### JSON Persistence

All mock servers persist drafts and submissions to disk (`data/` directory) via the shared `JsonStore` class. The persistence server (web app flow) uses the same `JsonStore` for its `data/` directory.

### Vault CLI (Claude Chat flow)

```bash
npm run vault -- list          # List all vault entries
npm run vault -- show <id>     # Show full data for an entry
npm run vault -- delete <id>   # Delete an entry
npm run vault -- clear         # Delete all entries
npm run vault -- seed          # Create sample entries for testing
```

## Mock Server API Contract (Claude Chat flow)

All mock servers implement the same AI-native API at `/ai-agent/v1/`:

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /discover` | No | Handshake — returns schema, instructions, auth token |
| `POST /validate` | Yes | Validate field values |
| `POST /upload-file` | Yes | Upload documents |
| `POST /submit-draft` | Yes | Submit draft, get preview |
| `POST /submit-final` | Yes | Commit final submission |
| `GET /drafts` | No | Retrieve saved drafts (optional `?email=` filter) |
| `GET /submissions` | No | Retrieve completed submissions (optional `?email=` filter) |

## Persistence Server API (Web App flow)

3 endpoints on port 3005, no auth:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/drafts` | Upsert draft `{ email, form_id, data }` |
| `GET /api/drafts/:email` | Get saved draft by email |
| `POST /api/submissions` | Save submission `{ email, form_id, data }` |

## Testing

```bash
npm run build
npm run test:integration    # 97 tests across 4 files
```

Test files:
- `action-parser.test.ts` — 13 tests for text+actions output format parsing (tests actual browser JS)
- `persistence-server.test.ts` — 11 tests for persistence server endpoints
- `client-validation.test.ts` — 45 tests for client-side validation functions
- `form-metadata.test.ts` — 28 tests for static form JSON structure validation

## Documentation

| Doc | Content |
|-----|---------|
| [Doc 1](docs/doc-1-architecture-claude-chat.md) | Architecture — Claude Chat UX |
| [Doc 2](docs/doc-2-api-contract.md) | API contract — all website endpoints |
| [Doc 3](docs/doc-3-mcp-tools.md) | MCP tool server spec (all 16 tools) |
| [Doc 4](docs/doc-4-masters-application.md) | Scenario — Master's Application (Northfield) |
| [Doc 5](docs/doc-5-patient-intake.md) | Scenario — Patient Intake Form |
| [Doc 6](docs/doc-6-vault-cross-site.md) | Vault — cross-site data reuse and profile |
| [Doc 7](docs/doc-7-interactive-testing.md) | Interactive testing guide (both UIs) |
| [Doc 8](docs/doc-8-architecture-web-app.md) | Architecture — Web App UX (refactored) |
