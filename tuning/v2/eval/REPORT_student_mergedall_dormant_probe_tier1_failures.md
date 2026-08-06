# Tier-1 failures — student_mergedall_dormant_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-mergedall-mlx` (port 8106, $0)  
Eval set: 13 cases, sha16 `72fbba993907c104`  
Overall pass: **6/13**  

| check | pass | rate |
|---|---|---|
| format | 13/13 | 100.0% |
| directive | 7/13 | 53.8% |
| grounding | 13/13 | 100.0% |
| echo | 13/13 | 100.0% |
| verbosity | 12/13 | 92.3% |
| repetition | 13/13 | 100.0% |

## directive — 6 failing case(s)

### s161 t8  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'email']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing that! I've recorded your TOEFL score of 105.
  > 
  > Now, could you please provide your email address so we can continue with your application?

### s160 t11  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'mailing_address']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing your TOEFL score of 98! I've recorded that for you.
  > 
  > Now, could you please provide your mailing address so we can continue with the application?

### s160 t1  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'program']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks! I've recorded your TOEFL score of 100.
  > 
  > Now, which program are you interested in applying to?

### s153 t12  (directive)
- directives: `[['dormant_set', 'english_test_score'], ['dormant_set', 'english_test_type'], ['reask_pending', 'has_work_experience']]`
- directive reason: dormant_set: ['english_test_score', 'english_test_type'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing your TOEFL score of 100! I've recorded that.
  > 
  > Now, **do you have relevant work experience?** (Yes / No)

### s160 t7  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'country_citizenship']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing that — I've recorded your TOEFL score of 98.
  > 
  > Now, could you please let me know your **country of citizenship**? You can select from the list provided.

### s150 t3  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'enrollment_type']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing your TOEFL score of 98 — I've recorded that for you.
  > 
  > Now, please select your **Enrollment Type**:
  > 
  > - Full-time
  > - Part-time

## verbosity — 1 failing case(s)

### s155 t8  (verbosity)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'country_residence']]`
- verbosity reason: 80 tokens > ask budget 60
- student prose:

  > Thanks for sharing that — I've recorded your TOEFL score of 110.
  > 
  > Just so you have it, the TOEFL details aren't required at this stage based on your current answers, but I've saved them anyway.
  > 
  > Now, please select your **Country of Residence** from the following options:
  > 
  > - United States
  > - Canada
  > - United Kingdom
  > - Australia
  > - New Zealand
  > - India
  > - China
  > - South Korea
  > - Japan
  > - Germany
  > - France
  > - Brazil
  > - Mexico
  > - Nigeria
  > - Other
