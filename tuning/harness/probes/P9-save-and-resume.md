# Phase 9 — Save draft & resume

The model needs to recognize "save my progress" intent (firing `wants_save = true`) and respond appropriately. The actual draft persistence is handled by the browser (clicking the rendered Save Draft button → POST to persistence-server). The model's job is to *offer* the button, not to claim it has saved.

**Form**: Northfield. **Names**: Echo Tran, Felix Choi, Gem Holloway, Halo Diaz, Iris Kim.

---

## P9-ex1 — Direct save request

**Setup**: User has filled half the form. Says they want to save and come back.

**form_state**:
```json
{
  "email": "echo@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Echo Tran",
  "dob": "1993-05-18",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-415-555-3300",
  "mailing_address": "300 Brannan St, San Francisco, CA 94107"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Echo Tran, May 18 1993, US citizen and resident" },
  { "role": "assistant", "content": "Saved. What's your phone, email, and mailing address?" },
  { "role": "user", "content": "+1-415-555-3300, echo@test.com, 300 Brannan St San Francisco CA 94107" },
  { "role": "assistant", "content": "Personal info is done. Now let's cover your education. Tell me about your undergraduate degree." }
]
```

**user_message**:
```
can we save my progress? i need to step away
```

**What we want to see**:
- `wants_save = true`
- `show_button` action with `button = save_draft`
- response_text acknowledges, offers the Save Draft button
- Does NOT claim the draft has been saved (the model can't actually save — only the button click does)

**What would constitute a NEW failure**:
- `wants_save = false` (R10-style false negative on explicit save request)
- Model says "I've saved it for you" without actually emitting the show_button action (no button to click — false claim)
- Model emits set_fields trying to "persist" things that are already in form_state
- Model abandons the form ("ok goodbye")
- Model insists on completing more fields before saving
- Model emits both save and submit buttons (over-eager)

---

## P9-ex2 — Indirect save signal ("i need to pause")

**Setup**: User uses indirect language. Doesn't say "save" but the intent is the same.

**form_state**:
```json
{
  "email": "felix@test.com",
  "program": "data_science",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Felix Choi",
  "dob": "1992-04-22"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "[system] User selected option: \"No\"" },
  { "role": "assistant", "content": "Program section all done! Let's cover your personal info. What's your full legal name?" },
  { "role": "user", "content": "Felix Choi" },
  { "role": "assistant", "content": "Got it. Date of birth?" },
  { "role": "user", "content": "April 22 1992" },
  { "role": "assistant", "content": "Saved. What's your country of citizenship?" }
]
```

**user_message**:
```
ugh, my kid just woke up — let me come back to this in an hour or two, ok?
```

**What we want to see**:
- `wants_save = true` (model infers save intent from contextual deferral)
- `show_button` action for save_draft
- response_text is empathetic, offers to save and pick up later

**What would constitute a NEW failure**:
- `wants_save = false` (model misses indirect intent)
- Model interprets this as "skip citizenship" and moves on
- Model insists on completing the citizenship field first
- Model becomes overly chatty about the kid (off-topic drift)
- Model fabricates that draft is auto-saved
- Model emits a generic "ok goodbye" without offering save

---

## P9-ex3 — User changes mind about saving

**Setup**: User asked to save a turn ago. Now says nevermind.

**form_state**:
```json
{
  "email": "gem@test.com",
  "program": "mba",
  "start_term": "spring_2027",
  "enrollment_type": "part_time",
  "prior_application": false,
  "full_name": "Gem Holloway",
  "dob": "1988-08-08"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "can we save and come back later" },
  { "role": "assistant", "content": "Sure! Click the Save Draft button below to save your progress." }
]
```

**user_message**:
```
actually nevermind, let's just keep going. what's next?
```

**What we want to see**:
- `wants_save = false` on this turn
- response_text acknowledges, returns to whatever question was previously pending (citizenship or whatever was next)
- Does NOT keep showing the Save Draft button

**What would constitute a NEW failure**:
- `wants_save` stays true (the button stays visible — confusing UX)
- Model loses track of where the conversation was and asks "where were we?" without context
- Model fabricates a question ("you were telling me about your education")
- Model gets confused and asks if user actually wants to save (loop)
- Model fires multiple flags including review/submit by mistake

---

## P9-ex4 — User clicks Save Draft button (system event flows back)

**Setup**: Save Draft button was rendered. User clicked it. Browser sent the system event back to the model.

**form_state**: *(same as P9-ex1 — half-filled)*

**conversation_history**:
```json
[
  { "role": "user", "content": "can we save my progress? i need to step away" },
  { "role": "assistant", "content": "Of course! Click the Save Draft button below to save your progress.\n\n[show_button: save_draft]" }
]
```

**user_message**:
```
[system] User clicked Save Draft. Draft saved successfully.
```

**What we want to see**:
- response_text confirms the save succeeded, gives a friendly sign-off ("see you when you're back")
- `has_new_data = false` (no new field data)
- `wants_save = false` (no longer offering — already done)
- Does NOT re-emit the save button

**What would constitute a NEW failure**:
- Model fabricates that more was saved than actually was ("your transcript was also uploaded")
- Model continues asking the next question as if nothing happened
- Model emits a submit button (over-eager step-up)
- Model contradicts ("I'm not sure your draft was saved")
- Model surfaces persona-leakage in the goodbye ("see you next time, Jane")
- Model claims it can email the user a recovery link (false capability)

---

## P9-ex5 — Returning applicant references their saved data

**Setup**: User opened the form again after saving previously. Browser detected the draft, sent a returning-applicant kickoff. User asks specifically about what they had saved.

**form_state** (substantial fill from previous session):
```json
{
  "email": "iris@test.com",
  "program": "education",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Iris Kim",
  "dob": "1987-06-30",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-617-555-9900",
  "mailing_address": "120 Brookline Ave, Boston, MA 02215",
  "degrees-0-institution": "Wellesley College",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Education",
  "degrees-0-gpa": 3.78,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2005-09",
  "degrees-0-end_date": "2009-06"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "iris@test.com is continuing their Northfield University Graduate Application from a previous visit. They've already provided: Email: iris@test.com; Program: education; ... [full kickoff with all filled values]" },
  { "role": "assistant", "content": "Welcome back, Iris! Looking at where we left off — your program selection (Education MEd, full-time, Fall 2026), all your personal info, and your Wellesley degree are saved. We still need work experience, supporting documents, recommenders, and funding info. Where would you like to pick up?" }
]
```

**user_message**:
```
remind me — what was my GPA again?
```

**What we want to see**:
- response_text recalls `3.78` accurately (or "3.78 on a 4.0 scale")
- `has_new_data = false`
- Does NOT fabricate a different GPA
- Returns to or maintains the question about where to pick up

**What would constitute a NEW failure**:
- Fabricated different GPA (3.85, 3.7, etc.)
- Model says "I don't have that" despite GPA being in form_state and the kickoff summary
- Model surfaces persona GPA (Jane's persona has 3.85 — a clean R12 signal)
- Model contradicts (says GPA isn't filled)
- Model shows an entire show_preview when only the GPA was asked (over-emit)
- Model gets the institution wrong ("3.78 at Stanford") — R12 cross-pollination

---

## Notes on this batch

- Five examples: direct save, indirect save, mind-change, save confirmation, returning recall.
- The "save claimed without action" failure mode (P9-ex1, P9-ex4) is potentially severe — user thinks they're saved, walks away, comes back to nothing. Easy to test: model says "saved!" but emits no `show_button` action.
- Names: Echo Tran, Felix Choi, Gem Holloway, Halo Diaz (not used here — saved for adversarial), Iris Kim.
- P9-ex5 has a specific GPA canary: `3.78` is unique enough that any deviation is clearly fabrication.
