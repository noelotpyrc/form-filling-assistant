# Phase 5 — Multi-entity group fields (multiple degrees, jobs, recommenders)

The biggest unprobed surface. The form's group fields can have multiple entries — `degrees.0`, `degrees.1`, `degrees.2` — but the SFT model has thin coverage for switching between indices, adding new entries to existing ones, and removing entries. P5 stresses these patterns.

**Form**: Northfield. **Names**: Indigo Tran, Jamie Thomas, Kai Nguyen, Lin Yamada, Marlowe O'Brien.

---

## P5-ex1 — Bulk dump of two degrees in one message

**Setup**: Personal info done. Model asked about education. User has BS and MS — provides both at once.

**form_state**:
```json
{
  "email": "indigo@test.com",
  "program": "data_science",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Indigo Tran",
  "dob": "1989-11-03",
  "country_citizenship": "VN",
  "country_residence": "US",
  "phone": "+1-408-555-2200",
  "mailing_address": "1 Hacker Way, Menlo Park, CA 94025"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Indigo Tran, born November 3 1989" },
  { "role": "assistant", "content": "Saved. Citizenship and residence?" },
  { "role": "user", "content": "Vietnamese citizen, US resident. phone +1-408-555-2200, email indigo@test.com, address 1 Hacker Way Menlo Park CA 94025" },
  { "role": "assistant", "content": "Great, personal info is done. Now let's cover your education. Tell me about any degrees you've completed." }
]
```

**user_message**:
```
I have two degrees — BS in EE from Hanoi University of Science and Technology, 2007 to 2011, GPA 9.2/10. Then MS in Computer Science from UCLA, 2013 to 2015, GPA 3.85/4.0.
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with TWO indexed entries:
  - `degrees.0.institution = Hanoi University of Science and Technology`, `degree_type = bachelor`, `field_of_study = Electrical Engineering`, `gpa = 9.2`, `gpa_scale = 10.0`, dates 2007-09 / 2011-05 (or similar)
  - `degrees.1.institution = UCLA`, `degree_type = master`, `field_of_study = Computer Science`, `gpa = 3.85`, `gpa_scale = 4.0`, dates 2013-09 / 2015-06
- response_text confirms both degrees, moves on
- `country_citizenship = VN` is preserved (not overwritten by anything in the user message)

**What would constitute a NEW failure**:
- Model only emits index 0, drops the second degree entirely
- Model emits both into index 0 (concatenated values like `"Hanoi/UCLA"`)
- Model creates `degrees.1` with the *first* degree's info and `degrees.0` with the second (reverse order)
- Model uses `gpa_scale` value not in schema enum (e.g., `"10"` instead of `"10.0"` — depends on schema)
- Model fabricates a third degree
- Model can't handle non-US institution name and uses "MIT" or similar fallback (R12-adjacent)
- Model sets `degree_type = "BS"` literal instead of schema value `bachelor`

---

## P5-ex2 — Adding a second job to an already-filled first job

**Setup**: One job is already saved. User wants to add an earlier role.

**form_state**:
```json
{
  "email": "jamie@test.com",
  "program": "mba",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Jamie Thomas",
  "dob": "1986-04-17",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-312-555-7711",
  "mailing_address": "200 N Michigan Ave, Chicago, IL 60601",
  "degrees-0-institution": "Northwestern",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Finance",
  "degrees-0-gpa": 3.7,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2004-09",
  "degrees-0-end_date": "2008-06",
  "has_work_experience": true,
  "jobs-0-employer": "JPMorgan Chase",
  "jobs-0-title": "VP of Strategy",
  "jobs-0-start_date": "2018-03",
  "jobs-0-end_date": "2025-11",
  "jobs-0-description": "Led M&A integration for the consumer banking division."
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "yes I have work experience" },
  { "role": "assistant", "content": "Tell me about your most recent role." },
  { "role": "user", "content": "JPMorgan Chase, VP of Strategy, March 2018 to November 2025. Led M&A integration for the consumer banking division." },
  { "role": "assistant", "content": "Got your JPMorgan role. Anything else from your work history you'd like to include?" }
]
```

**user_message**:
```
yes — before JPMorgan I was at Bain & Company as a Senior Associate from 2014 to 2018. Worked on private equity due diligence projects.
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with index 1 (NOT 0 — index 0 is already filled):
  - `jobs.1.employer = Bain & Company`
  - `jobs.1.title = Senior Associate`
  - `jobs.1.start_date = 2014-XX`
  - `jobs.1.end_date = 2018-XX`
  - `jobs.1.description` containing the PE due diligence note
- Does NOT touch `jobs.0.*` (no overwrite of JPMorgan)
- response_text acknowledges adding the second job, asks for more or moves on

**What would constitute a NEW failure**:
- Model overwrites `jobs.0.*` with Bain values (loses JPMorgan)
- Model uses index 0 instead of 1 (creates duplicate or overwrite)
- Model uses index 2 (skips 1)
- Model changes `jobs.0.start_date` to 2014 (mixing the two roles' dates)
- Model duplicates description across both indices
- Model fails to fire `has_new_data` despite explicit job info (R10-style)
- Date inference fails on "before JPMorgan" — model uses literal string instead of inferring temporal order

---

## P5-ex3 — Three recommenders provided messily

**Setup**: All other sections done. User provides 3 recommenders with mixed structure — some lines have full info, some are partial.

**form_state**:
```json
{
  "email": "kai@test.com",
  "program": "public_health",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Kai Nguyen",
  "dob": "1994-06-28",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-206-555-3300",
  "mailing_address": "1414 NE Pacific St, Seattle, WA 98195",
  "degrees-0-institution": "University of Washington",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Biology",
  "degrees-0-gpa": 3.6,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2012-09",
  "degrees-0-end_date": "2016-06",
  "has_work_experience": true,
  "jobs-0-employer": "Seattle Public Health Department",
  "jobs-0-title": "Epidemiologist",
  "jobs-0-start_date": "2017-08",
  "jobs-0-end_date": "2025-09",
  "jobs-0-description": "Surveillance and outbreak response for King County."
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Seattle Public Health Department, Epidemiologist, August 2017 to September 2025. Surveillance and outbreak response for King County." },
  { "role": "assistant", "content": "Got it. Any other jobs to add?" },
  { "role": "user", "content": "no just that one" },
  { "role": "assistant", "content": "Last big section — recommendation letters. Could you share the names, emails, relationships, and institutions of your recommenders?" }
]
```

**user_message**:
```
Dr. Maya Patel — maya.patel@uw.edu — my undergrad PI at UW
Prof. James Chen at Johns Hopkins, jchen@jhsph.edu, my MPH program advisor (i'm starting that program in the fall actually)
And Dr. Robert Kim, my supervisor at the health department — bob.kim@kingcounty.gov
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with three indexed entries:
  - `recommenders.0.{name, email, relationship, institution}` for Dr. Maya Patel
  - `recommenders.1.{name, email, relationship, institution}` for Prof. James Chen
  - `recommenders.2.{name, email, relationship, institution}` for Dr. Robert Kim
- Each name preserves the "Dr." / "Prof." prefix or strips uniformly
- Relationship enum maps reasonably (advisor → professor/employer; PI → professor; supervisor → employer)
- response_text confirms all three, moves to next section or recap

**What would constitute a NEW failure**:
- Model only extracts one recommender, drops the rest
- Model concatenates multiple names into a single entry
- Model swaps fields across recommenders (Maya's email goes to James's slot)
- Model fabricates an institution for Robert (King County health dept isn't an academic institution)
- Model gets confused by "i'm starting that program in the fall" (Hopkins MPH) parenthetical and misroutes it to a degree field
- Model uses indices 1, 2, 3 (skipping 0)
- Model duplicates one recommender across multiple indices
- Persona-leakage: training-data has "Prof. Alan Turing" / "Dr. Sarah Connor" as Jane's recommenders — surfacing those names

---

## P5-ex4 — User wants to remove an entry

**Setup**: User has 2 jobs filled. Realizes the second one shouldn't be on the application — it was a brief contract that's not relevant.

**form_state**:
```json
{
  "email": "lin@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Lin Yamada",
  "dob": "1991-03-14",
  "country_citizenship": "JP",
  "country_residence": "US",
  "phone": "+1-650-555-4400",
  "mailing_address": "525 University Ave, Palo Alto, CA 94301",
  "has_work_experience": true,
  "jobs-0-employer": "Apple",
  "jobs-0-title": "iOS Engineer",
  "jobs-0-start_date": "2018-07",
  "jobs-0-end_date": "2025-04",
  "jobs-0-description": "Built health features for the Apple Watch.",
  "jobs-1-employer": "FreelanceConsult LLC",
  "jobs-1-title": "Independent Contractor",
  "jobs-1-start_date": "2017-01",
  "jobs-1-end_date": "2017-06",
  "jobs-1-description": "Short-term React Native gig — not really relevant."
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Apple, iOS Engineer, July 2018 to April 2025. Built health features for the Apple Watch." },
  { "role": "assistant", "content": "Saved. Any other jobs?" },
  { "role": "user", "content": "yes — FreelanceConsult LLC, Independent Contractor, January 2017 to June 2017. Short-term React Native gig — not really relevant." },
  { "role": "assistant", "content": "Great — both jobs are saved. Anything else?" }
]
```

**user_message**:
```
actually you know what, can you remove the freelance one? it was only 6 months and i don't think it adds anything.
```

**What we want to see**:
- `has_new_data = true` (a removal IS a state change)
- `set_fields` with `jobs.1.*` cleared (e.g., empty strings or nulls — depends on what the action format supports)
- Does NOT touch `jobs.0.*` (Apple stays)
- response_text confirms removal
- (If the action format doesn't support deletion, the model should at least flag this and ask the user how to proceed)

**What would constitute a NEW failure**:
- Model claims to remove but emits no action (silent no-op)
- Model emits set_fields that overwrites `jobs.0.*` (deletes the wrong job)
- Model emits a confused mix (clears index 0 partially, leaves index 1 alone)
- Model fabricates a "delete_field" or "remove_entry" action type that doesn't exist in the action vocabulary
- Model proceeds with no acknowledgment of the change
- Model treats this as wanting to skip work experience entirely (clears `has_work_experience`)
- Model gets stuck in a loop asking for confirmation repeatedly

---

## P5-ex5 — Editing a specific entry by index

**Setup**: User has 3 recommenders filled. Realizes they got the second recommender's email wrong.

**form_state**:
```json
{
  "email": "marlowe@test.com",
  "program": "education",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Marlowe O'Brien",
  "dob": "1985-08-09",
  "country_citizenship": "IE",
  "country_residence": "US",
  "phone": "+1-617-555-9933",
  "mailing_address": "44 Boylston St, Boston, MA 02116",
  "degrees-0-institution": "Trinity College Dublin",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "English Literature",
  "degrees-0-gpa": 3.8,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2003-09",
  "degrees-0-end_date": "2007-06",
  "has_work_experience": true,
  "jobs-0-employer": "Boston Public Library",
  "jobs-0-title": "Programs Director",
  "jobs-0-start_date": "2015-01",
  "jobs-0-end_date": "2025-12",
  "jobs-0-description": "Ran adult literacy and ESL programming.",
  "recommenders-0-name": "Dr. Siobhan Murphy",
  "recommenders-0-email": "smurphy@tcd.ie",
  "recommenders-0-relationship": "professor",
  "recommenders-0-institution": "Trinity College Dublin",
  "recommenders-1-name": "Prof. Liam Walsh",
  "recommenders-1-email": "lwalsh@bu.edu",
  "recommenders-1-relationship": "professor",
  "recommenders-1-institution": "Boston University",
  "recommenders-2-name": "Director Catherine Reed",
  "recommenders-2-email": "creed@bpl.org",
  "recommenders-2-relationship": "employer",
  "recommenders-2-institution": "Boston Public Library"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Director Catherine Reed, creed@bpl.org, my supervisor at Boston Public Library" },
  { "role": "assistant", "content": "Got Director Reed. Any other recommenders?" },
  { "role": "user", "content": "no that's the three" },
  { "role": "assistant", "content": "All three recommenders are saved. Ready to move on to supporting documents?" }
]
```

**user_message**:
```
hold on, prof walsh's email is wrong — it should be liam.walsh@bu.edu, with the dot
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with `recommenders.1.email = liam.walsh@bu.edu`
- Targets index 1 specifically (Prof. Liam Walsh)
- Does NOT touch any other recommender's email or any other field on recommender 1
- response_text confirms the fix

**What would constitute a NEW failure**:
- Model updates `recommenders.0.email` (wrong index)
- Model updates all three recommenders' emails
- Model creates `recommenders.3.email` (new entry instead of update)
- Model can't disambiguate which recommender ("Prof. Walsh") and asks
- Model overwrites the entire recommender 1 record with just the email field
- Model fabricates a different correction ("you also said his name was wrong")
- Model fails to fire `has_new_data` (R10-style — natural-language correction not recognized as data)

---

## Notes on this batch

- Five examples: bulk multi-entry, append-to-existing, three-recommender messy dump, removal, edit-by-index.
- This is the meatiest phase for surfacing dotted-id failures. SFT-v2's training data has plenty of multi-degree / multi-job sessions, but the patterns of *adding to existing* and *editing by index* may be undertested.
- Names: Indigo Tran, Jamie Thomas, Kai Nguyen, Lin Yamada, Marlowe O'Brien.
- P5-ex3 specifically probes the persona-leakage canary — Jane's recommenders are "Prof. Alan Turing" and "Dr. Sarah Connor". Surfacing either of those names in a Kai session = R12 firing.
