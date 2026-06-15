# Doc 18 — Harness Redesign: Small-LLM-First Tuning (v2)

**Forward-looking design, 2026-06-10.** Companion to doc-17 (the status anchor).
Doc-17 describes where tuning v1 ended; this doc designs v2 from scratch.

**Thesis to prove:** with a limited task scope and a well-designed harness, a
small LLM (Qwen3.5-0.8B) can run the form-filling assistant by learning from a
teacher model. This is a research demo, not a customer product — scope cuts are
free, and the deliverable is the *measurement* (student vs. teacher on the same
suite), not feature coverage.

**Standing constraints:** stay on Qwen3.5-0.8B; v1 files stay in place
(doc-17 §0); Modal style per `tuning/modal_guide.md`; experiment hygiene
(anchor/preflight) per `CLAUDE.md`.

---

## 1. Why v1 failed — the one-paragraph diagnosis

v1 never had a single source of truth for the student's data contract. The
teacher (Claude in the simulator) ran under the web app's full system prompt
emitting free-form `text + ---actions---`; training data was a *retrofit* of
those transcripts (parse actions → infer route flags → splice in a different,
narrower context built by a second implementation → hand-patch sim bugs in
`clean_atomic.py`). Four hand-mirrored context builders diverged (options
`[:5]` vs. all, 300 vs. 600/8KB truncation), so SFT-v2 was trained on a context
format the serving path no longer produces. GEPA then mutated prompts against a
student SFT'd to byte-match one fixed prompt (~8% of predictions even changed —
doc-12 Exp 13), and GRPO's reward leaned "emit something" (empty-correct → 0%).
The numbers weren't measuring the model; they were measuring the misalignment.

**v2 principle: one program, one data path.** The DSPy program is the single
source of truth. Teacher data generation, student training, eval, and serving
are byte-identical executions of the same code — only the LM behind it changes.

---

## 2. Scope cuts (the v0 task contract)

Phased; v0 is deliberately small. The action vocabulary stays the web app's
(`set_fields`, `show_fields`, `ask_choice`, `show_preview`,
`show_button(save_draft|submit)`), so the existing browser UI keeps working.

| Phase | In scope | Rationale |
|---|---|---|
| **v0** | One form (Northfield), **flat fields only** (text / select / date / etc.), full conversational flow: extract, choice, review, save, **submit** | Groups (`degrees.N`, `jobs.N`) are CANNOT #5 (index management); submit flow had *zero* v1 training examples — fixed by construction here |
| v1.5 | Group/repeated fields | Re-test CANNOT #5 once flat extraction is proven |
| v2.5 | File uploads | Hardest capability (R6/R7, 8KB contexts); deferred, not dropped |
| held out | Second form (Riverside patient) | Generalization check, never trained on |

---

## 3. Architecture v2 — extract-then-respond

v1 gave the model five parallel modules designed for a Claude-quality LM. v2
inverts the design: **the model does only what doc-16 says it CAN** (extract
from direct text, generate fluent text); **deterministic code does the
CANNOTs** (state cross-checking, option lists, index/button logic, restraint).

Every turn's actions come from **two channels merged by the composer**: a
*responsive* channel (what the user's message caused) and a *proactive* channel
(what the harness does next, driven by a deterministic agenda). The harness
keeps two pieces of state — `pending` (the field/choice currently being asked
about, rendered into the extractor's context) and the unfilled-required
`queue` — so elliptical answers ("March 12, 1999") bind by lookup, not
inference. Per turn:

```
0. PRE-STEP (code)      [system] events + lexical intents
   - "[system] User selected option: X" → set_fields via pending choice;
     no model call for the action
   - save / submit / review requests → pattern-matched intent flags
1. EXTRACTOR (model)    context (incl. "Pending: <field>") + message
                        → field_id/value pairs (may be empty)
2. VALIDATOR (code)     schema membership, type coercion, option matching,
   hallucinated-id drop. has_new_data := (validated result non-empty) —
   derived, never predicted. Corrections = valid set on a filled field.
3. COMPOSER responsive (code)
   - ask_choice: missing/ambiguous select value — options come FROM THE
     SCHEMA (model never invents options → R3 dead)
   - show_preview: rendered deterministically from form state
   - show_button: from lexical intent, gated on code-computed completeness
4. STATE UPDATE (code)  apply set_fields, clear pending, recompute queue
5. COMPOSER proactive (code)  agenda picks next target from post-update
   state: select/boolean → ask_choice + pending; free field → text-ask
   directive + pending. Queue empty → TERMINAL: show_preview +
   show_button(submit) — the submit flow is the agenda running out of work,
   not a learned behavior. Guards: ≤1 ask_choice/turn (responsive wins),
   never re-emit an open ask_choice, pause agenda on save.
6. RESPONDER (model)    context + message + merged actions + directives
                        → response_text (pure verbalization — never decides)
   - the model SEES what actions fired this turn → R5 (text-action disconnect)
     and R11 (state hallucination) are killed structurally, not trained away
```

**The full routing spec — validator branch logic, agenda guards, the
directive glossary, the binding cascade, and traces for 16 enumerated
scenarios (elliptical answers, deflections, chitchat/trap turns, corrections,
bulk paste, bare-value dumps, premature submit, terminal, server-side
validation error) — is
[doc-18.1](doc-18.1-turn-logic.html)** (an interactive HTML with cross-linked
steps/scenarios), the contract M1 implements. The two residual model risks
both live in the extractor: restraint (`[]` on chitchat) and deflection
non-binding; both degrade benignly.

What disappears: `action_router` (5 booleans were a class-imbalance trap with
unreliable firing — doc-12 Exp 9, doc-16 CANNOT #4), `choice_builder`,
`review_builder`. The learned surface is exactly two calls.

**Why not keep a learned router?** Exp 9 moved categorical→booleans because
turns combine intents; v2 keeps that composability but derives the flags
(extraction result, schema state, lexical patterns) instead of predicting them.
If eval shows the patterns miss real phrasings, the fallback is *one* small
intent classifier trained on deliberately balanced data — added only on
evidence, not up front.

**Latency note:** two sequential 0.8B calls ≈ one v1 multi-module turn or
cheaper; chaining is affordable at this size.

---

## 4. Teacher-in-the-harness

The fix for retrofitting: the teacher runs the *same program*.

- **`ClaudeLM`** — a custom `dspy.LM` subclass that shells out to `claude -p`
  headless (same pattern as `tuning/gepa/judge_claude_headless.py`). The
  harness is stateless per turn, so no session persistence is needed. Teacher
  model: **sonnet** (haiku under-fills forms — known from web-app testing).
- **Sim v2:** LLM U is unchanged (persona via `claude -p`, reusing the existing
  profiles, action catalog, and `view-renderer` screen rendering). LLM A is
  **the v2 harness with `ClaudeLM`** — the alignment flagged back during sim
  cleanup ("LLM A should use the same flow as the tuning DSPy one").
- **Logging = training data.** Every model call logs its exact `(messages,
  completion)` pair at the point of inference. Training JSONL falls out of the
  sim directly — `extract.py` / `clean_atomic.py` have no v2 successors. There
  is nothing to retrofit and nothing to patch.
- **Serving:** v2 `serve.py` keeps the same FastAPI request shape on `:8200`,
  so the web app's `/api/generate-local` (`?backend=local`) works for both the
  teacher-backed harness (manual smoke) and the student.

---

## 5. Data design — sims are seeds, scenarios are specs

doc-14's stated-but-unexecuted shift, now executed:

- **Scenario specs with quotas** drive generation: pending-question→answer
  pairs are the *bulk* (they dominate real sessions — the agent asks, the user
  answers elliptically), plus deliberate bands for volunteered data,
  multi-field, choice flows, deflections, chitchat **and trap-chitchat**
  (restraint training for CANNOT #4 / R13 — doc-18.1 risk A/B), corrections,
  bulk paste, review, save, **submit**. The label distribution is *designed*,
  not whatever the sim happens to emit — the Exp 9 imbalance (`needs_choice`
  42% pos-recall, `wants_submit` zero positives) is fixed at the source.
- **Programmatic persona generation** with high name/value diversity, so no
  string is frequent enough to memorize (kills R12 persona leakage by
  construction). v1 sims/atomic data are inspiration for scenario authoring
  only — never training input.
- **Pilot before scale:** ~50 sessions, manual review of traces, then scale.
  Per-scenario counts reported at generation time (no silent gaps).

---

## 6. Eval design — the harness with frozen inputs

Eval is not a parallel rig; it is the same harness replaying a frozen scenario
suite. v1's 300-case set missed 9 of 13 real-app issues — v2 keeps both tiers:

- **Tier 1 — programmatic, every checkpoint:** extractor F1 / value-match /
  **empty-correct**, an **over-attribution rate** (fields filled — especially
  via a wrong confident attribution — when the turn didn't warrant it; this is
  the number that tells us the `{null}`-when-unsure behavior is being learned,
  per doc-18.1 risk B), a **wrong-field-assignment rate** on the bare-value /
  unlabeled-dump probe band (doc-18.1 S16), responder grounding checks
  (persona-leak regex, mentions-fired-actions), per-scenario-type breakdown
  with pos/neg confusion (no headline-accuracy hiding).
- **Tier 2 — behavioral:** multi-turn probe sweep (reuse the P1–P12 probe
  taxonomy from `tuning/harness/probes/`), plus a small judged rubric for text
  quality only. Judges hard-fail loudly — no silent fallback (the
  INCIDENT_2026-05-15 rule).
- **Anchor per checkpoint** via the existing `calibrate.py` pattern; preflight
  gates every costly run (CLAUDE.md hygiene carries over unchanged).
- **Gold** = teacher traces (spot-verified) + hand-authored CANNOT probes.
- **The teacher is the baseline.** First measurement is the teacher on the
  suite; the demo metric is the student/teacher ratio per metric.

---

## 7. Training plan

1. **SFT v3 — distillation.** Train the student on the teacher's exact
   per-call `(messages, completion)` pairs for the two learned calls. The
   ChatAdapter byte-match recipe from Exp 2/9 (Modal L4, Unsloth LoRA → fp16 →
   MLX) carries over — it's the one v1 piece that worked unambiguously.
2. **Measure** the student vs. teacher on the frozen suite; report the gap per
   metric. This is the thesis number.
3. **GEPA moves upstream.** Prompt optimization runs on the *teacher program*
   before data generation (the teacher follows prompts; the student can't —
   Exp 13). GEPA's v2 job is improving the program the student distills from,
   not the student's prompts. GEPA-on-student is retired.
4. **RL — targeted, optional.** Only if SFT plateaus on a specific measurable
   weakness; any reward must score empty-correct symmetrically with extraction
   (the Exp 7 lesson). Not scheduled until SFT v3 numbers exist.

**Success criteria** (concrete numbers set after the teacher baseline run):
student reaches a stated fraction of teacher score per Tier-1 metric, completes
scripted multi-turn sessions end-to-end, and serves under an acceptable
per-turn latency on the local Mac. Defining these is milestone M3, not a
retrofit after results.

---

## 8. Milestones

| M | Deliverable | Done when |
|---|---|---|
| M0 | This doc; scope cuts agreed | doc-18 merged |
| M1 | v2 harness in **`tuning/v2/`** (new dir; v1 untouched per doc-17): program (extractor + responder signatures), deterministic shell (pre-step / validator / composer / agenda per the doc-18.1 contract), `ClaudeLM` | The 16 doc-18.1 scenario traces pass as smoke turns with the teacher |
| M1.5 | `tuning/v2/serve.py` (FastAPI `:8200`, v1's request shape) behind the web app's `/api/generate-local` (`?backend=local`) | Manual browser drive with the teacher: fields fill live, choices/buttons/preview render, save + submit flow work end-to-end. (Same serve path M2/M4 reuse — only the LM swaps.) |
| M2 | Sim v2: LLM U ↔ teacher-harness; pilot ~50 sessions | Manual trace review passes; per-scenario quota report |
| M3 | Frozen eval suite + teacher baseline + anchor; success criteria numbers set | Teacher scored; anchor fixture written |
| M4 | SFT v3 distillation + student eval | Student/teacher gap report |
| M5 | Iterate: GEPA-on-teacher, data scaling, targeted RL, then phase v1.5 (groups) | Driven by M4 findings |

---

## Related docs
- **[doc-18.1](doc-18.1-turn-logic.html)** turn logic — the full extractor →
  composer → action routing spec as interactive HTML (pipeline chart,
  validator branches, agenda guards, directive glossary, binding cascade, 16
  cross-linked scenario traces); the M1 contract.
- **doc-17** status anchor (v1 end state) · **doc-16** CAN/CANNOT (drives §3) ·
  **doc-14** data issues (drives §5) · **doc-15** R1–R13 (R3/R5/R11/R12/R13
  addressed structurally above) · **doc-12** journal (Exp 2/7/9/13 lessons).
- `tuning/modal_guide.md` — Modal style for M4.
