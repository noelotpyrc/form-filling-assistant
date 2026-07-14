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

## Plumbing (P) — do first; all small, free/cheap, individually verifiable
- [x] **P1 — DONE 2026-07-14.** `datagen.py` hybrid generator, gates read green on **pilot2**
      (nemotron teacher $0 + sonnet U, `datagen_runs/pilot2/`): parity PASS (captured system
      byte-equals offline render), coverage 74/80 with all gaps accounted (1 API 502, rest
      json-only chains), extractor targets **0.0% malformed / 0.0% retried** (91/91), 117 pairs,
      $1.28. Caveats → P2/H1: responder chat_malformed 46% (P2 canonicalization is load-bearing);
      OpenRouterLM should also retry error-in-body 5xx (farm session 3 lost to an upstream 502)
      before H1 scale.
- [ ] **P2 — format bridge + target canonicalization.** v2 `{module, messages, completion}` → trainer's
      `{messages:[…, assistant]}`, then train/val split. **Canonicalize responder targets** (fixes the ~1/3
      malformed) by reusing the harness's `strip_markers()`, applied to *all* responder targets (uniform, no
      malformed-detection branch; also mops up leaked/partial markers):
      `canon = f"[[ ## response_text ## ]]\n{strip_markers(completion)}\n\n[[ ## completed ## ]]"`.
      `strip_markers()` is thus the single shared "what's the prose" definition, used by `forward()` at runtime
      AND here. Verify on a tiny existing sim run. *new:* `sim_to_sft.py`
- [ ] **P3 — fix trainer data path.** `train_sft_format_modal.py` `LOCAL_TRAIN_DATA` points at stale
      `~/work/form-filling-assistant/…` (functional-rebind pending, `[[migration-cleanup-scrubbed-paths]]`) →
      rebind to the real repo path + make the input configurable. *files:* `sft/train_sft_format_modal.py`
- [ ] **P4 — student LM + eval wiring.** `dspy.BaseLM` → served MLX student (OpenAI endpoint; 3.3.0b1 has no
      litellm, so custom like `ClaudeLM`) + `eval_score.py --port/--model`. Smoke vs any served model. *new:* `student_lm.py`; *edit:* `eval_score.py`

## Heavy (H) — one at a time; each gated on the pipes above
- [ ] **H1 — generate extractor training data at scale.** `datagen.py`: farm N sessions + injection to
      per-behavior quotas (teacher $, budget-confirm). *gated:* P1 (incl. its parity/coverage/cleanliness
      gates on a pilot), P2
- [ ] **H2 — Modal SFT run.** `modal run tuning/sft/train_sft_format_modal.py`. *gated:* P2, P3
- [ ] **H3 — merge + convert.** `merge_lora_modal.py` (LoRA → fp16) → fp16 → MLX. *gated:* H2
- [ ] **H4 — eval student on frozen set.** `eval_score.py` at the student → student/teacher gap = **thesis number**. *gated:* P4, H3

## Readiness of v1 assets
| asset | state |
|---|---|
| `sft/train_sft_format_modal.py` (Qwen3.5-0.8B, L4, Unsloth LoRA) | ✅ proven; module-agnostic (v2's 2 modules fine); ⚠️ stale data path (P3) |
| `sft/merge_lora_modal.py` | ✅ exists |
| MLX serve pattern (`mlx server --model … --port`) | ✅ documented (CLAUDE.md) |
| format bridge (P2), student LM (P4) | ❌ to build |

## Parked decisions
- **LLM U model at H1 scale.** Pilot1 runs sonnet U (apples-to-apples with M2). Before H1: one
  haiku-U A/B session (~$0.5) checking JSON-action discipline + phrasing diversity (farm user
  messages are extractor training inputs); switch if clean (~$12+ saved at 50+ sessions).
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
