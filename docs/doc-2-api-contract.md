# Doc 2: API Contract — AI-Native Website Interface

## 1. Overview

This document defines the generic API contract that any AI-native website implements to support AI agent form-filling. The contract is scenario-agnostic — specific form schemas are defined in scenario documents (Docs 4–5).

All endpoints are JSON over HTTP. Auth is via bearer token issued during discovery.

## 2. Base URL Convention

```
https://{domain}/ai-agent/v1/
```

For POC mock servers:
```
http://localhost:{port}/ai-agent/v1/
```

## 3. Endpoints

### 3.1 `POST /discover`

Initiates the agent ↔ website handshake. Returns form schema, instruction context, and temporary auth credentials.

**Request:**
```json
{
  "agent_id": "claude-agent-1.0",
  "form_type": "master-application"    // optional, if site hosts multiple forms
}
```

**Response:**
```json
{
  "form_id": "form_abc123",
  "auth_token": "tmp_token_xyz",
  "token_expires_at": "2026-02-11T12:00:00Z",
  "schema": { ... },
  "instructions": { ... }
}
```

**`schema`** — structured form definition. See Section 4.

**`instructions`** — agent-facing guidance for conversational behavior. See Section 5.

---

### 3.2 `POST /validate`

Validates one or more field values against the form's constraints. Optional — the agent can use this for fields with complex validation before submitting a draft.

**Request:**
```json
{
  "form_id": "form_abc123",
  "fields": [
    { "field_id": "gpa", "value": "3.7" },
    { "field_id": "email", "value": "jane@example.com" }
  ]
}
```

**Response:**
```json
{
  "results": [
    { "field_id": "gpa", "valid": true },
    { "field_id": "email", "valid": true }
  ]
}
```

**Validation failure example:**
```json
{
  "results": [
    {
      "field_id": "gpa",
      "valid": false,
      "error": "GPA must be between 0.0 and 4.0",
      "suggestion": "If your institution uses a different scale, select 'Other' for gpa_scale and provide the original value."
    }
  ]
}
```

---

### 3.3 `POST /submit-draft`

Submits collected data as a draft. Returns a formatted preview the agent can show the user for review. Can be called multiple times as the user makes edits.

**Request:**
```json
{
  "form_id": "form_abc123",
  "data": {
    "personal": {
      "full_name": "Jane Smith",
      "email": "jane@example.com",
      "phone": "+1-555-0123"
    },
    "education": {
      "institution": "State University",
      "gpa": "3.7",
      "graduation_date": "2023-05"
    },
    "files": {
      "transcript": { "file_id": "file_001", "filename": "transcript.pdf" },
      "sop": { "file_id": "file_002", "filename": "statement.pdf" }
    }
  }
}
```

**Response:**
```json
{
  "draft_id": "draft_001",
  "status": "draft",
  "preview": {
    "sections": [
      {
        "title": "Personal Information",
        "fields": [
          { "label": "Full Name", "value": "Jane Smith" },
          { "label": "Email", "value": "jane@example.com" },
          { "label": "Phone", "value": "+1-555-0123" }
        ]
      },
      {
        "title": "Education",
        "fields": [
          { "label": "Institution", "value": "State University" },
          { "label": "GPA", "value": "3.7 / 4.0" },
          { "label": "Graduation Date", "value": "May 2023" }
        ]
      }
    ]
  },
  "warnings": [
    { "field_id": "recommendation_letters", "message": "No recommendation letters uploaded. 2 are required." }
  ],
  "completeness": {
    "required_filled": 8,
    "required_total": 12,
    "percentage": 67
  }
}
```

---

### 3.4 `POST /upload-file`

Uploads a file associated with a form field. Returns a file ID for reference in draft/final submissions.

**Request:** `multipart/form-data`
- `form_id`: string
- `field_id`: string (which field this file is for)
- `file`: binary

**Response:**
```json
{
  "file_id": "file_001",
  "field_id": "transcript",
  "filename": "transcript.pdf",
  "size_bytes": 245000,
  "status": "accepted"
}
```

---

### 3.5 `POST /submit-final`

Commits the submission. Only succeeds if all required fields are filled and valid.

**Request:**
```json
{
  "form_id": "form_abc123",
  "draft_id": "draft_001"
}
```

**Response:**
```json
{
  "submission_id": "sub_20260211_001",
  "status": "submitted",
  "confirmation": {
    "message": "Your application has been submitted successfully.",
    "reference_number": "APP-2026-00421",
    "next_steps": [
      "You will receive a confirmation email within 24 hours.",
      "Application review takes 4-6 weeks.",
      "You can check status at https://example.com/status/APP-2026-00421"
    ]
  }
}
```

**Error (incomplete):**
```json
{
  "status": "rejected",
  "errors": [
    { "field_id": "recommendation_letters", "message": "At least 2 recommendation letters are required." }
  ]
}
```

---

## 4. Schema Format

The `schema` object returned by `/discover` defines the form structure.

```json
{
  "sections": [
    {
      "section_id": "personal",
      "title": "Personal Information",
      "fields": [
        {
          "field_id": "full_name",
          "label": "Full Legal Name",
          "type": "text",
          "required": true,
          "max_length": 200
        },
        {
          "field_id": "dob",
          "label": "Date of Birth",
          "type": "date",
          "required": true,
          "format": "YYYY-MM-DD"
        },
        {
          "field_id": "country",
          "label": "Country of Citizenship",
          "type": "select",
          "required": true,
          "options": ["US", "CA", "UK", "..."]
        }
      ]
    }
  ]
}
```

### Supported Field Types

| Type | Description | Extra Properties |
|---|---|---|
| `text` | Free text input | `max_length`, `min_length`, `pattern` (regex) |
| `textarea` | Long text (essays, statements) | `max_length`, `min_length`, `word_limit` |
| `number` | Numeric value | `min`, `max`, `decimal_places` |
| `date` | Date value | `format`, `min_date`, `max_date` |
| `select` | Single selection from options | `options` (array of values or `{value, label}` objects) |
| `multi_select` | Multiple selections | `options`, `max_selections` |
| `boolean` | Yes/no toggle | — |
| `email` | Email address | — |
| `phone` | Phone number | `require_country_code` |
| `file` | File upload | `accepted_types` (e.g., `["pdf", "jpg"]`), `max_size_mb` |
| `group` | Repeatable group of fields (e.g., multiple work experiences) | `fields` (nested), `min_items`, `max_items` |

### Conditional Fields

Fields can have a `condition` property that references another field:

```json
{
  "field_id": "gre_score",
  "label": "GRE Total Score",
  "type": "number",
  "required": false,
  "condition": {
    "field_id": "program",
    "operator": "not_in",
    "value": ["cs", "data_science"]
  }
}
```

Supported operators: `equals`, `not_equals`, `in`, `not_in`, `greater_than`, `less_than`.

## 5. Instruction Context Format

The `instructions` object guides the agent's conversational behavior. This is not schema — it's advice.

```json
{
  "greeting": "This is the graduate application for Example University. The applicant will need to provide personal details, academic history, test scores, a statement of purpose, and recommendation letters.",
  "section_order": ["personal", "education", "test_scores", "documents", "references"],
  "section_guidance": {
    "personal": {
      "intro": "Start by collecting basic personal and contact information.",
      "notes": "International applicants should provide their name exactly as it appears on their passport."
    },
    "test_scores": {
      "intro": "Ask about standardized test scores. Some programs have made GRE optional.",
      "notes": "If the applicant's program doesn't require GRE, let them know and ask if they'd like to submit scores anyway."
    },
    "documents": {
      "intro": "The applicant needs to upload their transcript and statement of purpose.",
      "notes": "If the applicant uploads a transcript file, try to extract GPA and graduation date from it rather than asking separately. The statement of purpose should be 500-1000 words."
    }
  },
  "general_notes": [
    "Be encouraging — applying to grad school is stressful.",
    "If the applicant seems unsure about a field, explain what it is and why it matters.",
    "The application can be saved as draft at any point — remind the user of this if they seem rushed."
  ]
}
```

## 6. Error Format

All endpoints use consistent error responses:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "One or more fields failed validation.",
    "details": [ ... ]
  }
}
```

Standard error codes: `VALIDATION_FAILED`, `FORM_NOT_FOUND`, `TOKEN_EXPIRED`, `INCOMPLETE_SUBMISSION`, `FILE_TOO_LARGE`, `UNSUPPORTED_FILE_TYPE`, `RATE_LIMITED`.

### 3.6 `GET /drafts`

Retrieves saved drafts. No authentication required — these are open read-only endpoints for the AI agent to check for prior work.

**Query parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `email` | string | no | Filter by applicant email. If omitted, returns all drafts. |

**Response (with email):**
```json
{
  "draft_id": "draft_001",
  "email": "jane@example.com",
  "data": {
    "personal": { ... },
    "education": { ... }
  }
}
```

**Response (without email — list all):**
```json
{
  "drafts": [
    { "draft_id": "draft_001", "email": "jane@example.com", "data": { ... } }
  ]
}
```

**Error (not found):**
```json
{ "error": "No draft found for email: unknown@example.com" }
```
HTTP 404

---

### 3.7 `GET /submissions`

Retrieves completed submissions. Same structure as `/drafts` but for finalized submissions.

**Query parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `email` | string | no | Filter by applicant email. If omitted, returns all submissions. |

**Response (with email):**
```json
{
  "submission_id": "sub_20260211_001",
  "email": "jane@example.com",
  "reference_number": "APP-2026-00421",
  "submitted_at": "2026-02-11T10:30:00.000Z",
  "data": { ... }
}
```

**Response (without email — list all):**
```json
{
  "submissions": [
    { "submission_id": "sub_20260211_001", "email": "jane@example.com", "data": { ... } }
  ]
}
```

**Error (not found):**
```json
{ "error": "No submission found for email: unknown@example.com" }
```
HTTP 404

---

## 7. Auth

All endpoints except `/discover`, `/drafts`, and `/submissions` require the `auth_token` from the discovery response:

```
Authorization: Bearer tmp_token_xyz
```

Tokens are short-lived (default 1 hour for POC). If expired, the agent must re-discover.
