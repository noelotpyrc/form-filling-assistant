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

---

### Run 1 — temp=0.0 — 10.8s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `true`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Great question! Here's what's saved so far:\n\n**\u2705 Completed sections:**\n- **Program Selection** \u2014 Data Science (MS), Fall 2026, Full-time\n- **Personal Information** \u2014 Juno Reyes, US citizen, 617-555-7700, juno@test.com\n- **Academic Background** \u2014 Boston University, BS in Statistics, 3.7 GPA\n- **Work Experience** \u2014 Biostatistician at MassGeneral (2014\u20132025)\n- **Documents** \u2014 Statement of Purpose & Resume ready\n- **Recommendation Letters** \u2014 Dr. Sarah Mitchell (professor)\n- **Additional Info** \u2014 Research assistantship interest\n\n**\u26a0\ufe0f Still needed:**\n- **GRE scores** \u2014 required for Data Science program\n- **TOEFL/IELTS** \u2014 not applicable for US citizens\n- **Additional documents** \u2014 Statement of Purpose and Resume (both ready to upload)\n\nEverything else is complete! You just need to **take the GRE** and come back to finish up. Would you like to save a draft now?"

**review_builder:** _(triggered by `wants_review`)_
- `summary_title` = "Application Progress"
- `summary_content` = "Completed 33 fields:\n- email: juno@test.com\n- program: data_science\n- start_term: fall_2026\n- enrollment_type: full_time\n- prior_application: False\n- full_name: Juno Reyes\n- preferred_name: Juno\n- dob: 1991-04-15\n- country_citizenship: US\n- country_residence: US\n- phone: +1-617-555-7700\n- mailing_address: 75 Massachusetts Ave, Cambridge, MA 02139\n- degrees-0-institution: Boston University\n- degrees-0-degree_type: bachelor\n- degrees-0-field_of_study: Statistics\n- degrees-0-gpa: 3.7\n- degrees-0-gpa_scale: 4.0\n- degrees-0-start_date: 2009-09\n- degrees-0-end_date: 2013-05\n- degrees-0-transcript: Juno_Transcript.pdf\n- has_work_experience: True\n- jobs-0-employer: MassGeneral\n- jobs-0-title: Biostatistician\n- jobs-0-start_date: 2014-07\n- jobs-0-end_date: 2025-12\n- jobs-0-description: Designed statistical analysis pipelines for clinical trial data.\n- statement_of_purpose: Juno_SOP.pdf\n- resume: Juno_Resume.pdf\n- recommenders-0-name: Dr. Sarah Mitchell\n- recommenders-0-email: smitchell@bu.edu\n- recommenders-0-relationship: professor\n- recommenders-0-institution: Boston University\n- funding_interest: True\n- funding_type: ['research_assistantship']"

**Composed final output (what the browser receives):**
```
Great question! Here's what's saved so far:

**✅ Completed sections:**
- **Program Selection** — Data Science (MS), Fall 2026, Full-time
- **Personal Information** — Juno Reyes, US citizen, 617-555-7700, juno@test.com
- **Academic Background** — Boston University, BS in Statistics, 3.7 GPA
- **Work Experience** — Biostatistician at MassGeneral (2014–2025)
- **Documents** — Statement of Purpose & Resume ready
- **Recommendation Letters** — Dr. Sarah Mitchell (professor)
- **Additional Info** — Research assistantship interest

**⚠️ Still needed:**
- **GRE scores** — required for Data Science program
- **TOEFL/IELTS** — not applicable for US citizens
- **Additional documents** — Statement of Purpose and Resume (both ready to upload)

Everything else is complete! You just need to **take the GRE** and come back to finish up. Would you like to save a draft now?

---actions---
```json
[
  {
    "type": "show_preview",
    "title": "Application Progress",
    "summary": "Completed 33 fields:\n- email: juno@test.com\n- program: data_science\n- start_term: fall_2026\n- enrollment_type: full_time\n- prior_application: False\n- full_name: Juno Reyes\n- preferred_name: Juno\n- dob: 1991-04-15\n- country_citizenship: US\n- country_residence: US\n- phone: +1-617-555-7700\n- mailing_address: 75 Massachusetts Ave, Cambridge, MA 02139\n- degrees-0-institution: Boston University\n- degrees-0-degree_type: bachelor\n- degrees-0-field_of_study: Statistics\n- degrees-0-gpa: 3.7\n- degrees-0-gpa_scale: 4.0\n- degrees-0-start_date: 2009-09\n- degrees-0-end_date: 2013-05\n- degrees-0-transcript: Juno_Transcript.pdf\n- has_work_experience: True\n- jobs-0-employer: MassGeneral\n- jobs-0-title: Biostatistician\n- jobs-0-start_date: 2014-07\n- jobs-0-end_date: 2025-12\n- jobs-0-description: Designed statistical analysis pipelines for clinical trial data.\n- statement_of_purpose: Juno_SOP.pdf\n- resume: Juno_Resume.pdf\n- recommenders-0-name: Dr. Sarah Mitchell\n- recommenders-0-email: smitchell@bu.edu\n- recommenders-0-relationship: professor\n- recommenders-0-institution: Boston University\n- funding_interest: True\n- funding_type: ['research_assistantship']"
  }
]
```
```

---

### Run 2 — temp=0.7 — 11.4s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `true`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Great question! Here's what's saved so far:\n\n**\u2705 Completed sections:**\n1. **Program Selection** \u2014 Data Science (MS), Fall 2026, Full-time\n2. **Personal Information** \u2014 Juno Reyes, US citizen, phone +1-617-555-7700, address in Cambridge, MA\n3. **Academic Background** \u2014 Boston University, BS in Statistics, 3.7 GPA/4.0, Sept 2009 \u2013 May 2013\n4. **Document Uploads** \u2014 Transcript (Juno_Transcript.pdf)\n5. **Work Experience** \u2014 Biostatistician at MassGeneral from July 2014 \u2013 Dec 2025\n6. **Statement of Purpose** \u2014 Juno_SOP.pdf\n7. **Additional Info** \u2014 Research assistantship interested\n\n**\u26a0\ufe0f Still needed:**\n- **GRE scores** \u2014 required for Data Science program\n- **TOEFL/IELTS** \u2014 not applicable since you're a US citizen\n- **Official Resume/CV**\n- **Additional documents** (statement of purpose + resume)\n\nThe only items still to come back are **GRE scores** and the **official resume**. If you have those handy, you can upload them now and we'll complete everything in one session.\n\nWant to save your application as a draft so nothing is lost?"

**review_builder:** _(triggered by `wants_review`)_
- `summary_title` = "Application Progress"
- `summary_content` = "Completed 36 fields:\n- email: juno@test.com\n- program: data_science\n- start_term: fall_2026\n- enrollment_type: full_time\n- prior_application: False\n- full_name: Juno Reyes\n- preferred_name: Juno\n- dob: 1991-04-15\n- country_citizenship: US\n- country_residence: US\n- phone: +1-617-555-7700\n- mailing_address: 75 Massachusetts Ave, Cambridge, MA 02139\n- degrees-0-institution: Boston University\n- degrees-0-degree_type: bachelor\n- degrees-0-field_of_study: Statistics\n- degrees-0-gpa: 3.7\n- degrees-0-gpa_scale: 4.0\n- degrees-0-start_date: 2009-09\n- degrees-0-end_date: 2013-05\n- degrees-0-transcript: Juno_Transcript.pdf\n- has_work_experience: True\n- jobs-0-employer: MassGeneral\n- jobs-0-title: Biostatistician\n- jobs-0-start_date: 2014-07\n- jobs-0-end_date: 2025-12\n- jobs-0-description: Designed statistical analysis pipelines for clinical trial data.\n- statement_of_purpose: Juno_SOP.pdf\n- resume: Juno_Resume.pdf\n- recommenders-0-name: Dr. Sarah Mitchell\n- recommenders-0-email: smitchell@bu.edu\n- recommenders-0-relationship: professor\n- recommenders-0-institution: Boston University\n- funding_interest: True\n- funding_type: ['research_assistantship']"

**Composed final output (what the browser receives):**
```
Great question! Here's what's saved so far:

**✅ Completed sections:**
1. **Program Selection** — Data Science (MS), Fall 2026, Full-time
2. **Personal Information** — Juno Reyes, US citizen, phone +1-617-555-7700, address in Cambridge, MA
3. **Academic Background** — Boston University, BS in Statistics, 3.7 GPA/4.0, Sept 2009 – May 2013
4. **Document Uploads** — Transcript (Juno_Transcript.pdf)
5. **Work Experience** — Biostatistician at MassGeneral from July 2014 – Dec 2025
6. **Statement of Purpose** — Juno_SOP.pdf
7. **Additional Info** — Research assistantship interested

**⚠️ Still needed:**
- **GRE scores** — required for Data Science program
- **TOEFL/IELTS** — not applicable since you're a US citizen
- **Official Resume/CV**
- **Additional documents** (statement of purpose + resume)

The only items still to come back are **GRE scores** and the **official resume**. If you have those handy, you can upload them now and we'll complete everything in one session.

Want to save your application as a draft so nothing is lost?

---actions---
```json
[
  {
    "type": "show_preview",
    "title": "Application Progress",
    "summary": "Completed 36 fields:\n- email: juno@test.com\n- program: data_science\n- start_term: fall_2026\n- enrollment_type: full_time\n- prior_application: False\n- full_name: Juno Reyes\n- preferred_name: Juno\n- dob: 1991-04-15\n- country_citizenship: US\n- country_residence: US\n- phone: +1-617-555-7700\n- mailing_address: 75 Massachusetts Ave, Cambridge, MA 02139\n- degrees-0-institution: Boston University\n- degrees-0-degree_type: bachelor\n- degrees-0-field_of_study: Statistics\n- degrees-0-gpa: 3.7\n- degrees-0-gpa_scale: 4.0\n- degrees-0-start_date: 2009-09\n- degrees-0-end_date: 2013-05\n- degrees-0-transcript: Juno_Transcript.pdf\n- has_work_experience: True\n- jobs-0-employer: MassGeneral\n- jobs-0-title: Biostatistician\n- jobs-0-start_date: 2014-07\n- jobs-0-end_date: 2025-12\n- jobs-0-description: Designed statistical analysis pipelines for clinical trial data.\n- statement_of_purpose: Juno_SOP.pdf\n- resume: Juno_Resume.pdf\n- recommenders-0-name: Dr. Sarah Mitchell\n- recommenders-0-email: smitchell@bu.edu\n- recommenders-0-relationship: professor\n- recommenders-0-institution: Boston University\n- funding_interest: True\n- funding_type: ['research_assistantship']"
  }
]
```
```


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

---

### Run 1 — temp=0.0 — 3.1s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "No problem! It seems like an error on your end \u2014 the email in the form is wrong. I can't change it for you, but you should check with your email provider to confirm.\n\nIn the meantime, let's save your draft so nothing gets lost."

**Composed final output (what the browser receives):**
```
No problem! It seems like an error on your end — the email in the form is wrong. I can't change it for you, but you should check with your email provider to confirm.

In the meantime, let's save your draft so nothing gets lost.
```

---

### Run 2 — temp=0.7 — 2.7s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "No worries at all! Let me fix that for you."

**Composed final output (what the browser receives):**
```
No worries at all! Let me fix that for you.
```


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

---

### Run 1 — temp=0.0 — 3.7s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Great question! Before your final submission, here's what's still needed:\n\n1. **Statement of Purpose** \u2014 \ud83d\udcc4 A PDF or DOCX between you and your recommenders (500\u20131000 words)\n2. **Resume / CV** \u2014 \ud83d\udcc4 PDF or DOCX\n3. **Official Transcript(s)** \u2014 \ud83d\udcc4 PDF for your IIT Delhi degree\n\nYou can save these as well and come back anytime to upload them. Everything else is complete!\n\nWould you like to save your progress as a draft for now?"

**Composed final output (what the browser receives):**
```
Great question! Before your final submission, here's what's still needed:

1. **Statement of Purpose** — 📄 A PDF or DOCX between you and your recommenders (500–1000 words)
2. **Resume / CV** — 📄 PDF or DOCX
3. **Official Transcript(s)** — 📄 PDF for your IIT Delhi degree

You can save these as well and come back anytime to upload them. Everything else is complete!

Would you like to save your progress as a draft for now?
```

---

### Run 2 — temp=0.7 — 4.3s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Good question! Before you can submit, you have a few things ready to go:\n\n1. **Statement of Purpose** \u2014 A 500\u20131,000 word essay about why you want to pursue the CS master's at Northfield\n2. **Resume / CV** \u2014 Your up-to-date resume\n3. **Official Transcript(s)** \u2014 PDF of your IIT Delhi degree\n\nYou also need at least one recommender \u2014 ideally 2\u20134 people who can speak to your academic or professional abilities. A contact email is fine.\n\nIf you have both the resume and transcript ready, you can come back and upload them to complete the application. Otherwise, we can save your progress as a draft for now too.\n\nWant me to save your draft?"

**Composed final output (what the browser receives):**
```
Good question! Before you can submit, you have a few things ready to go:

1. **Statement of Purpose** — A 500–1,000 word essay about why you want to pursue the CS master's at Northfield
2. **Resume / CV** — Your up-to-date resume
3. **Official Transcript(s)** — PDF of your IIT Delhi degree

You also need at least one recommender — ideally 2–4 people who can speak to your academic or professional abilities. A contact email is fine.

If you have both the resume and transcript ready, you can come back and upload them to complete the application. Otherwise, we can save your progress as a draft for now too.

Want me to save your draft?
```


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

---

### Run 1 — temp=0.0 — 3.4s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Since you're a US citizen, you won't need TOEFL/IELTS scores either \u2014 nice!\n\nLet's move on to **Academic Background**. Tell me about your degree(s):\n- **Institution name**\n- **Degree type** (Bachelor's, Master's, etc.)\n- **Field of study / major**\n- **GPA** (and what scale, if not 4.0)\n- **Start and end dates**\n\nAlso, do you have an **official transcript** (PDF) you'd like to upload?"

**Composed final output (what the browser receives):**
```
Since you're a US citizen, you won't need TOEFL/IELTS scores either — nice!

Let's move on to **Academic Background**. Tell me about your degree(s):
- **Institution name**
- **Degree type** (Bachelor's, Master's, etc.)
- **Field of study / major**
- **GPA** (and what scale, if not 4.0)
- **Start and end dates**

Also, do you have an **official transcript** (PDF) you'd like to upload?
```

---

### Run 2 — temp=0.7 — 3.6s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Sounds good! So let's knock out the remaining sections. \n\nI've filled in what you've shared so far. Here's what's still missing:\n\n1. **Academic Background** \u2014 institution, degree, GPA, dates, and transcript\n2. **GRE Scores** \u2014 required for Public Health\n3. **Work Experience** \u2014 jobs to list\n4. **Documents** \u2014 statement of purpose & resume\n5. **References** \u2014 2\u20134 recommenders\n6. **Additional Info** \u2014 funding interest, etc.\n\nLet's start with your academic history. What degree(s) have you earned, and what's your GPA?"

**Composed final output (what the browser receives):**
```
Sounds good! So let's knock out the remaining sections. 

I've filled in what you've shared so far. Here's what's still missing:

1. **Academic Background** — institution, degree, GPA, dates, and transcript
2. **GRE Scores** — required for Public Health
3. **Work Experience** — jobs to list
4. **Documents** — statement of purpose & resume
5. **References** — 2–4 recommenders
6. **Additional Info** — funding interest, etc.

Let's start with your academic history. What degree(s) have you earned, and what's your GPA?
```


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

---

### Run 1 — temp=0.0 — 7.7s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "No worries! Just let me know the filename (with the extension like `.pdf` or `.docx`) and I'll upload it right when you're ready."

**Composed final output (what the browser receives):**
```
No worries! Just let me know the filename (with the extension like `.pdf` or `.docx`) and I'll upload it right when you're ready.
```

---

### Run 2 — temp=0.7 — 6.6s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "No worries! Just let me know the exact filename of your Statement of Purpose (e.g., *Mavis_SOP_2026.pdf* or whatever your system expects). Common ones are *Statement_of_Purpose* or similar."

**Composed final output (what the browser receives):**
```
No worries! Just let me know the exact filename of your Statement of Purpose (e.g., *Mavis_SOP_2026.pdf* or whatever your system expects). Common ones are *Statement_of_Purpose* or similar.
```


## Notes on this batch

- Five examples: comprehensive review, edit-via-review, what's-missing, false-done, specific-file-recall.
- Every example tests recall accuracy against the form_state — these directly probe R11-class hallucinations under different framings.
- Names: Juno Reyes, Knox Singh, Lila Brooks, Mavis Sosa, Niles Carter (saved for P11).
