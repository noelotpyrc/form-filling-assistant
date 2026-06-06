# Doc 0 — Project Overview

This project builds an AI assistant that fills out web forms through conversation. Two independent apps share the same domain but have different architectures, target users, and development status.

## Two Apps

### App 1: Claude Chat + MCP (Doc 1, Doc 3)

The original flow. Users interact through Claude's native chat UI (claude.ai or Claude Desktop). The assistant uses MCP tools to discover forms, set fields, validate, and submit.

```
User  ←─ chat ─→  Claude  ←─ MCP tools ─→  MCP Server  ←─ HTTP ─→  Mock Servers
                                             16 tools                (3 servers)
```

- **Target user**: Developer/power user with Claude access
- **Architecture**: Server-heavy — MCP server + 3 mock servers
- **Form interaction**: MCP tools (`discover_form`, `set_fields`, `validate_fields`, `submit_final`)
- **Vault**: File-based (`~/.form-filling-assistant/`), managed via 6 MCP vault tools
- **Status**: Functional, not actively developed. Serves as reference implementation.
- **Docs**: Doc 1 (architecture), Doc 2 (API contract), Doc 3 (MCP tools), Doc 6 (vault)

### App 2: Web App (Doc 8)

A standalone browser app with split-panel UI: chat on the left, form panel on the right. All application logic runs in the browser (system prompt building, action parsing, validation, form state management, logging). The server is a single-endpoint proxy to the Claude CLI.

```
Browser (ALL logic: system prompt, action parsing, validation, logging)
    ↕ SSE stream
Web App Server (1 endpoint: POST /api/generate) → Claude CLI
    ↕ HTTP
Persistence Server (3 endpoints: drafts + submissions)
```

- **Target user**: Anyone with a browser — no Claude account needed
- **Architecture**: Browser-centric — server is a dumb proxy
- **Form interaction**: Text + actions format (LLM outputs text + JSON action blocks parsed by browser)
- **Vault**: Disabled (see `decision-vault-disabled.md`). IndexedDB code exists but is orphaned.
- **Status**: Active development. Current focus for simulation and synthetic data generation.
- **Simulation demo**: `/sim.html` — browser-driven visualization of LLM A ↔ LLM U turns for debugging and sanity-checking simulation behavior
- **Docs**: Doc 8 (architecture), Doc 10 (file handling)

## Key Differences

| Aspect | App 1: Claude Chat + MCP | App 2: Web App |
|---|---|---|
| UI | Claude's chat interface | Custom split-panel browser app |
| Server complexity | MCP server + 3 mock servers | 1 proxy endpoint + persistence server |
| Model communication | MCP tool_use / tool_result | Text + `---actions---` + JSON |
| System prompt | N/A (MCP provides context per tool call) | Built per-turn in browser JS (`SystemPrompt.build()`) |
| Form state | Server-side (MCP server in-memory) | Browser-side (JS variables, logged to IndexedDB) |
| Vault | Active (file-based, 6 MCP tools) | Disabled (not relevant for target users) |
| Local model ready | No | Yes (swap `ChatProvider`) |

## Shared Code

Both apps share:
- **Form schemas** (`packages/mock-masters/`, `packages/mock-masters-b/`, `packages/mock-patient/`) — same JSON format defines form structure for both flows
- **`packages/shared/`** — TypeScript types for persistence (JsonStore)
- **`packages/claude-agent/`** — wrapper around `claude` CLI, used by web app server and simulation

## Simulation Pipeline (Doc 9)

Built on top of App 2's architecture. Replaces the human user with LLM U (a second Claude session) and the browser with an adapter layer. Uses the same `SystemPrompt.build()`, `ActionParser`, and `/api/generate` endpoint as the real web app.

```
LLM U  ←─ adapter ─→  LLM A (via web app server, same as App 2)
```

- **Purpose**: Generate synthetic conversation data for fine-tuning
- **Demo**: `/sim.html` provides a browser UI for running simulations interactively and inspecting LLM U candidates per turn
- **Docs**: Doc 9 (simulator), `plan-llm-u-agent.md` (LLM U agent design)

## Doc Index

| Doc | Topic |
|---|---|
| Doc 0 (this) | Project overview — two apps, their relationship |
| Doc 1 | Architecture — Claude Chat + MCP flow |
| Doc 2 | API contract — mock server endpoints |
| Doc 3 | MCP tool server — 16 tools |
| Doc 4 | Masters application form (Northfield) |
| Doc 5 | Patient intake form (Riverside) |
| Doc 6 | Vault — cross-site data reuse (MCP flow) |
| Doc 7 | Interactive testing guide (both apps) |
| Doc 8 | Architecture — Web App |
| Doc 9 | Scenario simulator — synthetic data generation |
| Doc 10 | File handling architecture |
| Doc 11 | Small-model research — methods & feasibility |
| Doc 12 | Tuning journal — master experiment log |
| Doc 13 | SFT v1 diagnosis (superseded by Doc 12 Exp 9) |
| Doc 14 | Training-data quality issues |
| Doc 15 | Real-app issues (R1–R13, harness testing) |
| Doc 16 | Small-model capability catalog (CAN/CANNOT) |
| Doc 17 | Tuning status map — current state anchor |
