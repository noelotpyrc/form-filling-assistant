# Phase 7 — File uploads

The schema has three file fields: `degrees.0.transcript`, `statement_of_purpose`, `resume`, `additional_docs`. Browser-side `FileProcessor.process()` extracts text from PDFs and inlines into the user message as `[File: name]<text>[End of name]`. The model has to: (1) recognize document type, (2) ask which field it goes to, (3) on confirm, emit `set_fields` with `field_id=<file_field>, value=filename` AND extract any matching data.

We've already seen R6 (extraction errors), R7 (file not auto-assigned), R8 (history truncation). Probes below target patterns we *haven't* tested.

**Form**: Northfield. **Names**: Taylor Wells, Vale Brooks, Wren Carter, Xan Mosley, Yuri Andersson.

---

## P7-ex1 — User uploads a transcript (not a resume) — should route to degrees.0.transcript

**Setup**: User has filled their degree info. Now uploads a transcript PDF. Model should recognize it as a transcript and assign to `degrees.0.transcript` (not resume).

**form_state**:
```json
{
  "email": "taylor@test.com",
  "program": "data_science",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Taylor Wells",
  "dob": "1992-06-21",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-617-555-2244",
  "mailing_address": "30 Memorial Dr, Cambridge, MA 02139",
  "degrees-0-institution": "MIT",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Mathematics",
  "degrees-0-gpa": 4.7,
  "degrees-0-gpa_scale": "5.0",
  "degrees-0-start_date": "2010-09",
  "degrees-0-end_date": "2014-06"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "BS in Mathematics from MIT, GPA 4.7 on 5.0 scale, 2010-2014" },
  { "role": "assistant", "content": "Saved. Any other degrees?" },
  { "role": "user", "content": "no just the one" },
  { "role": "assistant", "content": "Your MIT degree is saved. Do you have a transcript or other supporting documents to attach?" }
]
```

**user_message**:
```
[File: Transcript.pdf]
UNOFFICIAL TRANSCRIPT
Massachusetts Institute of Technology

Student: Taylor Wells
Student ID: 905112233
Degree: Bachelor of Science in Mathematics
Conferred: June 2014

Course History:
Fall 2010: 18.01 Calculus I (A), 18.02 Calculus II (A-), 6.001 Intro to CS (A)
Spring 2011: 18.06 Linear Algebra (A), 6.0001 Intro to CS+Python (A), 8.01 Physics I (B+)
... [more course history] ...
Cumulative GPA: 4.7/5.0
[End of Transcript.pdf]
```

**What we want to see**:
- `has_new_data = true`
- `needs_choice = true` ideally (asking which field — transcript? additional_docs?) OR direct assignment
- `set_fields` with `degrees.0.transcript = Transcript.pdf` (the file assignment — R7 fix)
- Maybe also re-confirms degree info already in form_state
- response_text identifies it as a transcript, confirms placement

**What would constitute a NEW failure**:
- Model assigns to `resume` field (wrong file slot — recognized doc type wrong)
- Model assigns to `additional_docs` (default catch-all)
- Model doesn't emit any file assignment (R7 redux)
- Model overwrites already-filled GPA (4.7) with the value parsed from transcript (which matches, so ok) but uses different format (4.70 vs 4.7)
- Model fabricates additional fields from the transcript (e.g., extracting individual courses into nonexistent fields)
- Model surfaces "Jane Smith" as the student name (R12 — Jane's transcript pattern)

---

## P7-ex2 — User uploads a Statement of Purpose

**Setup**: Personal info, education, work experience all done. Model just asked about supporting documents.

**form_state**:
```json
{
  "email": "vale@test.com",
  "program": "education",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Vale Brooks",
  "dob": "1989-12-04",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-415-555-7700",
  "mailing_address": "200 Hayes St, San Francisco, CA 94102",
  "degrees-0-institution": "Stanford",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Education",
  "degrees-0-gpa": 3.8,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2007-09",
  "degrees-0-end_date": "2011-06",
  "has_work_experience": true,
  "jobs-0-employer": "Teach For America",
  "jobs-0-title": "Corps Member - 8th Grade Math",
  "jobs-0-start_date": "2011-08",
  "jobs-0-end_date": "2013-06",
  "jobs-0-description": "Taught math to underserved students in the Bay Area."
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Dr. Lisa Reyes, my undergrad advisor at Stanford, lreyes@stanford.edu, professor" },
  { "role": "assistant", "content": "Saved. Any other recommenders?" },
  { "role": "user", "content": "no just one is fine" },
  { "role": "assistant", "content": "Almost there — could you share your Statement of Purpose, resume, and any other supporting documents?" }
]
```

**user_message**:
```
[File: Personal_Statement.pdf]
Statement of Purpose

My journey toward graduate study in education began in eighth-grade math classrooms in East Oakland, where I saw first-hand how systemic inequities shape student outcomes. As a Teach For America corps member, I worked with students whose talent was undeniable but whose access to advanced curriculum was systematically constrained...

[continued essay content for 3-4 paragraphs about teaching philosophy, research interests in math pedagogy, why Northfield specifically, future career plans]
[End of Personal_Statement.pdf]
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with `statement_of_purpose = Personal_Statement.pdf` (file assignment)
- response_text identifies the document as a statement of purpose, confirms placement
- Does NOT extract specific phrases from the SOP into other fields (the SOP body shouldn't fill `anything_else` for example)
- Possibly summarizes briefly, asks for next document (resume)

**What would constitute a NEW failure**:
- Model assigns to `resume` (wrong field — name "Personal_Statement" should be a clue)
- Model dumps the SOP content into `anything_else` field (overflow)
- Model fabricates that the user is from a different program/background based on the SOP narrative
- Model says it can't process this document because it's prose not a form
- Model treats the essay content as new biographical data and tries to extract life events into fields that don't exist

---

## P7-ex3 — User uploads a resume but realizes mid-conversation they wanted it for a different field

**Setup**: User uploaded a resume. Then realizes they have multiple PDFs to attach and clarifies which one this is.

**form_state**:
```json
{
  "email": "wren@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Wren Carter",
  "dob": "1991-03-14",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-512-555-3300",
  "mailing_address": "44 Lavaca St, Austin, TX 78701",
  "degrees-0-institution": "UT Austin",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Computer Engineering",
  "degrees-0-gpa": 3.6,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2009-09",
  "degrees-0-end_date": "2013-05"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "BS in Computer Engineering from UT Austin, 3.6 GPA on 4.0 scale, 2009-2013" },
  { "role": "assistant", "content": "Saved. Any other degrees?" },
  { "role": "user", "content": "no" },
  { "role": "assistant", "content": "Could you upload your supporting documents — resume, statement of purpose, etc?" },
  { "role": "user", "content": "[File: Resume.pdf]\nWren Carter\nEmail: wren@test.com | Phone: +1-512-555-3300\n... [resume content] ...\n[End of Resume.pdf]" },
  { "role": "assistant", "content": "Thanks! I've assigned that to your resume field." }
]
```

**user_message**:
```
oh wait, that file is actually my writing sample, not my resume. can you move it?
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with:
  - `resume = ""` or null (clear the wrong assignment)
  - `additional_docs = Resume.pdf` (or whatever field the user means by "writing sample" — schema may not have that exact field)
- response_text acknowledges the mistake, confirms the move
- If schema has no "writing sample" field, model should explain and ask the user

**What would constitute a NEW failure**:
- Model says "done" but emits no action (no actual move)
- Model creates a new field (`writing_sample`) that doesn't exist in the schema
- Model leaves both fields populated (duplicate)
- Model overwrites unrelated fields when trying to clear `resume`
- Model gets confused and asks for a fresh upload
- Model contradicts the user ("but the file content looks like a resume")

---

## P7-ex4 — User says they'll upload later, doesn't actually attach anything

**Setup**: Model asked for resume. User mentions they'll upload but doesn't attach a file.

**form_state**:
```json
{
  "email": "xan@test.com",
  "program": "mba",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Xan Mosley",
  "dob": "1986-05-19",
  "country_citizenship": "US",
  "country_residence": "US"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Xan Mosley, May 19 1986, US citizen and resident" },
  { "role": "assistant", "content": "Saved. What's your phone, email, address?" },
  { "role": "user", "content": "let's skip those for now and come back later" },
  { "role": "assistant", "content": "No problem. Could you upload your resume? You can attach it using the paperclip button." }
]
```

**user_message**:
```
oh i don't have it on my laptop right now — i'll dig it up tonight and upload it later
```

**What we want to see**:
- `has_new_data = false`
- response_text acknowledges the deferral, suggests saving a draft, moves on (skip resume for now)
- `wants_save = true` would be reasonable here
- Does NOT fabricate a resume filename

**What would constitute a NEW failure**:
- Model fabricates `resume = "resume.pdf"` or `resume = "Wren_Carter_Resume.pdf"` placeholder
- Model creates a "pending upload" entry that isn't a real action
- Model insists the user upload now and won't move on
- Model confuses deferral with refusal and skips the entire supporting documents section
- Model proceeds as if the user did upload, asks about "the resume content"

---

## P7-ex5 — Re-upload to replace an existing file

**Setup**: User already uploaded an old version of their resume. Now uploading a newer version.

**form_state**:
```json
{
  "email": "yuri@test.com",
  "program": "data_science",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Yuri Andersson",
  "dob": "1990-08-11",
  "country_citizenship": "SE",
  "country_residence": "US",
  "phone": "+1-718-555-9900",
  "mailing_address": "456 Park Slope, Brooklyn, NY 11215",
  "degrees-0-institution": "KTH Royal Institute of Technology",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Computer Science",
  "degrees-0-gpa": 4.3,
  "degrees-0-gpa_scale": "5.0",
  "degrees-0-start_date": "2009-09",
  "degrees-0-end_date": "2013-06",
  "resume": "Yuri_Resume_Old.pdf"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "BS in Computer Science from KTH Royal Institute of Technology, 4.3 GPA on 5.0 scale, 2009-2013" },
  { "role": "assistant", "content": "Saved your KTH degree. Could you upload your resume?" },
  { "role": "user", "content": "[File: Yuri_Resume_Old.pdf]\nYuri Andersson | yuri.old@gmail.com | ... [old resume] ...\n[End of Yuri_Resume_Old.pdf]" },
  { "role": "assistant", "content": "Got your resume. Let me know if anything else needs attaching." }
]
```

**user_message**:
```
[File: Yuri_Resume_v2.pdf]
Yuri Andersson | yuri@test.com | +1-718-555-9900
EXPERIENCE
Senior Data Scientist - DoorDash (2023-Present)
Lead ML for menu recommendation system, ~30M users
Data Scientist - Stripe (2020-2023)
Built risk-scoring features for international merchants
EDUCATION
KTH Royal Institute of Technology, BS CS (2009-2013), 4.3/5.0
[End of Yuri_Resume_v2.pdf]

Sorry, here's the updated version
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with:
  - `resume = Yuri_Resume_v2.pdf` (replacing the old filename)
  - Updated job entries: `jobs.0.employer = DoorDash`, `jobs.0.title = Senior Data Scientist`, etc., AND `jobs.1.employer = Stripe`, etc.
- response_text confirms the replacement
- Does NOT keep both filenames in `resume` (concat)
- Does NOT email-conflict (the new resume has yuri@test.com which matches form_state)

**What would constitute a NEW failure**:
- Model concatenates: `resume = "Yuri_Resume_Old.pdf, Yuri_Resume_v2.pdf"`
- Model creates `resume_v2` as a new field
- Model creates index 2, 3 for jobs (skipping 0, 1 — or appending to existing without replacing)
- Model gets confused by the "old" email in the prior turn's history (`yuri.old@gmail.com`) and overwrites `email` with that
- Model fails to update jobs because they conflict with whatever was in form_state
- Model treats this as a new session entirely

---

## Notes on this batch

- Five examples: transcript routing, SOP routing, mis-assignment correction, deferred upload, re-upload to replace.
- Each tests a different aspect of the file-handling flow that R7 left unaddressed.
- File-block format follows the production format: `[File: <name>]\n<extracted_text>\n[End of <name>]`. The runner can construct these from real fixture PDFs in `mock_data/` if useful.
- Names: Taylor Wells, Vale Brooks, Wren Carter, Xan Mosley, Yuri Andersson.
- The transcript probe (P7-ex1) explicitly puts Taylor's name in the transcript content — surfacing "Jane Smith" or other simulator persona names there is a clean R12 signal.
