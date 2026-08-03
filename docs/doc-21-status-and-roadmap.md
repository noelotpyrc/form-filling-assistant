# Doc 21 — Where the project stands, and what happens next

**Written 2026-08-03.** The doc to read first. What exists today, where it lives,
what the numbers are, and the three chapters of work still ahead. Design
rationale lives elsewhere: [doc-18](doc-18-harness-redesign.md) for the harness,
[doc-19](doc-19-eval-framework.md) for the eval, [doc-20](doc-20-responder-tune-spec.md)
for the responder plan.

---

## 1. The project in one paragraph

A small language model (Qwen3.5-0.8B, LoRA-tuned) fills in a web form by talking
to a user. It does not decide where answers go: it reads the latest message and
emits `(field, value)` pairs, and a deterministic harness — pre-step, validator,
composer — places them, coerces types, matches options, and rejects what it
cannot place. A large teacher model (nemotron-3-ultra-550b) generates the training
data; the student is distilled from it. The deliverable is two things: an honest
measurement of how close a 0.8B model on a laptop gets to a 550B model, and a
demo where you can watch it happen.

---

## 2. Where things stand (2026-08-03)

| area | state |
|---|---|
| **Harness** | Finalized 2026-08-02. Three closing changes: a provenance gate in the validator (a non-choice value the current message does not support is DROPPED — nothing set, the field re-asks), a country alias table in `match_options` (Britain→UK, America→US), and phone canonicalization in `coerce` (digits-only storage). REPORT_evalv3 §12; M4_PLAN "Issue #1 fix — DONE". |
| **Extractor student** | `r3-oracle`, **FROZEN**. 363/414 whole-case on eval v3, final harness. F1 89.9, value-match 96.5, wrong-field 1.9. |
| **Teacher** | 400/414 on the same set. Wrong-field 1.9 — the student ties it. |
| **Base (untuned) Qwen3.5-0.8B** | 114/359. **55 of 414 cases were unparseable and skipped, not scored as failures** — always disclose this when quoting a base number; it flatters base on every rate. |
| **v1 tripwire** | 109-case byte-frozen set, r3-oracle: F1 99.5 / value-match 100.0 (`eval/baseline-sft_r3_oracle_evalv1_final.json`). Regression detector only. |
| **SFT era** | CLOSED for the extractor. No further extractor SFT is planned. |
| **Responder** | Untrained. The deployable stack today is a hybrid: student extractor local, teacher responder remote. → doc-20. Chapter-1 progress (2026-08-03, on leon-work): guidance tweaks landed (`program.py`, doc-20 item 1) and all 588 responder targets re-captured under the new prompt (`recapture.py`, item 2) — parity 0 mismatch, post-canon well-formed 588/588, $1.14. |
| **Multi-turn behaviour** | M3b probe, 26 sessions, all completed to the submit gate, every behavioural assertion passed. Latency p50 3.8s / p95 25.9s over 355 turns — but that bundles the remote teacher responder and its retries, so it is not a student latency number (`probe_runs/m3b_hybrid/report.json`). |

**Known extractor gaps, deliberately left for RL.** From `REPORT_evalv3.md` §5
(per-scenario whole-case, x/18; that table is from the §2 pre-final-harness run —
§12 did not republish per-scenario):

- **multi-value completeness** — `multi_select_subset` 6/18 (33%) vs teacher
  15/18. The student picks one option where the user named two.
- **third-party facts** — `third_party_fact` 11/18 vs teacher 18/18. "My brother
  lives in Germany" becomes `country_residence: DE`.
- **residence statements** — `residence_statement` 10/18 vs teacher 14/18, and
  the worst regression from round 2 (16/18, −33.3 pp). "I'm over in Seoul these
  days, so South Korea" leaks into `country_citizenship`.

None of these is a provenance problem — the values really are in the message — so
no deterministic gate reaches them. They are exactly the "specific measurable
weakness" that doc-18 §7 reserved RL for.

---

## 3. Assets and where they live

**Models** — external SSD, `/Volumes/Extreme SSD/form-filling-models/`:

| dir | what |
|---|---|
| `qwen35-08b-v2-r3-oracle-mlx` | the current extractor student (round 3, oracle-labeled) |
| `qwen35-08b-v2-slice1b-mlx` | round 2, kept for continuity |
| `qwen35-08b-v2-slice1-mlx` | round 1 |
| `hf_cache/` | the untuned base |
| `lora-dl*`, `fp16-dl*` | intermediate LoRA and fp16 artifacts per round |

Serve with `mlx_vlm.server --model <mlx dir> --port 810X`. **Quirk (H3):** this
server version loads whatever repo the request names, so the request body's
`model` field must be the real path and `V2_STUDENT_MODEL` must match it. Two
models under comparison get two ports and two servers.

**Modal** — `tuning/sft/train_sft_format_modal.py` and `merge_lora_modal.py`,
parameterized by `SFT_APP` / `SFT_VOLUME` / `SFT_TRAIN_DATA` / `SFT_VAL_DATA` /
`SFT_LORA_DIR`. Each slice gets a fresh volume so it cannot clobber an earlier
checkpoint; slice 1 used `sft-v2-slice1` (`train_sft_format_modal.py:41`).
*(The exact volume name used for the r3-oracle round is not recorded in the repo —
check `modal volume list` before assuming.)* Run through
`tuning/v2/.venv/bin/modal` from the repo root.

**Eval sets** — `tuning/v2/eval/`:

| file | what |
|---|---|
| `eval_set.jsonl` | v1, 109 cases, **byte-frozen** — never changes |
| `eval_set_v2.jsonl` | v2, 143 cases, kept for continuity |
| `eval_set_v3.jsonl` | v3, 414 cases on sampled real contexts — the current yardstick |
| `baseline-*_final.json` | runs on the **final** harness; unsuffixed ones predate 2026-08-02. They record model path and metrics but **not** port, env, or command — infer the backend from the label |
| `REPORT_evalv3.md` / `.html` | the four-model comparison, source of record |

**Session-seed allocation** — farm sessions are a finite resource and each range
has exactly one job:

| seeds | run dir | job |
|---|---|---|
| 1-10 | `datagen_runs/h1a/` | training (extractor rounds 1-3; responder per doc-20) |
| 102-131 | `eval_farm_p1`, `p2` | eval v3 contexts — **untouched** |
| 132-146 | `eval_farm_p3` | responder training — **per doc-20** |
| 147-161 | `eval_farm_p4` | frozen responder eval — **per doc-20** |
| 162-191 | `eval_farm_p5`, `p6` | RL prompts — **untouched, unread** |

Row counts per range are in [doc-20 §3](doc-20-responder-tune-spec.md); they were
verified from each run's `report.json`.

**Teacher** — `nvidia/nemotron-3-ultra-550b-a55b` via OpenRouter
(`tuning/v2/openrouter_lm.py`), temperature 0, native messages array. A full
414-case extractor pass costs **$0.7073**
(`eval/baseline-teacher_nemotron_v3_final.json`). The `:free` variant exists but
the free-models-per-day cap is **account-wide across all `:free` models** and free
routes get pulled without notice — use the paid slug for anything whose number
will be quoted.

**Costs to date.** Summing `cost.total` across all `datagen_runs/*/report.json`
($37.87) and `cost_usd` across all `eval/baseline-*.json` ($22.58) gives
**$60.45** of recorded API spend. That excludes Modal GPU time (~$0.15 per
training run) and the M3b probe. The single largest line is the failed pilot1
datagen run at $15.10; the two sonnet-era teacher baselines account for $18.93 of
the eval total and are historical.

---

## 4. Roadmap — three chapters, in order

### Chapter 1 — Tune the responder

Full spec: **[doc-20](doc-20-responder-tune-spec.md)**.

One SFT slice on the text responder, plus a two-tier eval where Tier-1 is
deterministic code scored against the composer's own directives and Tier-2 is a
judged rubric that never gates. Guidance tweaks land first and force a re-capture
of the responder targets.

**Exit condition:** the hybrid stack (student extractor + remote teacher
responder) is replaced by an all-student stack, and Tier-1 gates pass on the
frozen 223-turn responder eval.

**Cost:** ~$6.

### Chapter 2 — RL on the extractor

This is a sketch, not a spec — an implementer starts here and writes the spec.
doc-18 §7 pre-committed the shape: RL only against a specific measurable
weakness, and any reward must score empty-correct symmetrically with extraction.

- **Algorithm.** GRPO — group sampling, no value network. LoRA on top of
  `r3-oracle` as the initial policy, with a KL penalty to the SFT policy.
- **Reward.** A deterministic oracle through the **real harness**: parse the
  rollout, run it through `validate` and `compose`, compare the post-harness form
  delta against the injected expectation. Per-field F1, penalties for extra
  fields and for malformed output. Pure Python, **$0 per rollout**, no judge.
- **Prompts.** Injected turns over the 450 reserved snapshots from seeds 162-191
  (`eval_farm_p5`, `p6`), using the existing behavior registry in `datagen.py`.
  The 30 sessions behind eval v3 (seeds 102-131) never enter RL.
- **Gates.** Eval v3 frozen set; the v1 tripwire; the invention stress sweep
  (`stress_invent.py`); the multi-turn probe (`probe.py`).
- **Targets.** The three gaps in §2: multi-value completeness, third-party facts,
  residence statements.
- **Declared risk — reward hacking toward always-empty.** Empty-correct is the
  cheapest reward in this task: emit nothing, collect the points on every
  `empty` case. The counters are a per-field recall term in the reward and
  per-scenario monitoring during training, not a single scalar. This is the Exp-7
  lesson from v1's GRPO attempt, where format compliance rose while F1,
  value-accuracy and empty-correct all regressed and no checkpoint shipped
  (doc-17 §2).
- **Infra.** TRL on Modal L4/A10. **~$10-30.**

**Why RL is credible here and was not in v1.** The three things RL projects
usually lack all already exist: a reward function that is deterministic, free and
runs through the production harness; a prompt distribution of real conversation
states, reserved and untouched; and clean gates with recorded baselines. What is
left is training, not invention.

### Chapter 3 — Product and portfolio

- **Wire the student into the web app.** `tuning/v2/serve.py` (FastAPI on `:8200`,
  the v1 request/SSE contract) already sits behind the web app's
  `/api/generate-local` with `?backend=local`. It currently configures
  `ClaudeLM()` at startup; point it at `StudentLM` and, once chapter 1 lands, at
  the student responder too.
- **Responder story** per chapter 1's outcome — all-student or hybrid, stated
  honestly either way.
- **A top-level case-study README**, stitching the arc: doc-17 (why the v1
  approach ran out) → doc-18 (the redesign) → doc-19 (how the eval got
  trustworthy), the v1→v2→v3 eval progression and what each version fixed,
  oracle-labeled vs teacher-labeled training data with the measured delta
  (round 2 → round 3: whole-case 336/414 → 358/414 on the §2 harness), and the RL
  chapter.
- **The format-distillation latency observation** — the untuned base rambles to
  `max_tokens` while the student answers tersely at identical parameter count,
  reported at roughly 25× (~38s vs ~1.5s per call). **No artifact in this repo
  records those two numbers**; the eval JSONs carry cost but not wall time.
  Re-measure on both ports before publishing it.
- **A demo GIF.**

---

## 5. Standing conventions for any implementing agent

- **Experiment hygiene / anchors.** Before you trust a new number, reproduce an
  old one. Run the harness in no-op mode on an input whose answer is already
  recorded; if it does not reproduce, stop — the harness has drifted and any
  improvement you measure is an artifact of the drift. Anchors are
  model-specific: capture one per checkpoint with `tuning/harness/calibrate.py`,
  and give each model under comparison its own port and its own anchor.
  (CLAUDE.md; doc-19 §8.)
- **Describe first for multi-file changes.** Show exact diffs, then confirm,
  then edit.
- **Paid runs need explicit user confirmation** — model, sizes, judge, budget,
  paths. Take the instructions literally: no substitutions, no defaults quietly
  filled in.
- **Commits are grouped and only on request; pushes only on request.** Work on
  `main`.
- **Sub-agent rules** as in [doc-20 §5](doc-20-responder-tune-spec.md): sub-agents
  build offline with selftests, never call an LLM, never spend, never commit.
  Live runs are the orchestrator's.
- **Detach long runs** (`nohup` + a monitor loop). Background tasks have been
  killed externally twice.
- **OpenRouter caveats.** The free-models-per-day cap is account-wide across all
  `:free` models, and free routes get pulled the same day they are adopted. Paid
  fallbacks are cheap: nemotron $0.60/$3.60 per M tokens, hy3 $0.20/$0.80. Re-run
  the anchor preflight after switching routes.
- **`eval_score` skips unparseable cases.** `run_baseline` catches the exception,
  prints it, and continues, so those cases are not scored as failures. This
  matters almost exclusively for base-model runs — always disclose the scored
  denominator.
- **Known gap: no incremental writes.** `eval_score` writes its output at the end
  of the run. A long eval that dies at 90% loses everything. Add incremental
  writes before the next slow run.

---

## 6. Running this on another machine

The repo (GitHub) plus the external SSD (`/Volumes/Extreme SSD/form-filling-models/`)
plus Modal/OpenRouter credentials is a complete kit, under these conditions:

1. **Apple Silicon Mac only.** The serving stack is MLX (`mlx_vlm.server`); it does
   not run on Linux or Intel. If you must serve elsewhere (vLLM/llama.cpp on the
   fp16 weights in `fp16-dl*/`), you are on a different runtime: re-anchor before
   trusting any number (CLAUDE.md experiment hygiene).
2. **Restore the gitignored run data into the clone.** The SSD carries a copy at
   `repo-rundata/` (datagen_runs 202M, probe_runs 28M, sft_data 57M, stress_runs
   31M). Copy those four dirs into `tuning/v2/` — several test gates need them:
   `eval_gen --selftest` hard-requires `datagen_runs/eval_farm_p1..p2`;
   `stress_invent`'s anchor gate reads `probe_runs/m3b_hybrid`; the smoke suite's
   25-value replay gate reads `stress_runs/slice1b`. Gates that find files missing
   print a loud SKIP — a green run with SKIP lines means the restore is incomplete.
   **On `leon-work` this is already done** (synced 2026-08-03): run data is in
   place under `~/work/form-filling-assistant/tuning/v2/`, and the models live at
   `~/work/form-filling-models/` (r3-oracle MLX, slice1b MLX, base under
   `hf_cache/`, fp16 of r3-oracle). The work machine does not take the SSD.
3. **Rebuild the venv** with `python3.11 -m venv .venv` then
   `pip install --only-binary=litellm -r requirements.txt` (recent litellm is
   source-only and needs Rust ≥1.85 to build; the flag takes the newest prebuilt
   wheel instead). This restores the `modal` CLI at `tuning/v2/.venv/bin/modal`
   and `mlx-vlm` for serving — both are pinned in requirements.txt as of
   2026-08-03. Secrets: `OPENROUTER_API_KEY` in the shell env; `modal setup` for
   Modal auth.
4. **Model paths differ per machine.** Hub commands and the recorded baselines use
   `/Volumes/Extreme SSD/form-filling-models/...`; on `leon-work` the same models
   are at `~/work/form-filling-models/...`. Pass the local path as `--model` /
   `V2_STUDENT_MODEL` (the mlx server loads whatever path the request names) and
   set `HF_HOME=~/work/form-filling-models/hf_cache` when serving the base model.
   The path inside a baseline JSON's `model` field is provenance, not a promise.
5. **First-session check, before any new work:** run `smoke_deterministic` (46/46,
   no SKIP lines) and one known eval — r3-oracle on v1, expect F1 99.5 / value 100.
   Reproduce a known number before trusting a new one.

### Git between the two machines (set up 2026-08-03)

The worker machine is `leon-work` (`ssh work`), repo at
`~/work/form-filling-assistant`, seeded from a bundle. It has **no GitHub access
and no credentials to the hub machine** — all traffic is hub-initiated. The hub
holds `remote add work ssh://work/Users/lliao/work/form-filling-assistant`; the
worker's repo has `receive.denyCurrentBranch=updateInstead`, so a hub push
updates the worker's checkout but refuses if its tree is dirty.

Flow (hub only): `git push work main` to send work; `git fetch work main` +
`git log main..FETCH_HEAD` to review the worker's commits; ff-merge and
`git push origin main` to publish. **Single writer on `main`:** while the worker
owns a chapter, the hub does not commit to main — it fetches, reviews, relays.
If the worker's agent needs anything from GitHub or the hub, it cannot get it
itself by design; it should leave the request in its commit messages or a
NOTES file for the hub to act on.

Related: **[doc-20](doc-20-responder-tune-spec.md)** (chapter 1, in full) ·
**[doc-19](doc-19-eval-framework.md)** (eval framework) ·
**[doc-18](doc-18-harness-redesign.md)** + **doc-18.1** (harness and turn logic) ·
**[doc-17](doc-17-tuning-map.md)** (the v1 end state and why the redesign
happened) · `tuning/v2/M4_PLAN.md` (execution tracker) ·
`tuning/v2/eval/REPORT_evalv3.md` (results of record) · `CLAUDE.md`.
