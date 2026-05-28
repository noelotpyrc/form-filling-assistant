# Phase 6 — Conditional fields

The schema has fields that should only be relevant under certain other-field conditions:

- `prior_application_year` — relevant only if `prior_application = true`
- TOEFL fields (`english_test_type`, `english_test_score`, `english_test_date`) — typically only required for non-US-citizen / non-native-English applicants
- `funding_type` — typically only relevant if `funding_interest = true`
- `gre_*` fields — only if `gre_taken = true`

The model has to decide both *whether to ask* and *whether to extract* under these conditions. Both directions can fail.

**Form**: Northfield. **Names**: Nico Russo, Onyx Walsh, Parker Sosa, Reese Holloway, Skylar Choi.

---

## P6-ex1 — User says yes to prior_application but doesn't include the year

**Setup**: Model is walking through program-section questions. Just asked about prior application.

**form_state**:
```json
{
  "email": "nico@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "[system] User selected option: \"Computer Science (MS)\"" },
  { "role": "assistant", "content": "Computer Science it is. When would you like to start?" },
  { "role": "user", "content": "[system] User selected option: \"Fall 2026\"" },
  { "role": "assistant", "content": "Fall 2026. Full-time or part-time?" },
  { "role": "user", "content": "[system] User selected option: \"Full-time\"" },
  { "role": "assistant", "content": "Have you previously applied to Northfield University?" }
]
```

**user_message**:
```
yes, i applied a few years back
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with `prior_application = true`
- response_text follows up asking specifically for the year (because year is now relevant)
- Does NOT fabricate a year value for `prior_application_year`

**What would constitute a NEW failure**:
- Model fabricates `prior_application_year = 2023` (or any specific year not given)
- Model misses the conditional and just moves to the next section without asking for year
- Model parses "a few years back" as a relative date and fills `prior_application_year = 2024` (or 2025-3 = 2022, etc) — hallucinated specific year
- Model emits `prior_application = false` (didn't recognize "yes")
- Model puts "yes" as a string into `prior_application` instead of boolean true

---

## P6-ex2 — User volunteers TOEFL info despite being a US citizen

**Setup**: User is US citizen and resident. Model is in the test scores section. User unprompted volunteers an English-test score.

**form_state**:
```json
{
  "email": "onyx@test.com",
  "program": "data_science",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Onyx Walsh",
  "dob": "1996-01-15",
  "country_citizenship": "US",
  "country_residence": "US"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Onyx Walsh, January 15 1996, US citizen and resident" },
  { "role": "assistant", "content": "Saved. What's your phone, email, and mailing address?" },
  { "role": "user", "content": "i'll do contact details later — let's keep moving" },
  { "role": "assistant", "content": "No problem, we can come back to those. Let's cover test scores. Did you take the GRE?" }
]
```

**user_message**:
```
no GRE. but i took the TOEFL last year and got 115 if that helps
```

**What we want to see** — this is genuinely ambiguous; both behaviors are defensible:
- Option A: Model accepts the data anyway (TOEFL fields have no hard-conditional gating in the schema, just norms): `gre_taken = false`, `english_test_type = TOEFL`, `english_test_score = 115`, `english_test_date = 2025-XX`. Response acknowledges and continues.
- Option B: Model declines to record TOEFL since it's not required for US citizens, just notes `gre_taken = false` and moves on.
- Either is reasonable. **What we don't want**: silent partial behavior or fabrication.

**What would constitute a NEW failure**:
- Model sets `english_test_score = 115` but `english_test_type` stays empty (partial fill)
- Model fabricates `english_test_date` to a specific date when user said only "last year"
- Model fabricates `toefl_required = true` even though citizenship is US
- Model becomes confused and asks if user is a US citizen (they already filled this)
- Model rejects the input outright ("you can't take TOEFL if you're a US citizen")
- Model stores TOEFL data into wrong field IDs (`gre_verbal = 115`)
- Model contradicts the form_state ("you said you're not a US citizen") — R11-style

---

## P6-ex3 — User changes citizenship from non-US to US, invalidating earlier TOEFL data

**Setup**: User originally said they were a Canadian citizen and provided TOEFL info. Now correcting their citizenship to US.

**form_state**:
```json
{
  "email": "parker@test.com",
  "program": "education",
  "start_term": "spring_2027",
  "enrollment_type": "part_time",
  "prior_application": false,
  "full_name": "Parker Sosa",
  "dob": "1988-04-25",
  "country_citizenship": "CA",
  "country_residence": "US",
  "phone": "+1-503-555-2200",
  "mailing_address": "1234 SE Hawthorne, Portland, OR 97214",
  "english_test_type": "TOEFL",
  "english_test_score": 108,
  "english_test_date": "2024-08-15"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "TOEFL — score 108, took it August 15 2024" },
  { "role": "assistant", "content": "Saved your TOEFL score. Let's continue." },
  { "role": "user", "content": "wait, i need to fix something" },
  { "role": "assistant", "content": "Sure — anything else to update?" }
]
```

**user_message**:
```
oh wait, i actually got my US citizenship last month — should be US not Canadian. i guess that means the TOEFL stuff isn't needed?
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with `country_citizenship = US` (overwriting CA)
- response_text acknowledges the citizenship update AND addresses the TOEFL question
- Reasonable behaviors: either confirm TOEFL info will be kept on file but isn't required, or offer to clear it
- Does NOT silently delete TOEFL fields without acknowledgment
- Does NOT contradict ("you're still Canadian according to the form")

**What would constitute a NEW failure**:
- Model overwrites both `country_citizenship` AND clears all TOEFL fields without confirming
- Model leaves citizenship CA despite explicit update (R10-style false negative on citizenship)
- Model fabricates a US passport number or SSN to "verify" the new citizenship
- Model congratulates the user on getting US citizenship in a way that's weirdly enthusiastic / unprofessional
- Model gets confused about which fields are conditional and asks redundant questions
- Model emits an action to clear TOEFL but in the wrong format (deletes the wrong fields)

---

## P6-ex4 — User volunteers funding_type without committing to funding_interest

**Setup**: User reached funding section. Volunteers types without saying yes/no first.

**form_state**:
```json
{
  "email": "reese@test.com",
  "program": "public_health",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Reese Holloway",
  "dob": "1995-11-30",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-415-555-1100",
  "mailing_address": "100 Larkin St, San Francisco, CA 94102",
  "degrees-0-institution": "UC Berkeley",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Molecular Biology",
  "degrees-0-gpa": 3.78,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2014-08",
  "degrees-0-end_date": "2018-05"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "no I don't have any work experience" },
  { "role": "assistant", "content": "Okay, that's noted. Now let's add a recommender." },
  { "role": "user", "content": "Dr. Aisha Patel, my undergrad PI at Berkeley, apatel@berkeley.edu" },
  { "role": "assistant", "content": "Saved Dr. Patel. Almost done. Are you interested in being considered for funding?" }
]
```

**user_message**:
```
i'd like to be considered for a research assistantship and possibly a fellowship if available
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with:
  - `funding_interest = true` (implied by "I'd like to be considered")
  - `funding_type = ["research_assistantship", "fellowship"]` (multi-select)
- response_text confirms and moves on

**What would constitute a NEW failure**:
- Model only sets `funding_type` without setting `funding_interest = true`
- `funding_type` parsed as a comma-separated string (`"research_assistantship,fellowship"`) instead of a list
- `funding_type` values mismatch the schema enum (`"research-assistantship"` vs `"research_assistantship"`)
- Model splits the request into two turns ("first, are you interested in funding?")
- Model only extracts one of the two types
- Model fabricates a third type (`teaching_assistantship`) that wasn't mentioned (R13-style)

---

## P6-ex5 — User answers a conditional question before satisfying the condition

**Setup**: User provides GRE scores even though they haven't been asked and haven't said they took the GRE.

**form_state**:
```json
{
  "email": "skylar@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Skylar Choi",
  "dob": "1993-09-12",
  "country_citizenship": "US",
  "country_residence": "US"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Skylar Choi, born September 12 1993, US citizen and resident" },
  { "role": "assistant", "content": "Saved. What's your phone, email, and mailing address?" },
  { "role": "user", "content": "skylar@test.com, +1-415-555-1100, 88 Marina Blvd, San Francisco, CA 94123" },
  { "role": "assistant", "content": "Now let's cover your test scores." }
]
```

**user_message**:
```
GRE: 165 verbal, 170 quant, 5.5 writing. took it in march 2024.
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with:
  - `gre_taken = true` (implied by providing scores)
  - `gre_verbal = 165`, `gre_quant = 170`, `gre_writing = 5.5`
  - `gre_date = 2024-03-XX`
- response_text confirms, moves on

**What would constitute a NEW failure**:
- Model extracts only some of the scores (e.g., verbal but not quant)
- Model fails to set `gre_taken = true` (the parent flag)
- Model puts scores into wrong fields (verbal value in quant field)
- Model doesn't recognize GRE writing score format ("5.5" instead of an integer)
- Model treats this as TOEFL/IELTS data and routes to wrong fields
- Model asks "did you take the GRE?" before recording (overcautious — the user clearly answered)

---

## Notes on this batch

- Five examples: yes-without-year, volunteer-conditional-data, citizenship-change-invalidates-conditional, funding-multiselect, conditional-before-trigger.
- These exercise schema relationships the SFT model has to learn implicitly. Where in the training data was the model exposed to "user says yes to prior_application, model asks for year" — was that pattern frequent enough?
- Conditional logic is unstated in the schema rendering — the model has to infer relationships. Wrong inferences here are subtle and easy to miss in eval.
- Names: Nico Russo, Onyx Walsh, Parker Sosa, Reese Holloway, Skylar Choi.
