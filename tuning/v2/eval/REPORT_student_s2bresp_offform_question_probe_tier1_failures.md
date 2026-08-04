# Tier-1 failures — student_s2bresp_offform_question_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2bresp-mlx` (port 8103, $0)  
Eval set: 32 cases, sha16 `03e5cef1062f58b4`  
Overall pass: **29/32**  

| check | pass | rate |
|---|---|---|
| format | 32/32 | 100.0% |
| directive | 31/32 | 96.9% |
| grounding | 32/32 | 100.0% |
| echo | 32/32 | 100.0% |
| verbosity | 30/32 | 93.8% |

## directive — 1 failing case(s)

### s157 t15  (directive)
- directives: `[['reask_pending', 'mailing_address']]`
- directive reason: reask_pending: field 'mailing_address' not asked about
- student prose:

  > Great question! Yes, there is an interview stage after your application is reviewed. Would you like to proceed with the interview now, or would you prefer to wait for the next step?

## verbosity — 2 failing case(s)

### s157 t11  (verbosity)
- directives: `[['reask_pending', 'country_citizenship']]`
- verbosity reason: 68 tokens > ask budget 60
- student prose:

  > Great question! Tuition rates vary by program and year, but for the Data Science (MS) program, the starting tuition is approximately **$10,000 per year** (this is a rough estimate and can change).
  > 
  > To continue, could you please let me know your country of citizenship? You can choose from: United States, Canada, United Kingdom, Australia, New Zealand, India, China, South Korea, Japan, Germany, France, Brazil, Mexico, Nigeria, or Other.

### s157 t9  (verbosity)
- directives: `[['reask_pending', 'country_citizenship']]`
- verbosity reason: 61 tokens > ask budget 60
- student prose:

  > I don't have specific information about financial aid availability for part-timers at this time — that would be best shared directly with the prospective graduate.
  > 
  > To continue, could you please let me know your **country of citizenship**? You can choose from: United States, Canada, United Kingdom, Australia, New Zealand, India, China, South Korea, Japan, Germany, France, Brazil, Mexico, Nigeria, or Other.
