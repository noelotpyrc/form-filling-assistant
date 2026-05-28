# GEPA Eval Case Schema

JSONL file: `tuning/gepa/eval_cases.jsonl`. One JSON object per line. Consumed by `tuning/gepa/metric.py` during GEPA optimization.

## Top-level fields

```jsonc
{
  "test_id":        "gepa-#4-001",          // unique within the eval set
  "cannot_target":  "#4_commits_regardless", // string tag, see below
  "source_seed":    "P3-ex3",                // pointer back to /tmp/gepa_seed_inventory.md
  "form_state":     { ... },                 // current form values
  "conversation_history": [                  // last 6 turns max
    { "role": "user",      "content": "..." },
    { "role": "assistant", "content": "..." }
  ],
  "user_message":   "...",                   // the trigger
  "gold": { ... }                            // see below
}
```

`form_schema` is NOT in the case — the metric loads `masters-northfield.json` once and injects it.

## `cannot_target` valid values

- `#1_vibe`
- `#2_text_action_disconnect`
- `#3_state_check`
- `#4_commits_regardless`
- `#7_wrong_field_value`
- `#8_training_data_hallucination`

A case may have a single primary target. If multiple are relevant (e.g., R12 covers #4 and #8), author one case per CANNOT and tag accordingly — easier than multi-target tagging.

## `gold` structure

```jsonc
"gold": {
  "expected_flags": {
    "has_new_data": false,    // bool to enforce, null = don't care
    "needs_choice": null,
    "wants_review": null,
    "wants_save":   null,
    "wants_submit": null
  },
  "expected_set_fields": [    // exhaustive — model output must match
    { "field_id": "country_citizenship", "value": "US" }
  ],
  "programmatic_checks": [
    {
      "id":     "no_persona_leak",                       // unique within case
      "kind":   "regex_no_match",                        // see kinds below
      "params": { "regex": "Alex Chen|Jane Doe|Maria Garcia", "target": "response_text" },
      "weight": 5.0,
      "critical": true                                    // optional; default false
    }
  ],
  "rubric_items": [
    {
      "id":     "clarifies_format",
      "ask":    "Does the response answer the user's format question?",
      "weight": 1.0
    },
    {
      "id":     "no_fab_value",
      "ask":    "Does the response contain any specific date, number, or name not given by the user?",
      "weight": 2.0
    }
  ]
}
```

## Programmatic check `kind` types

| `kind` | Params | What it checks |
|---|---|---|
| `set_fields_count_eq` | `value: int` | `len(parsed_actions[set_fields].fields) == value` |
| `set_fields_subset` | `expected: [{field_id, value}]` | All `expected` entries appear in actual |
| `set_fields_exact` | `expected: [{field_id, value}]` | Exact match (no extras, no missing) |
| `field_id_match` | `field_ids: [str]` | Predicted `field_ids` set equals expected |
| `value_match_for_field` | `field_id: str, value: any` | Specific field has specific value |
| `regex_no_match` | `regex: str, target: "response_text"\|"raw_text"` | Pattern absent |
| `regex_match` | `regex: str, target: ...` | Pattern present |
| `flag_eq` | `flag: str, value: bool` | One specific flag matches |
| `format_compliance` | (none) | Standard format check from `compare_models.py` |
| `option_subset_of_schema` | `field_id: str` | `ask_choice` options all appear in schema's enum |

Each check returns `pass: bool` (and optionally a graded `score: float ∈ [0,1]` for non-binary checks like F1 — out of scope for v1).

## Rubric item structure

Each rubric item:
- `id`: unique within case
- `ask`: yes/no question for the judge LLM (must be answerable from the response alone)
- `weight`: float, default 1.0
- `critical: true` allowed but rarely used here

The judge LLM is called once per case with **all rubric items batched** in a single prompt (batched yes/no answers — keeps API cost down).

## Score computation per case

```
total_weight = sum(weights of programmatic + rubric checks)
weighted_passes = sum(weight * 1.0 if check passed else 0)
case_score = weighted_passes / total_weight   # ∈ [0, 1]

# Critical short-circuit: if any check with critical:true fails, case_score = 0
```

## Feedback string returned to GEPA

Sorted by weight descending. Includes failed checks (with description) and passed checks summarized.

```
Score: 0.42. Failed checks (by importance):
  - [weight 5.0, critical] no_persona_leak: response_text contains "Alex Chen"
  - [weight 2.0] no_fab_value: response includes "1995-01-04" not given by user
Passed: clarifies_format
```

## Storage

```
tuning/gepa/
├── README.md                  # overview + how to run
├── eval_cases_schema.md       # this doc
├── eval_cases.jsonl           # the cases
├── metric.py                  # the metric implementation
└── (later) optimize.py        # GEPA driver script
```

## Notes

- `expected_flags` and `expected_set_fields` are **hints** — the actual scoring goes through `programmatic_checks`. The hints are present for human readability and so a future tool could auto-generate baseline checks from them. They aren't double-counted in scoring.
- For cases targeting multiple CANNOTs, prefer authoring per-CANNOT cases over multi-tag. Simpler weights, simpler feedback.
- Rubric questions must be **yes-positive** (i.e., "yes" = good, "no" = bad). Phrase them carefully so the judge LLM's answer aligns with pass/fail.
