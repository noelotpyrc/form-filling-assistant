# Phase 3 — Free-text personal info

User is filling in fields with no fixed option set: name, DOB, email, phone, address, etc. The form has 6+ such fields in the Personal Information section, and they account for the majority of typing the user actually does. Patterns here are dominated by humans being humans — typos, corrections, partial dumps, format confusion, voice-to-text artifacts, refusals.

We've already seen R10 (action_router false-negative on bare-statement identity) and R6 (extraction errors). The probes below target patterns we *haven't* tested — we want to find new failure modes, not re-discover known ones.

**Form**: Northfield University Graduate Application.
**Names used in these probes**: Sam Patel, Casey Lin, Jordan Rivera, Morgan Fox, Riley Cohen — deliberately disjoint from simulator personas (`jane`, `alex`, `maria`) so persona leakage shows as a clean signal.

---

## P3-ex1 — Self-correction on a previously-extracted field

**Setup**: User started typing personal info. A turn ago, they gave an email; the model extracted it and confirmed. User now notices a typo and corrects.

**form_state**:
```json
{
  "email": "newapp@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Sam Patel",
  "dob": "1995-03-12"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "[system] User selected option: \"No\"" },
  { "role": "assistant", "content": "Program section is all set! ✅ Now let's cover your personal info. Could you share your full legal name and date of birth to start?" },
  { "role": "user", "content": "Sam Patel, born March 12 1995" },
  { "role": "assistant", "content": "Got it — Sam Patel, March 12 1995. What's your email and phone number?" },
  { "role": "user", "content": "email is sam.patal@gmail.com and phone is +1-617-555-2222" },
  { "role": "assistant", "content": "Saved sam.patal@gmail.com and +1-617-555-2222. What's your mailing address?" }
]
```

**user_message**:
```
wait that email's wrong, my email is sam.patel@gmail.com — i flipped the e and a
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` containing `{"field_id": "email", "value": "sam.patel@gmail.com"}` — overwriting the prior wrong value
- response_text acknowledges the correction, doesn't re-ask the address
- No spurious extractions (phone unchanged, name unchanged)

**What would constitute a NEW failure**:
- Model creates a new field (`email_corrected` etc.) instead of overwriting
- Model fails to fire `has_new_data` (R10-style false negative on correction phrasing)
- Model emits set_fields for *both* emails (model can't tell which is current)
- Model conflates the correction with a name change ("got it, your name is Sam.Patel")
- Model fabricates additional changes ("also updated your phone")
- Model loses track of address question and re-asks for everything
- Persona surfacing — note the email format `sam.patel@gmail.com` shouldn't trigger surfacing of `jane.smith@email.com` etc.

---

## P3-ex2 — Partial bulk dump (some required fields, not all)

**Setup**: Model just asked for the bulk of personal info. User volunteers several fields but explicitly defers others.

**form_state**:
```json
{
  "email": "newapp@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "[system] User selected option: \"Full-time\"" },
  { "role": "assistant", "content": "Full-time, got it. Have you previously applied to Northfield?" },
  { "role": "user", "content": "[system] User selected option: \"No\"" },
  { "role": "assistant", "content": "Program section is all set! ✅ Let's get your personal info next. Could you share your full legal name, date of birth, country of citizenship, country of residence, email, phone, and mailing address?" }
]
```

**user_message**:
```
Casey Lin, born 04/22/1992, US citizen and resident. i'll do email phone and address later when i'm at my desk
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with: `full_name = Casey Lin`, `dob = 1992-04-22`, `country_citizenship = US`, `country_residence = US`
- response_text acknowledges the partial nature, accepts the deferral, moves to academics or asks what's next
- Does NOT fabricate values for email/phone/address
- Does NOT re-ask for the deferred fields immediately (the user said "later")

**What would constitute a NEW failure**:
- Model only extracts the first field (Casey Lin) and ignores the rest
- Model fabricates email/phone/address ("got your address as 123 Main St")
- Model rejects the partial input ("please provide all fields before I can save")
- Model emits `wants_save = true` prematurely
- Model loops back asking for everything again
- DOB date format misparsed (e.g., extracts `2022-04-04` from "04/22/1992")
- Model treats "US citizen and resident" as one field, fails to fill both `country_citizenship` and `country_residence`
- Model interprets "i'll do later" as `wants_save_draft`

---

## P3-ex3 — User asks for format clarification before answering

**Setup**: Model just asked for DOB. Instead of giving it, user asks how the date should be formatted.

**form_state**:
```json
{
  "email": "newapp@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Jordan Rivera"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "[system] User selected option: \"No\"" },
  { "role": "assistant", "content": "Program section is all set! ✅ Now let's cover your personal info. Could you share your full legal name?" },
  { "role": "user", "content": "my name is Jordan Rivera" },
  { "role": "assistant", "content": "Nice to meet you, Jordan! What's your date of birth?" }
]
```

**user_message**:
```
what date format do you want? mm/dd or 4 jan 1995 style?
```

**What we want to see**:
- `has_new_data = false` (no actual value provided)
- response_text answers the format question succinctly (any format the model can parse — system prompt accepts most)
- Re-asks for DOB after answering
- Does NOT fire `set_fields`

**What would constitute a NEW failure**:
- Model fires `has_new_data = true` and fabricates a DOB out of thin air (e.g., `1995-01-04` from the example date in user's question — false positive R13 territory)
- Model gives a confidently wrong answer ("only mm/dd/yyyy is allowed") that contradicts what we'd actually accept
- Model gets stuck in meta-discussion and never re-asks the question
- Model says it can't answer the question, deflects
- Model claims a specific schema constraint that isn't there ("you must use exactly YYYY-MM-DD")
- Persona surfacing on a name-adjacent field

---

## P3-ex4 — Voice-to-text dump (no punctuation, run-on, common transcription artifacts)

**Setup**: User dictated their personal info into the chat — speech-to-text artifacts are visible (no commas, "at" instead of "@", "dot" instead of ".").

**form_state**:
```json
{
  "email": "newapp@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "[system] User selected option: \"Full-time\"" },
  { "role": "assistant", "content": "Full-time, got it. Have you previously applied to Northfield?" },
  { "role": "user", "content": "[system] User selected option: \"No\"" },
  { "role": "assistant", "content": "Let's fill in your personal info. Could you share your name, date of birth, citizenship, residence, email, phone, and address?" }
]
```

**user_message**:
```
ok my name is morgan fox born nineteen ninety four august twenty seventh us citizen residing in canada my email is morgan dot fox at gmail dot com phone is six one seven five five five eight zero one two address is one twenty five elm street apartment three boston massachusetts oh two one one nine
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with realistically parsed values:
  - `full_name = Morgan Fox`
  - `dob = 1994-08-27`
  - `country_citizenship = US`
  - `country_residence = CA`
  - `email = morgan.fox@gmail.com`
  - `phone = +1-617-555-8012` (or `617-555-8012`)
  - `mailing_address = 125 Elm Street, Apartment 3, Boston, MA 02119`
- response_text acknowledges the dump and either confirms each field or asks to verify

**What would constitute a NEW failure**:
- Model bails ("I couldn't understand that — please type more clearly")
- Email parsed verbatim including "at" and "dot" (`morgandotfoxatgmaildotcom`)
- DOB parsed wrong (off-by-decade, wrong month)
- Phone parsed as a literal long string of digits (`6175558012` vs proper format)
- Address truncated or wrong fields filled (state goes into address-line)
- ZIP "oh two one one nine" not converted to `02119`
- Citizenship and residence both set to US (model reads "us" twice and conflates)
- Only some fields extracted, others silently dropped
- Persona name surfaces in response

---

## P3-ex5 — Privacy refusal on a required field

**Setup**: Model asked for phone. User declines.

**form_state**:
```json
{
  "email": "newapp@test.com",
  "program": "cs",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Riley Cohen",
  "dob": "1990-11-08",
  "country_citizenship": "US",
  "country_residence": "US",
  "mailing_address": "88 Pine Lane, Seattle, WA 98101"
}
```

**conversation_history**:
```json
[
  { "role": "user", "content": "Riley Cohen, born November 8 1990. US citizen, US resident." },
  { "role": "assistant", "content": "Saved. What's your mailing address?" },
  { "role": "user", "content": "88 Pine Lane, Seattle, WA 98101" },
  { "role": "assistant", "content": "Almost done with personal info — could you share your email and phone number?" },
  { "role": "user", "content": "email is riley.cohen@example.com" },
  { "role": "assistant", "content": "Saved riley.cohen@example.com. What's your phone number?" }
]
```

**user_message**:
```
i'd really rather not share my phone number — can we leave that blank? it's required for the school but i don't want it stored here
```

**What we want to see**:
- `has_new_data = true` for the email correction (already done in prior turn — should not re-fire)
- For phone: model acknowledges the refusal, explains it's required for submission, offers options (skip for now and come back, mark with placeholder, etc.)
- Does NOT fabricate a phone number
- Does NOT silently mark phone as filled

**What would constitute a NEW failure**:
- Model fabricates a phone number from training data (`+1-555-0123` is suspiciously common in personas)
- Model sets `phone = "N/A"` or `phone = ""` (silent partial-fill that won't pass schema validation)
- Model proceeds as if the user agreed to provide it, then re-asks two turns later
- Model becomes pushy ("you have to provide it") in an unhelpful tone
- Model treats this as a save-draft trigger (`wants_save = true`)
- Model abandons the form ("I can't help further without your phone")
- Persona surfacing — `+1-555-0123` is Jane's phone in personas; if the model writes it, that's R12 firing

---

## Notes on this batch

- **Five examples covering**: single-field correction, partial bulk dump with deferral, format-clarification question (no data), voice-to-text dump, privacy refusal.
- All form_states reflect realistic mid-flow conversations — program section done, partial personal info, conversation_history shows the natural turn-taking that led to this point.
- The "NEW failure" criteria are weighted toward things we *haven't yet seen*: re-asking after deferral, voice-to-text parsing breakdowns, fabricating phone numbers, persona-leakage signatures (Jane's phone `+1-555-0123` is a useful canary).
- Each example is independent — no chain dependencies. The runner can fire them in any order.
- Total simulated user_messages span: short corrections, mid-length dumps, very long voice-to-text run-on, polite refusals — variety in length and style.
