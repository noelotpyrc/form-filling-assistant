# Tier-1 failures — student_s2cresp_dormant_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2cresp-mlx` (port 8104, $0)  
Eval set: 13 cases, sha16 `72fbba993907c104`  
Overall pass: **0/13**  

| check | pass | rate |
|---|---|---|
| format | 13/13 | 100.0% |
| directive | 0/13 | 0.0% |
| grounding | 13/13 | 100.0% |
| echo | 13/13 | 100.0% |
| verbosity | 13/13 | 100.0% |
| repetition | 13/13 | 100.0% |

## directive — 13 failing case(s)

### s156 t10  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'has_work_experience']]`
- directive reason: dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks! I've recorded your TOEFL score of 110.
  > 
  > Do you have relevant work experience?

### s161 t8  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'email']]`
- directive reason: dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing that! 105 is a solid score.
  > 
  > Now, could you please share your email address?

### s160 t11  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'mailing_address']]`
- directive reason: dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks! Your TOEFL score of 98 has been recorded.
  > 
  > Now I'll need your mailing address to continue. Please provide your complete mailing address.

### s160 t1  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'program']]`
- directive reason: dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks! Your TOEFL score has been recorded as 100.
  > 
  > Now, which program would you like to apply for?

### s147 t16  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'funding_type']]`
- directive reason: dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for confirming! Your TOEFL score of 100 has been recorded.
  > 
  > Now, **what is your preferred funding type?** You can select multiple options if you're open to more than one: Teaching Assistantship, Research Assistantship, Fellowship, or Scholarship.

### s155 t8  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'country_residence']]`
- directive reason: dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for confirming your TOEFL score. I've recorded it.
  > 
  > Now, could you please let me know your **Country of Residence**?

### s154 t15  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'phone']]`
- directive reason: dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing that! I've recorded your TOEFL score (105).
  > 
  > Now, what's your phone number to continue with the application?

### s155 t2  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'start_term']]`
- directive reason: dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for providing that score! 
  > 
  > Now, please choose your **Intended Start Term**:
  > 
  > - Fall 2026
  > - Spring 2027
  > 
  > Which term would you like to begin?

### s153 t12  (directive)
- directives: `[['dormant_set', 'english_test_score'], ['dormant_set', 'english_test_type'], ['reask_pending', 'has_work_experience']]`
- directive reason: dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks! Now, **do you have relevant work experience?** (Yes / No)

### s160 t7  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'country_citizenship']]`
- directive reason: dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks! Your TOEFL score of 98 has been recorded.
  > 
  > Now, could you please let me know your **country of citizenship**? Please select from the options provided.

### s150 t3  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'enrollment_type']]`
- directive reason: dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks! I've recorded your TOEFL score of 98.
  > 
  > Now, please select your **Enrollment Type**:
  > 
  > - Full-time
  > - Part-time

### s155 t6  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'dob']]`
- directive reason: dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for providing that score! 
  > 
  > Now, could you please share your **Date of Birth** (MM/DD/YYYY format, please)?

### s161 t5  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'full_name']]`
- directive reason: dormant_set: 'english_test_type' needs a not-required caveat + recorded/field mention; dormant_set: 'english_test_score' needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for providing that score! 
  > 
  > Could you please share your **full legal name** so we can continue with your application?
