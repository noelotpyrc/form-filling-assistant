# Tier-1 failures — student_s2bresp_chitchat_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2bresp-mlx` (port 8103, $0)  
Eval set: 60 cases, sha16 `5d718a096dc238ff`  
Overall pass: **55/60**  

| check | pass | rate |
|---|---|---|
| format | 60/60 | 100.0% |
| directive | 55/60 | 91.7% |
| grounding | 60/60 | 100.0% |
| echo | 60/60 | 100.0% |
| verbosity | 60/60 | 100.0% |

## directive — 5 failing case(s)

### s155 t2  (directive)
- directives: `[['reask_pending', 'start_term']]`
- directive reason: reask_pending: field 'start_term' not asked about
- student prose:

  > I'm having a wonderful day! How's your day going so far?

### s154 t17  (directive)
- directives: `[['reask_pending', 'funding_interest']]`
- directive reason: reask_pending: field 'funding_interest' not asked about
- student prose:

  > Hope the weather is nice where you are! I'm here to help you through the application process.
  > 
  > Do you have any relevant work experience for this program?

### s160 t5  (directive)
- directives: `[['reask_pending', 'full_name']]`
- directive reason: reask_pending: field 'full_name' not asked about
- student prose:

  > I'm having a wonderful day! How's your day going so far?

### s150 t13  (directive)
- directives: `[['reask_pending', 'funding_interest']]`
- directive reason: reask_pending: field 'funding_interest' not asked about
- student prose:

  > Hope the weather is nice where you are!

### s147 t6  (directive)
- directives: `[['reask_pending', 'dob']]`
- directive reason: reask_pending: field 'dob' not asked about
- student prose:

  > Hey there! How's your day going?
