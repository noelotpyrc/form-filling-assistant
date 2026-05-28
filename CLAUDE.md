# Project Rules

- Always work on the `main` branch. Do not create or switch to feature branches unless explicitly asked.
- After any major feature or endpoint changes, review and update the relevant docs in `docs/` before committing. Keep tool counts, endpoint lists, and test counts accurate.
- For all LLM model training tasks on Modal, refer to `tuning/modal_guide.md` for Modal coding style, API patterns, and best practices.

## Working with the user

1. **Distinguish discussion from execution.** Open exploration is fine when discussing solutions/directions. But when confirming params for a run that's about to start (model, sizes, judge, budget, paths, etc.), take the user's instructions literally — no substitutions, no defaults silently filled in, no walking back of their explicit overrides.
2. **Verify against current state, not memory.** When the user references a prior artifact ("the previous run", "the X file", "what we did last time"), look it up — `ls`, `grep`, `cat`, read the result JSON — rather than reconstructing from session memory.
3. **For costly actions, clarify ambiguity by asking — not by guessing.** If the action would take meaningful time or cost and there's room for interpretation, ask one short question before launching. Don't pick the interpretation I prefer and discover it was wrong after 30 minutes.

## Experiment hygiene

For any experimental task whose value comes from comparing "after" against "before" (GEPA / SFT / RL evals, A/B tests, pipeline migrations, etc.):

1. **Name the anchor explicitly.** What concrete output are we comparing against? A probe log, a prior journal measurement, a deployed system's output on a specific input — pick something concrete. "How the model usually behaves" is not an anchor.
2. **Reproduce the anchor before running the experiment.** Run the experimental harness in no-op mode (all plumbing, no experimental change applied) on the anchor's input. The output must match the anchor. If it doesn't, the harness diverges from the reference system and any "improvement" measured later is meaningless.
3. **Block the costly run on the smoke test.** Hard gate. If anchor ≠ harness, abort and surface the diff. Do not proceed on the assumption that the divergence is small or doesn't matter.

Most "improvement" numbers from experiments that skip step 2 are measuring artifacts of harness divergence, not the experimental change. When in doubt, diff against the anchor first.

### Anchors are model-specific

Anchors catch *harness* divergence, not legitimate model differences. When you train a new model, capture its anchor once with `tuning/harness/calibrate.py`, then point experiments at that anchor:

```bash
# 1. Start the server pointing at the new model (different port from existing)
mlx_vlm server --model /path/to/new_model --port 8101

# 2. Capture the new model's anchor
python -m tuning.harness.calibrate --model /path/to/new_model --port 8101 --label sft_v3
# → writes tuning/harness/fixtures/anchor_p1_ex3_sft_v3.json

# 3. Run experiments pointing at the new model + new anchor
python tuning/gepa/optimize.py \
    --student-port 8101 \
    --student-model /path/to/new_model \
    --anchor tuning/harness/fixtures/anchor_p1_ex3_sft_v3.json \
    ...
```

For comparing two models on the same eval, run them on separate ports (one server each), each with its own anchor. Both sides independently passing preflight means each harness is wired correctly to its own model — only then is the metric diff between them meaningful.
