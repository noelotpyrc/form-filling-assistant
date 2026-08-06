# Tier-1 failures — student_s2dresp_savedraft_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2dresp-mlx` (port 8105, $0)  
Eval set: 40 cases, sha16 `d7d684a45d53e451`  
Overall pass: **39/40**  

| check | pass | rate |
|---|---|---|
| format | 40/40 | 100.0% |
| directive | 39/40 | 97.5% |
| grounding | 40/40 | 100.0% |
| echo | 40/40 | 100.0% |
| verbosity | 40/40 | 100.0% |
| repetition | 40/40 | 100.0% |

## directive — 1 failing case(s)

### s155 t7  (directive)
- directives: `[['ack', 'Save Draft'], ['reask_pending', 'country_citizenship']]`
- directive reason: reask_pending: field 'country_citizenship' not asked about
- student prose:

  > Your draft has been saved. Would you like to save it now, or would you prefer to continue with your application later?
