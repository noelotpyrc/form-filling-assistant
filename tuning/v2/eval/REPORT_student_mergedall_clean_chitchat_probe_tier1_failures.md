# Tier-1 failures — student_mergedall_clean_chitchat_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-mergedall-mlx` (port 8106, $0)  
Eval set: 60 cases, sha16 `5d718a096dc238ff`  
Overall pass: **54/60**  

| check | pass | rate |
|---|---|---|
| format | 60/60 | 100.0% |
| directive | 54/60 | 90.0% |
| grounding | 60/60 | 100.0% |
| echo | 60/60 | 100.0% |
| verbosity | 60/60 | 100.0% |
| repetition | 60/60 | 100.0% |

## directive — 6 failing case(s)

### s161 t12  (directive)
- directives: `[['reask_pending', 'has_work_experience']]`
- directive reason: reask_pending: field 'has_work_experience' not asked about
- student prose:

  > It has been a long week! How's your day going so far?

### s151 t6  (directive)
- directives: `[['reask_pending', 'country_residence']]`
- directive reason: reask_pending: field 'country_residence' not asked about
- student prose:

  > It is nice out here! How's your day going so far?

### s147 t8  (directive)
- directives: `[['reask_pending', 'funding_type']]`
- directive reason: reask_pending: field 'funding_type' not asked about
- student prose:

  > It has been a long week! How's your week going so far?

### s158 t3  (directive)
- directives: `[['reask_pending', 'enrollment_type']]`
- directive reason: reask_pending: field 'enrollment_type' not asked about
- student prose:

  > I'm not quite sure what you're asking about — could you let me know what you'd like to do?

### s153 t3  (directive)
- directives: `[['reask_pending', 'enrollment_type']]`
- directive reason: reask_pending: field 'enrollment_type' not asked about
- student prose:

  > I'm not quite sure what you're asking about — could you let me know what you need?

### s159 t10  (directive)
- directives: `[['reask_pending', 'phone']]`
- directive reason: reask_pending: field 'phone' not asked about
- student prose:

  > It has been a long week! How's your day going so far?
