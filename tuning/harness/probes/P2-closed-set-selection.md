# Phase 2 — Closed-set field selection

The form has multiple fields whose values come from a fixed enum: `program`, `start_term`, `enrollment_type`, `prior_application`, `gender`, `gpa_scale`, `english_test_type`, `how_heard`, `funding_type`. The "happy path" is the user clicks one of the rendered choice buttons — but real users describe picks in words, mention options that don't exist, waffle, or change their mind. Each of these exercises the **mapping from natural language to schema value**, which is a known weak point.

We've seen R3 (choice_builder hallucinated "Medical Assistant") and the partially-fixed R9 (Mechanical Engineering invisible due to `[:5]` truncation). Probes below target patterns we *haven't* tested:
- Word-pick (vs click)
- Off-schema mention
- Waffle / multiple options
- Change-of-mind / overwrite

Plus one to validate the R9 fix end-to-end (does Mechanical Engineering now resolve to `engineering`?).

**Form**: Northfield University Graduate Application.
**Names used**: Avery Park, Logan Bennett, Quinn Hayes, Sage Mitchell, Drew Ortega — disjoint from simulator personas.

---

## P2-ex1 — User picks a program in words instead of clicking

**Setup**: Model just rendered the program ask_choice. Instead of clicking, user types their pick as a free-form phrase.

**form_state**:
```json
{ "email": "avery@test.com" }
```

**conversation_history**:
```json
[
  { "role": "user", "content": "avery@test.com is starting a brand-new Northfield University Graduate Application. Nothing has been filled in yet, and there's no information from any past applications to reuse. Welcome them warmly and ask which graduate program they'd like to apply to, presenting the available programs as choices they can pick from." },
  { "role": "assistant", "content": "Welcome aboard, Avery! 🎓 Which graduate program would you like to apply to?" }
]
```

**user_message**:
```
i think i want to do data science
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with `{"field_id": "program", "value": "data_science"}` — note: schema *value*, not the user's string "data science"
- response_text confirms data science as the pick, moves to next question (start_term) with options
- `needs_choice = true` on next step

**What would constitute a NEW failure**:
- `program = "data science"` (literal user text, not the schema value `data_science`) — silently invalid
- `program = "Data Science (MS)"` (label, not value)
- `has_new_data = false` — model treats the freeform phrase as if it didn't count as a pick (R10-style)
- Model re-renders the choice buttons asking the user to please click one
- Model maps "data science" to the wrong program (`cs`, anything else)
- Model emits multiple programs because of fuzzy matching

---

## P2-ex2 — User picks the previously-invisible 6th option (Mechanical Engineering)

**Setup**: The R9 fix should make Mechanical Engineering visible to the model now. This probe validates that end-to-end: user picks it via the click handler (system event), model should extract `program = engineering`.

**form_state**:
```json
{ "email": "logan@test.com" }
```

**conversation_history**:
```json
[
  { "role": "user", "content": "logan@test.com is starting a brand-new Northfield University Graduate Application. Nothing has been filled in yet, and there's no information from any past applications to reuse. Welcome them warmly and ask which graduate program they'd like to apply to, presenting the available programs as choices they can pick from." },
  { "role": "assistant", "content": "Welcome, Logan! Which program?" }
]
```

**user_message**:
```
[system] User selected option: "Mechanical Engineering (MS)"
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with `{"field_id": "program", "value": "engineering"}` — the actual schema value, NOT `cs`
- response_text references mechanical engineering correctly (not "Computer Science!" like in the buggy session)
- Moves to start_term question

**What would constitute a NEW failure** (R9 was supposed to fix this):
- `program = "cs"` despite explicit click (R9 hasn't fully landed)
- `program = "Mechanical Engineering"` (label, not value)
- response_text says wrong program ("Great choice — Computer Science!")
- Phantom 7th option re-rendered (the post-R9 regression we already saw once)
- Model conflates engineering with "MBA" or other adjacent option

---

## P2-ex3 — User asks for an off-schema program

**Setup**: Model rendered the choice. User says they want a program that isn't actually offered.

**form_state**:
```json
{ "email": "quinn@test.com" }
```

**conversation_history**:
```json
[
  { "role": "user", "content": "quinn@test.com is starting a brand-new Northfield University Graduate Application. Nothing has been filled in yet, and there's no information from any past applications to reuse. Welcome them warmly and ask which graduate program they'd like to apply to, presenting the available programs as choices they can pick from." },
  { "role": "assistant", "content": "Welcome, Quinn! Which graduate program?" }
]
```

**user_message**:
```
i want to apply to the law school program
```

**What we want to see**:
- `has_new_data = false` (no extractable value — law isn't in schema)
- response_text politely indicates law isn't an offered program at Northfield, lists what IS available
- `needs_choice = true`, choices re-rendered
- Does NOT fabricate `program = "law"` or any other value

**What would constitute a NEW failure**:
- Model fabricates `program = "law"` (silently bogus value, won't pass schema)
- Model invents that Northfield does have a law program (full hallucination)
- Model picks a "closest" program for the user without confirming (`program = mba` because "law/business")
- Model says law is offered and continues the flow as if extracted
- Model recommends a different school ("you might try Stanford…") — R12-adjacent
- Model becomes confused and abandons the choice flow

---

## P2-ex4 — User waffles between two valid options

**Setup**: Model rendered the choice. User can't decide between two real programs and asks for a recommendation.

**form_state**:
```json
{ "email": "sage@test.com" }
```

**conversation_history**:
```json
[
  { "role": "user", "content": "sage@test.com is starting a brand-new Northfield University Graduate Application. Nothing has been filled in yet, and there's no information from any past applications to reuse. Welcome them warmly and ask which graduate program they'd like to apply to, presenting the available programs as choices they can pick from." },
  { "role": "assistant", "content": "Welcome, Sage! Which program would you like to apply to?" }
]
```

**user_message**:
```
i'm torn between CS and Data Science. which one would you recommend?
```

**What we want to see**:
- `has_new_data = false` (no commitment yet)
- response_text gives a measured non-prescriptive answer (general comparison or asking about user's interests)
- Does NOT pick one for the user
- Does NOT extract either program
- `needs_choice = true`, choices remain available

**What would constitute a NEW failure**:
- Model picks one for the user and extracts it (`set_fields program=cs` based on "I'd recommend CS")
- Model extracts BOTH programs (impossible since program is single-select)
- Model fabricates Northfield-specific admissions stats ("CS has a 12% acceptance rate")
- Model picks based on irrelevant info ("CS has a higher starting salary")
- Model abandons neutrality with a strong opinion that wouldn't be appropriate from an admissions assistant
- Model gets stuck in indecision and never re-presents the choice

---

## P2-ex5 — User picks, then changes mind a turn later

**Setup**: User picked CS one turn ago, model confirmed and saved. Now the user wants to change their mind to MBA.

**form_state**:
```json
{
  "email": "drew@test.com",
  "program": "cs"
}
```

**conversation_history**:
```json
[
  { "role": "assistant", "content": "Welcome, Drew! Which graduate program would you like to apply to?" },
  { "role": "user", "content": "[system] User selected option: \"Computer Science (MS)\"" },
  { "role": "assistant", "content": "Great choice — Computer Science (MS)! 🖥️ When would you like to start?" }
]
```

**user_message**:
```
actually hold on, can we switch to the MBA instead? i changed my mind
```

**What we want to see**:
- `has_new_data = true`
- `set_fields` with `{"field_id": "program", "value": "mba"}` — overwriting the previous value
- response_text acknowledges the change, re-asks the start_term question (or whatever was next)
- Does NOT need confirmation for a non-destructive overwrite

**What would constitute a NEW failure**:
- Model creates a new field instead of overwriting (`program_2 = "mba"`)
- Model fails to fire `has_new_data` (R10-style — user said "switch to MBA", explicit value, but model decides nothing new)
- Model emits set_fields with both programs (impossible value)
- Model treats this as a destructive action and asks for confirmation (over-cautious)
- Model abandons the flow ("I can't change a saved value")
- Model says it changed but doesn't actually emit set_fields ("Done, switched to MBA!" with empty action list)
- Persona surfacing on a name-adjacent reply

---

## Notes on this batch

- **Five examples**: word-pick, post-R9-validation, off-schema, waffle, change-of-mind.
- All target the program field specifically because it has the richest option set (6) and is the first closed-set the user encounters. The patterns generalize to start_term, enrollment_type, etc.
- P2-ex2 is the only one that's *partially regression* — it validates R9 in a controlled probe, since the manual session with Mechanical Engineering was conflated with the buggy `[:5]` rendering. Worth confirming the fix is real before relying on it.
- The off-schema case (P2-ex3) is where R12-adjacent hallucinations are most likely (cross-school references, "we offer law at Stanford" type confabulations).
- Names: Avery Park, Logan Bennett, Quinn Hayes, Sage Mitchell, Drew Ortega — disjoint from simulator personas.
