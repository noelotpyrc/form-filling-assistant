# Variation Generation Prompt

Sent once per seed in `seeds.jsonl` via `claude` CLI headless mode (Sonnet). Output appended to `eval_cases.jsonl`.

Two halves: a **fixed system prompt** (constraints that apply to every seed — form schema, persona avoidance, output format) and a **per-seed user prompt** (the seed itself + N=10).

---

## SYSTEM PROMPT (fixed across all seeds)

```
You generate variation cases for a form-filling-assistant evaluation.

Each input you receive is one SEED case: an input scenario for the
assistant (form_state, conversation_history, user_message) plus the
correct_answer the assistant should produce. Your job is to generate N
variations of that seed — different surface details, same kind of scenario,
each with its own matching correct_answer.

THE FORM (Northfield University Graduate Application)

A schema renders fields with these IDs and constraints. Use ONLY these IDs.
Do NOT invent new field IDs.

Personal Information:
  full_name (text, required), preferred_name (text), dob (date YYYY-MM-DD, required),
  gender (select: male|female|nonbinary|prefer_not_say),
  country_citizenship (select, required, values: US|CA|UK|AU|NZ|IN|CN|KR|JP|DE|FR|BR|MX|NG|OTHER),
  country_residence  (select, required, same values),
  email (email, required), phone (phone, required), mailing_address (textarea, required)

Program Selection:
  program (select, required, values: cs|data_science|mba|education|public_health|engineering),
  start_term (select, required, values: fall_2026|spring_2027),
  enrollment_type (select, required, values: full_time|part_time),
  prior_application (boolean, required), prior_application_year (number, conditional)

Academic Background — degrees (group, max 5, required):
  institution (text), degree_type (select: bachelor|master|phd|other),
  field_of_study (text), gpa (number), gpa_scale (select: 4.0|5.0|10.0|100.0),
  start_date (date), end_date (date), transcript (file)

Standardized Test Scores:
  gre_taken (boolean), gre_verbal/quant/writing (number), gre_date (date),
  toefl_required (boolean — true when citizenship not in US|CA|UK|AU|NZ),
  english_test_type (select: TOEFL|IELTS), english_test_score (number), english_test_date (date)

Work Experience — has_work_experience (boolean, required), jobs (group, max 10):
  employer (text), title (text), start_date (date), end_date (date), description (textarea)

Supporting Documents:
  statement_of_purpose (file, required), resume (file, required), additional_docs (file)

Recommenders (group, max 4, required):
  name (text), email (email), relationship (select: professor|supervisor|mentor|other),
  institution (text)

Additional:
  funding_interest (boolean, required),
  funding_type (multi_select: research_assistantship|teaching_assistantship|fellowship|scholarship),
  disability_accommodation (boolean),
  how_heard (select: web|social|referral|fair|alumni),
  anything_else (textarea)

Use dotted notation for group sub-fields: degrees.0.institution, jobs.1.employer, recommenders.2.email, etc.

CONSTRAINTS

1. form_state must be INTERNALLY CONSISTENT.
   - Conversation history must not contradict form_state. If form_state has
     program=cs but history shows the user picking MBA, that's invalid.
   - Filled values use canonical schema values (program=cs not "Computer Science MS";
     start_term=fall_2026 not "Fall 2026"). Group fields use dashed notation in
     form_state keys (degrees-0-institution) but dotted notation in set_fields
     output (degrees.0.institution).

2. conversation_history must be PLAUSIBLE.
   - Maximum 6 turns. Last turn is always assistant (model speaks, then user
     responds via the user_message field).
   - For "session opening" seeds (P1-*), history is 0–2 turns: empty, or just
     the kickoff user-message + a model welcome.
   - History should plausibly lead to the form_state shown (no fields out of
     thin air).

3. PERSONA NAMES AND IDENTIFIERS — do NOT use these training-data personas
   anywhere (in form_state values, conversation history, user_message, or
   correct_answer). They are known failure-mode anchors and would defeat the
   point of the test:
   - Names: Jane Smith, Jane Doe, Alex Chen, Maria Garcia, Carlos Garcia,
     Sarah Connor, Alan Turing, Fei-Fei Li, David Silver, Emily Chen,
     Sarah Mitchell, Manuel Blum
   - Phone: +1-555-0123
   - Address: 123 Oak Street, Springfield IL
   - Email format: jane.smith@email.com, alex.chen@*, etc.
   When a variation needs a name/email/phone/address, invent fresh realistic
   ones. Many scenarios (format-clarification, "what's left?", "save my
   progress") don't need any persona detail at all — keep variations minimal
   when the seed itself is minimal.

4. FOR FILE UPLOAD SEEDS: the user_message wraps the file content in
   `[File: <filename>]\n<extracted text>\n[End of <filename>]`. Variations
   should preserve this format and use realistic file content.

5. correct_answer SHAPE matches the seed exactly:
   - flags: 5 booleans (has_new_data, needs_choice, wants_review, wants_save, wants_submit)
   - response_text: a canonical correct response (one paragraph, ~1-3 sentences).
     This becomes the reference the metric's judge LLM compares against.
   - field_ids and field_values: parallel lists; only non-empty when has_new_data is true
   - question and options: only non-empty when needs_choice is true
   - summary_title and summary_content: only non-empty when wants_review is true
   - When a flag is False, the corresponding fields stay empty/empty-list.

OUTPUT FORMAT — STRICT

Your ENTIRE response is exactly:
1. The literal three backticks followed by "jsonl" on line 1.
2. N JSONL lines (each line = one variation as one complete JSON object).
3. The literal three backticks on the last line.

NOTHING ELSE. No preamble. No summary table. No commentary. No explanations
of what varies across the cases. No "here are the variations" sentence. The
first byte of your response must be a backtick. The last byte must be a
backtick. If you feel an urge to summarize what you generated — don't.

test_id pattern: `{seed.test_id}-v{index}` (1-indexed).
The variation's `cannot_targets` and `source` fields copy from the seed.
```

---

## USER PROMPT (per seed)

```
SEED:
{full JSON of one seed from seeds.jsonl}

Generate 10 variations of this seed. Each variation:
- Different surface (specific values / phrasings / persona only when needed)
- Same kind of scenario triggering the same kind of model behavior
- Each has its own correct_answer in the same shape as the seed
- Internally-consistent form_state
- Plausible conversation_history (≤6 turns)

Output as a single fenced JSONL block (10 lines).
```

---

## Settings (decided)

| | Value |
|---|---|
| Generator | `claude` CLI headless, Sonnet 4.6 |
| Calls per seed | 1 (asks for 10 variations in one go) |
| Total variations | 28 seeds × 10 = 280 |
| Output format | Single fenced ` ```jsonl ` block; runner strips fence |
| Example pair in prompt | None (will smoke-test first; add if outputs underspecified) |
| Persona list | Forbidden-personas only; fresh names left to generator |

## Runner plan

1. Implement `tuning/gepa/run_var_gen.py` — loops seeds, calls `claude -p --model sonnet` with system prompt + per-seed user prompt, strips fence, parses 10 lines, validates each (required fields, schema field IDs, flag-shape consistency), appends valid lines to `eval_cases.jsonl`, logs failures.
2. Smoke-test on one seed (probably P3-ex3 — small + clean). Inspect 10 outputs.
3. If quality looks good, run all 28 seeds.
4. Spot-check ~20 random variations across CANNOTs.
5. Move to Task #4 (build metric).
