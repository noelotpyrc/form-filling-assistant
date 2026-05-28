# Doc 3: MCP Tool Server Spec

## 1. Overview

The MCP Tool Server is a lightweight bridge between the AI assistant (Claude) and AI-native website APIs. It exposes website interactions as MCP tools that Claude can call natively. The server handles HTTP communication, auth token management, and response formatting.

## 2. Architecture

```
Claude  ──MCP protocol──►  MCP Tool Server  ──HTTP──►  Website API
                           (Node.js process)
```

The MCP server is a single process that can manage connections to multiple website APIs simultaneously (one per active form session).

## 3. Session Management

The MCP server maintains in-memory session state per active form:

```
sessions: {
  "session_001": {
    form_id: "form_abc123",
    base_url: "http://localhost:3001/ai-agent/v1",
    auth_token: "tmp_token_xyz",
    token_expires_at: "2026-02-11T12:00:00Z",
    schema: { ... },
    instructions: { ... },
    current_draft_id: null
  }
}
```

Sessions are created during `discover_form` and referenced by `session_id` in subsequent tool calls.

## 4. Tool Definitions

### 4.1 `discover_form`

Connects to a website and retrieves form schema and instructions.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `url` | string | yes | Base URL of the website (e.g., `http://localhost:3001`) |
| `form_type` | string | no | Specific form to request if the site hosts multiple |

**Returns:**
```json
{
  "session_id": "session_001",
  "form_id": "form_abc123",
  "schema": { ... },
  "instructions": { ... }
}
```

**Behavior:**
1. Sends `POST /ai-agent/v1/discover` to the website
2. Stores the response (schema, instructions, auth token) in a new session
3. Returns schema and instructions to Claude (strips auth token — Claude doesn't need it)

---

### 4.2 `validate_fields`

Validates one or more field values against the website's constraints.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | yes | Active session ID |
| `fields` | array | yes | Array of `{ field_id, value }` objects |

**Returns:**
```json
{
  "results": [
    { "field_id": "gpa", "valid": true },
    { "field_id": "email", "valid": false, "error": "Invalid email format", "suggestion": "..." }
  ]
}
```

**Behavior:**
1. Sends `POST /validate` with the session's auth token
2. Returns validation results directly

---

### 4.3 `upload_file`

Uploads a file to the website for a specific form field.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | yes | Active session ID |
| `field_id` | string | yes | Which form field this file is for |
| `file_path` | string | yes | Local path to the file (provided by user via chat) |

**Returns:**
```json
{
  "file_id": "file_001",
  "field_id": "transcript",
  "filename": "transcript.pdf",
  "status": "accepted"
}
```

**Behavior:**
1. Reads the file from the local path
2. Sends `POST /upload-file` as multipart/form-data
3. Returns the file ID for use in draft/final submissions

---

### 4.4 `submit_draft`

Submits collected data as a draft and returns a preview for user review.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | yes | Active session ID |
| `data` | object | yes | Form data organized by section |

**Returns:**
```json
{
  "draft_id": "draft_001",
  "preview": {
    "sections": [ ... ]
  },
  "warnings": [ ... ],
  "completeness": {
    "required_filled": 10,
    "required_total": 12,
    "percentage": 83
  }
}
```

**Behavior:**
1. Sends `POST /submit-draft` with the data
2. Stores the `draft_id` in the session
3. Returns preview, warnings, and completeness info to Claude

---

### 4.5 `submit_final`

Commits the final submission. Requires a draft to exist.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | yes | Active session ID |

**Returns:**
```json
{
  "submission_id": "sub_20260211_001",
  "status": "submitted",
  "confirmation": {
    "reference_number": "APP-2026-00421",
    "message": "Your application has been submitted successfully.",
    "next_steps": [ ... ]
  }
}
```

**Behavior:**
1. Uses the `draft_id` stored in the session
2. Sends `POST /submit-final`
3. Returns confirmation details
4. Marks the session as completed

---

### 4.6 `get_session_status`

Returns current state of a form-filling session. Useful if Claude needs to resume or check where things stand.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | yes | Active session ID |

**Returns:**
```json
{
  "session_id": "session_001",
  "form_id": "form_abc123",
  "status": "in_progress",
  "current_draft_id": "draft_001",
  "token_expires_at": "2026-02-11T12:00:00Z",
  "completeness": {
    "required_filled": 10,
    "required_total": 12,
    "percentage": 83
  }
}
```

### 4.7 `get_drafts`

Retrieves saved drafts from the website. Useful for resuming a previously started form or checking if a user already has a draft on file.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | yes | Active session ID |
| `email` | string | no | Email to look up a specific draft. If omitted, returns all drafts. |

**Returns (found):**
```json
{
  "found": true,
  "email": "jane@example.com",
  "draft_id": "draft_001",
  "data": { ... }
}
```

**Returns (not found):**
```json
{
  "found": false,
  "email": "jane@example.com",
  "message": "No draft found for email: jane@example.com"
}
```

**Behavior:**
1. Sends `GET /drafts?email=...` to the website (no auth required)
2. Returns the result with a `found` boolean for easy branching

---

### 4.8 `get_submissions`

Retrieves completed submissions from the website. Useful for checking if a form was successfully submitted or looking up a confirmation reference number.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | yes | Active session ID |
| `email` | string | no | Email to look up a specific submission. If omitted, returns all submissions. |

**Returns (found):**
```json
{
  "found": true,
  "email": "jane@example.com",
  "submission_id": "sub_20260211_001",
  "reference_number": "APP-2026-00421",
  "submitted_at": "2026-02-11T10:30:00.000Z",
  "data": { ... }
}
```

**Returns (not found):**
```json
{
  "found": false,
  "email": "jane@example.com",
  "message": "No submission found for email: jane@example.com"
}
```

**Behavior:**
1. Sends `GET /submissions?email=...` to the website (no auth required)
2. Returns the result with a `found` boolean for easy branching

---

### 4.9 `set_fields`

Sets multiple form field values at once. Primarily used to auto-fill the web UI form panel with data extracted from documents, vault entries, or user input. Values are validated against the form schema before being accepted.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | yes | Active session ID |
| `fields` | array | yes | Array of `{ field_id, value }` objects |

**Returns:**
```json
{
  "summary": "Set 5 field(s) successfully, 1 error(s).",
  "set": [
    { "field_id": "full_name", "value": "Jane Smith", "valid": true },
    { "field_id": "gpa", "value": 5.0, "valid": false, "message": "GPA must be at most 4." }
  ],
  "errors": [
    { "field_id": "gpa", "message": "GPA must be at most 4." }
  ]
}
```

**Behavior:**
1. Looks up the session and its stored form schema
2. For each field: locates the field definition and validates the value against type, min/max, options, etc.
3. Returns results with valid/invalid status for each field
4. The web UI form panel intercepts the `tool_use` SSE event and updates field values in real-time

**Supported field types:** text, email, phone, textarea, number, date, select, multi_select, boolean. File fields return errors directing the user to use `upload_file`.

**Group sub-field support via dot notation:**

For group fields (e.g., `degrees`, `jobs`), use dot notation: `group_id.entry_index.sub_field_id`.

Example:
```json
{
  "fields": [
    { "field_id": "degrees.0.institution", "value": "MIT" },
    { "field_id": "degrees.0.degree_type", "value": "Bachelor's" },
    { "field_id": "degrees.0.gpa", "value": 3.85 },
    { "field_id": "degrees.1.institution", "value": "Stanford" }
  ]
}
```

The handler parses dot notation, resolves the group and sub-field definitions, validates the value against the sub-field's type/constraints, and checks entry_index against `max_items`. Fields set via `set_fields` are stored and reflected in the form panel. In the MCP flow, fields are automatically shown if not already visible. In the web app flow, fields render when the user expands a section — `set_fields` updates values and section progress counters.

---

### 4.10 `show_fields`

Shows specific form fields in the user's form panel. The panel starts empty — use this tool to progressively reveal fields as the conversation progresses. For group fields (repeatable entries like degrees or jobs), specify `entry_index` to show sub-fields for a specific entry.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | yes | Active session ID |
| `fields` | array | yes | Array of field descriptors to show |

Each item in `fields`:
| Name | Type | Required | Description |
|---|---|---|---|
| `field_id` | string | yes | Field ID from the form schema. For groups, use the group field_id (e.g., `"degrees"`). |
| `entry_index` | number | no | For group fields only. 0-based index of the entry (e.g., 0 = "Degree #1"). Defaults to 0. |
| `sub_fields` | string[] | no | For group fields only. Which sub-fields to show. If omitted, all non-file sub-fields are shown. |

**Returns:**
```json
{
  "shown": [
    { "field_id": "full_name", "label": "Full Name", "type": "text" },
    { "field_id": "email", "label": "Email Address", "type": "email" },
    {
      "field_id": "degrees",
      "entry_index": 0,
      "label": "Degree #1",
      "type": "group",
      "sub_fields_shown": ["institution", "degree_type", "gpa", "gpa_scale", "start_date", "end_date"]
    }
  ],
  "errors": [
    { "field_id": "unknown_field", "message": "Field \"unknown_field\" not found in form schema." }
  ]
}
```

**Behavior (MCP flow — Claude Chat/Desktop):**
1. Validates each field ID exists in the stored form schema
2. For group fields: validates `entry_index` against `max_items`, validates `sub_fields` if specified
3. No HTTP calls — purely schema validation (the web UI intercepts the `tool_use` SSE event to render fields)
4. Fields already shown are not duplicated (idempotent)
5. Previously completed fields remain visible as compact summaries

**Behavior (Web App flow):** In the web app, `show_fields` uses a simplified format — `{ "type": "show_fields", "section": "Education" }` — that focuses the user on a section (collapses all others, expands the target). Fields render automatically when the user expands a section. This action is used sparingly, not for progressive reveal.

**Examples:**
```
// Show simple fields in a batch
show_fields({ fields: [{ field_id: "full_name" }, { field_id: "email" }, { field_id: "phone" }] })

// Show first degree entry (all sub-fields)
show_fields({ fields: [{ field_id: "degrees", entry_index: 0 }] })

// Show specific sub-fields of a group entry
show_fields({ fields: [{ field_id: "degrees", entry_index: 0, sub_fields: ["institution", "degree_type", "gpa"] }] })

// Show second degree entry
show_fields({ fields: [{ field_id: "degrees", entry_index: 1 }] })
```

---

## 5. Vault Tools

The vault tools manage a local store of form data for cross-site reuse. See Doc 6 for full vault workflow details.

| Tool | Purpose |
|---|---|
| `vault_list` | List saved form entries (metadata only) |
| `vault_load` | Load full data from one or more vault entries |
| `vault_save` | Save form data for future reuse |
| `vault_delete` | Delete vault entries |
| `vault_merge` | Merge entries from the same website |
| `vault_set_profile` | Build/activate/clear a unified profile |

---

## 6. Error Handling

The MCP server translates website API errors into clear tool responses:

| Website Error | MCP Tool Response |
|---|---|
| `TOKEN_EXPIRED` | Auto-retry: re-discover and retry the original call. If re-discovery fails, return error to Claude. |
| `VALIDATION_FAILED` | Return validation details so Claude can ask the user to correct. |
| `FORM_NOT_FOUND` | Return error suggesting Claude check the URL or form type. |
| `RATE_LIMITED` | Wait and retry once. If still limited, inform Claude. |
| Network failure | Return error with suggestion to retry. |

## 7. Implementation Notes

- **Runtime:** Node.js with MCP SDK (`@modelcontextprotocol/sdk`)
- **No persistence:** All state is in-memory. Sessions are lost on restart (acceptable for POC).
- **Single user:** No multi-tenancy. One user, one assistant, one MCP server instance.
- **File handling:** Files are read from the local filesystem. In Claude Chat / Cowork, uploaded files are accessible at paths provided by the platform. In the web app, uploaded files are saved to a temp directory and the path is injected into the chat message.

## 8. Tool Summary

| Tool | Purpose | When Used |
|---|---|---|
| `discover_form` | Connect to website, get schema + instructions | Start of flow |
| `validate_fields` | Check field values before submission | During data collection (optional) |
| `upload_file` | Upload user files to the website | When user provides documents |
| `submit_draft` | Submit data, get preview | After data collection complete |
| `submit_final` | Commit the submission | After user confirms draft |
| `get_session_status` | Check session state | Resume or status check |
| `get_drafts` | Retrieve saved drafts from the website | Resume draft or check for prior work |
| `get_submissions` | Retrieve completed submissions from the website | Verify submission or look up reference number |
| `set_fields` | Set form field values in UI form panel | Auto-fill from documents, vault, or extracted data |
| `show_fields` | Show specific fields in UI form panel | Progressive reveal during data collection (MCP flow) / section focus (web app flow) |
| `vault_list` | List saved vault entries | Check for reusable data at start of flow |
| `vault_load` | Load full vault entry data | Pre-fill form from saved data |
| `vault_save` | Save form data to vault | After successful submission |
| `vault_delete` | Delete vault entries | User cleanup |
| `vault_merge` | Merge vault entries | Consolidate partial data |
| `vault_set_profile` | Set active vault profile | Streamline repeated form filling |
