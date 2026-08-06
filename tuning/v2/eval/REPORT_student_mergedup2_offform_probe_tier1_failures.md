# Tier-1 failures — student_mergedup2_offform_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-mergedup2-mlx` (port 8107, $0)  
Eval set: 32 cases, sha16 `03e5cef1062f58b4`  
Overall pass: **31/32**  

| check | pass | rate |
|---|---|---|
| format | 32/32 | 100.0% |
| directive | 32/32 | 100.0% |
| grounding | 32/32 | 100.0% |
| echo | 32/32 | 100.0% |
| verbosity | 31/32 | 96.9% |
| repetition | 32/32 | 100.0% |

## verbosity — 1 failing case(s)

### s154 t13  (verbosity)
- directives: `[['reask_pending', 'country_residence']]`
- verbosity reason: 62 tokens > ask budget 60
- student prose:

  > I don't have information about acceptance rates for specific programs — that's not something I can look up in the system.
  > 
  > To continue with your application, could you let me know your **country of residence**? You can choose from the same list: United States, Canada, United Kingdom, Australia, New Zealand, India, China, South Korea, Japan, Germany, France, Brazil, Mexico, Nigeria, or Other.
