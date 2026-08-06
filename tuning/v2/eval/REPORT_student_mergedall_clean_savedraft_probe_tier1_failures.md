# Tier-1 failures — student_mergedall_clean_savedraft_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-mergedall-mlx` (port 8106, $0)  
Eval set: 40 cases, sha16 `d7d684a45d53e451`  
Overall pass: **39/40**  

| check | pass | rate |
|---|---|---|
| format | 40/40 | 100.0% |
| directive | 40/40 | 100.0% |
| grounding | 40/40 | 100.0% |
| echo | 40/40 | 100.0% |
| verbosity | 39/40 | 97.5% |
| repetition | 40/40 | 100.0% |

## verbosity — 1 failing case(s)

### s155 t7  (verbosity)
- directives: `[['ack', 'Save Draft'], ['reask_pending', 'country_citizenship']]`
- verbosity reason: 69 tokens > ask budget 60
- student prose:

  > Your draft has been saved. Please review it and let me know if you'd like to submit or if you need any adjustments.
  > 
  > To continue, please select your **Country of Citizenship** from the following options:
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
