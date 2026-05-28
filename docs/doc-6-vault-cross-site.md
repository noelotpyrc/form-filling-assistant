# Doc 6: Vault — Cross-Site Data Reuse

## 1. Purpose

Users often fill forms across multiple websites that ask for overlapping information — name, email, education history, work experience, etc. Re-entering the same data every time is tedious and error-prone.

The **vault** is a local storage layer that lets the AI agent save raw form data after a submission and reuse it when filling out a form on a **different** website. This is not session management (that's the website server's job) — this is cross-site convenience for the user.

Since an AI agent always mediates access, vault entries use flexible natural-language descriptions and data summaries instead of rigid schemas. The AI reads the descriptions to determine relevance, and the user picks which entries to reuse.

## 2. How It Works

```
Site A (completed)                           Site B (new)
┌──────────────┐                            ┌──────────────┐
│ Masters App  │   vault_save               │ Research MS  │
│ Northfield U │ ──────────────►            │ Westbrook    │
│              │                 ┌────────┐ │              │
│ personal     │                 │ Local  │ │ personal  ◄──── reused from vault
│ education    │                 │ Vault  │ │ education ◄──── reused from vault
│ work exp     │                 │        │ │ work exp  ◄──── reused from vault
│ test scores  │                 │ dumps/ │ │ research  ◄──── new (collected from user)
│ documents    │                 │ index  │ │ technical ◄──── new (collected from user)
│ references   │                 └────────┘ │              │
└──────────────┘                     ▲      └──────────────┘
                            vault_list │
                            vault_load │
                                       │
                                    AI Agent
```

### Step-by-step

1. User asks the AI to fill a form on Site B.
2. AI calls `discover_form(url)` — learns what Site B needs (schema + instructions).
3. AI calls `vault_list()` — sees metadata for all saved entries.
4. AI compares Site B's required fields against vault entry `data_summary` values. If multiple entries are relevant, the AI presents them to the user and lets them pick.
5. User selects which entry (or entries) to reuse.
6. AI calls `vault_load(ids)` — retrieves the full raw data from the chosen entries.
7. AI maps the vault data onto Site B's fields. Fields that match are pre-filled; fields unique to Site B are collected from the user conversationally.
8. AI submits the form via `submit_draft` / `submit_final`.
9. AI asks the user if they want to save this submission. If yes, calls `vault_save()` to store the combined data (reused + new) as a new vault entry.

## 3. Storage Layout

```
~/.form-filling-assistant/
├── index.json                                              # metadata index
└── dumps/
    ├── 2026-02-15T18-30-00_masters-application-a1b2.json   # raw data dump
    ├── 2026-02-15T19-00-00_patient-intake-c3d4.json
    └── 2026-02-20T10-15-00_research-ms-westbrook-e5f6.json
```

Default location: `~/.form-filling-assistant/`. Override via the `FORM_FILLING_VAULT_DIR` environment variable (used by integration tests for temp directory isolation).

### ID Format

```
<ISO-timestamp>_<slugified-description>-<4-char-uuid>
```

Example: `2026-02-15T18-30-00_masters-application-to-northfield-university-a1b2`

- Timestamp: ISO 8601 with colons/dots replaced by hyphens, truncated to seconds
- Slug: first 50 chars of the description, lowercased, non-alphanumeric replaced with hyphens
- UUID suffix: 4 characters from `crypto.randomUUID()` to prevent same-second collisions

### index.json

```json
{
  "version": "1.0",
  "entries": [
    {
      "id": "2026-02-15T18-30-00_masters-application-to-northfield-a1b2",
      "file": "dumps/2026-02-15T18-30-00_masters-application-to-northfield-a1b2.json",
      "created_at": "2026-02-15T18:30:00.000Z",
      "source_url": "http://localhost:3001",
      "form_id": "form_abc123",
      "status": "submitted",
      "description": "Masters CS application to Northfield University for Jane Smith, Fall 2026",
      "data_summary": ["personal info", "education", "work experience", "test scores"]
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (also the dump filename without `.json`) |
| `file` | string | Relative path to the dump file |
| `created_at` | string | ISO 8601 timestamp |
| `source_url` | string | Base URL of the website this data was submitted to |
| `form_id` | string | Form ID returned by the website's discover endpoint |
| `status` | `"draft"` or `"submitted"` | Whether the form was fully submitted or saved as draft |
| `description` | string | AI-written natural-language description of the submission |
| `data_summary` | string[] | AI-written list of data categories (e.g., `["personal info", "education"]`) |

### Dump Files

Each dump file contains the raw form data object exactly as submitted — keyed by section:

```json
{
  "personal": {
    "full_name": "Jane Smith",
    "dob": "1995-06-15",
    "email": "jane@example.com",
    "phone": "+15559876543",
    "mailing_address": "456 Oak Ave, Springfield, IL 62704"
  },
  "education": {
    "degrees": [
      {
        "institution": "State University",
        "degree_type": "bachelor",
        "field_of_study": "Computer Science",
        "gpa": 3.85,
        "start_date": "2013-08",
        "end_date": "2017-05"
      }
    ]
  },
  "work_experience": {
    "has_work_experience": true,
    "jobs": [
      {
        "employer": "Tech Corp",
        "title": "Software Engineer",
        "start_date": "2017-06",
        "end_date": "2024-12",
        "description": "Full-stack development and ML infrastructure"
      }
    ]
  }
}
```

## 4. Vault MCP Tools

### Summary

| Tool | Status | Purpose | When Used |
|---|---|---|---|
| `vault_list` | Implemented | List saved entries (metadata only) | After `discover_form`, to find reusable data |
| `vault_load` | Implemented | Load full dump data by ID | After user picks which entries to reuse |
| `vault_save` | Implemented | Save form data as new vault entry | After submission, if user wants to save |
| `vault_delete` | Implemented | Delete entries from vault | Vault cleanup |
| `vault_merge` | Implemented | Merge entries from same site into one | Combine partial drafts or successive submissions |
| `vault_set_profile` | Implemented | Build, activate, or clear a unified profile | Auto-fill from cross-site synthesized data |

### 4.1 `vault_list`

List all entries in the vault. Returns metadata only — not the dump data itself.

**Parameters:** none

**Returns:**
```json
{
  "entries": [
    {
      "id": "2026-02-15T18-30-00_masters-application-a1b2",
      "description": "Masters CS application to Northfield University for Jane Smith",
      "data_summary": ["personal info", "education", "work experience"],
      "created_at": "2026-02-15T18:30:00.000Z",
      "status": "submitted",
      "source_url": "http://localhost:3001",
      "is_merged": false,
      "is_profile": false
    }
  ],
  "active_profile": {
    "id": "2026-02-20T10-00-00_unified-profile-a1b2",
    "description": "Unified profile for Jane Smith",
    "data_summary": ["personal", "education", "work experience"]
  }
}
```

### 4.2 `vault_load`

Load one or more dump files by their IDs. Returns the full raw data for each entry.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `ids` | string[] | yes | Vault entry IDs to load |

**Returns:**
```json
{
  "dumps": [
    {
      "id": "2026-02-15T18-30-00_masters-application-a1b2",
      "description": "Masters CS application to Northfield University for Jane Smith",
      "data": {
        "personal": { ... },
        "education": { ... },
        "work_experience": { ... }
      }
    }
  ]
}
```

### 4.3 `vault_save`

Save form data as a new vault entry. The AI writes the `description` and `data_summary` in natural language.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `description` | string | yes | AI-written description of the submission |
| `data_summary` | string[] | yes | List of data categories present |
| `source_url` | string | yes | Website URL where the form was submitted |
| `form_id` | string | yes | Form ID from `discover_form` |
| `status` | string | yes | `"draft"` or `"submitted"` |
| `data` | object | yes | The raw form data to save |

**Returns:**
```json
{
  "id": "2026-02-15T18-30-00_masters-application-a1b2",
  "file": "dumps/2026-02-15T18-30-00_masters-application-a1b2.json",
  "message": "Form data saved to vault successfully."
}
```

### 4.4 `vault_delete`

Delete one or more entries from the vault.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `ids` | string[] | yes | Vault entry IDs to delete |

**Returns:**
```json
{
  "deleted": ["2026-02-15T18-30-00_masters-application-a1b2"],
  "not_found": []
}
```

### 4.5 `vault_merge`

Merge multiple vault entries from the same website into a single consolidated entry. All entries must share the same `source_url`. Later entries override earlier ones on field conflicts (deep merge).

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `ids` | string[] | yes | At least 2 vault entry IDs to merge (order matters — later overrides earlier) |
| `description` | string | yes | Description for the merged entry |

**Returns:**
```json
{
  "id": "2026-02-20T10-00-00_merged-application-c3d4",
  "file": "dumps/2026-02-20T10-00-00_merged-application-c3d4.json",
  "merged_from": ["id-1", "id-2"],
  "message": "Merged 2 entries into a new vault entry."
}
```

### 4.6 `vault_set_profile`

Build, activate, or clear the active vault profile. A profile is a **unified personal data record** synthesized by the AI from multiple vault entries across different websites. When active, the AI uses profile data to pre-fill new forms without the list/pick step.

Unlike `vault_merge` (which consolidates entries from the **same** website), profiles combine data across **different** websites — merging name, email, education, work history, etc. into a single canonical record.

**Three modes:**

| Mode | Input | Behavior |
|------|-------|----------|
| BUILD | `source_ids` + `data` + `description` | Save synthesized profile, set as active |
| ACTIVATE | `id` only | Set an existing profile entry as active |
| CLEAR | no args | Deactivate the current profile |

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `id` | string | no | ACTIVATE: vault entry ID to set as active. Ignored in BUILD mode. |
| `source_ids` | string[] | no | BUILD: vault entry IDs used to synthesize this profile (provenance) |
| `data` | object | no | BUILD: the synthesized profile data (normalized categories) |
| `description` | string | no | BUILD: natural-language description of the profile |

**Returns (BUILD):**
```json
{
  "id": "2026-02-20T10-00-00_unified-profile-for-jane-smith-a1b2",
  "file": "dumps/2026-02-20T10-00-00_unified-profile-for-jane-smith-a1b2.json",
  "source_ids": ["entry-from-site-a", "entry-from-site-b"],
  "active": true,
  "message": "Profile created and set as active."
}
```

**Returns (ACTIVATE):**
```json
{
  "id": "2026-02-20T10-00-00_unified-profile-for-jane-smith-a1b2",
  "active": true,
  "message": "Profile ... is now active."
}
```

**Returns (CLEAR):**
```json
{
  "active": false,
  "previous_id": "2026-02-20T10-00-00_unified-profile-for-jane-smith-a1b2",
  "message": "Active profile cleared."
}
```

**Profile building flow:**
1. AI calls `vault_list()` → sees entries from multiple sites
2. AI calls `vault_load([ids])` → retrieves raw data from each
3. AI synthesizes a unified profile in conversation (merges, resolves conflicts, normalizes)
4. AI calls `vault_set_profile({ source_ids, data, description })` → stored and activated
5. On next form fill, `vault_list()` response includes `active_profile` → AI loads and pre-fills

**Storage:** Profile entries are regular vault entries with `is_profile: true`, `source_url: "profile"`, `form_id: "profile"`. Deleting the active profile entry auto-clears it.

## 5. Cross-Site Reuse Example

This example walks through the E2E flow using the two mock servers in this POC.

### The Scenario

| | Program A (Northfield) | Program B (Westbrook) |
|---|---|---|
| **Program** | MS in Computer Science | Research MS in Artificial Intelligence |
| **Port** | 3001 | 3003 |
| **Sections** | personal, education, work_experience, program, test_scores, documents, references, additional | personal, education, work_experience, research, technical |
| **Overlap** | personal, education, work_experience | personal, education, work_experience |
| **Unique** | program, test_scores, documents, references, additional | research, technical |

### Step-by-Step

**Phase 1 — Complete Program A:**

```
AI: discover_form("http://localhost:3001")
    → Gets 8-section schema for Northfield CS Masters

AI: [collects all data from user conversationally]

AI: submit_draft(session_id, { personal, education, work_experience, program, ... })
    → Gets draft preview, user confirms

AI: submit_final(session_id)
    → Submission confirmed

AI: "Want me to save this for future applications?"
User: "Yes"

AI: vault_save({
      description: "Masters CS application to Northfield University for Jane Smith, Fall 2026",
      data_summary: ["personal info", "education", "work experience", "program selection", "funding"],
      source_url: "http://localhost:3001",
      form_id: "form_abc123",
      status: "submitted",
      data: { personal: {...}, education: {...}, work_experience: {...}, ... }
    })
    → Saved as 2026-02-15T18-30-00_masters-cs-application-to-northfield-a1b2
```

**Phase 2 — Start Program B, reuse from vault:**

```
User: "Now fill out the Westbrook AI masters application"

AI: discover_form("http://localhost:3003")
    → Gets 5-section schema: personal, education, work_experience, research, technical
    → Instructions note: "If the applicant has existing saved data, suggest reusing personal info and education."

AI: vault_list()
    → entries: [{
        id: "..._masters-cs-application-to-northfield-a1b2",
        description: "Masters CS application to Northfield...",
        data_summary: ["personal info", "education", "work experience", ...]
      }]

AI: "I found your Northfield application from earlier. It has your personal info,
     education, and work experience. Want me to reuse that data?"
User: "Yes"

AI: vault_load(["..._masters-cs-application-to-northfield-a1b2"])
    → Gets full data: { personal, education, work_experience, ... }

AI: [maps personal, education, work_experience onto Program B fields]
AI: [asks user for research + technical sections — these are new]

AI: submit_draft(session_id, {
      personal: <from vault>,
      education: <from vault>,
      work_experience: <from vault>,
      research: <new from user>,
      technical: <new from user>
    })
    → 100% complete, no warnings

AI: submit_final(session_id) → confirmed

AI: vault_save({
      description: "Research MS in AI application to Westbrook Institute for Jane Smith",
      data_summary: ["personal info", "education", "work experience", "research experience", "technical skills"],
      source_url: "http://localhost:3003",
      form_id: "form_xyz789",
      status: "submitted",
      data: { personal, education, work_experience, research, technical }
    })
```

After both phases, the vault contains 2 entries from different sites. A third application could reuse data from either or both.

## 6. Testing

### Vault Unit Tests — `vault.test.ts` (18 tests)

Tests the vault MCP tools in isolation using a temporary directory (`FORM_FILLING_VAULT_DIR` env var).

Coverage:
- Empty vault list returns no entries
- Save + list round-trip (submitted and draft status)
- Metadata completeness (description, data_summary, source_url, form_id, status, created_at)
- Load single and multiple entries by ID
- Load non-existent ID returns error
- Same-second saves produce distinct IDs (UUID suffix collision prevention)
- Delete single and multiple entries, delete non-existent ID
- Merge entries from same source_url with deep merge (later overrides earlier)
- Merge rejects entries from different source_urls
- Profile BUILD: create profile from synthesized data, verify active
- Profile ACTIVATE/CLEAR: re-activate existing profile, clear profile
- Deleting active profile auto-clears active_profile_id
- Profile appears in vault_list with is_profile flag and active_profile metadata
- Cross-site scenario: save from site A, save from site B, list shows both, load each independently

### Cross-Site E2E Tests — `vault-cross-site.test.ts` (10 tests)

Full end-to-end scenario running both mock servers (Program A on port 4006, Program B on port 4007) and an MCP client.

Steps tested:
1. Discover Program A → submit draft with personal + education + work data → vault_save
2. Discover Program B → verify 5 sections including research and technical
3. vault_list → finds the Program A entry with matching data_summary
4. vault_load → retrieves reusable personal, education, work_experience data
5. Submit draft to Program B with reused + new data → 100% complete
6. vault_save Program B submission
7. vault_list shows 2 entries from different source URLs
8. vault_load Program B entry → contains both reused and new data

### Program B Server Tests — `mock-masters-b.test.ts` (9 tests)

Tests the Westbrook Institute mock server endpoints:
- Discover returns 5 sections with research and technical fields
- Instructions mention research-focused program
- Validation rules (email format, publications count range, multi-select programming languages)
- Submit draft with partial data returns correct completeness
- Submit final rejects incomplete submissions

## 7. Implementation Files

```
packages/mcp-server/src/
├── vault/
│   └── vault-manager.ts              # initVault, listEntries, loadDumps, saveDump, deleteDumps, mergeDumps, saveProfile, setActiveProfileId, getActiveProfileId
└── tools/
    ├── vault-list.ts                 # vault_list tool
    ├── vault-load.ts                 # vault_load tool
    ├── vault-save.ts                 # vault_save tool
    ├── vault-delete.ts               # vault_delete tool
    ├── vault-merge.ts                # vault_merge tool
    └── vault-set-profile.ts          # vault_set_profile tool (BUILD/ACTIVATE/CLEAR)

packages/mock-masters-b/
├── src/
│   ├── index.ts                      # Express server (port 3003)
│   ├── store.ts                      # in-memory session/draft storage
│   ├── middleware/auth.ts            # bearer token auth
│   ├── routes/                       # discover, validate, upload-file, submit-draft, submit-final
│   └── data/
│       ├── schema.ts                 # 5 sections: personal, education, work, research, technical
│       ├── instructions.ts           # research-focused guidance, suggests reusing saved data
│       └── validation-rules.ts       # field validation (no GRE/TOEFL, simpler than Program A)
└── package.json

packages/integration-tests/src/
├── vault.test.ts                     # 18 vault unit tests
├── vault-cross-site.test.ts          # 10 E2E cross-site tests
└── mock-masters-b.test.ts            # 9 Program B server tests
```

## 8. Related Documents

- **Doc 1: Architecture — Claude Chat UX** — System components and end-to-end flow for the Claude Chat interface
- **Doc 3: MCP Tool Server Spec** — Core form-filling tools (discover, validate, submit)
- **Doc 4: Scenario — Master's Application** — Program A (Northfield) schema and instructions
