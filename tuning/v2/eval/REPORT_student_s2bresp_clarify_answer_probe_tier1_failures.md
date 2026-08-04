# Tier-1 failures — student_s2bresp_clarify_answer_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2bresp-mlx` (port 8103, $0)  
Eval set: 39 cases, sha16 `195070cc7b72985a`  
Overall pass: **38/39**  

| check | pass | rate |
|---|---|---|
| format | 39/39 | 100.0% |
| directive | 39/39 | 100.0% |
| grounding | 39/39 | 100.0% |
| echo | 39/39 | 100.0% |
| verbosity | 38/39 | 97.4% |

## verbosity — 1 failing case(s)

### s151 t6  (verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- verbosity reason: 87 tokens > clarify budget 55
- student prose:

  > I'm not sure about the dual heritage part — that's a bit of a mess to track. But I'm happy to help you through the application!
  > 
  > For **Country of Residence**, please pick from the list:
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
  > 
  > Once you let me know which country you're currently living in, I'll need your **Email Address** to continue.
