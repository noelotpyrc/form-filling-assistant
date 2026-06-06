# Doc 17 — Tuning Status Map

**Status anchor as of 2026-06-06.** This is a *descriptive snapshot* of where the
`tuning/` module stands — what exists, what's load-bearing, what was learned, and
what's dead. It is **not** a plan. A separate forward-looking doc will cover the
planned redesign (rethink the harness around the small LLM → build a new eval →
restart GEPA / SFT / RL).

Two standing decisions frame this doc:
- **Nothing is moved, archived, or deleted.** Legacy files are labeled here and
  left in place. Dead code in git costs nothing; removing it risks breaking the
  import spine (§2).
- **Issues are fixed just-in-time** — only when a task actually touches the file.
  Known issues are recorded in §5, not fixed.

---

## 1. The system in one picture

The goal: fine-tune **Qwen3.5-0.8B** to imitate a DSPy pipeline that drives
form-filling, emitting the model-agnostic `text + ---actions---` format (same
format the web app parses), so a small local model can eventually serve the web
app in place of Claude.

**The DSPy program** — `FormAssistant` in `tuning/dspy/optimize_prompt.py`:

| Module (`dspy.Predict`) | Role |
|---|---|
| `action_router` | Reads context+message → 5 boolean flags: `has_new_data`, `needs_choice`, `wants_review`, `wants_save`, `wants_submit` |
| `text_responder` | Always fires — the conversational reply |
| `data_extractor` | Fires if `has_new_data` → `set_fields` |
| `choice_builder` | Fires if `needs_choice` → `ask_choice` |
| `review_builder` | Fires if `wants_review` → `show_preview` |

`forward()` runs the router first, then conditionally fires the task modules and
assembles the `text + actions` output.

**Serving path** — `tuning/harness/serve.py` (FastAPI on `:8200`) runs
`FormAssistant` on the SFT'd model and streams the composed output. The **web app
already proxies to it**: `/api/generate-local` (browser `?backend=local` →
`LocalSFTProvider`) forwards to `HARNESS_URL` (default `http://localhost:8200`).
So the harness is the local-model backend for the web app — not a throwaway rig.

**Eval / judge stack** — `tuning/gepa/metric.py` (composite: programmatic
per-module scores + an LLM-judge-weighted text score), judges
(`judge_claude_headless.py` N=3, `judge_openrouter.py`), and the experiment-hygiene
**anchor/preflight** system (`tuning/harness/{pipeline,preflight,calibrate}.py` +
`fixtures/anchor_*`), mandated by `CLAUDE.md`.

### Load-bearing import spine (do not break)

```
tuning/dspy/optimize_prompt.py   (FormAssistant + infer_route)
        ▲
        │ imported by
tuning/harness/pipeline.py + preflight.py   (context build + anchor gate)
        ▲
        │ imported by ~15 scripts
tuning/gepa/*.py   (optimize, metric, judges, eval_*, inspect_*)
```
Plus: `tuning/sft/gen_format_data.py`'s format/route logic is **mirrored by hand**
in `tuning/rl/*` and `tuning/harness/composer.py` (a fragility — see §5).

---

## 2. Status by pillar

### SFT — supervised fine-tune (the foundation; *current*)
- **Pipeline:** `gen_format_data.py` (emits exact chat messages via DSPy's own
  `ChatAdapter`, so training targets byte-match inference) → `split_data.py` →
  `train_sft_format_modal.py` (Modal L4, Unsloth `FastVisionModel`, LoRA r=16) →
  `merge_lora_modal.py` (LoRA → fp16) → MLX convert → `compare_models.py` eval.
- **Checkpoints:** v1 `qwen35-08b-dspy-format-mlx` (categorical-intent), v2
  `qwen35-08b-dspy-format-v2-mlx` (the boolean-flag action-router — **current**).
- **Result:** ~100% format compliance; content/routing still weak.
- **Format contract:** `tuning/sft/CONTEXT_FORMAT.md`. Refs: doc-12 Exp 2 (v1) /
  Exp 9 (v2), doc-13 (v1 diagnosis), doc-16 (capability catalog).

### GEPA — prompt optimization (concluded: no real lift)
- **Pipeline:** `optimize.py` (driver) + `metric.py` + `rubrics.py` + `judge.py`
  + two judge backends; data = `seeds.jsonl` (28 gold) + `run_var_gen.py`
  variations.
- **Result:** on SFT-v2, max gain ~+0.005 — indistinguishable from noise. The
  bottleneck is the **student's prompt-following**, not the prompt text.
- **Key incident:** an apparent +0.087 lift was traced to a *silent judge
  fallback* × 0.55 metric weight — this is what produced the experiment-hygiene
  **anchor rule** now in `CLAUDE.md`. Refs: doc-12 Exp 1/3/12, and the gepa docs
  `SUMMARY_2026-05-17`, `INCIDENT_2026-05-15`, `HANDOFF_20260511`.

### RL — GRPO on the DataExtractor (concluded: not deployed)
- **Pipeline:** `mutate_extractor_data.py` (LLM-mutated ~41.7k examples) →
  `train_grpo_modal.py` (Modal L4, 3 reward fns, ~1,800 steps, resume-chained) →
  `merge_checkpoints_modal.py` (fp16 merge) → `eval_grpo.py` / `eval_sweep.sh`.
- **Result:** format compliance ↑ (≈77→97%) but F1 / value-accuracy /
  empty-correct **regressed**; no checkpoint deployed. Ref: doc-12 Exp 6–7,
  `tuning/rl/EVAL_PLAN.md`.

---

## 3. Code map — live core vs. present-but-unused

Live/keeper files are the import spine + the reusable pipelines. "Legacy" files
are **left in place**, just labeled.

| Area | Live core (keep using) | Present but unused (legacy, left in place) |
|---|---|---|
| `dspy/` | `optimize_prompt.py` (`FormAssistant`, `infer_route`) — its `main()` + `load_form_context()` are self-deprecated *inside* a live file | — |
| `harness/` | `pipeline.py`, `preflight.py`, `calibrate.py`, `__init__.py`, `fixtures/anchor_*`; serving stack `serve.py`, `composer.py`, `state_check.py`, `lifecycle.py`, `logger.py`, `dspy_logger.py` | `probe_runner.py`, `probes/P*.md` + `probe_notes.md` (the 60-scenario failure taxonomy — high knowledge value), `probes/runs/*` |
| `sft/` | `gen_format_data.py`, `split_data.py`, `train_sft_format_modal.py`, `merge_lora_modal.py`, `compare_models.py`, `CONTEXT_FORMAT.md`, `sanity_check.py` | `sft_format_qwen35_08b.ipynb` (Colab predecessor, superseded by the Modal script) |
| `gepa/` | `optimize.py`, `metric.py`, `rubrics.py`, `judge.py`, `judge_claude_headless.py`, `judge_openrouter.py`, `seeds.jsonl`, `build_seeds.py`, `run_var_gen.py`, `variation_prompt.md`, `_litellm_executor_fix.py`; helpers `precalc_baseline.py`, `eval_candidate.py`, `eval_program.py`, `gen_cand_preds.py`, `score_differing.py`; docs `SUMMARY_/INCIDENT_/HANDOFF_` | judge-stability cluster (`probe_judge_stability*.py` — 4 no longer import cleanly, `_deepseek`, `probe_flip_inspect`, `measure_judge_variance`, `verify_judge_drift`, `test_num_threads`); one-off renderers (`pick_from_*`, `inspect_*`, `compare_outputs`, `extract_baseline_from_log`); `gen_and_score`, `import_legacy`, `sanity_check_baseline`; `eval_cases_schema.md` (outdated schema) |
| `rl/` | `mutate_extractor_data.py`, `train_grpo_modal.py`, `merge_checkpoints_modal.py`, `eval_grpo.py`, `eval_grpo_modal.py`, `eval_sweep.sh`, `analyze_grpo.py`, `analyze_model.py`, `EVAL_PLAN.md`; SFT-diagnosis tools (misfiled here) `eval_modules.py`, `build_eval_review.py` | `gen_grpo_data.py` (superseded by the mutation generator), `grpo_extractor_qwen35_08b.ipynb`, `debug_grpo_cpu.py`, intent-GRPO pair (`gen_intent_data.py`, `mutate_intent_seeds.py` — prepped, never trained), `grpo_minimal_test.ipynb`, `test_notebook_cpu.py`, vendored Unsloth `*_original.ipynb` (LGPL templates, never adapted), generated artifacts (`eval_review_sft.html`, PNGs, `model_comparison_report.txt`) |
| `scripts/`, `eval/`, top | `extract.py`, `sample.py`, `clean_atomic.py` (doc-14 schedules its eventual deletion), `eval/run_eval.py` (standalone *legacy* evaluator — own prompt/scorer, parallel to the harness metric stack), `modal_guide.md` (CLAUDE.md-canonical) | `TRIALS.md` (stale — describes the superseded IntentDecider/single-intent design) |

---

## 4. Known issues / drift (recorded — fix when encountered)

- `tuning/rl/gen_intent_data.py` imports `infer_intent` from `optimize_prompt`,
  which no longer exists (only `infer_route`) → **broken import** (in the
  never-trained intent branch).
- 4 `tuning/gepa/probe_judge_stability*.py` import `_build_case_prompt` /
  `_parse_yesno` / `LEGACY_TAG`, which no longer exist in the judge module → dead.
- `tuning/harness/README.md` says `probes/runs/` is not version-controlled, but 14
  run files are tracked.
- `tuning/harness/calibrate.py` documents a `fixtures/anchor_inputs/` dir that
  doesn't exist (inputs are hardcoded in `ANCHOR_INPUTS`).
- `docs/doc-12-tuning-journal.md` has two sections numbered "Experiment 4".
- Pending **functional rebind** (from the migration): `Path.home()/"work/..."`
  paths in the Modal scripts and `./models/...` defaults in `sanity_check.py`,
  `compare_models.py`, `harness/pipeline.py` don't resolve. PII-scrub was
  path-only; rebinding is deferred to when these are next run.

---

## 5. Limitations — why a rethink is coming

This map exists because the current approach has run its course, not because it's
finished. The honest seams:

- **The harness was built around the DSPy pipeline + a Claude-quality teacher,**
  not around the small student. Context building, the 5-module decomposition, and
  the judge-weighted metric all assume a capable model; the small LLM is then
  asked to imitate that.
- **GEPA dead-ends on this student** — prompt optimization yields no real lift
  because the limit is the 0.8B model's prompt-following, not the prompt.
- **Data quality is patched, not clean** — `clean_atomic.py` is a one-round
  text-surgery hack over upstream sim/web-app bugs (doc-14); the "sims are seeds,
  not training data" shift is acknowledged but not yet acted on.
- **The capability ceiling is mapped but unaddressed** — doc-16's CAN/CANNOT
  catalog shows where the small model structurally fails; some failures were
  offloaded to deterministic Python (`state_check.py`) rather than learned.

The **redesign** — a new harness designed around the small LLM, a fresh eval built
on that harness+model, and a restart of GEPA / SFT / RL on that footing — will be
its own forward-looking doc, built next.

---

## Related docs
- **doc-11** small-model research (methods menu) · **doc-12** tuning journal (the
  master experiment log) · **doc-13** SFT v1 diagnosis (superseded) · **doc-14**
  training-data issues · **doc-15** real-app issues (R1–R13) · **doc-16** model
  capability catalog · **plan-small-model-training** (original, historical).
- `tuning/modal_guide.md` — canonical Modal coding style.
- `tuning/gepa/{SUMMARY_2026-05-17,INCIDENT_2026-05-15,HANDOFF_20260511}.md` — the
  GEPA research narrative.
