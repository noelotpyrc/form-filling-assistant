# Doc 19 — How we evaluate the tuning work

**Written 2026-07-28.** How we evaluate the v2 tuning line: what a test case is,
where cases and answers come from, what the numbers mean, and the rules that make a
number trustworthy. Not a results doc — for those read
[`tuning/v2/eval/REPORT_evalv3.md`](../tuning/v2/eval/REPORT_evalv3.md) (or the HTML
next to it). No DSPy or project history needed.

---

## 1. What we are testing

This framework sits on the redesigned v2 harness — the extract-then-respond
pipeline around a deterministic core described in
[`doc-18-harness-redesign.md`](doc-18-harness-redesign.md) (turn logic in
[`doc-18.1-turn-logic.html`](doc-18.1-turn-logic.html)). Everything below assumes
that design: the eval exists to measure the student *inside* that harness, not as
a free-standing language model.

A small student model (Qwen3.5-0.8B, LoRA-tuned) reads a chat message and pulls
form answers out of it. It does not fill the form: it emits `(field, value)` pairs,
and a deterministic harness — validator plus composer — decides where each value
goes, coerces it to the field's type, matches it against the option list, and
rejects what it cannot place. So we do not score the model's raw text. We score
**what lands on the form after the harness has run**, through the same entry point
production uses (`FormAssistant.forward`: extract → validate → compose). Not a
parallel rig: when the harness changes, the eval sees it. The responder call is
skipped (`with_response=False`) — these metrics cover extraction only.

## 2. The one-turn eval case

One case is one user turn, frozen. It carries:

| part | what it is |
|---|---|
| `form_state` / `pending` | fields already filled; the field the assistant last asked about (or `null`) |
| `conversation_history` | the messages before this turn |
| `user_message` | the turn we are scoring |
| `expect` | the correct outcome. `sets` — these exact fields, these exact values, nothing else. `empty` — nothing may be set. `choice` — offer options on the named field, and set nothing |
| `band` | how deep in the form we are: `early` / `mid` / `late` |
| `scenario`, `variant`, `source` | which behaviour this probes, and which session/turn the context came from |

A positive case, verbatim from `eval_set_v3.jsonl` (line breaks added, nothing
else changed):

```json
{"id": "precedence-00", "scenario": "precedence", "band": "early", "variant": "frame0",
 "form_state": {}, "pending": "program", "source": {"session": 120, "turn": 1},
 "conversation_history": [{"role": "assistant", "content":
   "Welcome to Northfield University's Graduate Application! 🎓\n\nTo get started, which program are you interested in?"}],
 "user_message": "Before I forget — post goes to Unit 9, 250 Coalbrook Row, Dunedin 9016, New Zealand.",
 "expect": {"sets": {"mailing_address": "Unit 9, 250 Coalbrook Row, Dunedin 9016, New Zealand"}}}
```

The assistant asked about `program`, the user answered something else, and a
confident address must not be shoved into the pending slot.

An empty case, same file:

```json
{"id": "third_party_name-00", "scenario": "third_party_name", "band": "early", "variant": "frame0",
 "form_state": {}, "pending": "program", "source": {"session": 103, "turn": 1},
 "conversation_history": [{"role": "assistant", "content":
   "Welcome to Northfield University's Graduate Application! I'm here to help you through the process step by step.\n\nFirst, what program are you interested in applying for?"}],
 "user_message": "Anselm Bergkamp is the one who talked me into going back to school.",
 "expect": {"empty": true}}
```

A name in the message is not the applicant's name; setting `full_name` fails.

## 3. Where cases come from, and why that changed

Three versions; each fixed a real defect in the one before it.

**v1 — 109 cases, hand-built contexts (M3a).** Twelve message templates filled from
random personas (8 each) plus 13 hand-authored edge cases. Every case shipped
`conversation_history: []`, a state the product cannot reach: the assistant always
greets first, so the user never speaks into an empty history. Worse, 24 cases set
`pending` with no history — a question asked nowhere. When SFT round 1 was scored,
22 of its 27 failures were exactly those `pending_name` / `pending_phone` /
`boolean` cases. We were measuring an impossible state.

**v2 — 143 cases, one line of history.** Each realistic case got a deterministic
history line that makes its `pending` reachable (111 realistic; the 32 old
bare-history cases stayed as an ungated robustness band). The unreachable states were
gone, and the student promptly scored F1 99.6 on the realistic band, tying the
teacher. But every realistic case still had exactly **one** history message and a
near-empty form. Real failures happen mid-conversation, with eight fields filled and
ten turns of history in the prompt — v2 could not see them.

**v3 — 414 cases, real contexts.** 23 scenarios × 18. We keep the authored half
(message + expectation) and take the **context** from the simulator:
`datagen.farm_session` records `{form_state, pending, history}` at every turn of a
real session. v3 samples those snapshots from 30 held-out sessions (seeds 102–131;
132–191 stay reserved and unread), throws away the snapshot's own user message, and
injects ours. Each snapshot is used **once**. Turn 0 is excluded — its history is
empty for the same reason v1's was.

The lesson: **hand-authored contexts drift into states the product can never reach;
sampled contexts are reachable by construction.** Sample the context; author only
the message.

## 4. Where the correct answers come from

We write the expectations ourselves. That is the oracle idea, and it is simpler
than it sounds: **we built the message, so we already know the answer.** Injecting
"post goes to Unit 9, 250 Coalbrook Row…", the generator knows it just wrote a
mailing address into a turn whose pending field is `program`. Message and
expectation come out together — `variants()` returns `[(message, expect)]` as one
unit — so there is nowhere to attach an expectation afterwards, and nowhere to
sneak in a scoring-time exemption for a case the model keeps failing.

**Why not label with the teacher.** The teacher is a 550B model and still gets 14
of v3's 414 cases wrong (~3%). It is also inconsistent on conventions we designed:
on a refusal it sometimes returns `[]`, sometimes an engagement pair, and we
standardise on one. Grading the student against teacher output measures imitation,
not correctness, and bakes the teacher's mistakes into the ceiling. Two safety nets
keep the oracle honest:

1. **Coercion round-trip (a build gate).** Every expected value must survive the
   harness's own canonicalization (`validator.coerce`, `match_options`), and the
   canonical result is stored. An expectation the harness cannot process is a bug in
   the expectation, not a hard case for the model; the build fails.
2. **An independent teacher pass, read by hand.** We run the teacher over the whole
   set once and a human reads **every disagreement** — 17 on v3. Eight were our
   mistakes and were corrected; the other expectations stood. The audit catches bad
   expectations without making the teacher the judge. (Those counts come from the
   construction record, not the JSONs in `tuning/v2/eval/`.)

## 5. Guard rails learned the hard way

Each rule below exists because we shipped the mistake first. For each: what went
wrong, a concrete example, then the rule that now prevents it.

- **The exam must not quote the textbook.** We once trained the model on the
  sentence pattern `"I'm {name} and you can reach me at {email}."` — and one eval
  question was *"I'm Yuki Rossi and you can reach me at yuki.rossi63@example.com."*
  Word-for-word the same sentence, different name. Passing that question proves the
  model remembers the sentence, not that it can extract from new phrasing. This
  happened twice, and a "remember to grep for this" rule caught only the first one.
  **Rule:** an automated build step compares every eval phrasing against every
  training phrasing (with the fill-in-the-blank values stripped) and refuses to
  build the eval on a match.

- **Eval values must look different from training values.** Every phone number the
  training generator makes looks like `(892) 555-1089`; every email looks like
  `first.last##@example.com`. We proved (1,366-call stress sweep) that the model
  never repeats a training value verbatim — but when it *invents* a value, the
  invention has exactly those shapes. So if eval answers also had those shapes, a
  "correct" answer could just be the model auto-completing a familiar pattern
  rather than reading the message. **Rule:** eval values use shapes the generator
  never produces — `0161 496 0123`, `rmt3@student.northfield.edu`, UK postcodes —
  so a right answer can only come from reading.

- **Report scores by how full the form is.** The same model that is near-perfect
  at the start of a conversation falls apart near the end: round 2 scored F1 89
  when the form was nearly empty and 75 when it was nearly complete. Average those
  into one number and the collapse disappears. **Rule:** every case is tagged
  `early` (0–3 fields filled), `mid` (4–7), or `late` (8+), and results are
  reported per band.

- **One conversation, one question.** If five eval questions share the same
  conversation as their context, and that one conversation happens to be odd, one
  quirk counts as five failures (or five passes). **Rule:** each sampled
  conversation snapshot is used for exactly one case.

- **A scenario must not quietly collapse into one sentence.** Each scenario has
  4–6 different phrasings, but not every phrasing fits every context. Left to
  itself, the builder once filled a 19-case scenario with just two sentences — 14
  copies of one, 5 of the other — and the summary table looked fine. **Rule:** the
  build fails unless every scenario uses at least 4 distinct phrasings, and it
  reserves a context for each phrasing before filling quotas.

- **Never turn a harness bug into a "correct answer".** One case said *"the 3rd of
  March, 1994"* and expected the model to extract nothing — but only because our
  date parser doesn't know that format. A model that answers `1994-03-03` has read
  the date correctly and would be marked wrong. The case was removed. Same logic
  for "Britain" and "America": our option matcher fails to map them to United
  Kingdom / United States, which is a matcher bug to fix, not a behavior to demand.
  **Rule:** if the only reason an expectation holds is a harness limitation, the
  case does not go in the eval.

## 6. The metrics

Every case falls into one scoring band, derived from its expectation: `positive`
(`sets`), `choice`, `no_value` (`empty`, value-free noise), or `unplaceable`
(`empty`, a real-looking value with no valid target — the `ambiguous`, `no_match`,
`bare_date`, `bare_ambiguous`, `invalid_value` scenarios).

| metric | plain meaning | computed on |
|---|---|---|
| field precision | of the fields we set, how many should have been set | all cases |
| field recall | of the fields we should have set, how many we set | all cases |
| field F1 | the two combined into one number | all cases |
| value-match | for fields we correctly identified, how often the value is right | the overlap of expected and set fields |
| empty-correct | cases where nothing should be set, and nothing was | `no_value` + `unplaceable` |
| over-attribution | grabbed a field out of value-free noise (lower is better) | `no_value` |
| wrong-field | put a real value on a field it does not belong to (lower is better) | `unplaceable` |
| choice-correct | offered options on the expected field, and set nothing | `choice` |

**Whole-case pass** is the strict one, and the headline: a `sets` case passes only
if the field ids match exactly *and* every value matches; an `empty` case only if
nothing was set; a `choice` case only if a choice was offered on an expected field
and nothing was set. No partial credit.

On sampling: the teacher has no temperature or seed control, so we run each case
`--n` times, pool the rates, and list any case whose samples disagree
(`stability.flaky`). The student is served locally at temperature 0, so `n=1` is a
real draw for it — but at `n=1` an empty `flaky` list proves nothing, and a report
should say so.

## 7. Beyond the frozen set

The frozen set is one turn at a time, on cases we chose. Two other harnesses cover
what it cannot. **The stress sweep** (`tuning/v2/stress_invent.py`) is the
off-distribution probe: every turn it builds contains **no** bindable answer, so the right output is always
"set nothing", and it varies the pressure around that: message content, how full
the form is, which field is pending, how deep the history runs, whether PII sits in
the history — 576 calls per checkpoint. Each emitted value is classified by where it
could have come from: `supported` (in the utterance), `from_history` (copy-forward),
`from_corpus` (verbatim from training), `novel_in_format` (nobody wrote it, but it
is shaped exactly like the training generator's output), `other_novel`, plus
`semantic` for choices and booleans where a substring check means nothing. The last
three are invention — this is how we learned the model memorised formats, not
values.

**The multi-turn probe** (`tuning/v2/probe.py`) runs whole conversations: an LLM
user talks to the real system through `sim.run_session`, then an offline assertion
layer checks the transcript, final form state, and persona. It catches what only
shows up across turns — re-asking a filled field, a trap value binding six turns
later, the submit gate.

Which to use: the **frozen set** gates a training round (fast, free, comparable to
every earlier round); the **sweep** shows behaviour under pressure (when you suspect
invention or over-attribution); the **probe** buys end-to-end confidence.

## 8. Anchors and reproducibility

The rule from `CLAUDE.md`, in friendly words: **before you trust a new number,
reproduce an old one.** Run the harness in no-op mode on an input whose answer you
already recorded. If it does not reproduce, the harness has drifted from the
reference system, and any improvement you measure later is an artifact of the drift,
not of your change. Block the expensive run on that check.

Anchors are model-specific — they catch harness drift, not real differences between
models. Each checkpoint gets its own anchor via `tuning/harness/calibrate.py`, and
two models under comparison each run on their own port against their own anchor. The
stress sweep does this by default: it rebuilds one known real failure from the probe
log and aborts if the output differs.

Eval sets are frozen files, not code that regenerates. **v1 is byte-frozen** — a
regression detector, nothing changes in it ever. **v3's 8-case correction happened
before the first baseline was run**, during the teacher audit at build time; once
baselines exist a set is closed, and a wrong one gets a new version. **`--label` is
required** for v2 and v3 runs, so a run cannot overwrite a baseline by defaulting
to the old name.

## 9. File map

| file | what it is | when you touch it |
|---|---|---|
| `tuning/v2/eval/eval_set.jsonl` | v1, 109 cases, byte-frozen | never |
| `tuning/v2/eval/eval_set_v2.jsonl` | v2, 143 cases (111 realistic / 32 contract) | never; kept for continuity |
| `tuning/v2/eval/eval_set_v3.jsonl` | v3, 414 cases on real sampled contexts — the current yardstick | never edit; rebuild as v4 if it is wrong |
| `tuning/v2/eval_gen.py` | the v3 builder: scenarios, variants, value pools, build gates | adding a scenario or a guard rail |
| `tuning/v2/eval_score.py` | the scorer and the runner; `--selftest` is free and offline | changing a metric or a band |
| `tuning/v2/stress_invent.py` | off-distribution sweep for invention and over-attribution | investigating hallucinated values |
| `tuning/v2/probe.py` | multi-turn behavioural probe of whole sessions | before trusting a checkpoint end-to-end |
| `tuning/v2/eval/baseline-*.json` | one run's full output: metrics, per-band, per-case raw | written by a run; read when comparing |
| `tuning/v2/eval/REPORT_evalv3.md` | the current four-model comparison, source of record | when a new model is scored |
| `tuning/v2/eval/REPORT_evalv3.html` | the same report, styled and cross-linked for reading | regenerated from the markdown |

---

Related: **doc-18** §6 (the eval's origin, the success criteria) · **doc-18.1**
(turn logic — why the harness owns placement) · `tuning/v2/M4_PLAN.md` ("Eval v3
design decisions", "Oracle-as-labeler", "Invention stress sweep") · `CLAUDE.md`.
