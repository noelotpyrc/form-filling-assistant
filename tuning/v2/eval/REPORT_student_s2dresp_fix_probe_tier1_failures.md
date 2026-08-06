# Tier-1 failures — student_s2dresp_fix_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2dresp-mlx` (port 8105, $0)  
Eval set: 40 cases, sha16 `084f50ce6df3e2fd`  
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

### s147 t8  (verbosity)
- directives: `[['fix', 'the value for funding_type is invalid (field: funding_type).']]`
- verbosity reason: 47 tokens > ack budget 45
- student prose:

  > I'm sorry — that funding type isn't available for this application. Could you please select one of the four options:
  > 
  > - Teaching Assistantship
  > - Research Assistantship
  > - Fellowship
  > - Scholarship
  > 
  > Just pick the one that applies to you, and we'll continue.
  > 
  > What is your **country of citizenship**?
