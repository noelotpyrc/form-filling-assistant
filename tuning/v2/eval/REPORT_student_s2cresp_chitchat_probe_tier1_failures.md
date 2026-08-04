# Tier-1 failures — student_s2cresp_chitchat_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2cresp-mlx` (port 8104, $0)  
Eval set: 60 cases, sha16 `5d718a096dc238ff`  
Overall pass: **59/60**  

| check | pass | rate |
|---|---|---|
| format | 60/60 | 100.0% |
| directive | 60/60 | 100.0% |
| grounding | 60/60 | 100.0% |
| echo | 60/60 | 100.0% |
| verbosity | 59/60 | 98.3% |
| repetition | 60/60 | 100.0% |

## verbosity — 1 failing case(s)

### s147 t17  (verbosity)
- directives: `[['reask_pending', 'funding_type']]`
- verbosity reason: 62 tokens > ask budget 60
- student prose:

  > Thanks for the kind words! I'm glad I can help.
  > 
  > Just to clarify — **what type of funding are you interested in?** You can select one of the following:
  > - Teaching Assistantship
  > - Research Assistantship
  > - Fellowship
  > - Scholarship
  > 
  > Just let me know which ones appeal to you, or you can leave them all unchecked if you're not looking for specific funding.
