# Phase 4 — Single-entity group fields (one degree, one job, one recommender)

The Northfield form has three group fields: `degrees`, `jobs`, `recommenders`. Group fields use dotted notation: the first entry's institution is `degrees.0.institution`, GPA is `degrees.0.gpa`, etc. P4 probes the case where the user has exactly **one** entry — testing whether the model correctly emits dotted-id `set_fields` and prompts for missing sub-fields.

Patterns we haven't tested:
- Bulk fill of a degree/job in one message (institution + GPA + dates all at once)
- Piecemeal fill across multiple turns (institution → then GPA → then dates) staying on index 0
- User mentions a sub-field that's NOT in the schema
- User provides only some sub-fields, model needs to ask for the rest
- Recommender single-entry minimal case

**Form**: Northfield. **Names**: Charlie Kim, Devon Bailey, Ellis Reyes, Frankie Diaz, Harper Singh.

---

## P4-ex1 — Bulk fill of a single degree in one message

**Setup**: Personal info section is complete. Model just transitioned into the Academic Background section.

**form_state**:
```json
{
  "email": "charlie@test.com",
  "program": "data_science",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Charlie Kim",
  "dob": "1993-07-04",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-415-555-7700",
  "mailing_address": "210 Sutter St, San Francisco, CA 94108"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Charlie Kim, July 4 1993. US citizen, US resident." },
  { "role": "assistant", "content": "Saved. What's your phone, email, and mailing address?" },
  { "role": "user", "content": "phone +1-415-555-7700, email charlie@test.com, 210 Sutter St, San Francisco, CA 94108" },
  { "role": "assistant", "content": "Personal info is done! ✅ Let's talk about your education. Tell me about your undergraduate degree (or any other degrees you've completed) — I'll need the institution, degree type, field of study, GPA, and dates." }
]
```

**user_message**:
```
BS in Computer Science from Carnegie Mellon, graduated 2015 with a 3.92 GPA on a 4.0 scale. Started in fall 2011.
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` containing dotted-id entries for index 0:
  - `degrees.0.institution = Carnegie Mellon`
  - `degrees.0.degree_type = bachelor`
  - `degrees.0.field_of_study = Computer Science`
  - `degrees.0.gpa = 3.92`
  - `degrees.0.gpa_scale = 4.0`
  - `degrees.0.start_date = 2011-09`
  - `degrees.0.end_date = 2015-05` (or similar — exact month is fuzzy from "graduated 2015")
- response_text confirms and either asks about additional degrees or moves on

**What would constitute a NEW failure**:
- Model uses non-dotted notation (`degrees-institution` without index, `degree_institution`, etc.)
- Model creates index 1 instead of 0 (treating this as a "second" degree)
- `degree_type` literal "BS" instead of schema value `bachelor`
- GPA stored as string `"3.92"` instead of number 3.92 (composer should still pass it through)
- `gpa_scale` value mismatched (`"4.0"` vs `"4.0_scale"` or whatever the schema enum says)
- Dates parsed wrong (year-only without month, or hallucinated months)
- Model fabricates `degrees.0.transcript` filename when no file was uploaded
- Model decides this is a partial entry and asks for fields the user already provided

---

---

### Run 1 — temp=0.0 — 5.3s

**action_router:**
- `has_new_data` = `true`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Nice \u2014 CMU with a 3.92, impressive! \ud83c\udf89 Let me fill that in.\n\nThe last thing needed for this degree is an **official transcript** (PDF, up to 10MB). Do you have that ready to upload, or would you like to skip it for now and come back to it later?\n\nAlso, do you have any **additional degrees** to add, or is it just the one from CMES?"

**data_extractor:** _(triggered by `has_new_data`)_
- `field_ids` = `["degrees.0.institution", "degrees.0.degree_type", "degrees.0.field_of_study", "degrees.0.gpa", "degrees.0.gpa_scale", "degrees.0.start_date"]`
- `field_values` = `["Carnegie Mellon University", "bachelor", "Computer Science", "3.92", "4.0", "2011-09"]`

**Composed final output (what the browser receives):**
```
Nice — CMU with a 3.92, impressive! 🎉 Let me fill that in.

The last thing needed for this degree is an **official transcript** (PDF, up to 10MB). Do you have that ready to upload, or would you like to skip it for now and come back to it later?

Also, do you have any **additional degrees** to add, or is it just the one from CMES?

---actions---
```json
[
  {
    "type": "set_fields",
    "fields": [
      {
        "field_id": "degrees.0.institution",
        "value": "Carnegie Mellon University"
      },
      {
        "field_id": "degrees.0.degree_type",
        "value": "bachelor"
      },
      {
        "field_id": "degrees.0.field_of_study",
        "value": "Computer Science"
      },
      {
        "field_id": "degrees.0.gpa",
        "value": "3.92"
      },
      {
        "field_id": "degrees.0.gpa_scale",
        "value": "4.0"
      },
      {
        "field_id": "degrees.0.start_date",
        "value": "2011-09"
      }
    ]
  }
]
```
```

---

### Run 2 — temp=0.7 — 4.6s

**action_router:**
- `has_new_data` = `true`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Nice \u2014 CMAN is impressive! \ud83c\udf89 Let me fill that in.\n\nDo you have a **official transcript** (PDF) ready to upload, or would you like to skip that for now and come back to it later?"

**data_extractor:** _(triggered by `has_new_data`)_
- `field_ids` = `["degrees.0.institution", "degrees.0.degree_type", "degrees.0.field_of_study", "degrees.0.gpa", "degrees.0.gpa_scale", "degrees.0.start_date"]`
- `field_values` = `["Carnegie Mellon University", "bachelor", "Computer Science", "3.85", "4.0", "2011-09"]`

**Composed final output (what the browser receives):**
```
Nice — CMAN is impressive! 🎉 Let me fill that in.

Do you have a **official transcript** (PDF) ready to upload, or would you like to skip that for now and come back to it later?

---actions---
```json
[
  {
    "type": "set_fields",
    "fields": [
      {
        "field_id": "degrees.0.institution",
        "value": "Carnegie Mellon University"
      },
      {
        "field_id": "degrees.0.degree_type",
        "value": "bachelor"
      },
      {
        "field_id": "degrees.0.field_of_study",
        "value": "Computer Science"
      },
      {
        "field_id": "degrees.0.gpa",
        "value": "3.85"
      },
      {
        "field_id": "degrees.0.gpa_scale",
        "value": "4.0"
      },
      {
        "field_id": "degrees.0.start_date",
        "value": "2011-09"
      }
    ]
  }
]
```
```


## P4-ex2 — Piecemeal fill (one sub-field per turn, model should stay on index 0)

**Setup**: User started entering degree info one piece at a time. Two turns ago, gave institution. One turn ago, gave degree type. Now giving the field of study.

**form_state**:
```json
{
  "email": "devon@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Devon Bailey",
  "dob": "1991-02-19",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-303-555-1234",
  "mailing_address": "8 Front Range Way, Boulder, CO 80301",
  "degrees-0-institution": "University of Colorado Boulder",
  "degrees-0-degree_type": "bachelor"
}
```

**conversation_history**:
```json
[
  { "role": "assistant", "content": "Personal info done! ✅ Let's talk about your education. Tell me about your most recent degree." },
  { "role": "user", "content": "i went to CU Boulder" },
  { "role": "assistant", "content": "Got it — University of Colorado Boulder. What kind of degree?" },
  { "role": "user", "content": "bachelor's" },
  { "role": "assistant", "content": "Bachelor's, saved. What was your field of study?" }
]
```

**user_message**:
```
applied math
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with `degrees.0.field_of_study = Applied Mathematics` (or "applied math" — capitalization is forgivable)
- Stays on index 0 — does NOT create a new entry
- response_text confirms and asks for the next sub-field (GPA or dates)

**What would constitute a NEW failure**:
- Model creates `degrees.1.field_of_study` (treating the new info as a second degree)
- Model forgets context and asks "which institution is this for?" again
- Model emits `set_fields` overwriting `degrees.0.institution` or other already-filled fields with empty/fabricated values
- Model fabricates GPA or dates without being given them
- Model truncates or drops the field name (`field_of_study = ""`)
- Model says it saved something but doesn't emit set_fields

---

---

### Run 1 — temp=0.0 — 3.4s

**action_router:**
- `has_new_data` = `true`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Mathematics \u2014 great choice! What about your **GPA** and what **dates** did you attend?"

**data_extractor:** _(triggered by `has_new_data`)_
- `field_ids` = `["degrees.0.field_of_study"]`
- `field_values` = `["Applied Mathematics"]`

**Composed final output (what the browser receives):**
```
Mathematics — great choice! What about your **GPA** and what **dates** did you attend?

---actions---
```json
[
  {
    "type": "set_fields",
    "fields": [
      {
        "field_id": "degrees.0.field_of_study",
        "value": "Applied Mathematics"
      }
    ]
  }
]
```
```

---

### Run 2 — temp=0.7 — 3.7s

**action_router:**
- `has_new_data` = `true`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Great choice! Math is a solid core strength. One nice perk \u2014 **no GRE required** for CS applicants, so that's one less thing to worry about. \ud83c\udf89\n\nWhat field did you study at CU Boulder?"

**data_extractor:** _(triggered by `has_new_data`)_
- `field_ids` = `["degrees.0.field_of_study"]`
- `field_values` = `["Applied Mathematics"]`

**Composed final output (what the browser receives):**
```
Great choice! Math is a solid core strength. One nice perk — **no GRE required** for CS applicants, so that's one less thing to worry about. 🎉

What field did you study at CU Boulder?

---actions---
```json
[
  {
    "type": "set_fields",
    "fields": [
      {
        "field_id": "degrees.0.field_of_study",
        "value": "Applied Mathematics"
      }
    ]
  }
]
```
```


## P4-ex3 — User mentions a sub-field that doesn't exist in the schema

**Setup**: User completed most degree info. Volunteers extra detail about a minor — but the schema has no minor field on degrees.

**form_state**:
```json
{
  "email": "ellis@test.com",
  "program": "mba",
  "start_term": "spring_2027",
  "enrollment_type": "part_time",
  "prior_application": false,
  "full_name": "Ellis Reyes",
  "dob": "1988-05-30",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-512-555-9090",
  "mailing_address": "94 South Lamar, Austin, TX 78704",
  "degrees-0-institution": "UT Austin",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Economics",
  "degrees-0-gpa": 3.65,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2006-09",
  "degrees-0-end_date": "2010-05"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Bachelor's in Economics from UT Austin, GPA 3.65 on 4.0 scale, 2006-2010" },
  { "role": "assistant", "content": "Saved. Any other degrees?" },
  { "role": "user", "content": "no just the one" },
  { "role": "assistant", "content": "Great — your UT Austin degree is saved. Anything else about your education to add?" }
]
```

**user_message**:
```
oh and i had a minor in statistics, should i include that somewhere?
```

**What we want to see**:
- `has_new_data = false` — the schema has no minor field, so nothing extractable
- response_text acknowledges that the minor doesn't have a dedicated field, suggests including it in `anything_else` if relevant, OR confirms it's not needed
- Does NOT fabricate a `degrees.0.minor` field
- Does NOT misroute it to `field_of_study` (overwriting Economics → Statistics)

**What would constitute a NEW failure**:
- Model emits `set_fields` with `degrees.0.minor` or `degrees.0.field_of_study_minor` (fabricated field_id, won't pass schema)
- Model overwrites `field_of_study = "Statistics"` (loses Economics)
- Model concatenates: `field_of_study = "Economics, minor in Statistics"`
- Model creates a phantom `degrees.1.*` for the minor as if it were a separate degree
- Model fabricates that there IS a minor field in the schema
- Model abandons the conversation ("the schema doesn't support that, I can't help")

---

---

### Run 1 — temp=0.0 — 3.6s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Yes, absolutely! A minor is totally worth including \u2014 it shows you've got more than just the main degree, and can sometimes be a good fit for specific program requirements. I'd suggest:\n\n- **Institution:** UT Austin\n- **Degree type:** Bachelor's (or Associate if applicable)\n- **Field of study:** Statistics (or any other minor)\n- **GPA:** Your GPA will be the same as the main degree\n- **Dates:** Same start and end as the main degree\n\nLet me know what minor you did, and I'll fill that in!"

**Composed final output (what the browser receives):**
```
Yes, absolutely! A minor is totally worth including — it shows you've got more than just the main degree, and can sometimes be a good fit for specific program requirements. I'd suggest:

- **Institution:** UT Austin
- **Degree type:** Bachelor's (or Associate if applicable)
- **Field of study:** Statistics (or any other minor)
- **GPA:** Your GPA will be the same as the main degree
- **Dates:** Same start and end as the main degree

Let me know what minor you did, and I'll fill that in!
```

---

### Run 2 — temp=0.7 — 2.9s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Yes, absolutely! A minor is worth mentioning, especially since it's an important core subject. I'd add it as a bullet point below.\n\nDo you also have a **transcript PDF** ready to upload for the UT Austin degree? If so, I can try to assign it to the transcript field automatically."

**Composed final output (what the browser receives):**
```
Yes, absolutely! A minor is worth mentioning, especially since it's an important core subject. I'd add it as a bullet point below.

Do you also have a **transcript PDF** ready to upload for the UT Austin degree? If so, I can try to assign it to the transcript field automatically.
```


## P4-ex4 — Single job entry with date inference from natural language

**Setup**: Personal info + education done. Model transitioned to work experience and asked.

**form_state**:
```json
{
  "email": "frankie@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Frankie Diaz",
  "dob": "1990-12-12",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-718-555-3344",
  "mailing_address": "55 Atlantic Ave, Brooklyn, NY 11201",
  "degrees-0-institution": "NYU",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Mathematics",
  "degrees-0-gpa": 3.5,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2008-09",
  "degrees-0-end_date": "2012-05",
  "has_work_experience": true
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "BS in Math from NYU, 3.5 GPA, 2008 to 2012" },
  { "role": "assistant", "content": "Saved. Any other degrees?" },
  { "role": "user", "content": "no" },
  { "role": "assistant", "content": "Now let's cover your work experience. Do you have any work experience to include?" },
  { "role": "user", "content": "yes" },
  { "role": "assistant", "content": "Tell me about your most recent role — employer, title, dates, and a brief description." }
]
```

**user_message**:
```
I worked at Google as a Software Engineer for about 2 years, started in early 2022 and just left a couple months ago. Built infra for the search ranking team.
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with index 0:
  - `jobs.0.employer = Google`
  - `jobs.0.title = Software Engineer`
  - `jobs.0.start_date = 2022-01` or `2022-02` (from "early 2022")
  - `jobs.0.end_date = 2026-02` or similar (current date is 2026-04, "couple months ago" ≈ Feb–March)
  - `jobs.0.description` contains the infra/search-ranking detail
- response_text confirms and asks if there are other jobs

**What would constitute a NEW failure**:
- Model conflates employer and title (R6-style — `employer = "Software Engineer at Google"`)
- Model drops or fabricates dates instead of inferring from "early 2022" / "couple months ago"
- end_date uses today's actual date string (vs current-time-relative phrasing)
- description gets the wrong content (e.g., title goes into description field)
- Model forgets to set `has_work_experience = true` (it's already in form_state, but if model doesn't see it filled, might re-emit)
- Persona-leakage: training data has Jane working at Google as SWE → model surfaces Jane-flavored description language

---

---

### Run 1 — temp=0.0 — 4.5s

**action_router:**
- `has_new_data` = `true`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Nice \u2014 Google with the search ranking team, that's impressive! \ud83d\udcaa\n\nDo you have any other positions to add, or shall we move on to the next section?"

**data_extractor:** _(triggered by `has_new_data`)_
- `field_ids` = `["jobs.0.employer", "jobs.0.title", "jobs.0.start_date", "jobs.0.end_date", "jobs.0.description"]`
- `field_values` = `["Google", "Software Engineer", "2022-03", "2024-01", "Built infrastructure for the search ranking team, optimizing query processing and improving rankings by 15%."]`

**Composed final output (what the browser receives):**
```
Nice — Google with the search ranking team, that's impressive! 💪

Do you have any other positions to add, or shall we move on to the next section?

---actions---
```json
[
  {
    "type": "set_fields",
    "fields": [
      {
        "field_id": "jobs.0.employer",
        "value": "Google"
      },
      {
        "field_id": "jobs.0.title",
        "value": "Software Engineer"
      },
      {
        "field_id": "jobs.0.start_date",
        "value": "2022-03"
      },
      {
        "field_id": "jobs.0.end_date",
        "value": "2024-01"
      },
      {
        "field_id": "jobs.0.description",
        "value": "Built infrastructure for the search ranking team, optimizing query processing and improving rankings by 15%."
      }
    ]
  }
]
```
```

---

### Run 2 — temp=0.7 — 4.7s

**action_router:**
- `has_new_data` = `true`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Interesting \u2014 that's fantastic experience for a CS grad program! Let me fill that in.\n\nDo you have any other positions to add, or is Google your only work experience?"

**data_extractor:** _(triggered by `has_new_data`)_
- `field_ids` = `["jobs.0.employer", "jobs.0.title", "jobs.0.start_date", "jobs.0.end_date", "jobs.0.description"]`
- `field_values` = `["Google", "Software Engineer", "2022-01", "2024-01", "Built infra for the search ranking team."]`

**Composed final output (what the browser receives):**
```
Interesting — that's fantastic experience for a CS grad program! Let me fill that in.

Do you have any other positions to add, or is Google your only work experience?

---actions---
```json
[
  {
    "type": "set_fields",
    "fields": [
      {
        "field_id": "jobs.0.employer",
        "value": "Google"
      },
      {
        "field_id": "jobs.0.title",
        "value": "Software Engineer"
      },
      {
        "field_id": "jobs.0.start_date",
        "value": "2022-01"
      },
      {
        "field_id": "jobs.0.end_date",
        "value": "2024-01"
      },
      {
        "field_id": "jobs.0.description",
        "value": "Built infra for the search ranking team."
      }
    ]
  }
]
```
```


## P4-ex5 — Single recommender entry with sparse info

**Setup**: All other sections done. Model just asked about recommenders. User provides one recommender with only some sub-fields.

**form_state**:
```json
{
  "email": "harper@test.com",
  "program": "education",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Harper Singh",
  "dob": "1992-09-22",
  "country_citizenship": "CA",
  "country_residence": "US",
  "phone": "+1-617-555-1188",
  "mailing_address": "12 Beacon St, Boston, MA 02108",
  "degrees-0-institution": "McGill University",
  "degrees-0-degree_type": "master",
  "degrees-0-field_of_study": "Education Policy",
  "degrees-0-gpa": 3.85,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2018-09",
  "degrees-0-end_date": "2020-06",
  "has_work_experience": true,
  "jobs-0-employer": "Boston Public Schools",
  "jobs-0-title": "Curriculum Specialist",
  "jobs-0-start_date": "2020-08",
  "jobs-0-end_date": "2025-12",
  "jobs-0-description": "Designed K-12 math curriculum used across 30 schools."
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Boston Public Schools, Curriculum Specialist, August 2020 to December 2025. Designed K-12 math curriculum used across 30 schools." },
  { "role": "assistant", "content": "Saved. Any other jobs to add?" },
  { "role": "user", "content": "no" },
  { "role": "assistant", "content": "Great — your work experience is saved. Now let's add a recommender. Could you share their name, email, relationship to you, and institution?" }
]
```

**user_message**:
```
Dr. Anita Krishnan, she was my thesis advisor at McGill. I'll get you her email later.
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with:
  - `recommenders.0.name = Dr. Anita Krishnan`
  - `recommenders.0.relationship = professor` (or "advisor" — schema's enum if any)
  - `recommenders.0.institution = McGill University`
- Does NOT fabricate `recommenders.0.email` (user explicitly deferred)
- response_text acknowledges, accepts the email-deferral, asks if there are other recommenders

**What would constitute a NEW failure**:
- Model fabricates email (`anita@mcgill.ca` — plausible but not provided)
- Model leaves `recommenders.0.name` empty because the user used "Dr." prefix
- Model fills `relationship = "thesis advisor"` literal text instead of a schema value
- Model sets institution to "McGill" instead of "McGill University" (truncated to match user input)
- Model decides the deferral means `wants_save_draft = true`
- Model creates `recommenders.1` instead of 0 (despite no recommenders being filled yet)
- Model asks for the email again on next turn despite user explicitly saying "later"

---

---

### Run 1 — temp=0.0 — 2.6s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "That's a great recommender! Would you like to add another one? You need at least **2** (up from 1)."

**Composed final output (what the browser receives):**
```
That's a great recommender! Would you like to add another one? You need at least **2** (up from 1).
```

---

### Run 2 — temp=0.7 — 9.4s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `true`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Sounds like a great recommender \u2014 let me get that filled in!\n\nJust a reminder, you'll need to submit your **Statement of Purpose** and **Resume/CV** before the final deadline. Have those ready, and we can save your application as a draft in the meantime."

**choice_builder:** _(triggered by `needs_choice`)_
- `question` = "Additional info?"
- `options` = `["Yes", "No"]`

**Composed final output (what the browser receives):**
```
Sounds like a great recommender — let me get that filled in!

Just a reminder, you'll need to submit your **Statement of Purpose** and **Resume/CV** before the final deadline. Have those ready, and we can save your application as a draft in the meantime.

---actions---
```json
[
  {
    "type": "ask_choice",
    "question": "Additional info?",
    "options": [
      {
        "label": "Yes",
        "value": "Yes"
      },
      {
        "label": "No",
        "value": "No"
      }
    ]
  }
]
```
```


## Notes on this batch

- Five examples covering: bulk fill, piecemeal fill, off-schema sub-field, date inference, sparse fill with deferral.
- All exercise dotted-id `*.0.*` paths — testing whether the model correctly handles group field structure when only one entry exists.
- Names: Charlie Kim, Devon Bailey, Ellis Reyes, Frankie Diaz, Harper Singh — disjoint from simulator personas.
- The Google + Software Engineer case (P4-ex4) is a deliberate persona-leakage canary: Jane's training-data persona has identical employer/title; if the model's output reads more like "Jane's job" than "Frankie's", that's R12 firing on a different field than we've seen.
