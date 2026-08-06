# Tier-1 failures — student_s2dresp_clean_responder_tier1_frozen223

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2dresp-mlx` (port 8105, $0)  
Eval set: 223 cases, sha16 `2c7678f763a9256b`  
Overall pass: **221/223**  

| check | pass | rate |
|---|---|---|
| format | 223/223 | 100.0% |
| directive | 222/223 | 99.6% |
| grounding | 223/223 | 100.0% |
| echo | 223/223 | 100.0% |
| verbosity | 222/223 | 99.6% |
| repetition | 223/223 | 100.0% |

## directive — 1 failing case(s)

### s147 t15  (directive)
- directives: `[['reask_pending', 'funding_type']]`
- directive reason: reask_pending: field 'funding_type' not asked about
- student prose:

  > You're all set — hit submit and we'll get it in!

## verbosity — 1 failing case(s)

### s154 t4  (verbosity)
- directives: `[]`
- verbosity reason: 65 tokens > ask budget 60 (option re-enumeration?)
- student prose:

  > I don't have a specific definition for "relevant work experience" — the policy is that you should mention whether you have relevant experience, and the field is designed to be answered yes or no.
  > 
  > But since you're interested in mechanical engineering, would you be able to mention any relevant work experience? If you do have relevant experience, please let me know — I'll record it.
