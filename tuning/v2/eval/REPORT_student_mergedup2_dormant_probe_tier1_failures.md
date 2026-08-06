# Tier-1 failures — student_mergedup2_dormant_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-mergedup2-mlx` (port 8107, $0)  
Eval set: 13 cases, sha16 `72fbba993907c104`  
Overall pass: **10/13**  

| check | pass | rate |
|---|---|---|
| format | 13/13 | 100.0% |
| directive | 12/13 | 92.3% |
| grounding | 13/13 | 100.0% |
| echo | 13/13 | 100.0% |
| verbosity | 11/13 | 84.6% |
| repetition | 13/13 | 100.0% |

## directive — 1 failing case(s)

### s160 t1  (directive)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'program']]`
- directive reason: dormant_set: ['english_test_type', 'english_test_score'] needs a not-required caveat + recorded/field mention
- student prose:

  > Thanks for sharing your TOEFL score of 100 — I’ve recorded that for you. Now, which program are you interested in applying to?
  > 
  > - Computer Science (MS)
  > - Data Science (MS)
  > - Business Administration (MBA)
  > - Education (MEd)
  > - Public Health (MPH)
  > - Mechanical Engineering (MS)

## verbosity — 2 failing case(s)

### s155 t8  (verbosity)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'country_residence']]`
- verbosity reason: 77 tokens > ask budget 60
- student prose:

  > Thanks for sharing that, Lucas. I've recorded your TOEFL score of 110.
  > 
  > Just so you know, based on your current answers this English proficiency section isn't required, but I've saved it anyway.
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

### s160 t7  (verbosity)
- directives: `[['dormant_set', 'english_test_type'], ['dormant_set', 'english_test_score'], ['reask_pending', 'country_citizenship']]`
- verbosity reason: 65 tokens > ask budget 60
- student prose:

  > Thanks for sharing your TOEFL score of 98 — I've recorded that for you. Based on your current answers, an English proficiency test isn't required at this stage, but it's good to have on file.
  > 
  > Now, could you please let me know your **country of citizenship**? You can choose from the list (e.g., United States, Canada, India, etc.) or select "Other" if yours isn't shown.
