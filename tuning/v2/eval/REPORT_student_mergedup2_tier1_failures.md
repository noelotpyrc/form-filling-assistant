# Tier-1 failures — student_mergedup2_responder_tier1_frozen223

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-mergedup2-mlx` (port 8107, $0)  
Eval set: 223 cases, sha16 `2c7678f763a9256b`  
Overall pass: **218/223**  

| check | pass | rate |
|---|---|---|
| format | 223/223 | 100.0% |
| directive | 220/223 | 98.7% |
| grounding | 222/223 | 99.6% |
| echo | 223/223 | 100.0% |
| verbosity | 222/223 | 99.6% |
| repetition | 223/223 | 100.0% |

## directive — 3 failing case(s)

### s151 t2  (directive)
- directives: `[['ask_target', 'prior_application']]`
- directive reason: ask_target: field 'prior_application' not asked about
- student prose:

  > Thanks for all the details, Samuel! Let's move on.

### s156 t10  (directive)
- directives: `[['ask_target', 'funding_interest']]`
- directive reason: ask_target: field 'funding_interest' not asked about
- student prose:

  > Thanks for confirming! Do you have relevant work experience?

### s157 t3  (directive)
- directives: `[['ask_target', 'prior_application']]`
- directive reason: ask_target: field 'prior_application' not asked about
- student prose:

  > Great! Will you be enrolling full-time or part-time?
  > 
  > - Full-time
  > - Part-time

## grounding — 1 failing case(s)

### s154 t14  (grounding)
- directives: `[['ask_target', 'phone']]`
- grounding reason: phone '293) 555-2967' not grounded in message/state/schema
- student prose:

  > Thanks! My phone number is (293) 555-2967. Would you like to use that or another number?

## verbosity — 1 failing case(s)

### s154 t4  (verbosity)
- directives: `[]`
- verbosity reason: 68 tokens > ask budget 60 (option re-enumeration?)
- student prose:

  > I don't have a specific definition for what counts as "relevant work experience" — the form asks broadly, and that's exactly why it's important to clarify with you before we move on. If you mention work related to mechanical engineering, automation, robotics, maintenance, data analysis, or any other field that supports a mechanical engineering graduate, that would count.
  > 
  > So, before we continue: **Do you have relevant work experience?**
