# Tier-1 failures — student_s2dresp_dormant_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2dresp-mlx` (port 8105, $0)  
Eval set: 13 cases, sha16 `72fbba993907c104`  
Overall pass: **1/13**  

| check | pass | rate |
|---|---|---|
| format | 13/13 | 100.0% |
| directive | 2/13 | 15.4% |
| grounding | 13/13 | 100.0% |
| echo | 13/13 | 100.0% |
| verbosity | 11/13 | 84.6% |
| repetition | 13/13 | 100.0% |

## directive — 11 failing case(s)

### s156 t10  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'has_work_experience']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing that! I've recorded your TOEFL score of 110.
  > 
  > Now, do you have relevant work experience?

### s161 t8  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'email']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing that, Tariq! I've recorded your TOEFL score of 105.
  > 
  > Now, could you please share your email address so we can continue with your application?

### s160 t11  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'mailing_address']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing your TOEFL score of 98! I've recorded that.
  > 
  > Now, could you please provide your mailing address so we can continue with the application?

### s160 t1  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'program']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks! I've recorded your TOEFL score of 100.
  > 
  > Now, which program would you like to apply for?

### s155 t8  (directive, verbosity)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'country_residence']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing that, Lucas. I've recorded your TOEFL score of 110.
  > 
  > Just to confirm — since you've already selected **Australia** as your country of citizenship and **TOEFL** as your English proficiency test, the form doesn't require you to answer Country of Residence or English Test details. I've already noted those values for you.
  > 
  > Now, back to your program: **Mechanical Engineering (MS)**? Would you like to start in **Fall 2026**?

### s154 t15  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'phone']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing that! I've recorded your TOEFL score of 105.
  > 
  > Now, could you please provide your phone number so we can continue with the application?

### s155 t2  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'start_term']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing that! I've recorded your TOEFL score of 110.
  > 
  > Now, please let me know your **Intended Start Term**:
  > 
  > - Fall 2026
  > - Spring 2027
  > 
  > Which term would you like to begin?

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

  > Thanks for sharing your TOEFL score of 98 — I've recorded it. 
  > 
  > Now, could you let me know your **country of citizenship**? Please select from the list.

### s150 t3  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'enrollment_type']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing your TOEFL score of 98! I've recorded that.
  > 
  > Now, please select your **Enrollment Type**:
  > 
  > - Full-time
  > - Part-time

### s155 t6  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'dob']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing your TOEFL score of 98 — that's helpful for your application.
  > 
  > However, based on your current answers (English Proficiency Test selected, score shown), the form doesn't require additional details about English proficiency. I've recorded the TOEFL score anyway, just in case it's needed later.
  > 
  > Now, could you please provide your **Date of Birth** (MM/DD/YYYY format)?

## verbosity — 2 failing case(s)

### s147 t16  (verbosity)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'funding_type']]`
- verbosity reason: 65 tokens > ask budget 60
- student prose:

  > Thanks for sharing your TOEFL score — I've recorded it.
  > 
  > Now, regarding funding: since you don't mention it, we don't need to ask for a specific type. But since you're interested in assistantships, you can select any of the available options later if needed. For now, your current answers are good enough.
  > 
  > Just to confirm: are you interested in funding or assistantships at Northfield? (Yes/No)

### s155 t8  (directive, verbosity)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'country_residence']]`
- verbosity reason: 70 tokens > ask budget 60
- student prose:

  > Thanks for sharing that, Lucas. I've recorded your TOEFL score of 110.
  > 
  > Just to confirm — since you've already selected **Australia** as your country of citizenship and **TOEFL** as your English proficiency test, the form doesn't require you to answer Country of Residence or English Test details. I've already noted those values for you.
  > 
  > Now, back to your program: **Mechanical Engineering (MS)**? Would you like to start in **Fall 2026**?
