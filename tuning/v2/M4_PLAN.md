# M4 — SFT the student (execution tracker)

Working tracker for M4: distill the 0.8B student from the teacher, measure the
gap vs the locked criteria. **Design rationale** lives in
[doc-18 §7](../../docs/doc-18-harness-redesign.md) (training plan) and §6
(eval + criteria); this file is just execution state, updated as we go.

## Scope decision — extractor-first
M3a (frozen eval, criteria, `teacher_v2`) is all **extractor-only**
(`with_response=False`). Extractor targets are **0% malformed**; the responder is
**~1/3 malformed** (M2, `[[v2-m2-pilot-findings]]`) — but now **cleaned for free in
P2** (canonicalize, see Parked → resolved). So:
- **M4 slice 1 = extractor only** — matches the measuring stick we already have;
  fastest path to the thesis number.
- **Responder is no longer a blocked/heavy item** — its targets are clean-ready
  from P2. It can join slice 1 or a later slice; grading it still needs a
  responder eval (Tier-1 grounding / Tier-2), which we haven't built yet.

## Status snapshot (2026-07-14)
- ✅ Teacher **FINAL**: `nvidia/nemotron-3-ultra-550b-a55b:free` via `OpenRouterLM`
  (native messages, temp=0, $0/call) + one native compound demo + validator
  bare-value guard + enriched country labels → **`nemotron_v2` = 100% on all
  Tier-1** (109×3, 109/109 stable, `eval/baseline-nemotron_v2.json`). The
  sonnet-era `teacher_v2` baseline is historical (claude CLI path = legacy,
  demo-incompatible).
- ✅ Frozen eval: 109 cases (`eval/eval_set.jsonl`), scorer `eval_score.py`.
- ✅ Student criteria (extractor, frozen set): F1 ≥ 95, value ≥ 97, empty-correct ≥ 85,
  over-attribution ≤ 8, wrong-field ≤ 10, choice ≥ 95.

## Data-gen design — hybrid: context farm + behavior injection (2026-07-02)

Replaces "refactor `sim.py`". Rationale: multi-turn sim is a good **context
generator** but a bad **behavior controller** (M2 directive-fidelity finding);
single-turn synthesis is the opposite. Split the jobs; `sim.py` stays in place
as the M2 pilot reference; new module: **`datagen.py`**.

**Shared taxonomy.** One behavior vocabulary, shared with `eval_set.py`
(templates: single/multi value, select_by_label, boolean, bulk, pending-answer,
correction, asks_about_field, chitchat; edges: trap, bare_ambiguous, deflect,
typed_choice, restraint, precedence, no_match, refusal, compound, wrapped_value,
third_party, freetext_select, bare_date). Injection templates draw from this
taxonomy but with **disjoint instances** (different personas/seeds/values) — the
frozen 109 stay held out.

**Layer 1 — context farm (multi-turn).** LLM-U ↔ `build_teacher(schema)`
sessions run *natural* (default "answer" flow, programmatic personas + styles,
no behavior quotas — we stop demanding what the sim is bad at). Per-turn it
logs a **snapshot** `{form_state, pending, history, user_message}` (new — old
sim kept only turn text + final `filled`) and captures the natural turns as
training pairs (this is the bulk pending→answer data, and later the responder
corpus).

**Layer 2 — behavior injection (single-turn, quota-driven).** For each behavior:
sample a snapshot whose **preconditions** hold, template a message performing
that behavior, optionally naturalize, run one `forward(with_response=False)` at
that snapshot, capture the pair. Exact per-behavior counts. Preconditions
(checked in code):

| behavior | needs from snapshot |
|---|---|
| correction | target field already filled |
| deflect / asks_about_field / restraint / refusal | a pending set |
| typed_choice | pending is a `button_choice` field |
| no_match | pending is a select |
| precedence | pending of type X; inject clear value of type Y |
| compound | pending set + another unfilled field for the extra value |
| trap / bare_* (no-pending cases) | fall back to **constructed minimal contexts** — the farm rarely yields no-pending states, and these behaviors are inherently context-light |

**Naturalizer (thin).** Cheap `claude -p` rephrase of the templated message in
persona voice/style. Key liberty vs the eval: **training needs no
correct-by-construction expect — the teacher's output IS the label** — so the
naturalizer may rephrase freely as long as the behavior intent survives.

**Capture path.** Same `lm.history` pattern as sim/eval_score, plus: module
tagging by predictor (not system-prompt substring), **strip the teacher demos
from captured `messages`** (ChatAdapter renders them as extra user/assistant
pairs between system and final user — drop the middle pairs; P1 decision:
student learns the behavior, not the crutch), record `behavior` +
`source=farm|inject` per pair.

**Gates before scale (H1).** (a) Parity anchor: run the new capture on a
context the old `sim.py` also produced; `(messages, completion)` shape/format
must match. (b) Coverage report: per-behavior counts vs quota, no silent gaps.
(c) Cleanliness: sim_report-style malformed/hallucinated checks on a pilot.

**Why the cost works.** ~17-turn M2 session ≈ $0.88 (~$0.28 of it LLM-U). Each
farmed snapshot forks into many injected cases; an injected case costs one
extractor call — no U-turn, no session overhead. Realistic-context cost is
amortized across cheap behavior-controlled cases; coverage becomes designed,
not incidental.

### Pilot1 result (2026-07-10) — gates FAILED, root cause found
`--farm 3 --inject --quota 5`, $15.10 (vs ~$5 est). Farm mechanics fine (3/3
sessions completed, 43 snapshots, personas unique) — but parity FAILED,
coverage collapsed (10/80 injections captured, all farm "extractor" rows were
actually responder calls). Root cause via live probes:
1. **DSPy ChatAdapter silently retries via JSONAdapter** on marker-parse
   failure → one Predict = up to 2 lm.history entries → count/position tagging
   (the P1 spec) is unsound. Chat and JSON attempts can also disagree
   semantically. → **Fix in flight:** content-based classification (signature
   field in system → module; closing instruction → chat/json), chain grouping,
   train on chat entries only, retry/malformed rates in the report.
2. **Teacher chat compliance broke:** demo-free extract is clean TODAY, but
   extract WITH the LabeledFewShot demos (flattened to one user string by
   ClaudeLM._split) fails ~85–90%; responder (no demos) drifted ~19–33% (M2) →
   ~100% (unpinned `sonnet` alias / CLI 2.1.206). Retro-caveat: the
   teacher_v2=100% baseline ran through the JSON-fallback path (semantically
   valid, format claim void). The alias resolves to **claude-sonnet-5** as of
   2026-07-10 (CLI JSON `modelUsage`) — the June runs almost certainly ran an
   earlier sonnet, i.e. the drift is a model upgrade under the alias.
   → **Resolved (2026-07-13):** (a) pinned **claude-sonnet-5** as the code
   default in claude_lm.py (user call; re-baseline as teacher_v3 pending).
   (b) demo mechanism **retired** — band tests on pinned sonnet-5 showed the
   defect persists demo-free (bare_date 0/3) AND survives a sharpened Extract
   instruction ("never pick the field from its type alone" — ignored, 0/3,
   $1.22 band `eval/baseline-sonnet5_instr_band.json`). Sonnet-5 pragmatically
   binds a lone date to dob regardless of prompt. → policy moved into CODE:
   **bare-value demotion guard** in the deterministic shell (message that is
   entirely a bare date/number → demote confident attributions to {null} →
   cascade places: pending still binds (elliptical_dob unaffected), no-pending
   → CLARIFY). Model-independent (holds for the student too), smoke-testable
   free. Implementation + demo removal + offline-rendered parity anchor (the
   old byte-anchor breaks by design after prompt edits) in flight.
   (Provenance nice-to-have: ClaudeLM could record the CLI's resolved
   `modelUsage` id per call.)

### Teacher pivot (2026-07-13/14) — RESOLVED: nemotron via OpenRouter
User call: teacher = `nvidia/nemotron-3-ultra-550b-a55b:free` through the new
`OpenRouterLM` (native messages array → demos attach as real turns; temp=0;
usage-cost capture; free-tier backoff). Audition on the frozen eval was **$0**:
`nemotron_v1` = F1 99.1 (fp=0), native `{null}` on bare dates, 2 deterministic
misses → fixed free: **country option labels** in the form JSON (activates
`match_options`; `freetext_select` 0→100) and **one native compound demo**
(`build_extract_demos`, pending-answer+extra → both pairs; `compound` 0→100).
**`nemotron_v2` = 100% on every Tier-1 metric** (fix-band + full re-baseline
both 100%, zero regressions). Notes: temp=0 ≠ perfect format determinism
(occasional JSON-fallback; content-based capture handles it); free tier ≈
20 req/min & ~1000/day (account has credits); ~7s/call. Remaining wiring:
`datagen.py --backend` so pilot2's teacher is nemotron (LLM U stays sonnet).

### Responder data-gen (slice 2, sketch)
Same farm+injection architecture, but coverage is indexed by **directive/action
state** (ack / fix / submit_blocked / ask_target / reask_pending / clarify /
terminal / buttons / preview), not user-message type. Sources: farm turns cover
ask/ack/terminal free; flipping injection to `with_response=True` (teacher $0)
covers clarify/reask/choice; submit/save intents and `[system] Validation
error` events are injectable messages; and — unique to the responder — rare
directive combos can be generated by **direct respond-call injection** (its
`actions_taken`/`guidance` inputs are rendered by deterministic code, so
enumerate combos and call only the respond step). Build items when slice 2
starts: tag responder rows with fired directive kinds (coverage accounting) +
the responder eval (M3b) to grade any of it.

## Plumbing (P) — do first; all small, free/cheap, individually verifiable
- [x] **P1 — DONE 2026-07-14.** `datagen.py` hybrid generator, gates read green on **pilot2**
      (nemotron teacher $0 + sonnet U, `datagen_runs/pilot2/`): parity PASS (captured system
      byte-equals offline render), coverage 74/80 with all gaps accounted (1 API 502, rest
      json-only chains), extractor targets **0.0% malformed / 0.0% retried** (91/91), 117 pairs,
      $1.28. Caveats → P2/H1: responder chat_malformed 46% (P2 canonicalization is load-bearing);
      OpenRouterLM should also retry error-in-body 5xx (farm session 3 lost to an upstream 502)
      before H1 scale.
- [x] **P2 — DONE 2026-07-15.** `sim_to_sft.py`: reshape to trainer format (`messages` + assistant target),
      responder targets canonicalized uniformly via the shared `strip_markers()` (post-canon
      `is_well_formed` asserted, idempotent), malformed extractor rows dropped loudly (observed 0),
      **group-aware seeded split** (farm session / snapshot session / constructed singletons — no persona
      straddles train/val), per-module outputs `sft_data/<run>/{train,val}_{extractor,responder}.jsonl`.
      Verified on pilot2: 117→117, 12 responder targets fixed + 14 normalized, 26/26 well-formed post-canon,
      shape matches the v1 trainer's input. → P3: point `LOCAL_TRAIN_DATA`/`LOCAL_VAL_DATA`
      (train_sft_format_modal.py:31-37, stale `~/work/…` root) at `sft_data/<run>/{train,val}_extractor.jsonl`
      + make the input path a CLI param (slice 1 = the extractor files).
- [x] **P3 — DONE 2026-07-15.** Trainer data paths env-parameterized (`SFT_TRAIN_DATA`/`SFT_VAL_DATA`,
      read at module scope for Modal's import-time image build), defaults = the v1 files resolved
      repo-relative from `__file__` (stale `~/work/…` gone). v2 slice-1 usage documented: point the env
      vars at `sft_data/<run>/{train,val}_extractor.jsonl` and `modal run` from repo root. H2 note:
      app/volume names still v1 (`sft-format-*`) — give slice-1 its own volume to avoid clobbering v1
      checkpoints.
- [x] **P4 — DONE 2026-07-15.** `student_lm.py` (StudentLM -> local MLX OpenAI endpoint, temp=0, stub-server selftest), `program.assign_lms(extract_lm=, respond_lm=)` per-predictor override (verified against dspy source: `lm = kwargs.pop("lm", self.lm) or settings.lm`), `eval_score --backend student --port` with a **demo-free FormAssistant** (student trains on demo-stripped prompts; teacher's in-context demo at eval would be a train/serve mismatch). Original design note kept below.
      Was: **student LM + eval wiring.** `dspy.BaseLM` → served MLX student (OpenAI endpoint; 3.3.0b1 has no
      litellm, so custom like `OpenRouterLM`) + a `student` backend in `eval_score.py`. Smoke vs any served
      model. **Design requirement: per-PREDICTOR LM assignment** (a `{module → lm/port}` map via
      `predictor.lm`, not one global LM) — the two calls are fully decoupled through the deterministic core,
      and the working hypothesis (user, 2026-07-15) is that we'll run **different models per predictor**:
      extractor student vs responder student as separate SFT artifacts (same base, two LoRAs, two ports), and
      the slice-1 deployable is student-extractor + nemotron-responder. One-vs-two decided empirically at
      slice 2 (mixed vs split SFT, compared on frozen eval + responder eval). *new:* `student_lm.py`;
      *edit:* `eval_score.py`, serving path

## Heavy (H) — one at a time; each gated on the pipes above
- [x] **H1 — DONE 2026-07-20/21.** Probes (haiku-U approved: 3 sessions eyeballed + mix probe) →
      pre-H1 hardening (naturalizer → OpenRouter `V2_NAT_MODEL`; farm `--mix` non-answer directives;
      composer CLARIFY agenda guard; registry 16→20: deflect_free / partial_select / invalid_value /
      cross_select + trap/restraint widening; validator multi_select conjunction support, smoke 30/30) →
      main run `h1a` (10 farm sessions all complete+filled, mix 0.15; inject 13/20 behaviors before the
      account-wide free-cap hit — naturalizer shares the pool, my miss) → `--behaviors` top-up `h1a_fill`
      next UTC day (8 behaviors 200/200; naturalizer = PAID tencent/hy3 after the :free route was pulled
      same-day — free routes churn) → **audit + curation in the bridge** (per-behavior convention table;
      443/49 kept/dropped — incl. bare_date 12 dob-bindings, refusal 8 engagements) → row-weighted split fix.
      **Corpus `sft_data/h1a_merged/`: train_extractor 439 / val_extractor 110 / train_responder 118 /
      val_responder 25; extractor chat_malformed 0/598.** Cost ≈ $1.64. Teacher format: 598/598 clean.
- [x] **H2 — DONE 2026-07-21/23 (two rounds).** Env-parameterized names (`SFT_APP`/`SFT_VOLUME`), fresh
      volumes per slice (v1 checkpoints untouched). slice1: 439 rows, 11.5 min L4, eval_loss 0.143.
      slice1b (round-2 corpus, 594 rows): 16 min, eval_loss 0.131. ~$0.15/run.
- [x] **H3 — DONE.** merge_lora env-parameterized (`SFT_LORA_DIR`/`SFT_VOLUME`); artifacts on external
      SSD (`/Volumes/Extreme SSD/form-filling-models/`): lora → Modal merge → fp16 → `mlx_vlm.convert`.
      Serve: `mlx_vlm.server --model <mlx dir> --port 810X` (body `model` field must be the real path —
      this server version loads whatever repo the request names; V2_STUDENT_MODEL must match).
- [x] **H4 — DONE 2026-07-23 (round 2). THESIS RESULT: student ≈ teacher.**
      Round 1 (slice1): F1 90.0 / value 91.1 — failed 2 criteria; error analysis → 3 buckets
      (thin-context null-fallback never trained beyond dates; value transcription; compound).
      Round 2 (slice1b, +175 targeted rows): **frozen v1: F1 100 / value 99.1 — ALL 6 criteria pass.**
      eval v2 realistic band: student F1 99.6 = teacher F1 99.6 (nemotron N=3, value 100 vs 99.1).
      Untrained base Qwen3.5-0.8B: F1 20.3 (710 fp). Baselines committed in `eval/`.
      Total cost incl. all data: < $5. Known floor: rare value transcription slips (~1%).

## Readiness of v1 assets
| asset | state |
|---|---|
| `sft/train_sft_format_modal.py` (Qwen3.5-0.8B, L4, Unsloth LoRA) | ✅ proven; module-agnostic (v2's 2 modules fine); ⚠️ stale data path (P3) |
| `sft/merge_lora_modal.py` | ✅ exists |
| MLX serve pattern (`mlx server --model … --port`) | ✅ documented (CLAUDE.md) |
| format bridge (P2), student LM (P4) | ❌ to build |

## M3b hybrid probe findings (2026-07-24) — student issues DOCUMENTED, fix methodology TBD

Run: `probe_runs/m3b_hybrid/` — 26 sessions (13 scenarios × 2 seeds), hybrid = slice1b
extractor (MLX, port 8101) + nemotron responder + haiku LLM-U. All 26 completed to the
submit gate; every behavioral assertion passed (opening, terminal, conditionals, save,
premature-block, status, trap-no-bind on the story values, refusal, invalid→clarify→fix).
Latency p50 3.8s/turn (bundles nemotron responder + its 502 retries; student-only share
not yet isolated). Value mismatches vs persona decomposed into three causes:

1. ~~Harness bug~~ (fixed same day): prestep selected-option no-match set the raw label
   ('Save Draft' → prior_application). Now: no hits → no set.
2. **STUDENT ISSUE #1 — hallucinated PII under narrative pressure** (trap seed-1 turn 3):
   user said only "moved to Seoul in 2019... living in South Korea... miss Brazil";
   student emitted 4 pairs incl. **email `sara.yamamoto14@example.com` and phone
   `(892) 555-1089` — never uttered by anyone**, shaped exactly like training personas
   (memorized-value regurgitation), plus citizenship=KR over-attributed from "living in".
   Elicited by mid-form state + rich history — the frozen eval's thin contexts never
   trigger it (over-attr 0% there). Frequency: 1 turn / ~355. Worst class: invents PII.
3. **STUDENT ISSUE #2 — enthusiasm read as boolean yes** (refusal seed-2): "I'm ready to
   knock this out!" → has_work_experience=True. Over-attribution from filler tone.
4. Simulator infidelity (~6 cases): haiku deviated from persona (other country, partial
   address, different corrected dob); student extracted the utterance faithfully — NOT
   student errors. Probe now separates these (utterance-support classification).

**Fix methodology NOT decided — discuss before acting.** Candidate directions, each with
open questions: (a) round-3 training data: farm-context trap/filler injections (existing
trap behavior is empty-context; the failure needed mid-form history) — but does more
restraint data actually remove memorized-value regurgitation, or just lower its rate?
(b) decoding/serving guard: values emitted by the extractor that appear nowhere in the
turn's inputs could be dropped deterministically by the validator (a "provenance check" —
code-owns-placement extended to code-owns-provenance); strongest guarantee, but needs
care with normalization (dates/formats) to avoid killing legit coercions. (c) more
epochs/data against transcription noise generally. (d) accept + monitor: rate is 0.3%
of turns, and (b) would make it structurally harmless. Leaning (b)+(a), NOT decided.
Eval-v2.1 candidates: both cases as hand-authored edges (rich-history trap w/ mid-form
state; enthusiasm-filler boolean).

**Template contamination (2026-07-24, self-caught; SECOND collision found 2026-07-25):**
round-2's `compound_volunteer` training template "I'm {a} and you can reach me at {b}."
is verbatim the eval `t_multi` frame — so `multi-0`'s round-2 pass is a contaminated
witness. **Second collision (2026-07-25):** `datagen.py:704` wrapped_value template
"In line at the store — you can text me at {v}." vs eval `edge_chitchat_with_value`
"Sorry, typing in line at the store — anyway you can reach me at (212) 555-9981." — same
scene and construction, so that case is contaminated too. The compound-skill closure is
therefore down to **2 clean witnesses** (edge_answer_plus_extra, probe bulk turns with
organic phrasing), not 3. Remediate next datagen round: replace both templates.
The manual grep rule was insufficient (it missed this one) — replace it with a BUILD STEP:
strip slots from every eval template and every training template, fail the build on a
frame match or high overlap. See the eval-gen design below (decision 2).

## Invention stress sweep (2026-07-25) — `stress_invent.py`, 1366 calls, 3 checkpoints

Built to answer two questions about student issue #1: does the eval use out-of-sample
values, and what triggers the hallucination? `tuning/v2/stress_invent.py` — student
extractor only (temp 0, no responder, no LLM-U, $0), 576 constructed turns per
checkpoint that contain NO bindable answer (correct output = set nothing), each emitted
(field, value) classified `supported / expected_hint / semantic / from_history /
from_corpus / novel_in_format / other_novel`. Grid: content(6) x filled(3) x pending(6)
at history_depth=6 (block `main`, 432 calls) + content(6) x history_depth(3) x
pii_in_history(2) at filled=half (block `hist`, 144 calls), 4 personas per cell.
Anchor gate: the trap/seed-1 turn-3 input is rebuilt from `probe_runs/m3b_hybrid/
sessions.jsonl` and must reproduce the recorded sets — **ANCHOR OK on slice1b**, so the
failure is deterministic at temp 0 and the rig matches the reference system.

**Value provenance, before running anything.** eval_set.py and datagen.py call the SAME
`persona.gen_persona`, so eval values are same-format, different-seed: 0/204 train emails
and 0/96 train phones recur in eval_set_v2; 3/30 full names do (name space is only 552
pairs). The anchor's invented values are in NEITHER — `sara.yamamoto14@example.com`: 0
corpus hits ("Sara" is not even in FIRST); `(892) 555-1089`: 0 hits (area code `(892) 555`
appears 26x). Corpus audit of every free-text target value in h1b_merged: **371/371 are
literal substrings of that turn's own user_message** — 0 copy-forward, 0 invented. SFT
never saw a label that invents.

| checkpoint | calls | unparseable | set% | invention | from_corpus | from_history | semantic |
|---|---|---|---|---|---|---|---|
| base Qwen3.5-0.8B | 214 | 112 (52%) | 45.8% | 6.1% | **0** | 206 | 1181 |
| slice1 (439 rows) | 576 | 0 | 22.0% | 1.0% (6 calls / 10 values) | **0** | 37 | 59 |
| slice1b (594 rows) | 576 | 0 | 19.8% | 1.6% (9 calls / 25 values) | **0** | 9 | 75 |

`from_corpus` is 0 in all 1366 calls: **no verbatim memorization anywhere** — what was
memorized is the generator's FORMAT (`first.last##@example.com`, `(NXX) 555-XXXX`), which
is why a value-disjoint eval gives no protection. SFT did not introduce the behavior: base
invents at 7.4% on the 94 cells it shares with slice1b vs slice1b's 2.1%. slice1 -> slice1b
moved 6 -> 9 invention calls (not actionable at that n) while cutting copy-forward 37 -> 9.

**Triggers (slice1b).** filled empty/half/near_complete = 0.0% / 0.7% / **4.9%**;
content chitchat, numeric_filler, emotional_filler, deflect_ask = **0.0%** all four,
travel_story 2.8%, **third_person 8.3%**; pending email/phone = 5.6% / 2.8%, dob and
full_name 0.0%; history_depth and pii_in_history: no effect. Mechanism: a near-complete
form + a person's NAME in the turn -> the model completes the record around that name
(`"Ravi Ali in my office went through this exact process"` -> `email=ravi.ali14@example.com`,
`phone=(432) 555-1099`, `dob=1999-01-01`, `address=454 Elm Rd, Auburn, CA 30055`), and
`mailing_address="2098 Diego Johansson, China"` shows it is not even coherent.

**The sweep's larger finding — third-party name binding (NOT invention, NOT guardable).**
On `third_person` turns the friend's name is bound to `full_name` in **26/96 (slice1b)** and
**30/96 (slice1)** — bucket `supported`, because the name really is in the utterance. A
provenance check cannot touch it. `third_party` IS in the training registry (rule `empty`,
46 kept rows in round 2) yet does not transfer to a near-complete form: the same
thin-context-data / rich-context-failure pattern as the trap. Direct evidence for (a).
Boolean/choice over-attribution on non-answer turns rose round 1 -> 2:
`prior_application` 13 -> 30 values.

**Implication for the fix menu** (still NOT decided): (b) provenance check is cheap and
structurally sound — 371/371 training labels are utterance-literal, so requiring free-text
values to appear in the current utterance IS the training distribution and cannot
false-positive on a correctly learned skill; it kills all 25 slice1b invented values but
none of the ~56 supported-but-wrong or ~75 semantic ones. (a) round-3 farm-context
injections now has evidence (thin-context third_party/trap did not generalize) and is the
only lever on the third-party binding. (c) more data: slice1 -> slice1b is flat-to-worse
on both, so epochs/volume alone is not the answer. Booleans need their own rule (an
explicit affirmation token) or data — provenance cannot check `True`.
Runs: `tuning/v2/stress_runs/{base_qwen35,slice1,slice1b}/` (gitignored).

### Issue #1 fix — AGREED 2026-07-25, **DONE 2026-08-02**: validator provenance gate (code only, no retrain)

Scope: student issue #1 ONLY (unsupported free-text values). Issues #2 (boolean/choice
over-attribution) and third-party name binding stay OPEN — no provenance check can reach
them, see below.

- **Where.** `validator.py::_validate_pair` — it already receives `user_message` via
  `validate(pairs, state, user_message)`. For a non-choice field, a value the utterance
  does not support returns an outcome that sets nothing; the field stays unfilled and the
  harness re-asks. Same "code owns the decision" pattern as the `_bind_unplaced` cascade
  (code-owns-placement extended to code-owns-provenance).
- **Support test.** The logic already written as `probe.py::_invention_check` — email
  substring, phone digit-run, normalized substring for text, **coerce-span for dates**.
  Factor it into ONE shared helper so the guard, `probe.py` and `stress_invent.py` cannot
  drift apart. Dates MUST route through `validator.coerce`, never raw matching
  ("January 15, 1998" -> "1998-01-15" is not a substring) — that is the only real hazard.
- **Coverage.** All 25 invented values in the slice1b sweep are free-text (email, phone,
  dob, address) -> all 25 droppable. It removes 0 of the ~56 supported-but-wrong and 0 of
  the ~75 semantic sets.
- **Why low-risk.** 371/371 free-text training labels are literal substrings of their own
  turn's user_message, so requiring that at serve time IS the training distribution — it
  cannot reject a correctly learned skill.
- **Gates (all local, free), hard-block the change on all four:** 31/31 deterministic
  smoke; eval v1 (F1 100 / value 99.1 — tight regression detector); eval v2 realistic
  band; replay the 25 recorded invented values from `stress_runs/slice1b/results.jsonl`
  and confirm each is dropped.
- **Not decided:** whether a dropped value is logged/surfaced anywhere, and whether the
  same gate should apply to the teacher path (it is model-agnostic by construction).

**SHIPPED 2026-08-02 — as built.** `validator.value_supported(f, value, user_message)` is now
the ONE support test; `probe._invention_check` is a thin wrapper over it (persona escape hatch
kept), and `stress_invent` / `datagen` reach it through probe as before. `_validate_pair`
returns `Outcome(DROPPED, fid, "value not in message")` for an unsupported non-choice value —
nothing set, pending untouched, the composer's reask fires. The unplaced path is gated too,
AFTER `_bind_unplaced`, accepting either the text-style test or the bound field's type test, so
a canonicalized value the user spelled differently ("August 10, 2000." -> `2000-08-10`) still
binds. Built as **structural insurance for the RL phase** — the motivating failure had not
recurred with r3-oracle; the gate is there so drift under RL cannot write PII the user never
said. Gates: 46/46 deterministic smoke (was 31; +15 for the three changes, the date-format
regression and the replay) and the replay of all 25 recorded slice1b inventions ->
**25/25 DROPPED**. Eval v1 / v2 / v3 are run live by the orchestrator, not here.

**Date-support bug, found by the live v3 run and fixed 2026-08-02.** The first cut found date
spans with a REGEX, which was a second copy of `_DATE_FORMATS` and had already drifted: it did
not know the day-first `%d %b %Y` form ("2 Feb 1993") that `coerce` accepts, so the gate dropped
6 CORRECT dates on r3-oracle's v3 run (`pending_answer-03`, `compound-09`, `correction-08/14/16`,
`wrapped_value-14`). Support is now derived from `coerce` itself — a 1..5-token sliding window
over the message, each window coerced and compared to the candidate's ISO value — so any format
`coerce` learns is supported automatically and the two cannot diverge again. The same run's TRUE
drops (invented phone/email, wrong-year and wrong-digit transcriptions) are unaffected: a wrong
year off a right message still fails, and a differential over 11,340 probe comparisons shows
0 non-date behavior changes and 20 date comparisons flipping False -> True, none the other way.

**Two more harness changes in the same pass (2026-08-02).**
- **Phone canonicalization.** `coerce(value, phone)` now stores digits only, keeping a leading
  "+" ("(415) 782-3311" -> `4157823311`, "+49 30 901820" -> `+4930901820`); the >=7-digit
  ok-condition is unchanged. Model punctuation quirks stop being a value-match variable. For
  compatibility, `eval_score._val_eq` compares phone fields by digit string, so eval v1
  (byte-frozen) and v3 (frozen, baselines attached) keep their SURFACE expectations — no eval
  file was regenerated or edited.
- **Country alias table.** `match_options` gains a small alias map keyed by OPTION VALUE (so it
  cannot misfire on a non-country field): britain / great britain / england -> `UK`;
  america / usa / the states / united states of america -> `US`. Closes the doc-19 §5 gap
  ("Britain" returned `[]` although United Kingdom is an option). "korea" needed no entry (it
  already partial-matches South Korea); "holland" was deliberately NOT added — the Netherlands
  is not an option, so any mapping would file the applicant under the wrong country.

## Eval v3 design decisions (2026-07-25)

**`third_party_name` expects empty — a v3 CEILING, not a correctness fact.** The case
"Desmond Quaintrell is the one who talked me into going back to school." expects no set,
including no `how_heard=referral`. That is right for the current single-turn extraction
contract: the sentence is about persuasion, not about how the applicant heard of
Northfield, and nothing is pending. But a more capable system SHOULD do one of two things
we deliberately do not ask of the student: (a) carry the mention forward and propose it
when `how_heard` becomes pending — "you mentioned Desmond told you about this school;
shall I put referral?" — or (b) clarify at the time and bind `referral` in advance. Both
require cross-turn memory of an unbound hint plus a confirmation mechanic, neither of
which exists in the harness. So v3 scores "empty" as correct; when the composer grows a
deferred-hint mechanic, this expectation must be revisited rather than treated as settled.
Same family as the parked refusal defer mechanic.

**Unlisted option values — CONVENTION B, CONFIRMED 2026-07-25: no inference.** The
`country_*` fields carry 15 options: 14 countries plus `OTHER`/"Other". When a user names
a country that is not in the list ("I'm in Kenya"), the extractor emits what was said;
`match_options` returns `[]`; for a large select (15 > `CHOICE_BUTTON_MAX` 8) the validator
returns `Outcome(CLARIFY, ...)`; nothing is written, `clarified` suppresses the agenda, the
field stays pending, and the assistant asks the user to pick. `OTHER` binds ONLY when the
user says "Other" themselves. The rejected alternative (A: let the extractor infer `OTHER`
from an unlisted place name) is faster on the genuinely-unlisted path but loses data on
near-misses: `match_options` returns `[]` for "Britain", "Great Britain", "America" and
"Holland" even though United Kingdom and United States ARE options, so A would file a
British applicant under "Other". B costs one extra turn; A silently corrupts.
Consequences: (1) eval v3 gains an `unlisted_country` scenario expecting empty — this makes
the stress sweep's real failure (Nairobi/Kenya narrative -> `country_citizenship='NG'`)
detectable for the first time; (2) round-3 training should include country-field `no_match`
cases — `gen_persona` only ever draws LISTED countries, so the student has likely never
seen this; (3) SEPARATE ISSUE, not an eval case: `match_options` has no alias table, so
"Britain" fails to reach UK. Near-miss names are deliberately excluded from the eval —
scoring them `empty` would freeze a validator gap as ground truth, the same defect as the
removed "the 3rd of March, 1994" case.

## Oracle-as-labeler (proposed, NOT adopted) — 2026-07-25

Today the teacher writes every training label (692 of 916 rows in h1b_merged are
teacher-labeled injections) and the convention table only VETOES — `sim_to_sft` passes
completions through unchanged and drops violators, never rewrites. Eval v3 showed the
same convention table can WRITE labels instead (that is where v3's 414 expectations come
from, at $0 and with no teacher call). Extending that to injected training rows would
remove teacher noise from the majority of the corpus and retire curation's 8-10% drop tax.

NOT adopted, because auditing six dropped rows one per behavior showed the deletions are
three different things, and only the first is a loss:
- **(A) teacher error, convention right** — `bare_date` "January 15, 1998" -> teacher bound
  `dob`; `deflect_free` "what format should the Test Date be in?" -> teacher `[]` instead of
  engagement. Oracle labeling recovers a good row.
- **(B) convention choice, teacher defensible** — `refusal` "skip my phone for now" -> teacher
  `{phone, ""}`; we standardise on `[]` only because there is no defer mechanic. Substitution,
  not correction.
- **(C) the case itself is broken; deleting was CORRECT** — `boolean_phrase` renders a greeting
  with NO field ask (`_boolean_phrase_ctx` = `rng.choice(_BOOLEAN_FIELDS)` + `_greet_history`)
  while `pending` is deliberately not shown to the model, so "I did take it last fall" has no
  visible referent and the teacher's null-fallback is right; `cross_select` "Let's make it
  TOEFL." was naturalized into "are we sure that's the one we want to pick?", which no longer
  commits. Writing the spec label here would be WORSE than dropping the row.

**Naturalizer drift (measured, judged NOT a problem as-is).** 14.4% of statement-shaped
injections (78/542) came back containing "?" and 7.6% (41) with hedging. Mostly harmless
style ("Um, actually I think my Program of Interest should be Public Health (MPH)" still
commits); occasionally answer-inverting (the `cross_select` case). Under the CURRENT
pipeline this is self-correcting — the teacher answers the text as written, curation drops
the row, no wrong label enters training — so the cost is ~9 rows/round of quota, not data
quality. It becomes a correctness problem ONLY under oracle labeling. Therefore: if we ever
adopt oracle-as-labeler, a lexical guard is a PRECONDITION (reject/re-roll a naturalization
that adds "?" where the template had none, or hedging where the template committed, plus a
prompt line "keep the commitment; never turn a statement into a question"). Until then,
leave the naturalizer alone. It also partly re-explains the curation stats: `bare_date`
12/25 is genuine teacher guessing, but the `cross_select` / `deflect_free` drops are
substantially naturalizer semantics, not teacher unreliability.

## Parked decisions
- **LLM U model at H1 scale — RESOLVED: haiku.** 3 probe sessions + mix probe eyeballed (terse/chatty/
  unsure all style-faithful; bulk 7-value turn caught 7/7). ~$0.16/session vs sonnet's ~$0.55.
- **Pre-slice-2 responder guidance tweaks — DONE 2026-08-03 (doc-20 ch1 item 1).** (a) option
  re-enumeration: `render_guidance` ask_target branch now says buttons are shown, don't re-list;
  Respond docstring carries the same rule keyed on actions (covers the responsive ask_choice path).
  Hand check: the old re-listing turn (welcome/program) now asks without enumerating. (b) grounding:
  "say you don't know / never invent policies" added to the Respond docstring; M3b Tier-1 grounding
  checks target this. (c) RESOLVED: temp 0 for the datagen responder LM (reproducibility; revisit
  only if the tuned responder sounds robotic on eval). Consequence executed: all 588 responder
  targets re-captured under the new prompt via `recapture.py` (h1a_recap 143, eval_farm_p3_recap 222,
  eval_farm_p4_recap 223; parity 0 mismatch, post-canon 588/588, $1.14, full-forward replay).
- **third_party template wart.** "{n}, my neighbor, said this school has a great campus" is how_heard-
  adjacent → teacher bound how_heard 3/25 (curated out). Reword before next datagen round.
- **Refusal has no skip/defer mechanic.** Both extractor conventions ([] or engagement) end in the
  harness re-asking the refused field. Curation standardizes on []; a composer defer-pending feature
  (move on, revisit at end) is the real fix — post-M4.
- **OpenRouter free routes churn.** tencent/hy3:free was pulled the same day it was adopted; the
  free-models-per-day cap (~1000, ≥$10 credits) is ACCOUNT-WIDE across all :free models. Paid fallbacks
  are cheap: hy3 $0.20/$0.80 per M, paid nemotron $0.60/$3.60 per M (~$3-4 per H1-scale run; re-anchor
  via calibrate preflight before trusting metrics from the paid route).
- **Responder cleanup — RESOLVED: canonicalize (in P2).** Reconstruct the missing
  `[[ ## response_text ## ]]` marker by re-wrapping `strip_markers(completion)` — data-only, non-invasive.
  Clean targets → the student learns clean markers, so no raw-text signature change needed. Raw-text kept
  only as a **fallback** if a responder eval later shows the student still drops markers post-SFT.
  `[[v2-m2-pilot-findings]]`
- **Demos-in-student-prompt — RESOLVED: strip** (P1 capture path). The survival concern (will the
  `bare_date` restraint distill without the demo crutch?) is addressed structurally: the injection quota
  includes the bare/restraint behaviors, so the student sees `{null}` examples in training. Verify at H4;
  if it still over-attributes, raise those quotas before falling back to demos-in-prompt.
- **Student anchor/calibrate** (CLAUDE.md hygiene) — the frozen eval + `teacher_v2` already anchor the
  harness; confirm the student wiring reproduces a known point before trusting H4 numbers.
