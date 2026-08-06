# Tier-1 failures — student_mergedall_clarify_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-mergedall-mlx` (port 8106, $0)  
Eval set: 39 cases, sha16 `195070cc7b72985a`  
Overall pass: **38/39**  

| check | pass | rate |
|---|---|---|
| format | 39/39 | 100.0% |
| directive | 39/39 | 100.0% |
| grounding | 39/39 | 100.0% |
| echo | 39/39 | 100.0% |
| verbosity | 38/39 | 97.4% |
| repetition | 39/39 | 100.0% |

## verbosity — 1 failing case(s)

### s153 t7  (verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 58 tokens > clarify budget 55
- student prose:

  > I need you to select from the specific list provided. Could you please choose one of the following options for your Country of Citizenship:
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
