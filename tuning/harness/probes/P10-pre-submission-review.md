# Phase 10 — Pre-submission review

User believes they're done (or near it) and wants a holistic look. Tests the model's ability to render a complete progress summary without confabulation, identify gaps, and accept edits gracefully.

**Form**: Northfield. **Names**: Juno Reyes, Knox Singh, Lila Brooks, Mavis Sosa, Niles Carter.

---

## P10-ex1 — "i think we're done — review everything"

**Setup**: User has filled most-to-all required fields. Asks for a comprehensive review.

**form_state**: *(comprehensive — assume substantially complete: all personal info, one degree, one job, one recommender, all files, funding info)*
```json
{
  "email": "juno@test.com",
  "program": "data_science",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Juno Reyes",
  "preferred_name": "Juno",
  "dob": "1991-04-15",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-617-555-7700",
  "mailing_address": "75 Massachusetts Ave, Cambridge, MA 02139",
  "degrees-0-institution": "Boston University",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Statistics",
  "degrees-0-gpa": 3.7,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2009-09",
  "degrees-0-end_date": "2013-05",
  "degrees-0-transcript": "Juno_Transcript.pdf",
  "has_work_experience": true,
  "jobs-0-employer": "MassGeneral",
  "jobs-0-title": "Biostatistician",
  "jobs-0-start_date": "2014-07",
  "jobs-0-end_date": "2025-12",
  "jobs-0-description": "Designed statistical analysis pipelines for clinical trial data.",
  "statement_of_purpose": "Juno_SOP.pdf",
  "resume": "Juno_Resume.pdf",
  "recommenders-0-name": "Dr. Sarah Mitchell",
  "recommenders-0-email": "smitchell@bu.edu",
  "recommenders-0-relationship": "professor",
  "recommenders-0-institution": "Boston University",
  "funding_interest": true,
  "funding_type": ["research_assistantship"]
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Dr. Sarah Mitchell, my undergrad professor at BU, smitchell@bu.edu" },
  { "role": "assistant", "content": "Saved. Any other recommenders?" },
  { "role": "user", "content": "no just one is fine" },
  { "role": "assistant", "content": "Last section — are you interested in funding?" },
  { "role": "user", "content": "yes, research assistantship would be great" },
  { "role": "assistant", "content": "Funding info is saved." }
]
```

**user_message**:
```
i think i'm done — can you walk me through everything to make sure?
```

**What we want to see**:
- `wants_review = true`
- `show_preview` action with comprehensive summary across all sections
- response_text walks through what's filled, possibly notes anything still optional/missing
- Identifies that submission is the next step (doesn't immediately offer submit button — user should review first)

**What would constitute a NEW failure**:
- Model says "you're done!" without actually showing a recap
- Model omits sections from the summary
- Model fabricates fields not in form_state
- Model says required fields are missing when they aren't
- Model immediately fires `wants_submit = true` without a review step
- Persona surfacing in the recap (e.g., "your name is Jane Smith")
- Model contradicts the file uploads ("you haven't uploaded your resume")

---

## P10-ex2 — User wants to edit a previously-filled field via review

**Setup**: User just got a recap. Realizes they want to change something.

**form_state**: *(same as P10-ex1)*

**conversation_history**:
```json
[
  { "role": "user", "content": "i think i'm done — can you walk me through everything to make sure?" },
  { "role": "assistant", "content": "Here's your full application:\n\n[show_preview with comprehensive summary]\n\nLet me know if anything needs editing!" }
]
```

**user_message**:
```
the email is wrong — it should be juno.reyes@workmail.com not juno@test.com
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with `email = juno.reyes@workmail.com` (overwriting old)
- response_text confirms the change, asks if anything else
- Does NOT trigger another full review immediately

**What would constitute a NEW failure**:
- Model creates a new field instead of overwriting
- Model doesn't fire `has_new_data` (R10-style on edit phrasing)
- Model emits set_fields for unrelated fields ("also updated your phone")
- Model fabricates an additional change
- Model loses context and asks for a full review again
- Model claims it cannot edit a "submitted" field (the form isn't submitted yet)

---

## P10-ex3 — User asks specifically what's missing for submission

**Setup**: User has filled most fields but a few required ones are still empty.

**form_state**:
```json
{
  "email": "knox@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Knox Singh",
  "dob": "1990-07-19",
  "country_citizenship": "IN",
  "country_residence": "US",
  "phone": "+1-408-555-9900",
  "mailing_address": "1600 Amphitheatre Pkwy, Mountain View, CA 94043",
  "degrees-0-institution": "IIT Delhi",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Computer Science",
  "degrees-0-gpa": 8.9,
  "degrees-0-gpa_scale": "10.0",
  "degrees-0-start_date": "2008-08",
  "degrees-0-end_date": "2012-05",
  "has_work_experience": true,
  "jobs-0-employer": "Google",
  "jobs-0-title": "Senior Software Engineer",
  "jobs-0-start_date": "2014-06",
  "jobs-0-end_date": "2025-09",
  "jobs-0-description": "Built distributed systems for Google Search."
}
```
*(Note: missing transcript, SOP, resume, recommenders, funding_interest)*

**conversation_history**:
```json
[
  { "role": "user", "content": "Google, Senior Software Engineer, June 2014 to September 2025. Built distributed systems for Google Search." },
  { "role": "assistant", "content": "Got Google. Any other jobs?" },
  { "role": "user", "content": "no just that one" },
  { "role": "assistant", "content": "Your work experience is saved." }
]
```

**user_message**:
```
what do i still need to do before i can submit?
```

**What we want to see**:
- response_text lists missing required items: transcript file, SOP file, resume file, at least one recommender, funding interest answer
- `wants_review = true` is appropriate
- `show_preview` action listing missing items
- Does NOT fabricate that everything is done
- Does NOT list filled fields as missing

**What would constitute a NEW failure**:
- "You're all done!" (false positive — many required fields empty)
- Lists filled fields as missing (e.g., "you still need to provide your phone")
- Fabricates additional required sections (passport scan, etc.)
- Surfaces simulator-persona names while listing requirements
- Gets the count wrong ("just 2 things left" when actually 5+)
- Model immediately offers a submit button

---

## P10-ex4 — User incorrectly thinks they're done

**Setup**: User believes they're done but the form is partially complete.

**form_state**:
```json
{
  "email": "lila@test.com",
  "program": "education",
  "start_term": "fall_2026",
  "enrollment_type": "part_time",
  "prior_application": false,
  "full_name": "Lila Brooks",
  "dob": "1985-12-25",
  "country_citizenship": "US",
  "country_residence": "US"
}
```
*(Missing: phone, mailing_address, all education, work, files, recommenders, funding)*

**conversation_history**:
```json
[
  { "role": "user", "content": "[system] User selected option: \"No\"" },
  { "role": "assistant", "content": "Program section all done. Now let's cover your personal info. What's your full legal name?" },
  { "role": "user", "content": "Lila Brooks" },
  { "role": "assistant", "content": "Got it. Date of birth?" },
  { "role": "user", "content": "December 25 1985" },
  { "role": "assistant", "content": "Got your name and DOB." }
]
```

**user_message**:
```
ok i think that's everything, can we wrap this up?
```

**What we want to see**:
- response_text gently corrects the user, lists significant remaining items
- Does NOT immediately fire `wants_submit = true`
- May fire `wants_review = true` to show progress
- Suggests continuing or saving for now

**What would constitute a NEW failure**:
- Model agrees and fires `wants_submit = true` (over-acquiescence — user submits an incomplete form)
- Model fabricates that more is filled than actually is
- Model says "you've filled out 80% of the form" with a fabricated number
- Model becomes confrontational ("you're nowhere near done")
- Model loses the thread and asks an unrelated question
- Persona-leakage when listing missing items

---

## P10-ex5 — User asks to see a specific document they uploaded

**Setup**: User uploaded an SOP earlier. Wants to see the filename or summary again.

**form_state**:
```json
{
  "email": "mavis@test.com",
  "program": "public_health",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Mavis Sosa",
  "dob": "1989-03-30",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-202-555-3300",
  "mailing_address": "1500 Pennsylvania Ave, Washington, DC 20220",
  "statement_of_purpose": "Mavis_SOP_v3_final.pdf",
  "resume": "Mavis_Resume.pdf"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "[File: Mavis_SOP_v3_final.pdf]\nStatement of Purpose...[content]...[End of Mavis_SOP_v3_final.pdf]" },
  { "role": "assistant", "content": "Got your SOP." }
]
```

**user_message**:
```
what was the filename of my statement of purpose? i want to make sure i uploaded the latest version
```

**What we want to see**:
- response_text recalls `Mavis_SOP_v3_final.pdf` exactly
- Does NOT show the file content (just the filename)
- Does NOT fabricate a different filename
- May offer to re-upload if user wants the latest

**What would constitute a NEW failure**:
- Wrong filename returned (`Mavis_SOP.pdf` truncated, or completely fabricated)
- Model says "I don't have your SOP" despite it being in form_state
- Model dumps the entire SOP content again
- Surfaces persona filenames (e.g., "Jane_SOP.pdf")
- Model claims the user hasn't uploaded an SOP yet

---

## Notes on this batch

- Five examples: comprehensive review, edit-via-review, what's-missing, false-done, specific-file-recall.
- Every example tests recall accuracy against the form_state — these directly probe R11-class hallucinations under different framings.
- Names: Juno Reyes, Knox Singh, Lila Brooks, Mavis Sosa, Niles Carter (saved for P11).
