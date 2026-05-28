# Decision: Vault disabled in web app and simulation

**Date:** 2026-03-16
**Status:** Active

## Context

Vault is a feature for storing personal data locally and reusing it across different forms. It exists in two places:

1. **MCP Server** (`packages/mcp-server/src/vault/`) — 6 tools (save, load, list, delete, merge, set-profile) used by the Claude Chat + MCP flow.
2. **Web App** (`packages/web-app/public/js/vault.js`) — IndexedDB-based browser storage, integrated into the system prompt via `SystemPrompt.build()`.

## Decision

Disable vault in the web app system prompt and simulation pipeline. The MCP server vault code stays as-is (it serves a different flow).

## Reason

The web app targets casual users filling out a single form. These users are unlikely to:
- Set up a local vault before starting
- Return to reuse saved data across different forms
- Understand the concept of a "vault" without onboarding

Including vault context in the system prompt wastes tokens and adds instructions LLM A will never act on ("suggest reusing vault data", "suggest saving to vault after submission").

For the simulation pipeline, vault is irrelevant — synthetic sessions don't have saved data to reuse.

## What changed

- `SystemPrompt.build()`: Removed the vault section from the prompt. The `vaultSummary` parameter is kept (as `_vaultSummary`) for call-site compatibility but ignored.
- Removed vault-related behavior guidelines from the prompt ("auto-fill from vault", "suggest saving to vault").
- `vault.js` script remains loaded in the web app but is effectively orphaned — no prompt references it.

## Future considerations

Vault could be re-enabled if:
- The web app adds a "profile" or "saved data" feature for returning users
- Browser-side vault storage (IndexedDB) is surfaced in the UI with an onboarding flow
- The target audience shifts to power users who fill multiple forms
