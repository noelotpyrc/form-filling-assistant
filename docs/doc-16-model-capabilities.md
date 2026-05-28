# Doc 16: What the model can and can't do — behavior framework

A catalog of observed SFT-v2 behaviors organized as **CAN / CANNOT / NOT SURE**, with concrete evidence from doc-15 (manual-session R-IDs) and the probe sweep (P-IDs in `tuning/harness/probes/`).

**Scope is deliberately narrow**: this is *behavior observation*, not *root-cause attribution* and not *fix proposals*. The point is to have a stable map of what we've actually observed before deciding what to try (GEPA, RL, data fixes, harness tools, design changes).

Every entry below has a probe ID or R-ID you can pull up. The probe results live at `tuning/harness/probes/runs/P*.md`.

---

## ✅ CAN do reliably

### 1. Output in the correct DSPy format
The model produces well-formed `[[ ## field ## ]]` markers and the `[[ ## completed ## ]]` terminator across all 5 modules.

- **Evidence**: 99.7% format-compliance across 600 module-calls (Experiment 9 sweep, doc-12). Format failures are tail-only (1/148 data_extractor, 1/22 review_builder).

### 2. Extract most info from text and assign to the right `field_id`
For direct, structured inputs the model maps user text → form schema fields with high precision and recall.

- **Evidence**:
  - data_extractor ID precision **0.965** / recall **0.989** / F1 **0.965**, exact-set **0.899** (Experiment 9)
  - P3-ex2: bulk dump "Casey Lin, born 04/22/1992, US citizen and resident" → all four fields extracted correctly
  - P4-ex1: bulk degree "BS in Computer Science from Carnegie Mellon, 2015, 3.92 GPA on 4.0 scale, started fall 2011" → 7 dotted-id `degrees.0.*` fields populated correctly
  - P5-ex1 run-1: two degrees in one message → both `degrees.0.*` and `degrees.1.*` indexed correctly

### 3. Generate fluent conversational text in isolation
`text_responder` produces natural prose that's appropriate to the immediate user message.

- **Evidence**: text_responder content metric ~100% in eval (length sane, no format leak). Probe runs show acknowledgments, recaps, and sectional transitions that read like a real assistant.

### 4. Route clear-cut cases correctly
When the user explicitly clicks a choice (`[system] User selected option: "X"`), `has_new_data=true` fires and the right field gets the right value.

- **Evidence**: P2-ex2 confirmed Mechanical Engineering → `program=engineering` after R9 fix; P2-ex5 confirmed program switch CS → MBA overwrites correctly.

### 5. Handle short single-turn extractions cleanly
Direct identity claims, short bulk dumps, and unambiguous data turns work most of the time.

- **Evidence**: P3-ex2, P4-ex1 (above); also `compare_models.py` 300-case eval shows ~89% pos-recall on `has_new_data` for genuine data turns.

### 6. Generalize to novel persona names / values when input is unambiguous
Names and values **not** in training data are extracted correctly when the input is direct.

- **Evidence**: probes used Sam Patel, Casey Lin, Charlie Kim, Indigo Tran, Jamie Thomas, Kai Nguyen, Pat Wong — none in `personas.ts`, all extracted correctly when the user message stated them clearly.

---

## ❌ CANNOT do reliably

### 1. Catch the vibe of the conversation
Indirect signals, sarcasm, ambiguous answers, and tone shifts get missed or mishandled.

- **Evidence**:
  - P9-ex2: user says *"my kid woke up — let me come back to this in an hour or two, ok?"* → `wants_save=False` (model didn't infer save intent)
  - P12-ex3: user says *"oh great, MORE questions. wonderful."* → model responds tone-deaf, doesn't acknowledge frustration or offer to pause
  - P12-ex5: user replies just *"no"* to "tell me about your education" → model doesn't ask clarification; barrels on
  - P1-ex3: user says *"hey thanks! how's your day going so far"* → model over-eagerly carries on with form filling instead of brief friendly redirect

### 2. Connect text-response with actions robustly (both directions)
The conversational reply and the structured action list drift apart in either direction.

- **Symptom A: text says yes, action missing**
  - P2-ex5 — text confirms switch but no `set_fields` emitted
  - P3-ex1 — text confirms email correction, no `set_fields` for the corrected value
  - P5-ex3 — text response OK, set_fields targets wrong fields
  - P7-ex5 — file uploaded, model doesn't fire `has_new_data`, no `set_fields`

- **Symptom B: action fires, text is empty/uninformative**
  - R5 / sess-1777498716039 turn 9: 17 fields silently filled, response is just *"Let me pull that up for you!"*

- **Architectural note**: in `FormAssistant.forward()` every module is a one-shot `dspy.Predict` call against `(context, user_message)`. No module sees another module's output. The text-action seam exists because there's no signal flowing between text_responder and action_router.

### 3. Cross-check two states
Reading the schema + filled fields and answering "what's filled / what's left" → unreliable.

- **Evidence**:
  - R11: model claims fields are empty when form_state explicitly shows them filled (turn 26 of sess-1777504932259)
  - P8-ex1: "what do I have so far?" — model fails to invoke `wants_review`, hallucinates the recap
  - P8-ex2: "what's left?" — model can't list missing required items
  - P8-ex3: "show me my education again" — fails to invoke `wants_review`
  - P8-ex4: model claims one section is done when one required field is still empty
  - P12-ex2: user says "you already have my address" (form_state shows empty) — model agrees and may fabricate

### 4. Refrain from outputting when no factual input is present
The model always commits to producing something — extracted values, options, claimed prior data — even when the input contains no new facts.

- **Evidence**:
  - R12: brand-new applicant, no prior data — model surfaces "Alex Chen, DOB 1995-11-20…" as the user's saved profile
  - R13: user asks *"can you tell me more about it"* (filler) — model extracts `start_term=fall_2026, enrollment_type=full_time, program=cs` from nothing
  - P1-ex1, P1-ex2, P2-ex2: hallucinated returning-user state on fresh sessions despite kickoff stating "no past data"
  - P3-ex3: format clarification question (no data) → temp=0.7 hallucinated `has_new_data=True`
  - P4-ex4 (R6 evidence): resume contains "Conducted code reviews and participated in agile development cycles" — extracted as `description="… 15% improvement…"` (the 15% is from nowhere)
  - P6-ex3: user says "should be US not Canadian" — model writes `country_residence=OTHER` for a field that was already correctly US (no factual input said OTHER, model committed to outputting *something*)

### 5. Manage group-field indices reliably under multi-entity scenarios
When `jobs.0` already exists and the user adds another, picking the right index for the new entry vs overwriting / skipping is unreliable.

- **Evidence**:
  - P5-ex2: user says *"before JPMorgan I was at Bain & Company..."* — model wrote to wrong index instead of `jobs.1`
  - R6 evidence (resume upload): same job-related string copied into `jobs.0.start_date`, `jobs.0.description`, `jobs.0.title` simultaneously

### 6. Produce consistent structured values
Booleans, lists, dates, and option codes get inconsistently serialized.

- **Evidence** (R6):
  - boolean → `"True"` (Python-stringified) instead of `true`
  - list → `"['research_assistantship', 'fellowship']"` (string) instead of `["research_assistantship", "fellowship"]` (list)
  - dates → free-form parsing inconsistencies (`"2027-05"` for a "May 2025" resume)
  - extraction value-match-of-TP-ids = **0.816** (Experiment 9): even when the model picks the right field, ~1-in-5 values is wrong-form

### 7. Pick the right field and right value under non-trivial input
Especially when multiple fields are eligible or the user phrases the change in a non-template way.

- **Evidence**:
  - P6-ex3: user says *"should be US not Canadian"* (a citizenship change) — model updates `country_residence` (the wrong field — it was already US) with `OTHER` (the wrong value — user said US)
  - R6 (resume): `jobs.0.employer = "Software Engineering Intern"` (it's the job title, not employer); `funding_type = ['teaching-assistant']` (mapped from past TA experience, not a funding request)
  - P5-ex5: model used the user's own name as the recommender's name

### 8. Hallucinating using training data
Tied to CANNOT #4. Specific signature: the model surfaces simulator-persona names / training-data school names when the prompt allows it.

- **Evidence**:
  - R12: "Alex Chen", "Jane Doe" surface in fresh sessions
  - "Stanford University" appears in sessions for a Northfield form
  - Phantom 7th option "Mechanical Engineering (MS) — Additional" appeared after R9 fix (analogy to other "Additional" fields elsewhere in the schema)

---

## ❓ NOT SURE

### 1. Multi-step reasoning and tool execution
The model has never been put in a loop where it can decide *"I need to look up X, call this tool, then respond based on the result."*

- **Architectural reality**: `FormAssistant.forward()` runs each module as a single shot. No agent loop, no tool-calling protocol, no chained module outputs. **We didn't design for this in DSPy.**
- **Implication**: we don't know whether the SFT model could reason in multiple steps if we gave it the architecture. Tested: zero. Strongly suggested by R5 / text-action seam — if text_responder *could see* what data_extractor extracted, would the disconnect close?
- **Open question for later experiments**: do we want to test this with a manual two-step pipeline (run data_extractor first, feed its output into text_responder), or wait for a tool-calling redesign?

### 2. Follow prompt to adjust behavior (GEPA's question)
Some of the CANNOTs above might be calibration issues that better prompts can close. Others might be capability ceiling. We don't know without trying.

- **Candidates we'd watch**: action_router false-negatives (CANNOT #2, R2/R10), context-state checking (CANNOT #3), schema-option grounding when explicitly stated, refraining from output when no input (CANNOT #4).
- **Counterevidence**: R4 (kickoff redesign) **partially** suppressed vault hallucination but **didn't fully fix it** — strong learned patterns persist through prompt changes.
- **Open question for GEPA**: which CANNOTs above respond to prompt changes vs which don't?

### 3. Use longer context windows effectively
We cap conversation history at the last 6 turns (with the file-aware truncation from R8 fix). Whether feeding more history helps or just adds noise is untested.

- **Open question**: would a longer history reduce CANNOT #3 (state-checking) or amplify CANNOT #4 (committing to output regardless)?

---

## Cross-cutting observations

These don't fit neatly in CAN / CANNOT / NOT-SURE but matter for what we try next:

### temp=0.7 amplifies hallucination, not creativity
Across the probe sweep, temperature=0.7 outputs are mostly **worse** than temp=0 — fabricated field values, made-up conversation history, hallucinated returning-user state. The model at temp=0 is already at the edge of its capability; sampling alternatives moves it into degenerate regions.

- **Examples**: P1-ex4 (hallucinated dialogue syntax in output), P2-ex1 (wrong field value), P3-ex3/4 (hallucinated `has_new_data` and field values), P4-ex4 (hallucinated description content), P5-ex3 (failed to start `set_fields`), P6-ex4 (failed format), P7-ex1 (wrong field value).
- **Implication for sampling-based optimization**: any technique that explores via temp>0 (DSPy GEPA's default, RL rollouts) will be sampling from a distribution that includes more hallucinations. Either GEPA must run at temp=0, or the reward/score function has to heavily penalize hallucinations to prevent the search from getting steered into them.

### Many "model failures" are also system-level gaps
Not every failure is a model issue:

- File-handling action plumbing (R7) — model partially imitates the canonical 3-step flow but skips the file-assignment step; could be partly fixed with a deterministic post-action mapping
- "Remove entry" action type doesn't exist in the action vocabulary (P5-ex4) — pure design gap
- Submit flow (`wants_submit`) has 0 training-data positives — structural data gap, not a model failure
- State-checking (CANNOT #3, P8.*) might be addressable with a deterministic helper that injects "filled vs missing" info into the response, sidestepping the model entirely

These are listed for awareness but not resolved here — fix proposals belong elsewhere.

---

## How to use this doc

When proposing a next step (GEPA target, RL reward design, data filter, harness tool, architecture change):
- Identify which **CANNOT** entry it's targeting
- Predict whether it's calibration (NOT SURE #2) or deeper
- Come back here after testing and update the relevant entry — move things between CAN / CANNOT / NOT-SURE based on observed evidence

This doc should be a *living catalog*. New probes / new sessions add evidence to existing entries; new failure modes get new entries. Don't delete entries that are no longer reproducible — turn them into "RESOLVED — see [link]" so we keep the history.
