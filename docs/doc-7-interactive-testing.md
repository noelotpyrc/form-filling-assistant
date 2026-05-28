# Doc 7: Interactive Testing Guide

## 1. Prerequisites

- **Node.js** v18+ (for running the monorepo)
- **Claude Desktop**, **Claude Chat** (claude.ai) with MCP tool support, or the **Web App** (no Claude account needed)
- The repo cloned and dependencies installed:

```bash
git clone <repo-url>
cd form-filling-assistant
npm install
```

## 2. Build

Build all packages before starting:

```bash
npm run build
```

This compiles TypeScript in every workspace: shared types, MCP server, and all mock servers.

The MCP server **must** be built because `.mcp.json` points to the compiled output (`packages/mcp-server/dist/index.js`). The mock servers can run without a pre-build (the `dev` scripts use `tsx` for on-the-fly compilation), but building everything upfront avoids surprises.

After making code changes, re-run `npm run build` (or `npm run build -w packages/mcp-server` for just the MCP server).

## 3. Start Mock Servers

Open separate terminal windows for each server you want to test:

```bash
# Terminal 1 — Program A: Northfield CS Masters (port 3001)
npm run dev:masters

# Terminal 2 — Program B: Westbrook Research MS in AI (port 3003)
npm run dev:masters-b
```

Each server prints a startup message when ready:

```
mock-masters listening on http://localhost:3001
```

To use a custom port:

```bash
PORT=4001 npm run dev:masters
```

To verify a server is running:

```bash
curl http://localhost:3001/health
# → {"status":"ok","service":"mock-masters"}
```

### Available Mock Servers

| Server | Script | Default Port | Description |
|---|---|---|---|
| mock-masters | `npm run dev:masters` | 3001 | Northfield University, MS in CS (Program A) |
| mock-masters-b | `npm run dev:masters-b` | 3003 | Westbrook Institute, Research MS in AI (Program B) |
| mock-patient | `npm run dev:patient` | 3002 | Riverside Family Medical, Patient Intake |
| web-app | `npm run dev:web` | 3004 | Browser-based chat UI (use `-- --form <id>` to lock to one form) |

For the cross-site vault reuse flow, you need **both** masters and masters-b running.

## 4. Connect Claude to the MCP Server

The repo root contains a `.mcp.json` file that tells Claude how to start the MCP server:

```json
{
  "mcpServers": {
    "form-filling-assistant": {
      "command": "node",
      "args": ["packages/mcp-server/dist/index.js"]
    }
  }
}
```

### Claude Desktop

1. Open Claude Desktop.
2. Open the project folder (`form-filling-assistant/`) — Claude Desktop auto-discovers `.mcp.json` from the project root.
3. Claude starts the MCP server process automatically via stdio.

### Claude Code / Claude Chat

If using Claude Code, the `.mcp.json` is picked up automatically when you open the project directory.

### Verifying the Connection

Ask Claude:

> "What MCP tools do you have?"

Claude should list **16 tools**: 10 form-filling tools + 6 vault tools.

| Form-filling Tools | Vault Tools |
|---|---|
| `discover_form` | `vault_list` |
| `validate_fields` | `vault_load` |
| `upload_file` | `vault_save` |
| `submit_draft` | `vault_delete` |
| `submit_final` | `vault_merge` |
| `get_session_status` | `vault_set_profile` |
| `get_drafts` | |
| `get_submissions` | |
| `set_fields` | |
| `show_fields` | |

`set_fields` and `show_fields` are used by the web app's form panel UI. `set_fields` stores field values and updates progress counters. `show_fields` focuses the user on a specific section (collapses others, expands the target). In Claude Chat/Desktop, they are available but have no visible effect since there is no form panel.

If Claude doesn't see the tools, check that `npm run build` completed successfully and that `packages/mcp-server/dist/index.js` exists.

## 5. Alternative: Using the Web App

The web app provides a browser-based UI for users who don't have Claude Desktop or Claude Chat. It spawns the Claude CLI as a subprocess, so the same MCP tools and mock servers are used.

### Start the web app

```bash
# Production mode: locked to one form (no form selector)
npm run dev:web -- --form masters-northfield

# Dev mode: shows form selector for all available forms
npm run dev:web
```

Then open `http://localhost:3004` in your browser. You'll see a login screen asking for your email. After login, the split-panel interface loads: chat on the left, form panel on the right.

With `--form`, after login the conversation starts immediately. The browser checks for a saved draft — if found, restores it and tells Claude the user is returning. Without `--form`, after login you'll see a form selector.

### Session Inspector

Visit `http://localhost:3004/dev.html` to open the Session Inspector — a standalone page for viewing, exporting, and deleting session logs. Logs are stored in IndexedDB and can be downloaded as `.jsonl` files.

### Form panel

The right panel shows a **section-based accordion** derived from the form schema. Each section displays a progress indicator ("X/Y fields"). Sections expand on click to reveal rendered fields. Clicking "Save" collapses the section; re-expand anytime to edit.

### How it differs from Claude Chat

| | Claude Chat / Desktop | Web App |
|---|---|---|
| Form fields | Shown inline in chat | Section accordion in dedicated form panel (right side) |
| Field reveal | All at once via conversation | On demand — fields render when user expands a section |
| Auto-fill | Claude describes values in chat | `set_fields` stores values; section progress updates automatically |
| Section focus | N/A | `show_fields` collapses other sections and expands the target (used sparingly) |
| Section progress | N/A | Per-section "X/Y fields" + overall progress bar |
| File uploads | Platform file upload | Chat attachment button (📎) with auto-matching to form file fields |
| Requires Claude account | Yes | No (uses Claude CLI with API key) |

### Test flow

The conversational flow is the same as sections 6–8 below. The web app's system prompt guides Claude to use `set_fields` to auto-fill from vault/documents. The form panel self-manages field rendering — when the user expands a section, all fields for that section are rendered automatically. `show_fields` is used sparingly to focus the user's attention on a specific section when needed.

---

## 6. Test Flow: Single Form (Program A)

Before testing cross-site reuse, verify the basic flow works with one form.

### Start the conversation

> **You:** "Help me fill out the masters application at http://localhost:3001"

### Expected behavior

1. Claude calls `discover_form({ url: "http://localhost:3001" })` and receives an 8-section schema for the Northfield CS Masters program.
2. Claude reads the instructions and starts asking you for data section by section — personal info first, then program selection, education, etc.
3. You provide data (see sample data in section 9 below).
4. Claude may call `validate_fields` to check specific values.
5. Once all required data is collected, Claude calls `submit_draft` and shows you a preview.
6. You review and confirm.
7. Claude calls `submit_final` — you receive a confirmation with a reference number.
8. Claude asks if you want to save the data for future forms.
9. You say **yes** — Claude calls `vault_save` and confirms the entry was saved.

## 7. Test Flow: Cross-Site Vault Reuse (Program A → Program B)

This is the main scenario. It requires Program A to be completed and saved to the vault first (section 6 above).

### Continue the conversation

> **You:** "Now fill out the Westbrook AI masters application at http://localhost:3003"

### Expected behavior

1. Claude calls `discover_form({ url: "http://localhost:3003" })` — gets a 5-section schema: personal, education, work_experience, research, technical.

2. **Claude checks the vault.** Claude calls `vault_list()` and sees the Program A entry you saved earlier. It compares what Program B needs against the vault entry's `data_summary`.

3. **Claude offers to reuse data.** Something like: "I found your Northfield application from earlier. It has your personal info, education, and work experience. Want me to reuse that data for this application?"

4. You confirm — Claude calls `vault_load` with the Program A entry ID and retrieves the full data.

5. **Claude pre-fills the overlapping sections** (personal, education, work_experience) from the vault and only asks you for the **new** sections: research and technical.

6. You provide research + technical data (see sample data in section 9).

7. Claude calls `submit_draft` — should show 100% completeness with data from both sources.

8. You confirm — Claude calls `submit_final`.

9. Claude asks if you want to save. You say yes — Claude calls `vault_save` with a description covering all 5 sections.

10. The vault now contains **2 entries** from different websites.

### Verify the vault

You can ask Claude at any point:

> "List what's in the vault"

Claude calls `vault_list()` and should show 2 entries with different `source_url` values (`:3001` and `:3003`).

## 8. What to Look For

When testing interactively, watch for these behaviors:

| Checkpoint | What to verify |
|---|---|
| Vault check timing | Claude checks `vault_list` **after** `discover_form`, not before — it needs to know what the form requires first |
| Overlap detection | Claude correctly identifies that personal, education, and work_experience overlap between programs |
| User choice | Claude presents the reuse option and lets you choose — it doesn't silently reuse data |
| Data accuracy | Reused fields are accurate — no garbled, missing, or mismatched values |
| New sections only | Claude only asks for research + technical (Program B's unique sections), not the reused ones |
| Save both entries | After both submissions, `vault_list` shows 2 entries from different `source_url` values |
| Multiple vault entries | If you run the test multiple times, Claude should present all relevant entries and let you pick |

## 9. Sample Test Data

Copy-pasteable data you can provide to Claude during the conversation. This matches the test data used in the automated E2E tests.

### Personal Info (reused across both programs)

```
Full name: Jane Smith
Date of birth: 1995-06-15
Citizenship: US
Email: jane@example.com
Phone: +15559876543
Mailing address: 456 Oak Ave, Springfield, IL 62704
```

### Education (reused)

```
Institution: State University
Degree: Bachelor's in Computer Science
GPA: 3.85 / 4.0
Dates: August 2013 – May 2017
```

### Work Experience (reused)

```
Employer: Tech Corp
Title: Software Engineer
Dates: June 2017 – December 2024
Description: Full-stack development and ML infrastructure
```

### Research (Program B only)

```
Number of publications: 2
Research interests: Large language models, reinforcement learning from human feedback, and AI safety
Preferred advisors: Dr. Sarah Chen, Dr. Michael Torres
```

### Technical Skills (Program B only)

```
Programming languages: Python, C++, Rust
Technical statement: Proficient in PyTorch, JAX, and distributed training. Built ML pipeline serving 10M requests/day.
```

### Program A Additional Fields

For the Northfield application, Claude will also ask for program selection, test scores (GRE/TOEFL depending on your citizenship answer), documents, references, and additional info. You can provide any reasonable values or tell Claude to skip optional sections.

## 10. Resetting State

### Clear the vault

```bash
rm -rf ~/.form-filling-assistant
```

This deletes all saved entries and dump files. The vault is re-created automatically on the next `vault_list` or `vault_save` call.

### Restart mock servers

Mock server sessions are stored in memory. Restarting a server clears all sessions. Drafts and submissions are persisted to disk in each server's `data/` directory.

```
Ctrl+C  (in the server's terminal)
npm run dev:masters    (restart)
```

To also clear persisted drafts/submissions, delete the server's data directory:

```bash
rm -rf packages/mock-masters/data/
```

### Use a temporary vault directory

To avoid touching `~/.form-filling-assistant`, you can override the vault location by editing `.mcp.json`:

```json
{
  "mcpServers": {
    "form-filling-assistant": {
      "command": "node",
      "args": ["packages/mcp-server/dist/index.js"],
      "env": {
        "FORM_FILLING_VAULT_DIR": "/tmp/vault-interactive-test"
      }
    }
  }
}
```

Then delete `/tmp/vault-interactive-test` to start fresh.

## 11. Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| Claude says it can't connect to the website | Mock server not running or wrong port | Check that `npm run dev:masters` is running and the port matches the URL you gave Claude |
| Claude doesn't have any MCP tools | MCP server not built or `.mcp.json` not found | Run `npm run build` and verify `packages/mcp-server/dist/index.js` exists |
| `vault_list` returns empty | No data saved yet | Complete a form and save it to the vault first |
| Claude doesn't check the vault | Claude may not always call `vault_list` proactively | Prompt it: "Check if there's any saved data in the vault you can reuse" |
| Token expired error | Session timed out after long idle | The MCP server auto-retries by re-discovering. If it persists, start a fresh `discover_form` |
| Submit final rejected | Draft has missing required fields | Check the `submit_draft` response for warnings and completeness. Provide the missing data. |
| Port already in use | Another process or previous test run occupying the port | Kill the process (`lsof -i :3001`) or use a different port (`PORT=4001 npm run dev:masters`) |

## 12. Running Automated Tests Instead

If you want to verify the flow programmatically without interactive testing:

```bash
npm run build
npm run test:integration
```

This runs all 145 tests across 8 test files, including:
- `client-validation.test.ts` — 45 tests for schema-generic field validation
- `form-metadata.test.ts` — 28 tests for form schema loading and metadata
- `scenario-runner.test.ts` — 13 tests for scenario runner queue mechanics (QueuedAction dispatch, field_edit, show_button events, ask_choice auto-selection)
- `form-state.test.ts` — 13 tests for form state management
- `action-parser.test.ts` — 13 tests for text + actions output parsing
- `system-prompt.test.ts` — 12 tests for dynamic system prompt building
- `persistence-server.test.ts` — 11 tests for draft/submission persistence endpoints
- `sse-parser.test.ts` — 10 tests for SSE stream parsing

## 13. Related Documents

- **Doc 1: Architecture — Claude Chat UX** — System components and end-to-end flow for the Claude Chat interface
- **Doc 3: MCP Tool Server Spec** — Core form-filling tools (discover, validate, submit)
- **Doc 6: Vault — Cross-Site Data Reuse** — Vault storage format, tool specs, and cross-site workflow details
- **Doc 8: Architecture — Web App UX** — Browser-based alternative UI with split-panel form filling
