# Doc 14: Training Data Issues — Phantom Click Events & Empty Outputs

Findings from auditing `tuning/data/atomic.jsonl` (1,499 rows extracted from sim logs). Two upstream bugs — one in the web app, one in the simulator — combine to pollute training data with phantom `[system] User clicked: X` events and empty `assistant_output` rows.

Scope: **root-cause documentation only**. Upstream code fixes are deferred; for this training round we apply a hacky text-level cleanup in `tuning/scripts/clean_atomic.py` (tracked separately).

---

## TL;DR

- The production web app **never emits** `[system] User clicked: Save Draft` / `Submit`, despite the system prompt documenting these events.
- The simulator **synthesizes** these phantom events and sends them as a **second** LLM A call per button interaction (decomposition of a single user action into two separate turns).
- Result in training data:
  - **25 rows** (sub_turn > 0) whose `user_message` is the phantom event — outputs are often empty or hallucinate `[system] Save failed: server unreachable.`
  - **40 rows** (sub_turn = 0) where LLM A emitted empty output in response to a verbal save/submit request
  - **7 rows** (sub_turn = 0) where LLM A hallucinated a `[system] User clicked: Save Draft\n\n...` prefix in its own output (role-tag leak)
  - Many realistic `[system] Draft saved successfully.` turns (51 rows) carry a phantom click event in their `conversation_history`
- Severity: **high** — these patterns directly teach the model to (a) go silent on verbal save/submit requests, (b) emit `[system]` tokens as its own speech, and (c) expect an event that never fires in production.

---

## Bug 1: Web app is silent on button clicks

**Location:** `packages/web-app/public/index.html`, `handleSaveDraft` (lines 2012-2034), `handleSubmit` (lines 2037-2060).

**Observed behavior:**

```js
async function handleSaveDraft(btn) {
  btn.disabled = true;
  btn.textContent = 'Saving...';
  try {
    const res = await fetch('http://localhost:3005/api/drafts', { ... });
    if (res.ok) {
      sendSystemEvent('Draft saved successfully.');   // only event emitted
    } else {
      sendSystemEvent('Save failed: server returned an error.');
    }
  } catch (err) {
    sendSystemEvent(`Save failed: ${err.message}`);
  }
}
```

The handler fires `fetch` immediately on click, then emits **only** the result event. LLM A never receives a `[system] User clicked: Save Draft` message.

**Contradicts system-prompt docs:** `packages/web-app/public/js/system-prompt.js` lines 125-137 explicitly list the click event as part of LLM A's expected vocabulary:

```
- `[system] User clicked: Save Draft` — User clicked a show_button button.
```

So LLM A is conditioned during its context-turn to expect this event, but it never arrives in production.

**Proposed fix (deferred):**

Option A — keep single LLM call, combine events:
```js
async function handleSaveDraft(btn) {
  btn.disabled = true;
  btn.textContent = 'Saving...';
  try {
    const res = await fetch(...);
    if (res.ok) {
      sendSystemEvent('User clicked: Save Draft\n[system] Draft saved successfully.');
    } else {
      sendSystemEvent('User clicked: Save Draft\n[system] Save failed: server returned an error.');
    }
  } catch (err) { ... }
}
```

Option B — emit both events, let doGenerate run twice (matches docs literally but doubles LLM latency per click).

**Recommendation:** Option A. Eliminates the split entirely and gives LLM A full context in one call. Requires updating the system prompt docs to describe the combined form.

---

## Bug 2: Simulator decomposes `message + click_button` into two LLM A calls

**Location:** `packages/integration-tests/src/e2e/simulator/simulate.ts`, lines 693-711.

**Observed behavior:** when LLM U emits a candidate that bundles a `message` and a `click_button` action (a realistic user pattern — "Yes please save it" + click), the simulator:

1. Sends the message text as the first LLM A call (sub_turn = 0).
2. Synthesizes a second user message `[system] User clicked: Save Draft` and sends it as a second LLM A call (sub_turn = 1).
3. Queues `[system] Draft saved successfully.` as `pendingButtonResponse` (line 715), which fires as turn N+1 sub_turn = 0.

Net effect: **one user action produces three LLM A turns.** The middle turn (the phantom click) never exists in production.

**Concrete example** — session `sim-northfield-alex-confused-2026-03-25T03-14-26-720Z`, turn 25:

```
LLM U candidate (rank 2, intent=confirm):
  actions: [
    { action: 'message', text: "Oh great, that's reassuring! Yes, please save it." },
    { action: 'click_button' }
  ]
action_plan:
  messages: [{ text: "Oh great, that's reassuring! Yes, please save it." }]
  click_button: 'save_draft'

Simulator produces:
  turn 25 sub_turn 0  llm_a_input.user_message = "Oh great..."
  turn 25 sub_turn 0  llm_a_output.raw_text    = "...[system] User clicked: Save Draft\n\nGreat, let me save your draft now!\n---actions---[show_button save_draft]"   ← role-tag leak (A)
  turn 25 sub_turn 1  llm_a_input.user_message = "[system] User clicked: Save Draft"  ← phantom (C)
  turn 25 sub_turn 1  llm_a_output.raw_text    = ""                                    ← empty (B)
  turn 26 sub_turn 0  llm_a_input.user_message = "[system] Draft saved successfully." ← realistic
```

All three data-quality issues (A, B, C) trace to this single decomposition bug.

**Proposed fix (deferred):** bundle the click into the same LLM A call as the message. Pseudocode:

```ts
// Instead of:
await callAndLogLlmA(messages, subTurn=0);
if (clickButton) {
  await callAndLogLlmA([{text: `[system] User clicked: ${clickButton}`}], subTurn=1);
}

// Do:
const clickSuffix = clickButton ? `\n[system] User clicked: ${clickButton}` : '';
await callAndLogLlmA([{text: buildLlmAMessage(messages) + clickSuffix}], subTurn=0);
```

This also requires the web app's combined-event fix (Bug 1 Option A) to keep production and simulation behavior aligned.

---

## Bug 3: Returning-user saved fields not loaded at session start

**Location:** Simulator session setup (exact file TBD on upstream pass).

**Observed behavior:** When a sim session is configured as a "returning user" (draft-restored scenario), the saved fields are **not** pre-populated into the form state at turn 0. The first user message contains the hint (`[system] Draft restored. N fields previously filled.`), and the AI behaves as if the data is there — refers to "your Stanford degree", "your recommenders are already filled in", etc. — but the form's actual filled-field state stays empty for the first several turns.

Then, mid-session (typically around turn 4–6), the saved fields appear in the form state all at once, with no set_fields action in the session being responsible for them. From that point on, the session behaves normally.

**Concrete example** — session `sim-northfield-alex-returning-2026-03-24T15-19-00-534Z`:

```
Turn 0: user says "Draft restored. 15 fields previously filled."  form = 0 filled fields
Turn 1: user asks to see Personal Info                             form = 0 filled fields
Turn 3: user says "Nice, personal info is complete!"               form = 0 filled fields
Turn 4: AI says "everything else for your Stanford degree is already filled in"  form = 0 filled fields
Turn 5: (nothing in the session sets fields)                       form = 29 filled fields  ← data materializes
Turn 6+: normal flow
```

**Training-data impact:** 40 rows where the AI emits a review/preview card but the form state is empty (the "sparse-state review" rows). Dropping or back-filling them is needed; otherwise the synthetic review target is nonsensical (``Completed 0 fields:``).

Two sub-variants within the 40 rows that reflect separate failure modes:

- **Truncated session** (1 row): session ends at turn 0 before the mid-session data appears. No later state to back-fill from.
- **Profile-load never happened** (1 row): user claims to be a returning applicant mid-conversation; AI shows a preview of what it *would* load; but the saved profile never actually enters the form state at any point in the session. Session ends with only a handful of fields that the user manually dictated.

**Proposed fix (deferred):** on session setup for returning-user scenarios, the simulator should populate the form state with the draft's saved fields **before** turn 0 runs, mirroring what the web app does in production (backend hydrates the form from the draft at page load). The `[system] Draft restored` message should be the only artifact the AI sees; the data should already be in the form.

---

## Combined effect on training data

| Issue | Count | Root cause | Training hazard |
|---|---|---|---|
| A: role-tag leak in `assistant_output` | 7 | Bug 2 (LLM A sees a `[system]`-heavy context and starts its own output with the leaked prefix) | Model learns to emit `[system]` tokens as speech |
| B: empty `assistant_output` on verbal save/submit | 40 | Bug 1 (LLM A has no `save_draft` action and gets stuck when user verbally requests save) | Model learns to go silent on save/submit |
| C: phantom `[system] User clicked: X` turns | 25 | Bug 2 | Model learns to expect an event that never fires |
| D: `conversation_history` contains phantom click turns | ~dozens | Bug 2 | Same as C, leaks via history even after current-turn cleanup |
| E: returning-user review turns with empty form state | 40 | Bug 3 (draft fields appear mid-session instead of at turn 0) | Synthetic review target would be `Completed 0 fields:` — trains nonsense |

Coverage gaps (worth flagging but not caused by these bugs):

- **0 rows** with `[system] Save failed: ...`
- **0 rows** with `[system] Submission saved. Reference: ...`
- **0 rows** with `[system] Validation error: ...`

LLM A's system prompt documents all three, but none appear in sim data because LLM U never triggers save-failure paths and submit flows are rare. Will require targeted sim scenarios to cover.

---

## Current mitigation

For this training round, we apply a text-level cleanup in `tuning/scripts/clean_atomic.py`:

- **Issue C** → drop rows where `sub_turn > 0` (25 rows)
- **Issue A** → replace `assistant_output` with canned "press the button" template (7 rows)
- **Issue B** → same canned template (40 rows)
- **Issue D** → filter `conversation_history` entries that match phantom `[system] User clicked: ...` pattern
- **Issue E** → back-fill `form_state_before` for early-session review turns using the mid-session "jump" snapshot from the same session (38 rows). The 2 rows in sessions with no usable later state (truncated session + profile-never-loaded) are dropped.

Expected surviving row count: **1,474** (1,499 − 25). Of those, 47 have rewritten outputs and 38 have back-filled form states.

This is explicitly a hack — it does not fix the upstream bugs; it just makes this round's training data consistent with a plausible production behavior.

---

## When to resolve upstream

Before the **next** sim-regeneration cycle (not this one). Order of work:

1. Web app — apply Bug 1 Option A fix to `handleSaveDraft` and `handleSubmit`.
2. System prompt — update `system-prompt.js` lines 125-137 to describe the combined click+result event.
3. Simulator — apply Bug 2 fix in `simulate.ts:693-711`.
4. Simulator — apply Bug 3 fix so returning-user sessions pre-load saved fields into the form state at turn 0 (before the first LLM A call).
5. Sim scenario coverage — add scenarios that trigger `[system] Save failed`, `[system] Submission saved`, and `[system] Validation error` so those paths appear in training data (currently 0 rows each).
6. Delete `tuning/scripts/clean_atomic.py` and re-extract from fresh sim logs.

---

## Longer-term: change the mental model for training data

Even after the upstream bugs above are fixed, using raw sim sessions as direct training data will keep producing the same class of problems we keep hand-patching in this round:

- Every session involves an LLM playing the user and another LLM playing the assistant, plus a web app and a simulator in the middle. Any of the four can misbehave, and the resulting row looks plausible enough to slip through surface checks.
- Edge cases ("draft restored mid-session", "user clicks before AI finishes", "profile referenced but never loaded") show up with long tails and each one needs a bespoke cleanup.
- Validating a sim session requires understanding the full multi-turn context, which is slow and error-prone — we can only catch issues we thought to look for.

We should shift the mental model:

- **Treat sim sessions as *seeds*, not as training data directly.** A seed is a realistic skeleton of a conversation — personas, topics, pacing, user phrasing patterns — that captures how real interactions flow.
- **Programmatically mutate seeds to produce clean, validated training examples.** For each training scenario we care about (gather one field, gather several fields, ask a choice, show a review, offer save, handle a save failure, etc.), build a small generator that starts from a seed's surface features but synthesizes the form state, the expected actions, and the assistant output deterministically. The output is correct by construction — no hidden bug from any of the four LLM/app/simulator layers can contaminate it.
- **Benefits:** edge-case coverage becomes a matter of "did we write a generator for this scenario?" rather than "did the sim happen to produce this rare thing?". Validation becomes cheap — each generator's output is structurally checkable. And we can target gaps (Save failed, Submission saved, Validation error, returning-user flows) directly instead of waiting for sim luck.
- **Applies to both SFT and RL:** SFT gets clean supervised targets; RL gets curated eval scenarios with well-defined expected behavior, so reward functions can check concrete things instead of trying to match fuzzy sim trajectories.

Sim data still has a role as the seed source — that's where realistic user phrasing, persona nuance, and organic conversation shape come from — but we stop asking it to also be the ground truth.

This is a larger effort than the doc-14 upstream fixes and belongs in its own design doc when we're ready to plan it.
