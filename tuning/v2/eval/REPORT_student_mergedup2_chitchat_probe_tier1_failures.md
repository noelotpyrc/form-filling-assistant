# Tier-1 failures — student_mergedup2_chitchat_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-mergedup2-mlx` (port 8107, $0)  
Eval set: 60 cases, sha16 `5d718a096dc238ff`  
Overall pass: **53/60**  

| check | pass | rate |
|---|---|---|
| format | 60/60 | 100.0% |
| directive | 53/60 | 88.3% |
| grounding | 60/60 | 100.0% |
| echo | 60/60 | 100.0% |
| verbosity | 60/60 | 100.0% |
| repetition | 60/60 | 100.0% |

## directive — 7 failing case(s)

### s161 t12  (directive)
- directives: `[['reask_pending', 'has_work_experience']]`
- directive reason: reask_pending: field 'has_work_experience' not asked about
- student prose:

  > It has been a long week! How long has it been?

### s151 t6  (directive)
- directives: `[['reask_pending', 'country_residence']]`
- directive reason: reask_pending: field 'country_residence' not asked about
- student prose:

  > It is lovely out here! How's your day going so far?

### s148 t8  (directive)
- directives: `[['reask_pending', 'country_residence']]`
- directive reason: reask_pending: field 'country_residence' not asked about
- student prose:

  > It has been a long week! How long have you been with Northfield?

### s151 t9  (directive)
- directives: `[['reask_pending', 'has_work_experience']]`
- directive reason: reask_pending: field 'has_work_experience' not asked about
- student prose:

  > It has been a long week! How's your day going so far?

### s159 t10  (directive)
- directives: `[['reask_pending', 'phone']]`
- directive reason: reask_pending: field 'phone' not asked about
- student prose:

  > It has been a long week! How long has it been?

### s156 t2  (directive)
- directives: `[['reask_pending', 'start_term']]`
- directive reason: reask_pending: field 'start_term' not asked about
- student prose:

  > It has been a long week! How long have you been waiting for your application?

### s153 t10  (directive)
- directives: `[['reask_pending', 'phone']]`
- directive reason: reask_pending: field 'phone' not asked about
- student prose:

  > It is lovely out! How's your application coming along so far?
