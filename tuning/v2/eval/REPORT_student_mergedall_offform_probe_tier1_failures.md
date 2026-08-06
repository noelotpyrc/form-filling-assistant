# Tier-1 failures — student_mergedall_offform_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-mergedall-mlx` (port 8106, $0)  
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

### s149 t4  (verbosity)
- directives: `[['reask_pending', 'prior_application']]`
- verbosity reason: 63 tokens > ask budget 60
- student prose:

  > I don't have information about the application timeline — that's something you'd want to check with the admissions office or the program's website.
  > 
  > To continue with your application, would you like to:
  > - Answer the question "Have you previously applied to Northfield University?"
  > - Or pick up where we left off (your application status?)
  > 
  > Just let me know which works best for you.

### s157 t11  (verbosity)
- directives: `[['reask_pending', 'country_citizenship']]`
- verbosity reason: 68 tokens > ask budget 60
- student prose:

  > I don't have tuition information for specific programs at this time — you'd need to check the university's website or contact the admissions office for the most current details.
  > 
  > To continue with your application, could you please let me know your country of citizenship? You can choose from: United States, Canada, United Kingdom, Australia, New Zealand, India, China, South Korea, Japan, Germany, France, Brazil, Mexico, Nigeria, or Other.

### s157 t9  (verbosity)
- directives: `[['reask_pending', 'country_citizenship']]`
- verbosity reason: 61 tokens > ask budget 60
- student prose:

  > I don't have information about application timelines — that's something you'd want to check with the admissions office or the program's website.
  > 
  > To continue with your application, could you please let me know your country of citizenship? You can choose from: United States, Canada, United Kingdom, Australia, New Zealand, India, China, South Korea, Japan, Germany, France, Brazil, Mexico, Nigeria, or Other.
