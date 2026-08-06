# Doc 22 — Responder scenario coverage: the matrix, the rule, the tooling

**Written 2026-08-04.** After two reactive fix rounds (terminal/submit_blocked,
then chitchat-steer-back), a design review found the root cause: the responder's
training pool and its eval were both sampled from the same organic farm
distribution, so every scenario that distribution under-produces was invisible
twice over — absent from training AND from the eval meant to catch it. This doc
records the miss, the coverage matrix, and the standing rule that closes the
class.

## 1. The miss, mechanically

The extractor never had this problem: its corpus got 682 injected rows across
20+ manufactured behaviors, and eval v3 is scenario-enumerated (23 classes ×
18 cases). The responder pipeline failed to inherit that discipline through two
specific artifacts:

1. `datagen.run_injection` was hardcoded `with_response=False` — every injected
   hard case captured **extractor targets only**. The responder's reply to those
   same situations was generated and thrown away.
2. doc-20 §3 defined the responder pool as "farm turns, by construction," and
   the frozen eval was built from the same farm turns.

A cooperative simulated user structurally never produces certain events, so the
affected directive kinds had **zero** coverage on both sides — not low
probability; zero by construction:

- `fix` fires only on a `[system] Validation error:` UI event. The farm
  simulates a user, not a browser; the event never occurred in any session.
- `clarify` fires on a validator CLARIFY outcome (ambiguous multi-option
  match). Cooperative users are specific; ambiguity must be manufactured.
- `ack` (as a directive) fires only on `[system] User clicked:` /
  system-confirmation events (Save Draft flow). Farm users never click it.
  (Option-select clicks take a different prestep branch that carries the
  acknowledgment in the `set_fields` action — that path IS covered.)
- `submit_blocked` / `terminal` were merely *scarce* (premature submits and
  completed-form lingering are rare), which is why they surfaced first, as
  round-2 failures.
- `reask_pending` existed (24 rows) but only in the quiet-turn context — the
  chitchat context was absent, which is why the round-2 model chitchats back
  instead of steering (probe: 55/60).

## 2. The coverage matrix (2026-08-04, pre-round-3)

Directive kinds are a closed vocabulary (`render_guidance`, composer + prestep).
Counts per side; training = bridged `responder_s2b_merged` (427 rows), eval =
frozen 223 + probes:

| directive kind | training | eval | state |
|---|---|---|---|
| ask_target | 299 | 178 | covered |
| terminal | 51 | 14 | patched in round 2 |
| submit_blocked | 48 | 1 | patched in round 2 |
| reask_pending (quiet) | 24 | 22 | covered |
| reask_pending (chitchat) | 0 | 60 (probe) | round 3 |
| respond-naturally / off-form | 5 | 8 | thin — round 3 |
| clarify | 0 | 0 | round 3 |
| fix | 0 | 0 | round 3 |
| ack / save-draft flow | 0 | 0 | round 3 |

## 3. The standing rule

**Every reachable cell of (directive kind × user-context) gets a minimum quota
in the training pool AND a dedicated eval probe before a responder round
ships.** Manufactured by injection where the farm can't produce it. Zero
coverage of a reachable cell is a build failure, not a footnote.

- Training injections draw from seeds ≤146; eval probes from 147–161. Never
  cross. RL reserves (162–191) stay untouched.
- Probes are separate files next to the frozen set (`eval_responder_*_probe.jsonl`),
  never merged into it. The frozen 223 stays byte-frozen
  (sha16 `2c7678f763a9256b`).
- A probe case must test what it claims: probes filter to cases where the
  intended directive actually fired (matters for clarify, whose realization
  depends on live extraction).
- Coverage is verified by `tuning/v2/coverage_report.py` (the companion tool):
  it prints this matrix from the actual artifacts and flags zero-coverage
  reachable kinds. Run it before any responder training round.

## 4. Round-3 ledger

Baselines first (current model on every new probe), then one consolidated
training injection covering chitchat + clarify + fix + save-draft + off-form,
one bridge, one retrain, then the frozen 223 + all probes and a failure read.
Decision per the standing decision rule: numbers say where to look, the
hand-read of failures decides (doc-20 §2 amendment, 2026-08-03).

## 5. LLM-U model rule (2026-08-05)

Two different jobs, two different models:

- **Farming (datagen + eval contexts): haiku-U.** Cheap (~$0.16/session),
  style-faithful, and it IS the house distribution — every farm run to date
  (h1a, eval_farm_p1-p6) used it (verified from `cost.farm_u` per session).
- **Scripted probes (probe.py scenarios): sonnet-U.** Scenario directives are
  stage directions ("now ask to save"); haiku-U ignored the save direction in
  both m3c seeds, so those scenarios silently never executed. A probe needs an
  actor that follows the script.
- Probe reports record `wiring.sim_user_model` (added after the m3b/m3c
  comparison had to reconstruct the U model from per-session costs).
- Probe-assertion refinement queued: `conditional_consistency` flags volunteered
  values stored in condition-inactive fields; ruled acceptable-by-design
  (2026-08-05) — storage is fine, conditions govern use/display.

## 6. Merged-model data mix: the upsampling lesson (2026-08-05/06)

The one-vs-two-LoRAs comparison (doc-20 §6 #5, decided empirically) produced a
finding worth keeping: **in a merged extractor+responder model, the data mix is
a shared knob with cross-task consequences, and duplicate-upsampling a narrow
pattern is a blunt setting.**

What happened. `mergedall` (one model, union corpus, no reweighting) beat the
frozen extractor on eval v3 — whole-case 370/414 vs 363, value 97.4 vs 96.5,
wrong-field 0% — while holding responder parity (427/447 vs split 429). To lift
the dormant-caveat behavior (6/13), the 17 dormant responder rows in train were
duplicated ×4 (`mergedup2`). Dormant rose to 10/13 — but extraction paid:
whole-case 356, value 93.9, and 22 regressed cases in three families:

1. **Tail drops on multi-value turns** (bulk/compound): leading items kept, the
   LAST item dropped (email+phone kept, mailing address lost; address kept,
   trailing nickname lost). `multi_select_subset`, the extractor's known
   completeness gap, fell 6/18 → 3/18.
2. **Value-boundary leakage** (wrapped_value): the chatty wrapper copied INTO
   the stored value ("Half-listening, sorry, the kettle's going — post goes to
   88 Halyard Court…" stored as the address).
3. Scattered: one leading-zero phone slip, one missed wrapped date, one
   wrong-field.

Theory (inference from the failure pattern, not proven). The failures are
premature list termination, not misunderstanding — order preserved, survivors
correct, only tails lost. Every duplicated row drills one-value-per-turn with a
short prose completion that EMBEDS the value ("your TOEFL score of 105 — I've
recorded it"). The two tasks share all weights: 68 copies × 3 epochs shifted the
shared "how much output does a turn deserve" prior shorter (→ tail drops) and
blurred the value/wrapper boundary (→ leakage). Test, if ever needed: retrain at
×2 and check whether tail-drop rate moves monotonically with duplication factor.

Rules of thumb this yields:
- Prefer **varied new exemplars** over duplicates when strengthening a rare
  behavior in a merged model; variety spreads the signal without concentrating
  its side patterns.
- Any reweighting of a merged corpus obligates **both** frozen evals, not just
  the task being tuned.
- Measurement hygiene, learned the hard way the same day: **one served model
  per eval run.** With ~6 concurrent 1.7GB MLX servers on a 16GB machine,
  inference silently degenerated (`!!!!…` to the token cap) with no server
  error; the same bytes served alone were clean. Kill other servers before any
  number you intend to keep.

Related: [doc-20](doc-20-responder-tune-spec.md) (chapter-1 spec; §2 Tier-1,
§3 partition) · [doc-21](doc-21-status-and-roadmap.md) (status) ·
`tuning/v2/M4_PLAN.md` (execution log) · doc-19 §3 (the extractor's
scenario-enumerated eval, the precedent this rule generalizes).
