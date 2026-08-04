# Tier-1 failures — student_s2cresp_offform_question_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2cresp-mlx` (port 8104, $0)  
Eval set: 32 cases, sha16 `03e5cef1062f58b4`  
Overall pass: **29/32**  

| check | pass | rate |
|---|---|---|
| format | 32/32 | 100.0% |
| directive | 32/32 | 100.0% |
| grounding | 32/32 | 100.0% |
| echo | 32/32 | 100.0% |
| verbosity | 29/32 | 90.6% |
| repetition | 32/32 | 100.0% |

## verbosity — 3 failing case(s)

### s154 t13  (verbosity)
- directives: `[['reask_pending', 'country_residence']]`
- verbosity reason: 62 tokens > ask budget 60
- student prose:

  > I don't have information about acceptance rates for specific programs — that's not something I can look up in the system.
  > 
  > To continue with your application, could you let me know your **country of residence**? You can choose from the same list: United States, Canada, United Kingdom, Australia, New Zealand, India, China, South Korea, Japan, Germany, France, Brazil, Mexico, Nigeria, or Other.

### s157 t11  (verbosity)
- directives: `[['reask_pending', 'country_citizenship']]`
- verbosity reason: 63 tokens > ask budget 60
- student prose:

  > I don't have information on tuition rates — that's something you'd need to check with the university directly or look up on their website.
  > 
  > To continue with your application, could you please let me know your country of citizenship? You can choose from: United States, Canada, United Kingdom, Australia, New Zealand, India, China, South Korea, Japan, Germany, France, Brazil, Mexico, Nigeria, or Other.

### s157 t9  (verbosity)
- directives: `[['reask_pending', 'country_citizenship']]`
- verbosity reason: 62 tokens > ask budget 60
- student prose:

  > I don't have information about the application timeline — that would be something the admissions office or the university would need to provide.
  > 
  > To continue with your application, could you please let me know your country of citizenship? You can choose from: United States, Canada, United Kingdom, Australia, New Zealand, India, China, South Korea, Japan, Germany, France, Brazil, Mexico, Nigeria, or Other.
