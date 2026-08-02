# Eval v3 — four-model comparison

**Generated:** 2026-07-26. **Eval set:** `tuning/v2/eval/eval_set_v3.jsonl` (frozen, v3).

## 1. Provenance

**Eval set v3** — 414 cases, 23 scenarios x 18 cases each. Depth bands: early 125, mid 124,
late 165 (band = number of already-filled form fields at the point the case is cut: early 0-3,
mid 4-7, late 8+). Contexts are sampled from 30 held-out farm sessions, seeds 102-131, one
snapshot per case (`report_v3.json`: `snapshots_used` 414, `snapshot_reuse` 0). Expectations
were written by the injection spec (the convention table), not by a model, then audited
independently against a full teacher run: 17 disagreements were adjudicated and 8 cases
corrected. (That audit count comes from the eval-v3 construction record; it is not derivable
from the JSONs in this directory.) Expectation shapes: 198 `sets` cases, 180 `empty` cases,
36 `choice` cases.

**Scoring** — `tuning/v2/eval_score.py`. A `sets` case passes only if the set of field ids
matches exactly AND every value matches (string-equal after strip, or bool-equal). An `empty`
case passes only if nothing was set. A `choice` case passes only if a choice was offered on an
expected field and nothing was set. Derived rates: over-attribution is measured on the
`no_value` sub-band (value-free noise), wrong-field-assignment on the `unplaceable` sub-band
(`ambiguous`, `no_match`, `bare_date`, `bare_ambiguous`, `invalid_value`); together those two
make up the empty-correct denominator.

**Models**

| label | JSON | provenance |
|---|---|---|
| base Qwen3.5-0.8B | `baseline-base_qwen35_evalv3.json` | `mlx-community/Qwen3.5-0.8B-bf16`, untuned |
| slice1b (round 2) | `baseline-sft_v2_slice1b_evalv3.json` | teacher-labeled corpus `h1b_merged`: 718 extractor rows after curation dropped 55 convention-violating teacher labels |
| r3-oracle (round 3) | `baseline-sft_r3_oracle_evalv3.json` | oracle-labeled injections: 682 rows labeled by the injection spec with zero teacher involvement + 81 teacher-labeled farm rows = 763; curation drops 0 by construction; 11 assistant-voice naturalizations dropped at merge; hyperparams identical to round 2 (3 epochs, batch 8, lr 2e-4, L4); final eval_loss 0.132 |
| teacher nemotron | `baseline-teacher_nemotron_v3.json` | `nvidia/nemotron-3-ultra-550b-a55b` via OpenRouter — the model that labels farm conversations |

**Eval cost** (`cost_usd` in each JSON): base $0.0000, slice1b $0.0000, r3-oracle $0.0000,
teacher $0.6992. All four runs are `n=1` sample per case; `stability.flaky` is empty in all
four.

## 2. Headline

| metric | base Qwen3.5-0.8B | slice1b (round 2) | r3-oracle (round 3) | teacher nemotron |
|---|---|---|---|---|
| cases scored | 358 of 414 | 414 | 414 | 414 |
| field F1 | 21.5 | 84.8 | **90.2** | 97.1 |
| precision | 12.6 | 80.2 | **90.9** | 95.8 |
| recall | 75.2 | **89.9** | 89.5 | 98.4 |
| value-match | **93.5** (n=170) | 93.1 (n=231) | 93.0 (n=230) | 99.6 (n=253) |
| empty-correct (n=180) | 25.3 | 77.8 | **91.1** | 96.1 |
| over-attrib (n=126) | 80.6 | 25.4 | **11.9** | 4.0 |
| wrong-field (n=54) | 63.5 | 14.8 | **1.9** | 3.7 |
| choice-correct (n=36) | 0.0 | **100.0** | 97.2 | 100.0 |
| tp / fp / fn | 170 / 1184 / 56 | 231 / 57 / 26 | 230 / 23 / 27 | 253 / 11 / 4 |
| whole-case pass rate | 27.4 (98/358) | 81.2 (336/414) | 86.5 (358/414) | 96.6 (400/414) |
| eval cost (USD) | 0.0000 | 0.0000 | 0.0000 | 0.6992 |

Bold marks the best of the three locally-served models (base / slice1b / r3-oracle) per row.
Lower is better for over-attribution and wrong-field. Rates are percentages.

**Base disclosure — read before comparing base to anything.** The base run scored **358 of
414** cases. The other 56 raised an exception in `run_case` (unparseable completions);
`run_baseline` catches it, prints it, and `continue`s, so those cases are **skipped, not scored
as failures**. Every base rate above is therefore computed over the subset of cases where base
produced parseable output, which flatters base. The skips are not uniform:

- by band: early 14, mid 18, late 24
- by expectation shape: `sets` 173 of 198 scored, `empty` 150 of 180, `choice` 35 of 36
- by scenario: pending_answer 7, third_party_name 7, restraint_question 6, wrapped_value 6,
  refusal 5, boolean_phrase 4, narrative_trap 4, chitchat 3, bulk 2, compound 2, invalid_value 2,
  residence_statement 2, unlisted_country 2, deflect 1, multi_select_subset 1, precedence 1,
  third_party_fact 1

Base's derived-rate denominators are correspondingly smaller than the other models': empty-correct
n=150 (vs 180), over-attribution n=98 (vs 126), wrong-field n=52 (vs 54), choice n=35 (vs 36; the
skipped choice case is `deflect-12`). A run that scored the unparseable cases as failures would
put base lower on every row.

## 3. v1 frozen-eval continuity (109 cases)

The v1 set is the byte-frozen 109-case regression detector from M3a. It is reported here only to
show that round 3 did not break the criteria round 2 met.

| model | samples n | observations | field F1 | P | R | value-match | empty-correct | over-attrib | wrong-field | choice-correct | whole-case pass | failing case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| slice1b (round 2) | 1 | 109 | 100.0 | 100.0 | 100.0 | 99.1 | 100.0 | 0.0 | 0.0 | 100.0 | 108/109 | correction_email-7 |
| r3-oracle (round 3) | 1 | 109 | 99.5 | 100.0 | 99.1 | 100.0 | 100.0 | 0.0 | 0.0 | 100.0 | 108/109 | edge_answer_plus_extra |
| teacher nemotron | 3 | 327 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 0.0 | 100.0 | 327/327 | none |

Sources: `baseline-sft_v2_slice1b.json`, `baseline-sft_r3_oracle_evalv1.json`,
`baseline-nemotron_v2.json`. The teacher row is `n=3` samples (327 observations over 109 cases).
The two students trade one case each: slice1b misses a value on `correction_email-7`, r3-oracle
drops a field on `edge_answer_plus_extra`.

## 4. Per depth band

| model | band | n | field F1 | P | R | value-match | empty-correct | over-attrib | wrong-field | choice-correct |
|---|---|---|---|---|---|---|---|---|---|---|
| base Qwen3.5-0.8B | early | 111 | 25.6 | 15.4 | 77.4 | 95.1 (n=41) | 44.7 (n=38) | 68.2 (n=22) | 37.5 (n=16) | 0.0 (n=28) |
| base Qwen3.5-0.8B | mid | 106 | 26.3 | 15.6 | 84.6 | 98.7 (n=77) | 14.3 (n=35) | 76.5 (n=17) | 94.4 (n=18) | 0.0 (n=3) |
| base Qwen3.5-0.8B | late | 141 | 15.4 | 8.8 | 63.4 | 84.6 (n=52) | 20.8 (n=77) | 86.4 (n=59) | 55.6 (n=18) | 0.0 (n=4) |
| slice1b (round 2) | early | 125 | 91.2 | 86.1 | 96.9 | 95.2 (n=62) | 79.5 (n=44) | 25.0 (n=28) | 12.5 (n=16) | 100.0 (n=29) |
| slice1b (round 2) | mid | 124 | 91.9 | 91.4 | 92.3 | 96.9 (n=96) | 87.8 (n=41) | 4.8 (n=21) | 20.0 (n=20) | 100.0 (n=3) |
| slice1b (round 2) | late | 165 | 73.0 | 65.8 | 82.0 | 86.3 (n=73) | 72.6 (n=95) | 31.2 (n=77) | 11.1 (n=18) | 100.0 (n=4) |
| r3-oracle (round 3) | early | 125 | 87.7 | 86.4 | 89.1 | 96.5 (n=57) | 84.1 (n=44) | 25.0 (n=28) | 0.0 (n=16) | 96.6 (n=29) |
| r3-oracle (round 3) | mid | 124 | 95.1 | 96.1 | 94.2 | 98.0 (n=98) | 97.6 (n=41) | 0.0 (n=21) | 5.0 (n=20) | 100.0 (n=3) |
| r3-oracle (round 3) | late | 165 | 86.2 | 88.2 | 84.3 | 84.0 (n=75) | 91.6 (n=95) | 10.4 (n=77) | 0.0 (n=18) | 100.0 (n=4) |
| teacher nemotron | early | 125 | 96.9 | 96.9 | 96.9 | 100.0 (n=62) | 97.7 (n=44) | 0.0 (n=28) | 6.2 (n=16) | 100.0 (n=29) |
| teacher nemotron | mid | 124 | 98.6 | 99.0 | 98.1 | 100.0 (n=102) | 100.0 (n=41) | 0.0 (n=21) | 0.0 (n=20) | 100.0 (n=3) |
| teacher nemotron | late | 165 | 95.7 | 91.8 | 100.0 | 98.9 (n=89) | 93.7 (n=95) | 6.5 (n=77) | 5.6 (n=18) | 100.0 (n=4) |

## 5. Per scenario (whole-case pass, x/18)

Sorted by delta (r3-oracle minus slice1b). :warning: marks every scenario where r3-oracle is
worse than slice1b. Base denominators vary because of its skipped cases.

| scenario | base (n scored) | slice1b | r3-oracle | teacher | delta r3 - slice1b |
|---|---|---|---|---|---|
| narrative_trap | 0/14 | 7/18 | 17/18 | 18/18 | +55.6 pp |
| third_party_name | 2/11 | 9/18 | 14/18 | 13/18 | +27.8 pp |
| invalid_value | 0/16 | 14/18 | 18/18 | 18/18 | +22.2 pp |
| multi_select_subset | 2/17 | 3/18 | 6/18 | 15/18 | +16.7 pp |
| correction | 7/18 | 16/18 | 18/18 | 18/18 | +11.1 pp |
| refusal | 1/13 | 16/18 | 18/18 | 18/18 | +11.1 pp |
| bulk | 2/16 | 11/18 | 13/18 | 18/18 | +11.1 pp |
| no_match | 10/18 | 15/18 | 17/18 | 17/18 | +11.1 pp |
| bare_ambiguous | 9/18 | 17/18 | 18/18 | 17/18 | +5.6 pp |
| chitchat | 5/15 | 17/18 | 18/18 | 18/18 | +5.6 pp |
| asks_about_field | 0/18 | 18/18 | 18/18 | 18/18 | +0.0 pp |
| boolean_phrase | 0/14 | 16/18 | 16/18 | 18/18 | +0.0 pp |
| compound | 3/16 | 12/18 | 12/18 | 18/18 | +0.0 pp |
| freetext_select | 12/18 | 18/18 | 18/18 | 18/18 | +0.0 pp |
| pending_answer | 5/11 | 18/18 | 18/18 | 18/18 | +0.0 pp |
| precedence | 3/17 | 16/18 | 16/18 | 18/18 | +0.0 pp |
| restraint_question | 1/12 | 15/18 | 15/18 | 18/18 | +0.0 pp |
| unlisted_country | 10/16 | 18/18 | 18/18 | 18/18 | +0.0 pp |
| third_party_fact :warning: | 0/17 | 12/18 | 11/18 | 18/18 | -5.6 pp |
| wrapped_value :warning: | 2/12 | 16/18 | 15/18 | 18/18 | -5.6 pp |
| deflect :warning: | 0/17 | 18/18 | 17/18 | 18/18 | -5.6 pp |
| typed_choice :warning: | 13/18 | 18/18 | 17/18 | 18/18 | -5.6 pp |
| residence_statement :warning: | 11/16 | 16/18 | 10/18 | 14/18 | -33.3 pp |

## 6. Case-level flips, slice1b -> r3-oracle

| slice1b -> r3-oracle | cases |
|---|---|
| pass -> pass | 316 |
| pass -> fail (regression) | 20 |
| fail -> pass | 42 |
| fail -> fail (joint residue) | 36 |
| total | 414 |

### 6.1 All 20 pass -> fail regressions

| id | scenario | band | user_message | expected | slice1b got | r3-oracle got |
|---|---|---|---|---|---|---|
| boolean_phrase-11 | boolean_phrase | late | I've been working full-time since I graduated. | `{"has_work_experience": true}` | `{"has_work_experience": true}` | (nothing) choice=`has_work_experience` |
| bulk-02 | bulk | late | Three things at once — my email's rmt3@student.northfield.edu, my number's 07700 900461, post goes to 88 Haly… | `{"email": "rmt3@student.northfield.edu", "phone": "07700 900461", "mailing_address": "88 Halyard Court, Apt 4B, New Bedford, MA 02740"}` | `{"email": "rmt3@student.northfield.edu", "phone": "07700 900461", "mailing_address": "88 Halyard Court, Apt 4B, New Bedford, MA 02740"}` | `{"email": "rmt3@student.northfield.edu", "phone": "(07700) 900461", "mailing_address": "88 Halyard Court, Apt 4B, New Bedford, MA 02740"}` |
| compound-05 | compound | late | 1704 Quarry Bend Parkway, Chattanooga, TN 37405 — and while I'm here, friends call me Sunny. | `{"mailing_address": "1704 Quarry Bend Parkway, Chattanooga, TN 37405", "preferred_name": "Sunny"}` | `{"mailing_address": "1704 Quarry Bend Parkway, Chattanooga, TN 37405", "preferred_name": "Sunny"}` | `{"mailing_address": "1704 Quarry Bend Parkway, Chattanooga, TN 37405", "phone": "(293) 555-6163", "preferred_name": "Sunny"}` |
| compound-06 | compound | mid | Perpetua Vanterpool. Oh, give me a ring on 0161 496 0123 too. | `{"full_name": "Perpetua Vanterpool", "phone": "0161 496 0123"}` | `{"full_name": "Perpetua Vanterpool", "phone": "0161 496 0123"}` | `{"full_name": "Perpetua Vanterpool", "phone": "(0161) 496-0123"}` |
| deflect-16 | deflect | early | I'd rather sort out enrollment first. What's on offer? | choice: `enrollment_type` | (nothing) choice=`enrollment_type` | (nothing) choice=`start_term` |
| no_match-00 | no_match | mid | Can I do a loan from my uncle instead? | (empty) | (nothing) choice=`funding_type` | `{"funding_interest": true}` |
| precedence-14 | precedence | late | Not what you asked, but give me a ring on 0161 496 0123. | `{"phone": "0161 496 0123"}` | `{"phone": "0161 496 0123"}` | `{"phone": "(016) 496-0123"}` |
| residence_statement-00 | residence_statement | early | Moved to Toronto in 2019 and I've been living in Canada since. | `{"country_residence": "CA"}` | `{"country_residence": "CA"}` | (nothing) |
| residence_statement-01 | residence_statement | mid | I'm over in Seoul these days, so South Korea. | `{"country_residence": "KR"}` | `{"country_residence": "KR"}` | `{"country_citizenship": "KR"}` |
| residence_statement-05 | residence_statement | early | Moved to Lagos in 2019 and I've been living in Nigeria since. | `{"country_residence": "NG"}` | `{"country_residence": "NG"}` | (nothing) |
| residence_statement-06 | residence_statement | early | I'm over in Seoul these days, so South Korea. | `{"country_residence": "KR"}` | `{"country_residence": "KR"}` | `{"country_citizenship": "KR"}` |
| residence_statement-07 | residence_statement | mid | Been based in Toronto for years now — Canada, that is. | `{"country_residence": "CA"}` | `{"country_residence": "CA"}` | `{"country_citizenship": "CA"}` |
| residence_statement-08 | residence_statement | early | We relocated to Canada last spring; Toronto, specifically. | `{"country_residence": "CA"}` | `{"country_residence": "CA"}` | (nothing) |
| residence_statement-11 | residence_statement | early | I'm over in Seoul these days, so South Korea. | `{"country_residence": "KR"}` | `{"country_residence": "KR"}` | `{"country_citizenship": "KR"}` |
| third_party_fact-00 | third_party_fact | early | My cousin went through this same application a couple of years back. | (empty) | (nothing) | `{"prior_application": true}` |
| third_party_name-14 | third_party_name | late | My old manager Marguerite Ibori wrote one of my references. | (empty) | (nothing) choice=`how_heard` | `{"funding_interest": true}` |
| typed_choice-05 | typed_choice | early | Put me in mechanical engineering. | `{"program": "engineering"}` | `{"program": "engineering"}` | (nothing) |
| wrapped_value-05 | wrapped_value | late | Half-listening, sorry, the kettle's going — post goes to Flat 12, 3 Kirkgate Terrace, Leeds LS2 7DJ. | `{"mailing_address": "Flat 12, 3 Kirkgate Terrace, Leeds LS2 7DJ"}` | `{"mailing_address": "Flat 12, 3 Kirkgate Terrace, Leeds LS2 7DJ"}` | `{"mailing_address": "Flat 12, 3 Kirkgate Terrace, Leeds LS2 7DQ"}` |
| wrapped_value-11 | wrapped_value | late | Typing one-handed with a toddler on me, so: 07700 900461. | `{"phone": "07700 900461"}` | `{"phone": "07700 900461"}` | (nothing) |
| wrapped_value-14 | wrapped_value | early | Ignore the background noise, upstairs neighbours again — born 28 Sep 1995. | `{"dob": "1995-09-28"}` | `{"dob": "1995-09-28"}` | `{"dob": "2025-09-28"}` |

Grouped: residence_statement 7, wrapped_value 3, compound 2, and one each in boolean_phrase,
bulk, deflect, no_match, precedence, third_party_fact, third_party_name, typed_choice (20 total).

### 6.2 fail -> pass, by scenario (42)

| scenario | n | case ids |
|---|---|---|
| narrative_trap | 10 | 00, 02, 03, 06, 07, 08, 12, 13, 15, 16 |
| third_party_name | 6 | 02, 05, 10, 13, 15, 17 |
| invalid_value | 4 | 05, 06, 08, 15 |
| bulk | 3 | 01, 05, 17 |
| multi_select_subset | 3 | 01, 07, 09 |
| no_match | 3 | 03, 12, 13 |
| compound | 2 | 03, 15 |
| correction | 2 | 10, 15 |
| refusal | 2 | 08, 14 |
| wrapped_value | 2 | 09, 15 |
| bare_ambiguous | 1 | 02 |
| boolean_phrase | 1 | 04 |
| chitchat | 1 | 15 |
| precedence | 1 | 00 |
| residence_statement | 1 | 04 |
| **total** | **42** | |

Worked examples for the biggest movers:

- **narrative_trap-02** (mid), "My daughter was born the year we moved house, 2017." Expected
  empty. slice1b set `{"dob": "2017-05-23"}`; r3-oracle set nothing. Eight of the ten
  narrative_trap flips have this shape — slice1b bound a date or a country code from
  autobiographical narration, r3-oracle bound nothing; in the other two (`-03`, `-08`) slice1b
  bound a boolean (`prior_application`, `has_work_experience`).
- **third_party_name-13** (late), "Anselm Bergkamp filled one of these out for a different
  university." Expected empty. slice1b set `{"full_name": "Anselm Bergkamp",
  "country_citizenship": "US", "country_residence": "MX"}` — the name is from the message, the
  two country codes are not. r3-oracle set nothing.
- **correction-10** (mid), "Scratch the name I gave you — use Beatrix Ohlmann instead."
  Expected `{"full_name": "Beatrix Ohlmann"}`. slice1b set `preferred_name`; r3-oracle set
  `full_name`. `correction-15` is the same substitution on a different name.
- **invalid_value-05** (mid), "I believe it was sometime in early 1993." Expected empty
  (unplaceable — no day/month). slice1b set `{"dob": "1993-01-01"}`; r3-oracle set nothing.
  All four invalid_value flips are this month-less-date-to-Jan-1 pattern (`-15` used `1993-01-31`).
- **refusal-14** (late), "Skip the Do you have relevant work experience? for me, please."
  Expected empty. slice1b set `{"has_work_experience": false}`; r3-oracle set nothing.
  `refusal-08` is the same, on `funding_interest`.

### 6.3 fail -> fail: the joint residue (36)

Cases neither student passes. This is the remaining-work list.

| scenario | n | case ids |
|---|---|---|
| multi_select_subset | 12 | 00, 02, 05, 06, 08, 11, 12, 13, 14, 15, 16, 17 |
| third_party_fact | 6 | 02, 03, 08, 09, 14, 15 |
| bulk | 4 | 00, 04, 08, 14 |
| compound | 4 | 01, 02, 09, 14 |
| restraint_question | 3 | 02, 07, 12 |
| third_party_name | 3 | 03, 08, 12 |
| boolean_phrase | 1 | 13 |
| narrative_trap | 1 | 10 |
| precedence | 1 | 17 |
| residence_statement | 1 | 16 |
| **total** | **36** | |

One example each for the top three scenarios:

- **multi_select_subset-02** (late), "Both apply: Fellowship and Scholarship." Expected
  `{"funding_type": ["fellowship", "scholarship"]}`. Both students set
  `{"funding_type": ["scholarship"]}` — one member of the pair. The teacher passes 15/18 here.
- **third_party_fact-03** (early), "My brother lives in Germany these days." Expected empty.
  Both students set `{"country_residence": "DE"}`. All six third_party_fact residue cases are
  this shape (three "My brother lives in Germany these days." -> `country_residence: DE`, three
  "My father is a Canadian citizen." -> `country_citizenship: CA`). The teacher passes 18/18 here.
- **bulk-04** (mid), "To save time — my email's k.oyelaran+apps@mailbox.org, my number's
  +49 30 901820, post goes to 62 Ashgrove Crescent, Ottawa, ON K1S 5B6." Expected all three
  fields; both students set phone and mailing_address and dropped `email`.

## 7. Error-cause breakdown

### 7.1 Positive-expectation (`sets`) cases — 198 total

For each failed `sets` case, each expected field is classified as **dropped** (field id absent
from `got_sets`) or **wrong value** (present, value differs). The **same digit-string** column is
the subclass of wrong-value where stripping non-digits from expected and got yields the same
non-empty string. **Extra fields** counts field ids in `got_sets` that are not in `expect`.

| model | failed `sets` cases | expected fields dropped | wrong value | ... of which same digit-string | extra fields set |
|---|---|---|---|---|---|
| slice1b (round 2) | 38 | 26 | 16 | 3 | 8 |
| r3-oracle (round 3) | 39 | 27 | 16 | 6 | 7 |
| teacher nemotron | 7 | 4 | 1 | 0 | 4 |

Per-field detail:

```
slice1b -- dropped by field: {'mailing_address': 8, 'funding_interest': 6, 'preferred_name': 4, 'full_name': 3, 'email': 2, 'country_residence': 2, 'has_work_experience': 1}
slice1b -- wrong-value by field: {'funding_type': 12, 'mailing_address': 1} ; same-digit by field: {'phone': 3}
slice1b -- extra fields: {'preferred_name': 2, 'country_citizenship': 2, 'phone': 1, 'email': 1, 'has_work_experience': 1, 'country_residence': 1}
slice1b -- dropped ids: compound-01/mailing_address; compound-02/preferred_name; compound-14/preferred_name; compound-15/full_name; bulk-01/mailing_address; bulk-04/email; bulk-05/mailing_address; bulk-08/mailing_address; bulk-08/preferred_name; bulk-14/mailing_address; bulk-14/preferred_name; bulk-17/email; correction-10/full_name; correction-15/full_name; wrapped_value-15/mailing_address; residence_statement-04/country_residence; residence_statement-16/country_residence; boolean_phrase-04/funding_interest; boolean_phrase-13/has_work_experience; multi_select_subset-05/funding_interest; multi_select_subset-06/funding_interest; multi_select_subset-13/funding_interest; multi_select_subset-14/funding_interest; multi_select_subset-15/funding_interest; precedence-00/mailing_address; precedence-17/mailing_address
r3 -- dropped by field: {'country_residence': 8, 'funding_interest': 5, 'preferred_name': 4, 'mailing_address': 2, 'has_work_experience': 2, 'funding_type': 2, 'program': 1, 'full_name': 1, 'email': 1, 'phone': 1}
r3 -- wrong-value by field: {'funding_type': 8, 'dob': 1, 'phone': 1} ; same-digit by field: {'phone': 5, 'mailing_address': 1}
r3 -- extra fields: {'country_citizenship': 5, 'phone': 1, 'email': 1}
r3 -- dropped ids: typed_choice-05/program; compound-01/full_name; compound-01/mailing_address; compound-02/preferred_name; compound-14/preferred_name; bulk-04/email; bulk-08/preferred_name; bulk-14/preferred_name; wrapped_value-11/phone; residence_statement-00/country_residence; residence_statement-01/country_residence; residence_statement-05/country_residence; residence_statement-06/country_residence; residence_statement-07/country_residence; residence_statement-08/country_residence; residence_statement-11/country_residence; residence_statement-16/country_residence; boolean_phrase-11/has_work_experience; boolean_phrase-13/has_work_experience; multi_select_subset-00/funding_type; multi_select_subset-05/funding_interest; multi_select_subset-06/funding_interest; multi_select_subset-13/funding_interest; multi_select_subset-14/funding_interest; multi_select_subset-14/funding_type; multi_select_subset-15/funding_interest; precedence-17/mailing_address
teacher -- dropped by field: {'country_residence': 4}
teacher -- wrong-value by field: {'funding_type': 1} ; same-digit by field: {}
teacher -- extra fields: {'funding_interest': 3, 'full_name': 1}
teacher -- dropped ids: residence_statement-01/country_residence; residence_statement-06/country_residence; residence_statement-11/country_residence; residence_statement-16/country_residence
```

Caveat on the same-digit-string subclass: 5 of r3-oracle's 6 are phone punctuation
(`0161 496 0123` -> `(0161) 496-0123`); the 6th, `wrapped_value-05`, has an identical digit
string but a changed postcode letter (`LS2 7DJ` -> `LS2 7DQ`), so it is a transcription error,
not a reformat. All 3 of slice1b's are phone punctuation or space-stripping.

### 7.2 Empty-expectation cases — 180 total

Which fields get set when nothing should be.

| model | empty cases scored | cases with any set | fields set | field ids set (count) |
|---|---|---|---|---|
| base Qwen3.5-0.8B | 150 | 112 | 570 | country_residence 62, full_name 53, country_citizenship 50, dob 36, program 35, enrollment_type 29, start_term 28, mailing_address 27, gender 26, prior_application 26, funding_interest 23, email 22, +15 more |
| slice1b (round 2) | 180 | 40 | 49 | country_residence 11, country_citizenship 9, dob 7, full_name 5, funding_interest 5, prior_application 5, enrollment_type 2, has_work_experience 2, phone 2, email 1 |
| r3-oracle (round 3) | 180 | 16 | 16 | funding_interest 5, prior_application 4, country_citizenship 3, country_residence 3, has_work_experience 1 |
| teacher nemotron | 180 | 7 | 7 | how_heard 3, anything_else 1, funding_interest 1, mailing_address 1, prior_application 1 |

## 8. Value-transcription check

Restricted to cases where structure is not the variable — only the value is.

Both students produced exactly the expected field ids on **162 of the 198** `sets` cases. On 18 of those 162, at least one value differs from expected:

| id | band | field | expected | slice1b | r3-oracle |
|---|---|---|---|---|---|
| compound-03 | mid | phone | `"0161 496 0123"` | `"01614960123"` :x: | `"0161 496 0123"` |
| compound-06 | mid | phone | `"0161 496 0123"` | `"0161 496 0123"` | `"(0161) 496-0123"` :x: |
| compound-09 | mid | phone | `"07700 900461"` | `"07700900461"` :x: | `"(07700) 900461"` :x: |
| bulk-00 | early | phone | `"07700 900461"` | `"(07700) 900461"` :x: | `"(07700) 900461"` :x: |
| bulk-02 | late | phone | `"07700 900461"` | `"07700 900461"` | `"(07700) 900461"` :x: |
| wrapped_value-05 | late | mailing_address | `"Flat 12, 3 Kirkgate Terrace, Leeds LS2 7DJ"` | `"Flat 12, 3 Kirkgate Terrace, Leeds LS2 7DJ"` | `"Flat 12, 3 Kirkgate Terrace, Leeds LS2 7DQ"` :x: |
| wrapped_value-09 | early | mailing_address | `"88 Halyard Court, Apt 4B, New Bedford, MA 02740"` | `"New Bedford, MA 02740"` :x: | `"88 Halyard Court, Apt 4B, New Bedford, MA 02740"` |
| wrapped_value-14 | early | dob | `"1995-09-28"` | `"1995-09-28"` | `"2025-09-28"` :x: |
| multi_select_subset-01 | mid | funding_type | `["teaching_assistantship", "research_assistantship"]` | `["research_assistantship"]` :x: | `["teaching_assistantship", "research_assistantship"]` |
| multi_select_subset-02 | late | funding_type | `["fellowship", "scholarship"]` | `["scholarship"]` :x: | `["scholarship"]` :x: |
| multi_select_subset-07 | late | funding_type | `["teaching_assistantship", "research_assistantship"]` | `["research_assistantship"]` :x: | `["teaching_assistantship", "research_assistantship"]` |
| multi_select_subset-08 | late | funding_type | `["fellowship", "scholarship"]` | `["fellowship"]` :x: | `["scholarship"]` :x: |
| multi_select_subset-09 | late | funding_type | `["research_assistantship", "scholarship"]` | `["research_assistantship"]` :x: | `["research_assistantship", "scholarship"]` |
| multi_select_subset-11 | late | funding_type | `["teaching_assistantship", "research_assistantship"]` | `["research_assistantship"]` :x: | `["research_assistantship"]` :x: |
| multi_select_subset-12 | late | funding_type | `["fellowship", "scholarship"]` | `["scholarship"]` :x: | `["scholarship"]` :x: |
| multi_select_subset-16 | late | funding_type | `["fellowship", "scholarship"]` | `["scholarship"]` :x: | `["scholarship"]` :x: |
| multi_select_subset-17 | late | funding_type | `["teaching_assistantship", "fellowship"]` | `["fellowship"]` :x: | `["fellowship"]` :x: |
| precedence-14 | late | phone | `"0161 496 0123"` | `"0161 496 0123"` | `"(016) 496-0123"` :x: |

:x: marks the value that does not match. Of the 18 rows: 9 are `funding_type` multi-select
subsets missing one of the two expected options; 5 are phone reformatting with the same digit
string (spaces vs parentheses-and-hyphens vs stripped); 1 is a dropped phone digit (r3-oracle,
`precedence-14`, `0161` -> `016`); 1 is a truncated address (slice1b, `wrapped_value-09`); 1 is a
postcode letter change (r3-oracle, `wrapped_value-05`); 1 is a year change 1995 -> 2025
(r3-oracle, `wrapped_value-14`).

## 9. Invented-PII spot check

Across all 36 `third_party_name` and `third_party_fact` cases, every `email` / `phone` / `dob` /
`mailing_address` value in either student's `got_sets` was checked against the case's
`user_message` plus full `conversation_history` (literal substring, then digit-string). One case
produced values present in neither:

| id | band | model | field | value |
|---|---|---|---|---|
| third_party_name-08 | late | slice1b | email | `marguerite.ibori48@example.com` |
| third_party_name-08 | late | slice1b | phone | `(587) 555-8460` |

`third_party_name-08` user_message: "Marguerite Ibori filled one of these out for a different
university." slice1b's full output on that case:
`{"full_name": "Marguerite Ibori", "country_citizenship": "OTHER", "country_residence": "US", "email": "marguerite.ibori48@example.com", "phone": "(587) 555-8460"}`.
r3-oracle's output on the same case: `{"prior_application": true}` — wrong, but nothing
invented. r3-oracle produced no invented PII value on any of the 36 cases.

## 10. Observations

Factual patterns only.

- r3-oracle beats slice1b on field F1 (90.2 vs 84.8), precision (90.9 vs 80.2), empty-correct
  (91.1 vs 77.8), over-attribution (11.9 vs 25.4) and wrong-field (1.9 vs 14.8), and is behind on
  recall (89.5 vs 89.9), value-match (93.0 vs 93.1) and choice-correct (97.2 vs 100.0).
- False positives fall from 57 to 23; false negatives rise from 26 to 27; true positives fall from
  231 to 230.
- On empty-expectation cases, cases-with-any-set falls from 40 to 16, and fields-set from 49 to 16.
  slice1b sets more than one field on 5 of its 40 (three cases with 2 fields, one with 3, one with
  5); r3-oracle and the teacher never set more than one field on an empty case.
- Whole-case pass: base 98/358, slice1b 336/414, r3-oracle 358/414, teacher 400/414.
- narrative_trap moved 7/18 -> 17/18; third_party_name 9/18 -> 14/18; invalid_value 14/18 -> 18/18;
  correction 16/18 -> 18/18; refusal 16/18 -> 18/18; multi_select_subset 3/18 -> 6/18.
- residence_statement moved 16/18 -> 10/18: 7 regressions, 1 gain (`-04`), 1 joint-residue failure
  (`-16`). In all 7 regressions the message names a country of residence; r3-oracle set
  `country_citizenship` instead on 4 (`-01`, `-06`, `-07`, `-11`) and set nothing on 3 (`-00`,
  `-05`, `-08`). The teacher scores 14/18 on the same scenario; all 4 of its failures are the
  identical message "I'm over in Seoul these days, so South Korea." (`-01`, `-06`, `-11`, `-16`).
- `country_citizenship` is r3-oracle's most common extra field on failed `sets` cases (5 of 7);
  slice1b's extra fields are spread across 6 field ids.
- Per band, r3-oracle is below slice1b on early (F1 87.7 vs 91.2) and above on mid (95.1 vs 91.9)
  and late (86.2 vs 73.0).
- The late band is the weakest for both students (r3-oracle F1 86.2, value-match 84.0) and for the
  teacher (F1 95.7 vs 98.6 mid).
- On empty cases the teacher's 7 sets are spread over 5 field ids with no repeat above 3
  (`how_heard` 3); r3-oracle's 16 are spread over 5 field ids (`funding_interest` 5,
  `prior_application` 4).
- The teacher fails 14 of 414: 4 residence_statement (all the Seoul message), 5 third_party_name,
  3 multi_select_subset, 1 bare_ambiguous, 1 no_match. All 3 multi_select_subset failures add
  `funding_interest: true` where the expectation does not include it (`-09` also drops one
  `funding_type` option); the expectation includes `funding_interest` exactly on the 5 cases where
  `pending == funding_interest`.
- r3-oracle's only choice-band failure is `deflect-16`: it offered `start_term` where
  `enrollment_type` was expected.
- 5 of the 20 regressions are same-field wrong-value (`compound-06`, `bulk-02`, `precedence-14`
  phone; `wrapped_value-05` postcode letter; `wrapped_value-14` dob year); the other 15 differ in
  which fields were set.

## 11. Limitations

- **Base's 56 skipped cases** (section 2). Base's rates are computed over 358 cases and are not
  comparable to the 414-case runs. The scorer skips unparseable completions rather than failing
  them.
- **n=1 for every run.** The teacher is nominally temp-0 but served remotely, so its single
  sample is not a guaranteed-reproducible draw; the v1 continuity table's teacher row is the only
  multi-sample run here (n=3, no flaky cases). `stability.flaky` is empty in all four v3 runs,
  which for n=1 is vacuous.
- **Bands have uneven scenario mixes**, so cross-band comparisons are descriptive, not controlled.
  Six scenarios are missing a band entirely:

| scenario | early | mid | late |
|---|---|---|---|
| compound | 0 | 12 | 6 |
| correction | 0 | 12 | 6 |
| freetext_select | 0 | 15 | 3 |
| invalid_value | 0 | 17 | 1 |
| pending_answer | 0 | 12 | 6 |
| residence_statement | 12 | 6 | 0 |

  So residence_statement contributes nothing to the late band, and compound, correction,
  freetext_select, invalid_value and pending_answer contribute nothing to the early band. Band
  totals are also unequal (early 125 / mid 124 / late 165).
- **Repeated messages.** The 414 cases contain 286 distinct (scenario, user_message) pairs; the
  most-repeated message appears 5 times. Contexts differ per case, but a single message-level
  behaviour can move up to 5 cases at once (e.g. 3 of the 7 residence_statement regressions and
  all 4 of the teacher's residence_statement failures are the same Seoul sentence).
- **The `third_party_name` expectation of empty is a declared v3 ceiling**, not a correctness
  fact (see `tuning/v2/M4_PLAN.md`, "Eval v3 design decisions"): a system with a deferred-hint
  mechanic should carry the mention forward. Both students and the teacher lose cases to it.
- **Positive-band cases ignore choices.** `score_observation` checks only the set fields for
  `sets` cases, so a model that both sets the right field and also offers an unrelated choice
  still passes (e.g. slice1b passes `typed_choice-05` while recording `choice_field=start_term`).

---

## 12. Addendum (2026-08-02): final-harness re-baseline

After this report was generated, three harness changes closed the SFT era (see
`M4_PLAN.md` "Issue #1 fix — DONE" and `doc-18.1` Stage-2 addendum): a provenance gate
in the validator (a non-choice value not supported by the current user message is
DROPPED — nothing is set, the field re-asks), a country alias table in `match_options`
("Britain"→UK, "America"→US), and phone canonicalization in `coerce` (digits-only
storage; the scorer compares phone fields by digit string, so the frozen eval files are
unchanged). The eval set is byte-identical; only the harness and scorer changed. All
four models were re-run; JSONs carry the `_final` suffix.

| v3 (414 cases) | base* | r3-oracle | teacher |
|---|---|---|---|
| field F1 | 26.0 | 89.9 | 97.3 |
| precision / recall | 15.8 / 74.0 | 91.5 / 88.3 | 95.8 / 98.8 |
| value-match | 95.2 | 96.5 | 99.6 |
| empty-correct | 32.7 | 91.1 | 95.6 |
| over-attribution | 76.5 | 11.9 | 5.6 |
| wrong-field | 50.0 | 1.9 | 1.9 |
| choice-correct | 0.0 | 97.2 | 100.0 |
| whole-case pass | 114/359 | 363/414 | 400/414 |

\* base scored on 359 parseable cases, 55 skipped (same caveat as §2). slice1b was not
re-run — its §2 numbers stand as the round-2 record on the pre-fix harness.

r3-oracle vs its own §2 numbers: whole-case pass 358 → **363** (5 fixed, 0 broken —
three phone-punctuation cases pass via canonicalization, one case recovers because the
gate blocks an invented extra phone, one day-first date passes after the date-span fix),
value-match 93.0 → **96.5**. Field F1 dips 90.2 → 89.9 by accounting only: three
wrong-value transcriptions (`LS2 7DQ`, year `2025`, a dropped phone digit) are now
DROPPED by the gate instead of landing as matched-field-wrong-value, converting tp to
fn; the same three cases failed under both harnesses, and the wrong value no longer
reaches the form. v1 tripwire unchanged (99.5 / 100.0). The gate's first live run also
caught its own defect — a date-span finder narrower than `coerce`'s formats dropped six
correct day-first dates — fixed by deriving span support from `coerce` itself
(token-window scan), so the two cannot drift again; the numbers above are post-fix.

---

Generated 2026-07-26 by the eval pipeline; §12 added 2026-08-02. Source JSONs in
`tuning/v2/eval/` (final-harness runs suffixed `_final`).
