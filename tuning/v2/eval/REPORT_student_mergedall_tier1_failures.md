# Tier-1 failures — student_mergedall_responder_tier1_frozen223

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-mergedall-mlx` (port 8106, $0)  
Eval set: 223 cases, sha16 `2c7678f763a9256b`  
Overall pass: **220/223**  

| check | pass | rate |
|---|---|---|
| format | 222/223 | 99.6% |
| directive | 221/223 | 99.1% |
| grounding | 223/223 | 100.0% |
| echo | 223/223 | 100.0% |
| verbosity | 222/223 | 99.6% |
| repetition | 223/223 | 100.0% |

## format — 1 failing case(s)

### s147 t0  (format, directive)
- directives: `[['ask_target', 'program']]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

## directive — 2 failing case(s)

### s147 t0  (format, directive)
- directives: `[['ask_target', 'program']]`
- directive reason: ask_target: field 'program' not asked about
- student prose:

  > !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

### s157 t3  (directive)
- directives: `[['ask_target', 'prior_application']]`
- directive reason: ask_target: field 'prior_application' not asked about
- student prose:

  > Great! Will you be enrolling part-time or full-time?

## verbosity — 1 failing case(s)

### s157 t9  (verbosity)
- directives: `[]`
- verbosity reason: 62 tokens > ask budget 60 (option re-enumeration?)
- student prose:

  > I'd love to share details about the funding options, but I don't have information about the specific types of assistantships or fellowships Northfield offers. The funding section is just one of several categories in the application.
  > 
  > To continue, would you like to:
  > - Select a preferred funding type (Teaching Assistantship, Research Assistantship, Fellowship, Scholarship)
  > - Skip the funding question and move on
