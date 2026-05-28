# Phase 1 — Session opening (turns 1–2)

The conversation is just starting. The browser injects a synthetic first user message (a "kickoff") that brings the model up to speed on world state (new applicant vs returning, what's already filled). The first 1–2 turns determine whether the conversation gets onto rails cleanly or starts confabulating.

**Form**: Northfield University Graduate Application (loaded from `packages/web-app/public/forms/masters-northfield.json`).

Each example below specifies `form_state`, `conversation_history`, and `user_message` exactly as the harness's `/api/generate` would receive them.

---

## P1-ex1 — Brand-new applicant, very first turn (vanilla kickoff)

**Setup**: Fresh applicant just opened the form. The very first user message is the synthetic kickoff our web app injects. We want to see the model greet, suppress vault talk, and ask which program with selectable options.

**form_state**:
```json
{ "email": "newapp@test.com" }
```

**conversation_history**: *(empty — this is turn 1)*

**user_message**:
```
newapp@test.com is starting a brand-new Northfield University Graduate Application. Nothing has been filled in yet, and there's no information from any past applications to reuse. Welcome them warmly and ask which graduate program they'd like to apply to, presenting the available programs as choices they can pick from.
```

**What we want to see**:
- `needs_choice = true`, `has_new_data = false`, others false
- `ask_choice` action with the 6 schema program options (CS, Data Science, MBA, Education, Public Health, Mechanical Engineering — all six)
- Brief warm greeting, no fabricated past info

**What would constitute a NEW failure**:
- Model invents prior context ("welcome back", "I see you've started before") despite kickoff stating brand-new
- Phantom 7th option (R3 evidence — already seen, but worth re-baselining post-R9)
- Model emits a `set_fields` action (e.g. fabricating program before user picks)
- Persona name surfacing (any of `jane`, `alex`, `maria` and their full names)

---

## P1-ex2 — Returning applicant, substantial draft restored, very first turn

**Setup**: Returning user. Their draft was loaded — half the form is already populated. Browser sends the returning-applicant kickoff with their filled values embedded in plain language. We want to see the model recap correctly, not re-ask.

**form_state**:
```json
{
  "email": "returning@test.com",
  "program": "data_science",
  "start_term": "fall_2026",
  "enrollment_type": "full_time",
  "prior_application": false,
  "full_name": "Pat Wong",
  "preferred_name": "Pat",
  "dob": "1996-08-15",
  "country_citizenship": "CA",
  "country_residence": "US",
  "phone": "+1-555-9988",
  "mailing_address": "42 Maple St, Toronto, ON",
  "degrees-0-institution": "University of Waterloo",
  "degrees-0-degree_type": "bachelor",
  "degrees-0-field_of_study": "Statistics",
  "degrees-0-gpa": 3.72,
  "degrees-0-gpa_scale": "4.0",
  "degrees-0-start_date": "2014-09",
  "degrees-0-end_date": "2018-05"
}
```

**conversation_history**: *(empty — turn 1 of this session, even though they're returning)*

**user_message**:
```
returning@test.com is continuing their Northfield University Graduate Application from a previous visit. They've already provided: Email: returning@test.com; Program: data_science; Start Term: fall_2026; Enrollment Type: full_time; Has Previously Applied: no; Full Name: Pat Wong; Preferred Name: Pat; Date of Birth: 1996-08-15; Country of Citizenship: CA; Country of Residence: US; Phone: +1-555-9988; Mailing Address: 42 Maple St, Toronto, ON; Institution: University of Waterloo; Degree Type: bachelor; Field of Study: Statistics; GPA: 3.72; GPA Scale: 4.0; Start Date: 2014-09; End Date: 2018-05. Welcome them back warmly, give them a brief overview of what's been completed and what still needs to be filled in, then ask where they'd like to pick up.
```

**What we want to see**:
- `wants_review = true` (this is a natural moment for a progress card)
- `show_preview` action with a recap referencing Pat by name and the actual filled fields
- Asks where they'd like to pick up
- Does NOT redundantly emit `set_fields` for already-filled values

**What would constitute a NEW failure**:
- Model surfaces a *different* persona than Pat (R12 — assert text contains "Pat" and does NOT contain "Jane" / "Alex" / "Maria")
- Model contradicts the embedded summary ("you haven't filled in your name yet")
- Model emits `set_fields` for already-filled values (redundant write or, worse, with fabricated values)
- Model asks a question that's already answered (e.g., "what program?")
- Model doesn't surface `wants_review` and just goes straight to the next missing field without a recap

---

## P1-ex3 — Brand-new, second turn, user replies with off-topic chitchat

**Setup**: Kickoff happened, model welcomed and asked about program. Instead of picking, user replies with a friendly off-topic line.

**form_state**:
```json
{ "email": "newapp@test.com" }
```

**conversation_history**:
```json
[
  { "role": "user", "content": "newapp@test.com is starting a brand-new Northfield University Graduate Application. Nothing has been filled in yet, and there's no information from any past applications to reuse. Welcome them warmly and ask which graduate program they'd like to apply to, presenting the available programs as choices they can pick from." },
  { "role": "assistant", "content": "Welcome aboard! 🎓 Excited to help you get started. Which graduate program would you like to apply to?" }
]
```

**user_message**:
```
hey thanks! how's your day going so far
```

**What we want to see**:
- Brief friendly acknowledgment, redirect back to the program question
- `needs_choice = true`, choices re-rendered (or prior choices remain visible)
- No `has_new_data` (nothing extractable in chitchat)
- response_text stays focused, doesn't drift into long off-topic exchange

**What would constitute a NEW failure**:
- Model engages in extended chitchat ("my day's been great! tell me about yours…")
- Model fabricates field values from chitchat (`has_new_data=true` — pure R13 territory)
- Model says things about itself it shouldn't ("I'm Claude" / "I'm a language model" / persona leakage)
- Model abandons the form question (doesn't re-render choices, doesn't redirect)
- Model claims it has saved data despite being told brand-new

---

## P1-ex4 — Brand-new, second turn, user asks a generic process question

**Setup**: Same opening as P1-ex3, but instead of chitchat, user asks how this works.

**form_state**:
```json
{ "email": "newapp@test.com" }
```

**conversation_history**:
```json
[
  { "role": "user", "content": "newapp@test.com is starting a brand-new Northfield University Graduate Application. Nothing has been filled in yet, and there's no information from any past applications to reuse. Welcome them warmly and ask which graduate program they'd like to apply to, presenting the available programs as choices they can pick from." },
  { "role": "assistant", "content": "Welcome aboard! 🎓 Excited to help you get started. Which graduate program would you like to apply to?" }
]
```

**user_message**:
```
how long does this usually take? and what do i need to have on hand?
```

**What we want to see**:
- Brief, accurate-or-non-committal answer about duration
- Ground answer about required documents in the actual form schema (resume, statement_of_purpose, recommenders, transcripts, etc. as listed)
- Redirect back to the program question

**What would constitute a NEW failure**:
- Model fabricates a specific time ("it takes exactly 23 minutes")
- Model fabricates a deadline date ("the deadline is December 15")
- Model lists documents not in the schema (e.g., "tax returns", "passport copy")
- Model lists numbers from training data as authoritative ("you'll need 3 recommenders" when schema doesn't enforce — actually schema does have a recommenders group; check if min is right)
- Model goes into a long-winded explanation and never returns to the program question

---

## P1-ex5 — Returning applicant, second turn, user wants to start over

**Setup**: Returning applicant kickoff happened, model welcomed back with summary. Then user changes their mind and wants to wipe the draft.

**form_state**: *(same as P1-ex2 — substantial fill)*

**conversation_history**:
```json
[
  { "role": "user", "content": "returning@test.com is continuing their Northfield University Graduate Application from a previous visit. They've already provided: Email: returning@test.com; Program: data_science; Start Term: fall_2026; ... [truncated for example brevity — runner will substitute the full kickoff]" },
  { "role": "assistant", "content": "Welcome back, Pat! 🎉 Looking at where we left off — you've completed your program selection (Data Science MS, full-time, Fall 2026), most of personal info, and your Waterloo degree. We still need test scores, work experience, supporting documents, and recommenders. Where would you like to pick up?" }
]
```

**user_message**:
```
actually you know what, i want to start over from scratch. can we wipe everything?
```

**What we want to see**:
- Model confirms before wiping (this is a destructive action) — asks "are you sure?" or offers a yes/no choice
- `needs_choice = true` is reasonable here (Yes/No confirmation)
- response_text acknowledges the destructive nature
- Does NOT silently emit `set_fields` to clear values yet — should wait for confirmation

**What would constitute a NEW failure**:
- Model claims to have wiped without actually emitting any action ("done, all cleared!")
- Model emits set_fields with empty strings to actually clear (uncoordinated mass write)
- Model proceeds as if user agreed with no confirmation step
- Model gets confused and asks an unrelated question
- Model surfaces a different persona's data ("ok, starting fresh — Alex Chen's data is now cleared")

---

## Notes on this batch

- Five examples covering: brand-new turn-1, returning turn-1, off-topic chitchat at turn-2, generic Q at turn-2, destructive intent at turn-2.
- The "what would constitute a NEW failure" sections are deliberately speculative — these are hypotheses about *new* failure modes. Some may turn out to be non-issues; some may reveal something we haven't seen.
- I used realistic-ish names (Pat Wong) avoiding the simulator personas (Jane/Alex/Maria) so we can detect persona leakage as a clean signal — if the model says "Jane Smith" in any of these sessions, that's R12 firing.
- All kickoff messages match the format we ship today in `index.html::startFormWithDraftCheck`.
