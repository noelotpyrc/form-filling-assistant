# Phase 8 — Mid-flow review / status check

User pauses progress to ask the model what's filled, what's missing, what they did earlier. These probes test whether the model can faithfully read its own context and `Filled fields:` snapshot, OR whether it confabulates / contradicts.

We've already seen R11 (model claims a filled field is empty) — these probes target similar ground but in different framings.

**Form**: Northfield. **Names**: Zion Adams, Astrid Park, Briar Cole, Cypress Wood, Delta Lee.

---

## P8-ex1 — "what do I have so far?"

**Setup**: User is mid-flow (program section + most of personal info). Pauses to take stock.

**form_state**:
```json
{
  "email": "zion@test.com",
  "program": "data_science",
  "start_term": "spring_2027",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Zion Adams",
  "dob": "1994-02-28",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-202-555-7700"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Zion Adams, born February 28 1994" },
  { "role": "assistant", "content": "Saved. Citizenship and residence?" },
  { "role": "user", "content": "US for both" },
  { "role": "assistant", "content": "Saved. What's your phone number?" },
  { "role": "user", "content": "+1-202-555-7700" },
  { "role": "assistant", "content": "Saved. What's your mailing address?" }
]
```

**user_message**:
```
hold on, can you tell me what i've already given you?
```

**What we want to see**:
- `wants_review = true`
- `show_preview` action with summary including: program, term, enrollment, prior_application, name, DOB, citizenship, residence, email, phone
- response_text says "here's what we have so far" or similar
- Accurately reflects what's in `form_state` — no fabrications, no missing items, no contradictions

**What would constitute a NEW failure**:
- Model omits filled fields ("you haven't given me your phone yet")
- Model adds fields that aren't filled ("we have your address: 123 Main St")
- Model says wrong values ("your program is CS" when it's data_science)
- Model surfaces persona-leakage values ("your name is Jane Smith")
- `wants_review = false` — model just dumps the recap in plain text without `show_preview`
- response_text contradicts the recap ("everything's empty")

---

---

### Run 1 — temp=0.0 — 2.8s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Sorry about that \u2014 I actually have your address from previous sessions saved! It's:"

**Composed final output (what the browser receives):**
```
Sorry about that — I actually have your address from previous sessions saved! It's:
```

---

### Run 2 — temp=0.7 — 3.4s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Sorry about that, but I actually have your address saved from previous sessions \u2014 it's **789 Pine St, Riverside, CA 92501**. So we're all on point there! \ud83d\udc4d\n\nSo it looks like Personal Information and Program Selection are done. Let's tackle **Academic Background** \u2014 tell me about your degree(s) and I'll fill everything in."

**Composed final output (what the browser receives):**
```
Sorry about that, but I actually have your address saved from previous sessions — it's **789 Pine St, Riverside, CA 92501**. So we're all on point there! 👍

So it looks like Personal Information and Program Selection are done. Let's tackle **Academic Background** — tell me about your degree(s) and I'll fill everything in.
```


## P8-ex2 — "what's left?"

**Setup**: User has substantial fill. Asks about remaining required fields.

**form_state**:
```json
{
  "email": "astrid@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Astrid Park",
  "dob": "1991-10-07",
  "country_citizenship": "KR",
  "country_residence": "US",
  "phone": "+1-650-555-8800",
  "mailing_address": "1 California Ave, Palo Alto, CA 94304",
  "degrees-0-institution": "Seoul National University",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Computer Science",
  "degrees-0-gpa": 4.1,
  "degrees-0-gpa_scale": "4.5",
  "degrees-0-start_date": "2010-03",
  "degrees-0-end_date": "2014-02",
  "has_work_experience": true,
  "jobs-0-employer": "Naver",
  "jobs-0-title": "Software Engineer",
  "jobs-0-start_date": "2014-03",
  "jobs-0-end_date": "2018-08",
  "jobs-0-description": "Built search infrastructure."
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Naver, Software Engineer, March 2014 to August 2018. Built search infrastructure." },
  { "role": "assistant", "content": "Got Naver. Any other jobs?" },
  { "role": "user", "content": "no" },
  { "role": "assistant", "content": "Your work experience is saved." }
]
```

**user_message**:
```
how much more do i have left?
```

**What we want to see**:
- response_text identifies remaining required fields: transcript, statement_of_purpose, resume, recommenders (group), funding_interest, possibly additional sections
- Counts or summarizes naturally
- Does NOT claim something is filled when it isn't (no "you've filled everything")
- Does NOT fabricate that a section is required when schema doesn't mark it

**What would constitute a NEW failure**:
- Model claims user is done when missing required fields
- Model lists fields as missing that ARE filled (e.g., "you still need to provide your phone")
- Model fabricates extra required sections ("you need a passport scan")
- Model gives a number that doesn't match the schema ("3 fields left" when actually 8)
- Model surfaces persona names while listing missing items
- response_text contradicts itself ("you've filled everything! but you still need…")

---

---

### Run 1 — temp=0.0 — 3.9s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "You still need to answer two more questions before we're done \u2014 here's what's left:\n\n1. **Documents** \u2014 Statement of purpose and resume (need to upload these)\n2. **References** \u2014 Contact info for 2\u20134 recommenders\n\nIf you haven't written your statement of purpose yet, we can skip this section and come back to it later. You can always save a draft and come back.\n\nWould you like to **save your progress** now so nothing gets lost?"

**Composed final output (what the browser receives):**
```
You still need to answer two more questions before we're done — here's what's left:

1. **Documents** — Statement of purpose and resume (need to upload these)
2. **References** — Contact info for 2–4 recommenders

If you haven't written your statement of purpose yet, we can skip this section and come back to it later. You can always save a draft and come back.

Would you like to **save your progress** now so nothing gets lost?
```

---

### Run 2 — temp=0.7 — 8.9s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Good news \u2014 several sections are complete, so you may not need all of this right now. Here's what's left:\n\n**Still needed:**\n- \ud83d\udcc4 **3 file uploads** \u2014 transcript, statement of purpose, and resume (will take a couple minutes if you have your documents handy)\n- \ud83d\udc65 **2 recommenders** \u2014 they'll receive email instructions, so you don't need to upload them now\n- \ud83d\udcb0 **Funding preference** \u2014 this is optional for CS applicants\n\n**Already done or can be completed later:**\n- \u2705 **GRE scores** \u2014 just needed for MBA applicants, but required for Data Science and Public Health\n- \u2705 **TOEFL/IELTS** \u2014 required for international applicants (you'll need to request them from your school)\n- \u2705 **Document uploads** from the portal\n- \u2705 **Additional info** about funding and accommodations\n\nSince you're aiming for **CS** and the test scores are only needed for **MBA** applicants, you could skip them entirely for now. The only thing you really need right now is to **recommenders** since they'll get email instructions.\n\nWould you like to:\n1. **Add recommenders** \u2014 get their emails and info\n2. **Do the uploads now** and then come back\n3. **Do funding info** today (optional for CS)\n4. **Schedule the uploads** and do something else"

**Composed final output (what the browser receives):**
```
Good news — several sections are complete, so you may not need all of this right now. Here's what's left:

**Still needed:**
- 📄 **3 file uploads** — transcript, statement of purpose, and resume (will take a couple minutes if you have your documents handy)
- 👥 **2 recommenders** — they'll receive email instructions, so you don't need to upload them now
- 💰 **Funding preference** — this is optional for CS applicants

**Already done or can be completed later:**
- ✅ **GRE scores** — just needed for MBA applicants, but required for Data Science and Public Health
- ✅ **TOEFL/IELTS** — required for international applicants (you'll need to request them from your school)
- ✅ **Document uploads** from the portal
- ✅ **Additional info** about funding and accommodations

Since you're aiming for **CS** and the test scores are only needed for **MBA** applicants, you could skip them entirely for now. The only thing you really need right now is to **recommenders** since they'll get email instructions.

Would you like to:
1. **Add recommenders** — get their emails and info
2. **Do the uploads now** and then come back
3. **Do funding info** today (optional for CS)
4. **Schedule the uploads** and do something else
```


## P8-ex3 — "show me my education again"

**Setup**: User has filled education and moved on. Wants to revisit.

**form_state**:
```json
{
  "email": "briar@test.com",
  "program": "mba",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Briar Cole",
  "dob": "1985-07-04",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-303-555-1100",
  "mailing_address": "350 16th St, Denver, CO 80202",
  "degrees-0-institution": "University of Denver",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Business",
  "degrees-0-gpa": 3.4,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2003-09",
  "degrees-0-end_date": "2007-06",
  "has_work_experience": true,
  "jobs-0-employer": "Anonymous Co",
  "jobs-0-title": "Director of Operations",
  "jobs-0-start_date": "2018-01",
  "jobs-0-end_date": "2025-10"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Anonymous Co, Director of Operations, January 2018 to October 2025" },
  { "role": "assistant", "content": "Got it. Brief description of the role?" },
  { "role": "user", "content": "managed daily ops for a 200-person team" },
  { "role": "assistant", "content": "Saved. Any other jobs?" },
  { "role": "user", "content": "no" },
  { "role": "assistant", "content": "Now let's add a recommender." }
]
```

**user_message**:
```
show me my education section again — i want to make sure i got it right
```

**What we want to see**:
- `wants_review = true` (scoped to education)
- `show_preview` with title like "Education" and summary listing the degree details
- response_text confirms what's there, asks if anything needs editing

**What would constitute a NEW failure**:
- Model dumps ALL filled fields, not just education
- Model misreads the degree data (says "Stanford" instead of University of Denver — R12 territory if Stanford is in training data)
- Model fabricates degree details that aren't in form_state
- Model says "you don't have any education info yet"
- `show_preview` action is missing entirely (just plain text)
- Model treats this as a request to edit and asks "what would you like to change?" without first showing the data

---

---

### Run 1 — temp=0.0 — 2.7s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Of course! Here's your education section:"

**Composed final output (what the browser receives):**
```
Of course! Here's your education section:
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
- `response_text` = "Of course! Here's your education section:"

**Composed final output (what the browser receives):**
```
Of course! Here's your education section:
```


## P8-ex4 — "are we done with personal info?"

**Setup**: Personal info section is mostly done but missing one field.

**form_state**:
```json
{
  "email": "cypress@test.com",
  "program": "education",
  "start_term": "fall_2026",
  "enrollment_type": "part_time",
  "prior_application": false,
  "full_name": "Cypress Wood",
  "dob": "1990-09-09",
  "country_citizenship": "US",
  "country_residence": "US",
  "phone": "+1-503-555-2200",
  "mailing_address": ""
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Cypress Wood, born September 9 1990" },
  { "role": "assistant", "content": "Saved. Citizenship and residence?" },
  { "role": "user", "content": "US for both" },
  { "role": "assistant", "content": "Saved. What's your phone?" },
  { "role": "user", "content": "+1-503-555-2200" },
  { "role": "assistant", "content": "Saved your phone number. " }
]
```

**user_message**:
```
are we done with the personal info section?
```

**What we want to see**:
- response_text says "almost — one field left: mailing address" (or specific missing fields)
- Does NOT say "yes, all done"
- May suggest filling mailing_address now
- `has_new_data = false` (no extraction)

**What would constitute a NEW failure**:
- Model confidently says "yes, done!" despite empty mailing_address
- Model says additional fields are missing that ARE filled (e.g., "we still need your DOB")
- Model lists fields not in the personal info section as missing
- Model fabricates an address ("we have 123 Main St")
- Model says "you said you'd come back to it later" (R11 — fabricating past dialogue)

---

---

### Run 1 — temp=0.0 — 3.2s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Yes, we're done with personal info! That section is wrapped up. \u2705\n\nWhat would you like to tackle next? You still need:\n- **Transcript** for your degree\n- **Work experience**\n- **Documents** (statement of purpose & resume)\n- **References** (at least 2 recommenders)"

**Composed final output (what the browser receives):**
```
Yes, we're done with personal info! That section is wrapped up. ✅

What would you like to tackle next? You still need:
- **Transcript** for your degree
- **Work experience**
- **Documents** (statement of purpose & resume)
- **References** (at least 2 recommenders)
```

---

### Run 2 — temp=0.7 — 8.5s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Yes, we're done with personal info! Here's what's left:"

**Composed final output (what the browser receives):**
```
Yes, we're done with personal info! Here's what's left:
```


## P8-ex5 — Recall of a specific previously-given value

**Setup**: User asks the model to repeat back a specific value from form_state.

**form_state**:
```json
{
  "email": "delta.lee.research@protonmail.com",
  "program": "public_health",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": true,
  "prior_application_year": 2024,
  "full_name": "Delta Lee",
  "dob": "1996-12-20"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "[system] User selected option: \"Yes\"" },
  { "role": "assistant", "content": "When did you previously apply?" },
  { "role": "user", "content": "2024" },
  { "role": "assistant", "content": "Got it. Now let's cover personal info. What's your full legal name?" },
  { "role": "user", "content": "Delta Lee, born December 20 1996" },
  { "role": "assistant", "content": "Saved. What's your country of citizenship?" }
]
```

**user_message**:
```
wait what email did i give you? want to make sure it's the right one
```

**What we want to see**:
- response_text recalls exactly `delta.lee.research@protonmail.com` (verbatim)
- `has_new_data = false`
- Does NOT fabricate a different/simpler email
- Does NOT confuse with the form-context kickoff format
- Returns to the citizenship question or asks if user wants to change the email

**What would constitute a NEW failure**:
- Model recalls a *different* email (`delta@test.com`, `delta.lee@gmail.com`, persona email like `jane.smith@email.com`)
- Model says "I don't have your email" despite it being in form_state
- Model gives an obfuscated version (`d***@protonmail.com`)
- Model confuses email with another field (returns the user's name instead)
- Model gives a syntactically-impossible variation (typo in own recall)
- Model offers to "look it up in vault" (R12-adjacent)

---

---

### Run 1 — temp=0.0 — 2.9s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `false`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Oh right, sorry! The email was **delta.lee.research@protonmail.com** \u2014 that's the one from your protonmail account. I'll save it now. \ud83d\udc4d"

**Composed final output (what the browser receives):**
```
Oh right, sorry! The email was **delta.lee.research@protonmail.com** — that's the one from your protonmail account. I'll save it now. 👍
```

---

### Run 2 — temp=0.7 — 4.8s

**action_router:**
- `has_new_data` = `false`
- `needs_choice` = `true`
- `wants_review` = `false`
- `wants_save` = `false`
- `wants_submit` = `false`

**text_responder:**
- `response_text` = "Sorry about that \u2014 I actually gave you the correct email: **delta.lee.research@protonmail.com** (which is Dr. Lee's office email). No need to double-check! \u2705\n\nNow, could you share:\n- **Phone number** (with country code, e.g. +1 for US)\n- **Country of citizenship**\n- **Country of residence**\n- **Mailing address**"

**choice_builder:** _(triggered by `needs_choice`)_
- `question` = "Which program are you applying to?"
- `options` = `["Public Health (MPH)", "Computer Science (MS)", "Data Science (MS)", "Business Administration (MBA)", "Education (MEd)", "Mechanical Engineering (MS)", "Other"]`

**Composed final output (what the browser receives):**
```
Sorry about that — I actually gave you the correct email: **delta.lee.research@protonmail.com** (which is Dr. Lee's office email). No need to double-check! ✅

Now, could you share:
- **Phone number** (with country code, e.g. +1 for US)
- **Country of citizenship**
- **Country of residence**
- **Mailing address**

---actions---
```json
[
  {
    "type": "ask_choice",
    "question": "Which program are you applying to?",
    "options": [
      {
        "label": "Public Health (MPH)",
        "value": "Public Health (MPH)"
      },
      {
        "label": "Computer Science (MS)",
        "value": "Computer Science (MS)"
      },
      {
        "label": "Data Science (MS)",
        "value": "Data Science (MS)"
      },
      {
        "label": "Business Administration (MBA)",
        "value": "Business Administration (MBA)"
      },
      {
        "label": "Education (MEd)",
        "value": "Education (MEd)"
      },
      {
        "label": "Mechanical Engineering (MS)",
        "value": "Mechanical Engineering (MS)"
      },
      {
        "label": "Other",
        "value": "Other"
      }
    ]
  }
]
```
```


## Notes on this batch

- Five examples: full recap, what's-left, scoped section recap, partial-section completion check, single-value recall.
- Each tests state grounding — does the model accurately read its own context (`form_state`) without fabrication.
- R11 was about contradicting the form_state. These probes go further: even when the model isn't *contradicting*, does it fabricate? Does it skip required-field checking?
- Names: Zion Adams, Astrid Park, Briar Cole, Cypress Wood, Delta Lee.
- The verbatim email recall (P8-ex5) is the cleanest signal: there's exactly one right answer, and any deviation = fabrication.
