# Doc 1: Architecture Overview — Claude Chat UX

## 1. Purpose

A proof-of-concept system where an AI assistant fills out web forms on behalf of users. The user interacts only with the AI assistant via chat — never touching the target website directly. Target websites expose AI-native APIs that the assistant uses to discover form structure, collect user data conversationally, and submit completed forms.

## 2. Components

### 2.1 AI Assistant (Claude)
The orchestrator. Runs inside Claude Chat or Cowork. No custom UI. The assistant uses MCP tools to interact with website APIs and uses natural conversation to interact with the user.

### 2.2 MCP Tool Server
A lightweight tool layer that exposes website API interactions as MCP tools Claude can call. Handles protocol mechanics (auth tokens, request formatting) and provides a clean interface for the assistant.

### 2.3 AI-Native Website API
The target website's agent-facing interface. Exposes form schema, instruction context, validation, draft preview, and final submission endpoints. For the POC, these are mock servers we build ourselves.

## 3. Component Interaction

```
┌─────────────┐       chat        ┌─────────────────┐     MCP tools     ┌─────────────────┐
│    User      │ ◄──────────────► │  AI Assistant    │ ◄───────────────► │  MCP Tool Server │
│  (human)     │   text, files    │  (Claude)        │   discover,       │                  │
└─────────────┘                   └─────────────────┘   validate,        └────────┬─────────┘
                                                        submit_draft,             │
                                                        submit_final              │ HTTP
                                                                                  │
                                                                         ┌────────▼─────────┐
                                                                         │  Website API      │
                                                                         │  (Mock Server)    │
                                                                         └──────────────────┘
```

## 4. Assumptions

- A public protocol exists for AI agent ↔ website handshake (discovery, auth). We mock this for the POC.
- The website provides both structured schema and instruction context to guide the agent's conversational behavior.
- Auth is handled via temporary credentials issued during the handshake. We simulate this with static mock tokens.
- The assistant (Claude) handles all data interpretation, fuzzy matching, file parsing, and conversational UX natively — no custom logic needed for this.

## 5. End-to-End Flow

### Phase 1: Discovery
1. User tells the assistant which website/form they want to fill out.
2. Assistant calls `discover_form(url)` via MCP tools.
3. MCP tool server hits the website's discovery endpoint.
4. Website returns: form schema + agent instruction context + temp auth credentials.
5. Assistant receives the full form definition and understands what data is needed.

### Phase 2: Data Collection
6. Assistant reads the instruction context to understand field groupings, ordering, and dependencies.
7. Assistant presents the first group of fields to the user conversationally (e.g., "Let's start with your personal information — I'll need your full name, date of birth, and contact details.").
8. User responds with data — can type directly, paste content, or upload files (resume, transcript, ID, etc.).
9. Assistant parses and extracts structured data from user input and files.
10. Assistant may call `validate_field(field, value)` for fields with complex constraints.
11. For conditional fields, assistant evaluates dependencies and only asks relevant follow-ups.
12. Repeat steps 7–11 for each field group until all required data is collected.

### Phase 3: Review & Submit
13. Assistant calls `submit_draft(form_id, data)` with all collected data.
14. Website API returns a formatted draft/preview of the submission.
15. Assistant presents the draft to the user: "Here's what your application looks like. Please review each section."
16. User confirms or requests changes.
17. If changes needed, assistant updates the relevant fields and re-submits draft. Loop until confirmed.
18. Assistant calls `submit_final(form_id, data)` to commit the submission.
19. Website returns confirmation (submission ID, next steps, etc.).
20. Assistant relays confirmation to user.

### Conversational Flow Patterns

**Batching:** The assistant groups related fields and asks for them together rather than one at a time. Grouping is driven by the instruction context from the website.

**Explanation:** When fields are domain-specific or ambiguous, the assistant proactively explains what's being asked, using hints from the instruction context. E.g., "The MCAT score — this is your total score across all sections, usually between 472 and 528."

**File Handling:** When the user uploads a file, the assistant extracts relevant data and maps it to form fields. The assistant confirms extracted values with the user before proceeding. E.g., "I pulled your GPA (3.7) and graduation date (May 2023) from your transcript. Does that look right?"

**Conditional Logic:** The assistant evaluates field dependencies in real time. If a user's answer makes a section irrelevant, the assistant skips it and explains why. E.g., "Since you selected the CS program, GRE scores are optional. Want to include them anyway?"

**Error & Validation:** If the website API rejects a field value during validation, the assistant explains the issue and asks the user to correct it. E.g., "The system says the phone number needs to include a country code. Can you provide it as +1-555-...?"

**Draft Review:** The assistant presents the draft in a structured, readable format — section by section — and explicitly asks the user to confirm or flag changes. It does not rush to final submission.

## 6. POC Scope

Three mock scenarios to demonstrate the system:

| Scenario | Characteristics |
|---|---|
| Master's Degree Application (Program A — Northfield) | Long multi-section form, document uploads (transcripts, SOP, recommendations), conditional fields (GRE, work experience), diverse field types |
| Patient Intake Form | Shorter form, sensitive data, medical terminology, heavy conditional branching (medications, family history), mix of structured and freetext fields |
| Research MS Application (Program B — Westbrook) | Overlaps with Program A (personal, education, work) plus unique sections (research, technical). Used to test cross-site vault data reuse. |

## 7. Related Documents

- **Doc 2: API Contract** — Generic website API endpoint specifications
- **Doc 3: MCP Tool Server Spec** — Tool definitions the assistant uses
- **Doc 4: Scenario — Master's Degree Application** — Mock schema and instruction context
- **Doc 5: Scenario — Patient Intake Form** — Mock schema and instruction context
- **Doc 6: Vault — Cross-Site Data Reuse** — Local vault storage, vault MCP tools, and cross-site reuse workflow
- **Doc 7: Interactive Testing Guide** — How to set up and test the system with Claude Desktop or Claude Chat
- **Doc 8: Architecture — Web App UX** — Browser-based alternative UI with split-panel form filling
