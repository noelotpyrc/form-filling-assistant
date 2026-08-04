# Tier-1 failures — student_s2bresp_responder_tier1_frozen223

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2bresp-mlx` (port 8103, $0)  
Eval set: 223 cases, sha16 `2c7678f763a9256b`  
Overall pass: **221/223**  

| check | pass | rate |
|---|---|---|
| format | 223/223 | 100.0% |
| directive | 221/223 | 99.1% |
| grounding | 223/223 | 100.0% |
| echo | 223/223 | 100.0% |
| verbosity | 223/223 | 100.0% |

## directive — 2 failing case(s)

### s151 t8  (directive)
- directives: `[['reask_pending', 'has_work_experience']]`
- directive reason: reask_pending: field 'has_work_experience' not asked about
- student prose:

  > I'm doing well, thank you for asking!

### s156 t10  (directive)
- directives: `[['ask_target', 'funding_interest']]`
- directive reason: ask_target: field 'funding_interest' not asked about
- student prose:

  > Thanks! I've recorded your mailing address as 2227 Pine Way, Madison, GA 59313.
  > 
  > Do you have relevant work experience?
