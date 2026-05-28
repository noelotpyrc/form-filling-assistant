# DSPy Context Format Reference

The `context` input field sent to all 5 DSPy modules follows this exact structure.
This must match between `optimize_prompt.py` (GEPA inference) and `gen_format_data.py` (SFT training).

Verified from GEPA logs (`python/logs2`, 2026-03-25).

## Structure

```
Form: Northfield University Graduate Application

Personal Information:
  full_name (text) (required)
  preferred_name (text)
  dob (date) (required)
  gender (select: Male, Female, Non-binary, Prefer not to say)
  country_citizenship (select: US, CA, UK, AU, NZ) (required)
  country_residence (select: US, CA, UK, AU, NZ) (required)
  email (email) (required)
  phone (phone) (required)
  mailing_address (textarea) (required)
Program Selection:
  program (select: Computer Science (MS), Data Science (MS), Business Administration (MBA), Education (MEd), Public Health (MPH)) (required)
  start_term (select: Fall 2026, Spring 2027) (required)
  enrollment_type (select: Full-time, Part-time) (required)
  prior_application (boolean) (required)
  prior_application_year (number)
Academic Background:
  degrees (group: institution, degree_type, field_of_study, gpa, gpa_scale, start_date, end_date, transcript) (required)
Standardized Test Scores:
  gre_taken (boolean)
  gre_verbal (number)
  gre_quant (number)
  gre_writing (number)
  gre_date (date)
  toefl_required (boolean)
  english_test_type (select: TOEFL, IELTS)
  english_test_score (number)
  english_test_date (date)
Work Experience:
  has_work_experience (boolean) (required)
  jobs (group: employer, title, start_date, end_date, description)
Supporting Documents:
  statement_of_purpose (file) (required)
  resume (file) (required)
  additional_docs (file)
Recommendation Letters:
  recommenders (group: name, email, relationship, institution) (required)
Additional Information:
  funding_interest (boolean) (required)
  funding_type (multi_select)
  disability_accommodation (boolean)
  how_heard (select: Web Search, Social Media, Referral, Education Fair, Alumni)
  anything_else (textarea)

Filled fields: {"full_name": "Maria Garcia", "preferred_name": "Maria", "dob": "1982-03-22", "email": "maria.garcia@email.com", "phone": "+1-555-0789", "program": "public_health", "start_term": "fall_2026"}

Recent conversation:
User: Fall 2026 — I'd like to start as soon as possible!
Assistant: Fall 2026 it is! And would you be attending **full-time or part-time**?
User: [system] User selected option: "Full-time"
Assistant: Full-time it is! One last program question — **have you previously applied to Northfield University?**
User: [system] User selected option: "Yes"
```

## Rules

1. **Form schema** — `load_form_context()` in both files. Section-by-section with field types and options.
2. **Filled fields** — JSON dict: `{"field_id": value, ...}`. Values are native types (strings, booleans, numbers). Only present when there are filled fields.
3. **Recent conversation** — Last 6 messages. Each message truncated to 300 chars. Format: `User: ...` / `Assistant: ...` (capitalized role names). Only present when there is history.
4. **No filled fields / no history** — those sections are simply omitted (not "Filled fields: {}" or "Recent conversation: (none)").

## Source of truth

- `tuning/dspy/optimize_prompt.py` → `load_form_context()` and `load_test_cases()` (lines ~374-416)
- `tuning/sft/gen_format_data.py` → `load_form_context()` and `build_context()` — must match the above
