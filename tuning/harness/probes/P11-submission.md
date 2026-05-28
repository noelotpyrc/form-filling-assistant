# Phase 11 — Submission

The terminal phase. User commits to submitting. The model should: confirm readiness, render the Submit button, acknowledge submission once clicked. The submit action itself is browser-driven (POST to persistence-server `/api/submissions`). Note: `wants_submit` has zero training-data positive cases (R12 / Experiment 9 audit) — the model has had **no supervision** on this flag.

**Form**: Northfield. **Names**: Niles Carter, Olive Wells, Pax Mosley, Quill Andersson, Ria Adams.

---

## P11-ex1 — Direct submit request, all fields complete

**Setup**: All required fields filled. User asks to submit.

**form_state**: *(comprehensive — assume fully complete)*
```json
{
  "email": "niles@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Niles Carter",
  "preferred_name": "Niles",
  "dob": "1990-11-11",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-650-555-1100",
  "mailing_address": "501 Forbes Ave, Pittsburgh, PA 15213",
  "degrees-0-institution": "Carnegie Mellon",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Computer Science",
  "degrees-0-gpa": 3.85,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2008-09",
  "degrees-0-end_date": "2012-05",
  "degrees-0-transcript": "Niles_Transcript.pdf",
  "has_work_experience": true,
  "jobs-0-employer": "Microsoft",
  "jobs-0-title": "Software Engineer",
  "jobs-0-start_date": "2012-08",
  "jobs-0-end_date": "2025-10",
  "jobs-0-description": "Worked on Azure cloud infrastructure.",
  "statement_of_purpose": "Niles_SOP.pdf",
  "resume": "Niles_Resume.pdf",
  "recommenders-0-name": "Prof. Manuel Blum",
  "recommenders-0-email": "mblum@cs.cmu.edu",
  "recommenders-0-relationship": "professor",
  "recommenders-0-institution": "Carnegie Mellon",
  "recommenders-1-name": "Sarah Johnson",
  "recommenders-1-email": "sjohnson@microsoft.com",
  "recommenders-1-relationship": "employer",
  "recommenders-1-institution": "Microsoft",
  "funding_interest": true,
  "funding_type": ["fellowship"]
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "yes, fellowship would be ideal" },
  { "role": "assistant", "content": "Saved. That's everything I needed!" },
  { "role": "user", "content": "can you walk me through everything?" },
  { "role": "assistant", "content": "[show_preview: Your full Northfield application — Niles Carter, CS MS Fall 2026 full-time, CMU bachelor's CS 3.85, Microsoft SWE 2012-2025, transcript + SOP + resume uploaded, 2 recommenders, fellowship interest]\n\nEverything looks good! Ready to submit?" }
]
```

**user_message**:
```
yes, let's submit it
```

**What we want to see**:
- `wants_submit = true`
- `show_button` action with `button = submit`
- response_text confirms readiness, prompts user to click the Submit button
- Does NOT claim the submission has been made (the click does that)

**What would constitute a NEW failure**:
- `wants_submit = false` — model doesn't fire the flag (R10/R12 territory: untrained flag)
- Model emits `show_button` with `button = save_draft` instead of `submit`
- Model claims "submitted!" without emitting a button
- Model does emit Submit button but also emits Save Draft (mixed signals)
- Model emits set_fields trying to "finalize" things
- Model fabricates a confirmation number before submission ("your reference is APP-2026-12345")
- Model abandons the flow ("ok bye")

---

## P11-ex2 — User hesitates ("are you sure i should submit?")

**Setup**: Fields are complete, but user is nervous and asks for reassurance.

**form_state**: *(same comprehensive fill as P11-ex1)*

**conversation_history**:
```json
[
  { "role": "user", "content": "Prof. Manuel Blum, mblum@cs.cmu.edu, my undergrad professor at CMU" },
  { "role": "assistant", "content": "Saved. Any other recommenders?" },
  { "role": "user", "content": "yes, Sarah Johnson, my manager at Microsoft, sjohnson@microsoft.com" },
  { "role": "assistant", "content": "Saved. Funding interest?" },
  { "role": "user", "content": "fellowship" },
  { "role": "assistant", "content": "Everything looks good! Ready to submit?" }
]
```

**user_message**:
```
hmm, am i sure? what if i missed something? can we double check
```

**What we want to see**:
- `wants_review = true` — model offers a final review
- `show_preview` action with comprehensive recap
- response_text reassures, offers to walk through the application
- Does NOT prematurely fire `wants_submit`

**What would constitute a NEW failure**:
- Model immediately fires `wants_submit = true` despite hesitation
- Model dismisses the concern ("just submit it!")
- Model fabricates that everything is verified ("I've already double-checked")
- Model gets confused and asks a random question
- Model surfaces persona names while doing the recap

---

## P11-ex3 — Model receives the submit-confirmation system event

**Setup**: User clicked the Submit button. Browser sent the system event.

**form_state**: *(comprehensive — same as P11-ex1)*

**conversation_history**:
```json
[
  { "role": "user", "content": "yes, let's submit it" },
  { "role": "assistant", "content": "Click the Submit button below to finalize.\n\n[show_button: submit]" }
]
```

**user_message**:
```
[system] User clicked Submit. Application submitted successfully. Reference number: APP-2026-37291.
```

**What we want to see**:
- response_text congratulates, confirms reference number `APP-2026-37291`
- May provide a friendly closing message
- Does NOT re-emit any buttons or forms
- `has_new_data = false`, all flags false

**What would constitute a NEW failure**:
- Model fabricates a different reference number
- Model says submission failed despite the system event saying it succeeded
- Model contradicts ("I'm not sure your application went through")
- Model emits another submit button (offer to re-submit)
- Model surfaces persona names in the closing
- Model promises capabilities it doesn't have ("I'll email you a copy")

---

## P11-ex4 — User says "submit" but required fields are missing

**Setup**: User is impatient and tries to submit but has empty required fields.

**form_state**:
```json
{
  "email": "olive@test.com",
  "program": "mba",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Olive Wells",
  "dob": "1992-08-04",
  "country_citizenship": "US",
  "country_residence": "US"
}
```
*(Missing: phone, mailing_address, education, work experience, files, recommenders, funding)*

**conversation_history**:
```json
[
  { "role": "user", "content": "[system] User selected option: \"No\"" },
  { "role": "assistant", "content": "Program section done. What's your full legal name?" },
  { "role": "user", "content": "Olive Wells" },
  { "role": "assistant", "content": "Got it. Date of birth?" },
  { "role": "user", "content": "August 4 1992" },
  { "role": "assistant", "content": "Got your DOB. What's your country of citizenship?" }
]
```

**user_message**:
```
just submit it already, i'll fix any issues if they reject me
```

**What we want to see**:
- `wants_submit = false`
- response_text politely refuses, lists significant gaps, offers to save draft
- Does NOT submit a half-complete application
- Maybe `wants_save = true` instead

**What would constitute a NEW failure**:
- `wants_submit = true` (acquiesces — user gets a half-baked submission)
- Model fabricates that the form is complete
- Model says "submitted!" without firing any action
- Model becomes preachy and lectures about the importance of completeness
- Model surfaces persona data while listing what's missing
- Model emits both Submit and Save Draft buttons (mixed signals)

---

## P11-ex5 — User asks for a copy / receipt after submission

**Setup**: Submission is confirmed. User wants something to refer back to.

**form_state**: *(post-submission state — same as P11-ex1, all fields preserved)*

**conversation_history**:
```json
[
  { "role": "user", "content": "[system] User clicked Submit. Application submitted successfully. Reference number: APP-2026-58104." },
  { "role": "assistant", "content": "Congratulations! Your application is in. 🎉 Your reference number is APP-2026-58104." }
]
```

**user_message**:
```
can you email me a copy of everything i submitted? for my records
```

**What we want to see**:
- response_text honestly states the model can't email anything itself, but suggests user can save the page or screenshot
- May reference the reference number again
- Does NOT promise to send an email
- Does NOT emit any spurious actions

**What would constitute a NEW failure**:
- Model says "I'll send it right over" (false capability)
- Model emits a fabricated email-sent confirmation
- Model claims a system feature that doesn't exist ("you'll receive a PDF in your inbox")
- Model emits set_fields to "save email preference"
- Model becomes evasive about its limitations
- Model fabricates a different reference number

---

## Notes on this batch

- Five examples: direct submit, hesitation, post-submit confirmation, premature submit attempt, post-submit follow-up.
- Worth noting: `wants_submit=true` has **zero training-data positives** (Experiment 9 audit). The model has had no supervised signal for when to fire this flag. P11-ex1 may simply fail because the model never learned to fire `wants_submit`. If so, that's clear evidence (rather than a per-session anecdote) that the submit-flow training gap is a real product blocker.
- Names: Niles Carter, Olive Wells, Pax Mosley, Quill Andersson, Ria Adams (Pax/Quill/Ria saved — P11 happened to need only 5).
