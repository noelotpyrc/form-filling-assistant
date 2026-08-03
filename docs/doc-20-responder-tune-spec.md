# Doc 20 — Tuning the responder (SFT slice 2) and how we grade it

**Written 2026-08-03.** A build spec. The extractor half of the student is
finished; this is the plan for the other half — the text responder — and, in more
detail, the eval that decides whether it worked. Read
[`doc-21-status-and-roadmap.md`](doc-21-status-and-roadmap.md) first for where the
project stands; read [`doc-19-eval-framework.md`](doc-19-eval-framework.md) for the
extractor eval this design copies.

Every number below is either cited to a file or marked OPEN.

---

## 1. Why now, and what is in scope

The extractor is done. `r3-oracle` scores 363/414 whole-case on eval v3 on the
final harness (F1 89.9, value-match 96.5, wrong-field 1.9 — the last one ties the
teacher), recorded in
[`tuning/v2/eval/REPORT_evalv3.md`](../tuning/v2/eval/REPORT_evalv3.md) §12. The
SFT era for the extractor is closed; the remaining extractor gaps are RL work
(doc-21 §4).

The responder is the untrained half. Today the deployable stack is a hybrid:
student extractor on MLX, teacher responder over the network. Tuning the responder
replaces the last remote call and completes the all-student on-device story before
the RL phase starts.

**Scope: one SFT slice, no iteration planned.** This is a style task, not a
judgment task. The composer has already decided what the turn does — every action
and every directive is produced by deterministic code in
`tuning/v2/composer.py::compose` and `tuning/v2/prestep.py::run` before the
responder is called. The responder's whole job is to render that decision as
prose. See `tuning/v2/program.py::Respond`:

> The actions for this turn have ALREADY been decided (shown in actions_taken).
> Your job is only to verbalize them naturally and follow the guidance.

If one slice does not clear the gates, the answer is more targeted rows, not a
different architecture.

**Out of scope:** the extractor (frozen), the composer's decisions (code), the
web-app wiring (doc-21 §4 chapter 3).

---

## 2. The eval design — two tiers

The core idea, stated plainly: **the composer's directives are the ground truth
for what a response must contain.** We know the turn acknowledges a set, or asks
for `start_term`, or apologizes for a validation error, because code decided it
and handed the decision to the responder as a string. So most of the eval is
deterministic code comparing prose against the directive list that produced it.
This is the same oracle move as the extractor eval (doc-19 §4 — "we built the
message, so we already know the answer"), one layer up.

### Tier-1 — code-scored, $0, GATES the round

Five check families. All run offline against a captured `(inputs, prose)` pair; no
model, no network.

| check | what it asserts | why it exists |
|---|---|---|
| **format** | the completion is a well-formed responder target — `[[ ## response_text ## ]]` … `[[ ## completed ## ]]`, no stray markers leaking into the prose. Reuse `datagen.is_well_formed("responder", …)`. | The teacher emits malformed markers on roughly half of farm turns (measured below). `program.strip_markers` papers over it at serve time and `sim_to_sft.canon_responder` fixes the training targets, but the student must emit clean markers on its own. |
| **directive realization** | every directive and action the harness produced this turn is reflected in the prose: `ask_target(f)` / `reask_pending(f)` → the reply asks about that field; `clarify(f)` → the reply asks the user to clarify it; `ack(x)` → the reply acknowledges `x`; `fix(err)` → apology plus a re-ask; `submit_blocked` → says it can't submit yet and offers save-or-continue; `terminal` → invites review and submit; a `set_fields` action → the set is acknowledged (an ack cue — "great", "thanks", "got it" — or the field name; **amended 2026-08-03** from "by name always" after the teacher baseline hand-read: teacher style is a generic ack, and restating five field names after a bulk set is the verbosity we're training away). A field asked via its option labels ("full-time or part-time?") counts as asking that field. | This is the whole job. A responder that writes pleasant prose about the wrong field is broken in a way no rubric score catches reliably. |
| **grounding** | every email / phone / date / number token appearing in the prose exists in `form_state`, in the schema (labels and option labels), or in this turn's `user_message`. | The motivating incident: on a deflect turn in `tuning/v2/datagen_runs/h1_probe_mix2/`, the teacher responder invented admissions and funding policy — "part-time students are typically eligible for fewer funding opportunities (like teaching or research assistantships)…". Nothing in the schema says that. **Reuse `validator.value_supported(f, value, user_message)`** — the shared support test built for the extractor provenance gate (M4_PLAN "Issue #1 fix — DONE"). Do not write a second one; the last time this logic was duplicated, the copy drifted and dropped six correct dates (REPORT §12). |
| **echo fidelity** | a state value repeated in the prose matches `form_state` exactly (after the same canonicalization `validator.coerce` applies — phone fields compare by digit string, per the 2026-08-02 phone change). | "I've got your number as (415) 782-3311" when the form holds something else is a trust bug, and it is free to detect. |
| **verbosity** | token count per turn stays inside a budget indexed by turn type (ask / ack / clarify / terminal / submit_blocked). | The known wordiness mode is option re-enumeration: the composer already emits an `ask_choice` action carrying the option list, and the responder re-lists every option in prose on top of it. Budgets are OPEN (§6). |

Tier-1 gates the round. If it fails, the round fails; no judged number overrides
it.

**Amended 2026-08-03 (user decision): thresholds are reference lines, not the
verdict.** The go/no-go on the tuned student is made by hand-reading its actual
failures on the frozen set, not by a mechanical threshold pass. Reference lines
(set under the teacher's measured numbers: directive ≥90, grounding ≥99, echo
≥99, verbosity ≥90; format ≥99 pre-committed) say where to look first; the
item-8 report must carry a per-case failure dump (case, check, reason, prose) so
that reading is possible. What stands from the original framing: a Tier-2 judged
number still never overrides Tier-1 findings.

**Tier-1 doubles as training curation.** Teacher prose is the label — an oracle
cannot write style, so unlike the extractor's round-3 corpus there is no
oracle-labeling option here. But a teacher row that fails Tier-1 is **dropped**,
not repaired. Teacher writes, code vetoes: exactly the division the extractor
convention table uses in `sim_to_sft.py` (`CURATION` / `curation_passes` — passes
completions through unchanged, drops violators, never rewrites).

**Known gap — eval-time vs serve-time directives (2026-08-03).** The frozen
set's `actions`/`directives` are recomputed from the **teacher** extractor's
temp-0 pairs. At serve time the **student** extractor drives `compose`, so the
responder sees a slightly different directive distribution wherever the student
extracts differently (its known gaps: multi-select subsets, third-party facts,
residence statements). Tier-1 therefore measures responder quality **given
correct harness decisions**; end-to-end all-student behavior is the probe's job
(`probe.py`), not this eval's.

### Tier-2 — LLM-judged, ~$1-2, REPORTED, never gates

Two parts, on the frozen responder eval set:

1. **Fixed rubric** — tone, coherence, helpfulness, scored per turn.
2. **Pairwise win-rate against the teacher's response on the same turn.**

Tier-2 never gates, because a judged number moves when the judge moves, and a
gate that moves is not a gate. It exists to notice things Tier-1 was not built to
see. **If Tier-2 finds something alarming, the fix is a new Tier-1 check** — the
judgment migrates into code. That is the project's standing direction, and every
Tier-1 check listed above got there the same way.

---

## 3. Session partition

Farm sessions are the only source of realistic conversation contexts, and they
are a finite, allocated resource. Two of the four rows below are **hard
commitments already in force** and must not be touched: seeds 102-131 are the
contexts eval v3 is built on (doc-19 §3), and seeds 162-191 are reserved, unread,
for RL prompts. The 132-161 assignment is decided here (2026-08-03).

| sessions (seeds) | run dir | snapshots | responder turns | use |
|---|---|---|---|---|
| 1-10 | `datagen_runs/h1a/` | 143 | **143** | responder training |
| 132-146 | `datagen_runs/eval_farm_p3/` | 222 | **222** | responder training |
| 147-161 | `datagen_runs/eval_farm_p4/` | 223 | **223** | frozen responder eval |
| 162-176 | `datagen_runs/eval_farm_p5/` | 238 | 238 | UNTOUCHED — RL prompts |
| 177-191 | `datagen_runs/eval_farm_p6/` | 212 | 212 | UNTOUCHED — RL prompts |
| 102-116 | `datagen_runs/eval_farm_p1/` | 224 | 224 | UNTOUCHED — eval v3 contexts |
| 117-131 | `datagen_runs/eval_farm_p2/` | 229 | 229 | UNTOUCHED — eval v3 contexts |

Counts verified from each run's `report.json` (`snapshots`,
`pairs.by_module.responder`) and `wc -l snapshots.jsonl`. One farm turn produces
exactly one responder call, so snapshots and responder turns are equal by
construction.

- **Training pool: 143 + 222 = 365 responder turns.** The seeds 1-10 rows are the
  farm half of the H1 corpus; they appear in `sft_data/h1a_merged`,
  `sft_data/h1b_merged` and `sft_data/r3_oracle_merged` as 143 rows each time,
  split differently (118/25, 126/17, 115/28 train/val). They all come from the one
  run, `datagen_runs/h1a/` (`pairs.by_source_module["farm/responder"] = 143`).
- **Frozen eval: 223 turns** from seeds 147-161.
- Reserved for RL: 238 + 212 = **450 snapshots** across seeds 162-191.

**One structural fact the eval must handle:** in `eval_farm_p3`, 107 of 222 turns
produced no extractor row at all. Those are pre-step-handled turns — `[system]
User selected option: …`, `[system] User clicked: …`, `[system] Validation error
…` — where `prestep.run` settles the turn and `program.forward` skips the
extractor but still calls the responder (`tuning/v2/prestep.py:38-69`,
`program.py:224-256`). Roughly half of all responder turns are these. The
directive-realization check must therefore cover the pre-step directives (`ack`,
`fix`) as first-class cases, not as an afterthought.

---

## 4. Guidance tweaks come first — and force a re-capture

Two parked decisions land before any responder data is captured (M4_PLAN "Parked
decisions" → "Pre-slice-2 responder guidance tweaks"):

**(a) Option re-enumeration verbosity.** When the composer emits an `ask_choice`
action the UI already renders the buttons; the guidance should tell the responder
not to re-list them in prose. Touches `program.py::render_guidance` (the
`ask_target` branch) and/or the `Respond` docstring.

**(b) Grounding.** Add to the guidance: outside the form, say you don't know;
never invent policy. This is the fix for the `h1_probe_mix2` fabricated-funding-
policy turn, and it is the behaviour the Tier-1 grounding check measures.

**(c) OPEN:** temperature > 0 for the datagen responder LM via
`program.assign_lms(respond_lm=…)`, for prose variety in training targets. Eval
stays at temperature 0 either way. Not decided (§6).

### The re-capture consequence — read this before writing any code

The responder rows already captured in `eval_farm_p3/train.jsonl` and
`eval_farm_p4/train.jsonl` embed the **current** system prompt inside their
`messages` array. `render_guidance` and the `Respond` signature docstring are both
rendered into that prompt by DSPy's ChatAdapter. Edit the guidance, and every
captured row now trains the student on a prompt that serving will never send —
a train/serve mismatch, the same class of defect as demos-in-prompt (M4_PLAN P4,
resolved by stripping demos precisely for this reason).

**So: after the tweaks, the responder targets must be re-captured.** Both the
training turns and the frozen-eval turns. The mechanism is a replay:

1. Read each turn's snapshot from `datagen_runs/<run>/snapshots.jsonl` — it
   carries `{session, turn, form_state, pending, history, user_message}`
   (`datagen.py:340`).
2. `state = datagen.rebuild_state(schema, snap)` (`datagen.py:1112`).
3. `agent(state=state, user_message=snap["user_message"], history=snap["history"],
   with_response=True)` with the teacher LM.
4. `rows, _ = datagen.capture_pairs(lm, prev, True, base)` — content-based
   classification and chain grouping, already handles the ChatAdapter's silent
   JSON retry.

That is exactly the loop in `datagen.run_injection` (`datagen.py:1230-1245`),
differing only in `with_response=True` and in replaying a recorded message
instead of templating a new one. Follow that plumbing; do not invent a parallel
capture path.

**Cost.** 365 + 223 = 588 turns. `forward(with_response=True)` makes two LM calls
per turn (extractor + responder), except on the ~48% pre-step-handled turns where
only the responder fires — so roughly **900-1,180 teacher calls**. Anchor for the
arithmetic: a full 414-case extractor pass on paid nemotron cost **$0.7073**
(`eval/baseline-teacher_nemotron_v3_final.json`). Responder completions are longer
than extractor completions, so budget **$1-2**, not $0.70. (Cheaper option, OPEN:
replay only the responder call by driving `program.respond` directly with a
recomputed `actions_taken` / `guidance`, which skips the extractor call entirely
and is deterministic from the snapshot.)

**Nothing else changes.** The snapshots are the frozen substrate; re-capture
rewrites labels against them, so the session partition in §3 still holds and the
frozen eval set is still built from seeds 147-161 only.

---

## 5. Build items, in order

Each item is done when its acceptance criterion passes. Items 1-5 are offline and
free; 6-8 cost money.

**1. Guidance tweaks in `program.py` + smoke.**
Accept: `tuning/v2/smoke_deterministic.py` still passes 46/46; a hand-run turn
with an `ask_choice` action shows the responder no longer re-listing options; the
grounding line is present in the rendered system prompt.

**2. Replay-capture script.**
A small module over `snapshots.jsonl` following §4. Accept: on a 5-turn dry run
with the teacher, the captured `messages` byte-match an offline render of the new
prompt (the `datagen.run_parity` / `parity_offline` pattern), and every captured
responder completion passes `datagen.is_well_formed` after
`sim_to_sft.canon_responder`.

**3. Tier-1 scorer module** (`tuning/v2/eval_responder.py` or similar).
All five check families from §2. Accept: an offline `--selftest` flag, in the
style of `eval_score.py --selftest` and `sim_to_sft.py`'s selftest, with
hand-built pass and fail cases for **every** check — a fabricated policy sentence,
a phone digit not in state, a reply that asks the wrong field, an over-budget
option re-enumeration, a leaked `[[ ## … ]]` marker. Selftest runs with no
network and no model.

**4. Frozen responder eval-set builder.**
Turns from seeds 147-161 only, one file, written once. Accept: 223 cases, each
carrying the snapshot inputs plus the harness-computed `actions` and `directives`
(recompute them, don't trust a stale capture), and a build gate that fails if any
session outside 147-161 appears. Frozen from the moment the first baseline is run.

**5. Curation wiring in the bridge.**
`sim_to_sft.py` currently canonicalizes responder rows and drops nothing
(`transform`, line ~199). Add the Tier-1 veto for `module == "responder"`, matching
the extractor's drop-and-log behaviour. Accept: the run report gains a responder
drop table (count + reason per row), and the selftest covers a dropped row.

**6. Teacher baseline on the frozen set.**
Run the teacher responder over all 223 cases, score Tier-1, read the failures by
hand. Accept: a baseline JSON in `tuning/v2/eval/` with a `--label`, plus **gate
thresholds set from these numbers**. This is the M3a pattern: criteria are locked
*after* the teacher's numbers exist, not invented in advance (doc-18 §7 —
teacher = 100% on the frozen extractor set, then criteria were written under it).
Format is the exception: the student must emit clean markers **≥99%** regardless
of what the teacher does, because `canon_responder` guarantees the training
targets are clean.

**7. SFT via the existing Modal pipeline.**
`tuning/sft/train_sft_format_modal.py` with `SFT_TRAIN_DATA` / `SFT_VAL_DATA`
pointed at `sft_data/<run>/{train,val}_responder.jsonl`, and `SFT_APP` /
`SFT_VOLUME` set to a **fresh** volume so no earlier checkpoint is clobbered.
Run with `tuning/v2/.venv/bin/modal` from the repo root. Then
`tuning/sft/merge_lora_modal.py` (`SFT_LORA_DIR` / `SFT_VOLUME`) → fp16 →
`mlx_vlm.convert` → `mlx_vlm.server --model <mlx dir> --port 810X`. Note the
serving quirk from H3: the request body's `model` field must be the real model
path, and `V2_STUDENT_MODEL` must match it.
Accept: eval loss recorded; the served model answers a smoke turn.

**8. Student eval, Tier-1 + Tier-2.**
Tier-1 on the frozen 223 against the step-6 gates; Tier-2 rubric + pairwise
win-rate reported next to it, never gating. Accept: a report in
`tuning/v2/eval/` in the shape of `REPORT_evalv3.md`, disclosing any case the
student failed to parse.

**Whether the responder is a second LoRA or one merged model is still open.** P4
built `program.assign_lms(extract_lm=, respond_lm=)` precisely so the two
predictors can run on different ports and different artifacts, and the
one-vs-two question was explicitly deferred "to slice 2, decided empirically"
(M4_PLAN P4). Two LoRAs is the low-risk default — it cannot regress the frozen
extractor — and a mixed single model is the thing to compare against on both the
v3 extractor eval and the responder eval.

### Cost summary

| item | cost |
|---|---|
| re-capture (step 2, 588 turns) | ~$1-2 |
| Modal train + merge (step 7) | ~$3 (slice-1 runs were ~$0.15 each; budget headroom for retries) |
| Tier-2 judging (step 8) | ~$2 |
| Tier-1, selftests, eval-set build | $0 |

### Standing execution rules

- **Sub-agents build offline.** A sub-agent writes code and selftests. It never
  calls an LLM, never spends money, never commits, never pushes.
- **Live and paid runs belong to the orchestrator**, after explicit user
  confirmation of model, sizes, paths and budget — taken literally, no
  substitutions (CLAUDE.md "Working with the user").
- **Detach long runs from the task system.** Use `nohup` plus a monitor loop.
  Background tasks have been killed externally twice; a 40-minute capture that
  dies at minute 35 costs real money.
- **Every eval run needs `--label`.** `eval_score.py` enforces this for v2 and v3
  (`eval_score.py:441`) so a run cannot overwrite a baseline; the responder scorer
  must do the same.
- **Frozen sets are never edited once a baseline exists.** If the set is wrong,
  build a new version. Same rule as eval v1 and v3 (doc-19 §8).
- **Reproduce before you trust.** Before the student eval, replay a recorded
  teacher turn through the harness and confirm the recorded output. If it does not
  reproduce, stop — the harness has drifted and the comparison is meaningless
  (CLAUDE.md, doc-19 §8).

---

## 6. Open decisions

Each of these is genuinely undecided. Do not fill one in silently.

| # | decision | notes |
|---|---|---|
| 1 | **Tier-2 judge model.** | Cost, availability and drift all matter. OpenRouter free routes churn and the free cap is account-wide (M4_PLAN "Parked"), so a paid slug is probably right for a number anyone will quote. |
| 2 | **Verbosity budgets.** | Per turn type, in tokens. Set them from the teacher-baseline distribution at step 6 rather than guessing now. |
| 3 | **Temperature > 0 for the datagen responder LM** (parked option (c)). | **DECIDED 2026-08-03: temperature 0** — reproducible captures, consistent with every prior artifact. Revisit only if the tuned responder sounds robotic on eval. |
| 4 | **Gate thresholds.** | Set at step 6 from the teacher's Tier-1 numbers. The one pre-committed number is format ≥99%. |
| 5 | **One model or two LoRAs.** | See step 7. Decided empirically, on both evals. |
| 6 | **Cheap re-capture path.** | **DECIDED 2026-08-03: full `forward()` replay** (`recapture.py`) — matches serving exactly, follows the `run_injection` plumbing; the respond-only saving (~$1) wasn't worth hand-recomputing harness state. |

---

Related: **[doc-21](doc-21-status-and-roadmap.md)** (status and roadmap; this doc
is chapter 1) · **[doc-19](doc-19-eval-framework.md)** (the extractor eval this
design copies) · **[doc-18](doc-18-harness-redesign.md)** §6-7 (harness, training
plan, milestone table) · `tuning/v2/M4_PLAN.md` ("Parked decisions", "Responder
data-gen (slice 2, sketch)", "Issue #1 fix — DONE") · `CLAUDE.md`.
