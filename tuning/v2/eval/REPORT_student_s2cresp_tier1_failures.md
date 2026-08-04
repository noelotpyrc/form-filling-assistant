# Tier-1 failures — student_s2cresp_responder_tier1_frozen223

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2cresp-mlx` (port 8104, $0)  
Eval set: 223 cases, sha16 `2c7678f763a9256b`  
Overall pass: **220/223**  

| check | pass | rate |
|---|---|---|
| format | 223/223 | 100.0% |
| directive | 223/223 | 100.0% |
| grounding | 223/223 | 100.0% |
| echo | 223/223 | 100.0% |
| verbosity | 220/223 | 98.7% |
| repetition | 223/223 | 100.0% |

## verbosity — 3 failing case(s)

### s147 t16  (verbosity)
- directives: `[['reask_pending', 'funding_type']]`
- verbosity reason: 61 tokens > ask budget 60
- student prose:

  > Thanks for providing all those details — I've recorded your non-binary gender, email, phone, mailing address, and that you do have relevant work experience in education.
  > 
  > Now, **what is your preferred funding type?** You can select one of the following:
  > - Teaching Assistantship
  > - Research Assistantship
  > - Fellowship
  > - Scholarship
  > 
  > Just let me know which one(s) apply, and we'll move forward.

### s154 t4  (verbosity)
- directives: `[]`
- verbosity reason: 63 tokens > ask budget 60 (option re-enumeration?)
- student prose:

  > I don't have specific criteria for what counts as relevant work experience — it's best to be honest about what you've done rather than guessing. You can simply say "Yes" or "No" and let the admissions committee ask for details later.
  > 
  > Now, back to the program: Mechanical Engineering (MS) — which term are you planning to start?
  > 
  > - Fall 2026
  > - Spring 2027

### s157 t9  (verbosity)
- directives: `[]`
- verbosity reason: 62 tokens > ask budget 60 (option re-enumeration?)
- student prose:

  > I don't have detailed information about specific funding or assistantship types that vary by year — the main options are typically Teaching Assistantships, Research Assistantships, Fellowships, and Scholarships. If you're interested in any of those, you can select them when we get to that section.
  > 
  > To continue, would you like to select a preferred funding type (Teaching Assistantship, Research Assistantship, Fellowship, Scholarship)?
