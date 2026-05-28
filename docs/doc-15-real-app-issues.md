# Doc 15: Real-App Issue Log (Local SFT Harness)

Issues observed when driving the local SFT model end-to-end through the web app via the harness (see [doc-12 Experiment 10](doc-12-tuning-journal.md#experiment-10-e2e-harness--plug-sft-v2-into-the-web-app-planned)). Synthetic eval is the regression net; this doc is the bug bucket for things that only show up under real interactive use.

## How to add an issue

When something looks wrong in a session:

1. Save the session log path: `logs/session-<session_id>.jsonl`
2. Add an entry below using the next R-number in the index
3. Fill in:
   - **Symptom**: what the user saw
   - **Trace**: pointer into the JSONL (line numbers or turn descriptions)
   - **Root cause**: which layer is broken — harness / composer / browser / model behavior / training data / form schema
   - **Severity**: `blocker` (session unusable), `painful` (visible misbehavior, user can work around), `minor` (cosmetic / rare)
   - **Status**: `open`, `fixed`, `deferred — model fix`, `deferred — data fix`, `wontfix`
   - **Fix** (if applied): commit ref + 1-line summary

Issues whose root cause is upstream (training data, action-router calibration) get deferred here and tracked under the relevant Experiment in doc-12 instead. This doc is for *observed failures*, not *fixes*.

## Layer cheat-sheet

When triaging a new issue, check in this order:

| Layer | Symptoms typically look like | Fix lives in |
|---|---|---|
| Browser UI | undefined values, missing renders, click handlers breaking | `packages/web-app/public/index.html`, `chat-provider.js`, `action-parser.js` |
| Harness composer | model emits a flag but no action appears, or action shape mismatches UI contract | `tuning/harness/composer.py` |
| Harness pipeline | DSPy parsing errors, context-string oddities, latency surprises | `tuning/harness/pipeline.py` |
| Harness lifecycle | save_draft / submit_final flow broken | `tuning/harness/lifecycle.py`, persistence-server |
| Model behavior (action_router) | flag fires when it shouldn't, or fails to fire when it should | training-side fix; track in doc-12 |
| Model behavior (content modules) | hallucinated values, wrong fields, paraphrased options | training-side or RL/GEPA; track in doc-12 |
| Training data | systematic class of errors traceable to bad atomic.jsonl rows | doc-14, retrain |
| Form schema | option labels/values inconsistent, fields missing | `packages/web-app/public/forms/*.json` |

---

## Issue index

| ID | Date | Severity | Status | Root cause | One-liner |
|---|---|---|---|---|---|
| R1 | 2026-04-29 | blocker | fixed | harness composer | `ask_choice` options emitted as `[str]` but UI expected `[{label,value}]` — clicks returned "undefined" |
| R2 | 2026-04-29 | painful | deferred — model fix | action_router false negative | `needs_choice` doesn't fire when `text_responder` organically asks a question |
| R3 | 2026-04-29 | painful | deferred — model fix | choice_builder hallucination | Model included a program ("Medical Assistant (MA)") that doesn't exist in the form schema |
| R4 | 2026-04-29 | painful | fixed | thin kickoff message | First-turn vault hallucination + question with no choice buttons; rewritten kickoff with explicit world-state in plain assistant voice |
| R5 | 2026-04-29 | painful | deferred — model fix (data/RL) | parallel modules lose context | text_responder produces empty reply ("Let me pull that up for you!") while data_extractor silently fills 17 fields — modules run in parallel and don't share outputs |
| R6 | 2026-04-29 | painful | deferred — training data | data_extractor structural errors | Resume extraction confused job title with employer; hallucinated `funding_type` from teaching-assistant role; fabricated `how_heard` |
| R7 | 2026-04-29 | blocker (file UX) | deferred — model fix | missing file-assignment step | Model extracts data from uploaded resume but doesn't emit `set_fields {field_id: resume, value: filename}`; file slot stays empty |
| R8 | 2026-04-29 | painful | fixed | harness build_context | Conversation history truncated to 300 chars per turn — uploaded file content disappears after one turn; model says "no attachment" |
| R9 | 2026-04-29 | blocker (silently wrong values) | fixed | harness render_form_schema | `select` field options truncated at `[:5]` — schema's 6th+ options invisible to model; user picks them, model defaults to wrong value (e.g., Mechanical Engineering → `cs`) |
| R10 | 2026-04-29 | painful | deferred — model fix | action_router false negative | `has_new_data=False` on bare-statement identity claims like *"Let Sea is my full name"* — model acknowledges in text but doesn't extract; user repeatedly asks for name to be filled |
| R11 | 2026-04-29 | painful | deferred — model fix | text_responder hallucination | Model claims fields are empty when form_state explicitly shows them filled (contradicts its own context) |
| R12 | 2026-04-29 | **blocker** | deferred — model fix (data) | training-data leakage | Model surfaces a memorized training-data persona ("Alex Chen, DOB 1995-11-20...") as the *current* user's saved data — pure confabulation, doubles down when corrected |
| R13 | 2026-04-29 | painful | deferred — model fix | data_extractor false positives | Model fabricates field values (`start_term=fall_2026`, `enrollment_type=full_time`, `program=cs`) from conversational filler ("can you tell me more"), without any user input |

---

## R1 — ask_choice options shape mismatch (browser ↔ harness contract)

- **Date**: 2026-04-29
- **Session**: `logs/session-sess-1777478609477-e4d1ud.jsonl`
- **Severity**: blocker — once the user clicks a choice, the entire flow corrupts because the next user message becomes `[system] User selected option: "undefined"`.

### Symptom

User clicked a program choice button. The next turn arrived as `[system] User selected option: "undefined"` instead of the actual program name. Subsequent turns spiraled because the model didn't know what was selected.

### Trace

JSONL turn 16:
```
"message": "[system] User selected option: \"undefined\""
```

Earlier in turn 6 the model emitted a valid `ask_choice` action — the buttons rendered, but the click handler couldn't read the option's label.

### Root cause

`packages/web-app/public/index.html::renderAskChoice` (line ~1979) reads `opt.label`:

```js
btn.textContent = opt.label;
sendSystemEvent(`User selected option: "${opt.label}"`);
```

But our composer emitted `options` as a plain list of strings, matching the SFT model's `ChoiceBuilderSignature.options: list[str]`:

```json
"options": ["Computer Science (MS)", "Data Science (MS)", ...]
```

Production Claude evidently emits `[{label, value}, ...]` (the system prompt likely instructs that shape). The harness composer didn't match the contract.

This bug was invisible to the synthetic eval because that eval scores option-set F1 — it never simulates a click.

### Fix

`tuning/harness/composer.py::_build_ask_choice` now wraps each string in `{label, value}` (using the label as both since the SFT model doesn't carry form-internal value codes):

```python
wrapped.append({"label": s, "value": s})
```

Harness restart picks it up — no model retrain needed.

### Lesson

Every action type in the `---actions---` block has an implicit shape contract enforced only by the browser UI. The synthetic eval doesn't know about these; only E2E does. Worth adding a passing-shape sanity check somewhere (e.g., a JSON-schema validation of the composed `parsed_actions` against the contracts the UI expects) so we catch the next contract drift as a unit test rather than a real-session blocker.

---

## R2 — action_router false negative on `needs_choice`

- **Date**: 2026-04-29
- **Session**: `logs/session-sess-1777478609477-e4d1ud.jsonl`
- **Severity**: painful — the model's text contains a question, but no choice buttons render. User has to ask "what are the choices" or "i can't see" to elicit a corrected turn.

### Symptom

Turn 1: model says *"Let's start with the basics — which program are you interested in?"* but no choice buttons render. Action list is empty.

Turns 3 & 4: same pattern repeats — the model says it's about to show options, but `needs_choice=False`, so no action is emitted.

The user sees free-form text asking a question but no clickable answer.

### Trace

JSONL turn 3 `module_outputs`:
```json
{
  "response_text": "...which program are you interested in?",
  "needs_choice": false,
  "options": []
}
```

Turn 9 same. Turn 12 same.

Turn 15 *finally* fires `needs_choice=true` — but only after the user explicitly typed "still can't see".

### Root cause

The action_router and text_responder run independently against the same input. Text_responder organically generated a question; action_router predicted "no choice needed" from the user message alone.

This is exactly the false-negative bias measured in [doc-12 Experiment 9](doc-12-tuning-journal.md#experiment-9-sft-v2--binary-flag-action-router): `needs_choice` pos-recall is **42%**.

### Why it's not a harness bug

The harness faithfully composes whatever the action_router predicts. Action_router's prediction is wrong. Fix has to happen at training/prompt time.

### Status: deferred — model fix

Candidate approaches (none chosen yet):
- **GEPA** on the action_router prompt — cheapest, optimizes the instructions/few-shots for better calibration on `needs_choice` and `wants_review`
- **More training data** with positive `needs_choice` cases, especially turns where the assistant text contains an interrogative
- **RL** with a per-flag pos-recall reward — heaviest but most directly targets the bias
- **Cross-module coupling** — feed text_responder's output back into action_router. Architectural change, requires retraining

This is the dominant interactive-use failure mode and warrants its own experiment.

### Lesson

Eval headline accuracy hid this because it averaged over a class-imbalanced gold (mostly negatives). The pos/neg recall split (now in `compare_models.py report`) shows it clearly, but only the harness reveals how *painful* it is in the actual loop — multiple wasted turns trying to surface choices that the model semantically wants to ask.

---

## R3 — choice_builder hallucinated a non-existent program

- **Date**: 2026-04-29
- **Session**: `logs/session-sess-1777478609477-e4d1ud.jsonl`
- **Severity**: painful — user could be misled into asking about a program that doesn't exist; if they pick it the form_state ends up inconsistent.

### Symptom

Model's response in turn 6:

> 5. **Public Health (MPH)** — ...
> And there's a **Medical Assistant (MA)** program if you want to work in healthcare — but that's a different program altogether!

"Medical Assistant (MA)" is not in `packages/web-app/public/forms/masters-northfield.json`. The schema's `program` field has 6 options: cs / data_science / mba / education / public_health / engineering. None is a "Medical Assistant" track.

### Trace

JSONL turn 6 `module_outputs.options`:
```json
[
  "Computer Science (MS)",
  "Data Science (MS)",
  "Business Administration (MBA)",
  "Education (MEd)",
  "Public Health (MPH)",
  "Mechanical Engineering (MS)"
]
```

So the *structured* options list is correct (6 valid programs). The hallucination is only in the conversational `response_text` from text_responder — Medical Assistant isn't actually in the action's options list.

### Root cause

Two-stage:

1. **Text_responder** drifted off-schema and made up a 7th program.
2. **Choice_builder** correctly stuck to the 6 schema options.

Text_responder doesn't have strong grounding to the form schema in its prompt. It's optimized for naturalistic phrasing, not for refusing to invent unlisted options.

This is a content-quality gap consistent with Experiment 9's `choice_builder option F1 0.45` — though here the failure is in *text_responder*, which currently has no eval scorer for "respects schema constraints."

### Status: deferred — model fix

Candidate approaches:
- Stronger schema grounding in the text_responder system prompt (cheap, GEPA-tunable)
- Training data filter — drop turns where the assistant text mentions an option not in the schema
- Add a schema-grounding metric to `compare_models.py` (e.g., flag any text_responder output whose mentioned options are a superset of the schema's option labels for that field)

### Lesson

Different modules drift in different ways. Eval coverage on text_responder is currently very loose (length + format leak only). This is the second time text_responder behavior surprised us in real use; worth tightening its eval scorer so future regressions are visible.

### Additional evidence — sess-1777506409520-9v4fwl (turn 0, post-R9 fix)

After fixing the schema truncation (R9), the model started emitting an *extra phantom 7th option* in the program ask_choice:

```
options: [..., 'Mechanical Engineering (MS)', 'Mechanical Engineering (MS) — Additional']
```

The schema only has 6 program options. The 7th — `'Mechanical Engineering (MS) — Additional'` — is fabricated. Possible explanation: the SFT model trained on contexts with `[:5]` rendering, now seeing 6 options, generates a 7th by analogy ("if there's an Additional Documents file field elsewhere, maybe Additional applies here"). This is an *interaction effect* between the R9 fix and the model's training distribution — fixing one issue surfaced another.

Worth keeping in mind: deviating from training-time context format can introduce new hallucinations, even when the deviation is strictly more informative.

---

## R4 — Kickoff message redesign (fixed first-turn vault hallucination + missing initial choice)

- **Date**: 2026-04-29
- **Trigger session**: `logs/session-sess-1777484863000-lz71l3.jsonl`
- **Verifying session**: `logs/session-sess-1777498716039-g9pdc7.jsonl` (turn 1 confirmed clean)
- **Severity**: painful — every new session was misleading users by mentioning saved data we don't have, and burying the first question without selectable options.

### Symptom

Turn 1 model output:
> "Hello! I'd be happy to help you fill out the Northfield University Graduate Application. 🎓
> Before we dive in, let me check if you have any saved data from previous forms that we can reuse."

Turn 2 model output (after user said "no I don't"):
> "...What program are you interested in applying to?"

— with `needs_choice=False`, so no buttons rendered. User had to ask "what choice do I have" to surface the options.

### Root cause

Two compounding issues at the kickoff:

1. **Vault talk is a strong learned pattern.** 89/1442 (6.2%) of training turns mention vault / saved data / previous applications, because Claude (whose outputs the SFT model imitates) was vault-aware. We have no vault tools wired up in the local-SFT path, so the model invents one.
2. **Original kickoff was too thin.** `"The user has opened the {form} form. Their email is X. Please greet them and get started."` Gives the model no world-state, so it falls back to its training prior — including the vault-check pattern.

The action_router's false-negative bias on `needs_choice` (R2, 42% pos-recall) compounded: text_responder organically asked "what program?" but action_router saw a vague start-of-session input and decided no choice was needed.

### Fix

`packages/web-app/public/index.html::startFormWithDraftCheck()` rewritten to:

- **Use plain assistant voice** — the model's role is form-filling assistant. Instructions should be in user-facing language, not technical terms (no "schema", "ask_choice", "field_id", "vault", "set_fields", etc.).
- **State the world explicitly** — for new applicants: "starting a brand-new application, nothing has been filled in yet, no information from any past applications to reuse." For returning applicants: embed actual filled values via a new helper `summarizeFilledForGreeting(schema, formState)` that walks the schema for human labels.
- **Nudge toward presenting choices** — "ask which graduate program they'd like to apply to, presenting the available programs as choices they can pick from." Naturalistic phrasing, but matches a pattern in training data where Claude paired "ask which X" with `ask_choice`.

New kickoff for new applicants:
> *"kkkl@oka.com is starting a brand-new Northfield University Graduate Application. Nothing has been filled in yet, and there's no information from any past applications to reuse. Welcome them warmly and ask which graduate program they'd like to apply to, presenting the available programs as choices they can pick from."*

New kickoff for returning applicants:
> *"X is continuing their {form} from a previous visit. They've already provided: Full Name: Jane Smith; Email: ...; Program: data_science. Welcome them back warmly, give them a brief overview of what's been completed and what still needs to be filled in, then ask where they'd like to pick up."*

### Verified

In the next session (`sess-1777498716039-g9pdc7`):
- Turn 1: no vault talk; clean welcome, identifies email is filled
- Turn 1 ALSO fired `needs_choice=True` and rendered the 6-program ask_choice action correctly

R2 is therefore *partially mitigated by R4* on the first turn — explicit prompting can route around the action_router bias when the directive is in the user message itself.

### Lesson

The model-as-form-filling-assistant framing matters at the kickoff. Telling it the *state of the world* (no draft, no vault) in natural language costs nothing and short-circuits its strongest hallucination patterns. Technical terms in the kickoff would have leaked into the model's response and broken the assistant persona; plain user-facing language keeps the role consistent.

This also confirms a more general pattern: directive prompting can paper over action_router calibration issues for *the specific turn it covers*, but doesn't generalize. Subsequent sessions still fail R2 elsewhere.

---

## R5 — text_responder produces empty/uninformative reply when other modules do the work

- **Date**: 2026-04-29
- **Session**: `logs/session-sess-1777498716039-g9pdc7.jsonl` (turn 9 — Resume.pdf upload)
- **Severity**: painful — user saw no acknowledgment that 17 fields silently appeared in the panel.

### Symptom

User uploaded Resume.pdf. The data_extractor module successfully extracted 17 fields and the form panel updated correctly. But text_responder's conversational reply was literally just:

> "Let me pull that up for you!"

No mention of what was found, no progress recap, no confirmation. The user couldn't tell whether the model understood the upload.

### Root cause

`FormAssistant.forward()` runs the modules in *parallel* (or at least, independently — text_responder doesn't read data_extractor's outputs):

```python
text_result = self.text_responder(context=context, user_message=user_message)
if has_new_data:
    extract = self.data_extractor(context=context, user_message=user_message)
```

Each module sees only `(context, user_message)` — none see another module's outputs. So text_responder can't say "I extracted Jane Doe's GPA of 3.58" because it doesn't know data_extractor will produce that.

This is structural to the 5-module split, not a per-turn bug.

### Status: deferred — model fix (data + likely RL)

Approaches in order of effort:

1. **Generate training data where text_responder learns to acknowledge work.** When `has_new_data=True`, the response_text should be patterns like:
   - "I'm working on it — let me pull that information out for you."
   - "I filled in some of these from the resume — could you check the form panel and confirm?"
   - "Got it — added your education and most of your work history. Take a look and let me know if anything needs fixing."
   Pair with a `show_preview` action so the user actually sees what changed.

2. **RL on the same target** — text_responder reward includes "did your reply reference the work being done."

3. **Architectural change**: chain modules so text_responder runs *after* data_extractor and sees its output. Bigger refactor; affects FormAssistant + GEPA path.

### Lesson

Parallel-module architectures lose cross-module context cheaply but pay for it in user-facing coherence. In synthetic eval this didn't surface (text_responder content scoring is loose); in real interactive use, the disconnect is jarring — the user sees a one-liner reply while the form magically populates.

Worth keeping the modular split but training text_responder to be aware of *what other modules typically do* so it can reference the work even without seeing the actual output.

---

## R6 — data_extractor structural errors on resume upload

- **Date**: 2026-04-29
- **Session**: `logs/session-sess-1777498716039-g9pdc7.jsonl` (turn 9)
- **Severity**: painful — wrong values in the form panel until the user notices and corrects.

### Symptom

Resume.pdf extracted text contained:
> *"Software Engineering Intern - TechCorp, Summer 2024 | San Francisco, CA"*

Model's `set_fields` action emitted:

| Field | Extracted | Expected |
|---|---|---|
| `jobs.0.employer` | "Software Engineering Intern" | "TechCorp" |
| `jobs.0.title`    | "Software Engineering Intern" | "Software Engineering Intern" ✓ |
| `funding_type`    | `"['teaching-assistant']"` | not present in resume; fabricated |
| `how_heard`       | "Web Search" | not present in resume; fabricated |

The employer/title swap is the most concerning — both fields got the same value, and the wrong one. The funding_type hallucination suggests the model conflated the user's *teaching assistant experience* with a *funding-type request*.

### Root cause

Two compounding factors:

1. **Thin file-handling training coverage**: only 26/1442 (1.8%) of training turns involved file uploads. The model has limited exposure to the structural patterns of resumes, transcripts, etc.

2. **No semantic distinction between "this happened in their past" vs "this is what they want now"**: the model saw "Teaching Assistant" in the resume and mapped it to `funding_type` — which is asking about *desired financial support*, not past roles.

Consistent with Experiment 9's `data_extractor value_match=0.82` finding — about 1-in-5 correctly-identified fields gets the wrong value, often due to structural misreads like this.

### Status: deferred — training data

Approaches:

1. **More file-handling training data** with explicit (resume_text, expected_fields) pairs — particularly examples that disambiguate experience from funding requests, employer from title, etc.
2. **Filter existing training data** to drop turns where the assistant clearly confused fields (would need a sweep over atomic.jsonl).
3. **Add a schema-grounding metric** to `compare_models.py` — flag extractions where the value contradicts the field's type / option set (e.g., `funding_type` value not in the schema's options).

### Lesson

`value_match=0.82` in synthetic eval was vague; manual inspection of one real resume reveals the failures are *structural* (wrong field association) rather than random noise. This is a harder problem than tweaking prompts — needs better training-data semantics.

### Additional evidence — sess-1777504932259-hx4cxv (turn 19, second resume upload)

A second resume upload turn produced a different — and more severe — pattern: **the same string was written to four different fields**:

| Field | Extracted | Expected |
|---|---|---|
| `jobs.0.employer` | `Software Engineering Intern - TechCorp` | `TechCorp` |
| `jobs.0.title` | `Software Engineering Intern` | `Software Engineering Intern` ✓ |
| `jobs.0.start_date` | **`Software Engineering Intern`** | `2024-06` |
| `jobs.0.description` | `Software Engineering Intern - TechCorp` | the bullet points |
| `degrees.0.end_date` | `2027-05` | `2025-05` (resume says May 2025) |
| `full_name` | (not extracted) | `Jane Doe` |

The `start_date = "Software Engineering Intern"` failure is particularly telling — the model is essentially shoving the same string into multiple fields when it can't otherwise locate the right value. Combined with the `full_name` miss (R10) and date hallucination (`2027-05` for May 2025), this turn is a microcosm of the SFT model's file-handling weaknesses.

The root cause is the same — thin coverage (1.8% file turns in training) — but the failure mode is more brittle than the original R6 evidence suggested.

---

## R7 — uploaded file not auto-assigned to its file field

- **Date**: 2026-04-29
- **Session**: `logs/session-sess-1777498716039-g9pdc7.jsonl` (turn 9)
- **Severity**: blocker for the file-upload UX — even when extraction succeeds, the file box in the form panel stays empty.

### Symptom

User uploaded Resume.pdf. The model's `set_fields` action:
- Emitted 17 field/value pairs from the resume content (education, work, etc.)
- **Did NOT include** `{ "field_id": "resume", "value": "Resume.pdf" }`

Browser-side `assignFileToField()` (in index.html) only fires when a `set_fields` action targets a *file*-type field. Without that entry, the resume slot in the form panel stays empty, even though all the resume's data is now elsewhere in the form values.

### Root cause

Production Claude follows a 3-step file flow per its system prompt (`packages/web-app/public/js/system-prompt.js:196-243`):

1. Recognize document type (resume / transcript / SOP)
2. `ask_choice` to confirm which file field it goes to
3. On confirm, `set_fields` with `field_id=<file_field>, value=<filename>` AND extract data

Our SFT model:
- Skipped step 1 (no doc-type acknowledgment in text)
- Skipped step 2 (no `ask_choice` for which field — fired `needs_choice=False`)
- Did step 3's *data extraction* but NOT step 3's *file assignment*

The model partially imitated Claude but lost the file-assignment muscle memory because (a) the system prompt isn't given to the SFT model, and (b) only 26 file-upload turns in training.

### Status: deferred — model fix

Approaches:

1. **Add a natural-language hint in the harness context preamble**: "When the applicant attaches a document, save the file to the matching slot AND extract any matching information from it. Confirm what you found and which field it went to."
2. **Train more file-upload examples** that explicitly emit `set_fields {field_id: <file_field>, value: <filename>}`.
3. **GEPA on data_extractor's signature** to add this behavior in its instructions.
4. **UI-side fallback (hacky)**: auto-assign uploaded files to their best-matching file field when no `set_fields` action does so within a turn. Feels wrong — masks model error.

### Lesson

When you've shipped a model that imitated a more capable assistant, the *reflexes* survive (extract data) but the *meta-step* (recognize document, confirm placement, assign by filename) often doesn't. SFT gives you behavior but not introspection — you need to train each step you want to keep, not assume composition.

---

## R8 — conversation history truncation drops file content after one turn

- **Date**: 2026-04-29
- **Session**: `logs/session-sess-1777498716039-g9pdc7.jsonl` (turn 10 — "i already uploaded")
- **Severity**: painful — multi-turn references to uploaded files break catastrophically.
- **Status**: open (fix incoming next).

### Symptom

Turn 9: User uploads Resume.pdf. 17 fields populate the form panel.
Turn 10: User types "i already uploaded".
Turn 10 model reply: *"It looks like the file didn't come through again — I don't see an attachment in your message. Could you try uploading the resume again?"*

### Root cause

`tuning/harness/pipeline.py::build_context()` truncates each conversation_history entry at **300 characters**:

```python
ctx += "\n".join(
    f"{'User' if h.get('role') == 'user' else 'Assistant'}: "
    f"{(h.get('content') or '')[:300]}"
    for h in recent
)
```

When the model looked at its `Recent conversation` block on turn 10, the resume content was cut off mid-word at exactly 300 chars:

```
User: [File: Resume.pdf]
Jane Doe  Email: jane.doe@example.com | Phone: (123) 456-7890 | Anytown, USA LinkedIn: ...
... May 2025 | GPA: 3.58 | Honors: Cum Laude  Experience  Software E       ← cuts off here
Assistant: Let me pull that up for you!
```

So the file marker `[File: Resume.pdf]` is visible but the content is effectively gone. The model sees "user mentioned a file but I can't see what was in it" and decides nothing was uploaded.

The 300-char cap was inherited from `compare_models.py::build_context` where it makes sense for chatty turns. It does not make sense for file-upload turns.

### Fix

`pipeline.py::build_context()` should be **file-aware**:
- For turns containing `[File: ...]` markers, preserve the entire block (cap at e.g. 8000 chars to bound worst case for huge files).
- For normal chatty turns, keep the existing 300-char cap (matches training distribution).

The `[File: name]<text>[End of name]` convention makes file blocks identifiable — match on the markers and don't cut inside them.

### Lesson

Bounded context windows are a sensible default for synthetic eval (test cases are short, isolated turns) but become destructive in real interactive use where users reference earlier uploads, earlier choices, earlier sections. The default truncation should be *content-aware* — preserve rare-but-important blocks (file uploads, structured data) intact, truncate only ordinary chatter.

This was a harness-side bug masked by the synthetic eval — `compare_models.py` is single-turn so the truncation never bit. Real multi-turn use surfaced it immediately. Another point in favor of E2E testing as the actual development driver, with synthetic eval as the regression net.

---

## R9 — `select` field options truncated at 5; 6th+ options silently invisible to model

- **Date**: 2026-04-29
- **Session**: `logs/session-sess-1777504932259-hx4cxv.jsonl` (turn 3)
- **Severity**: blocker — produces silently-wrong field values whenever a user picks a beyond-5th option.
- **Status**: fixed.

### Symptom

User clicked **Mechanical Engineering (MS)** in the program-selection ask_choice. Model:
- response_text said *"Great choice — Computer Science (MS)!"*
- emitted `set_fields` with `program = cs`

Both wrong. The selected program is `engineering`, not `cs`, and the conversational reply named the wrong program entirely. Form panel ended up storing the wrong value.

### Trace — what the model actually saw

The schema rendering inside the context for that turn:

```
program (select: Computer Science (MS), Data Science (MS), Business Administration (MBA), Education (MEd), Public Health (MPH)) (required)
```

Five options. **Mechanical Engineering is missing**, even though the form schema (`packages/web-app/public/forms/masters-northfield.json`) lists it as the 6th option with `value: engineering`.

### Root cause

Three places in the codebase were rendering select options with `[:5]`:

| File | Function |
|---|---|
| `tuning/sft/gen_format_data.py` | `load_form_context()` (training-time) |
| `tuning/sft/compare_models.py` | `load_form_context()` (eval-time) |
| `tuning/harness/pipeline.py` | `render_form_schema()` (serve-time, this harness) |

So during SFT training, the model never saw the 6th option of any select field. At inference, the model has no representation of `engineering` as a valid program value. When the user picks it, the model defaults to whichever `program` value is most associated with "Mechanical Engineering" in its weights — apparently `cs`.

This is the worst kind of bug: **silently wrong**. The model is confidently writing a wrong field value, no error fires anywhere, and the user has no idea unless they manually verify the form panel.

### Fix

`tuning/harness/pipeline.py::render_form_schema()` now shows ALL options:

```python
opts = [
    o.get("label", o.get("value", "")) if isinstance(o, dict) else str(o)
    for o in f["options"]   # show ALL options, not just [:5] — see R9
]
```

This deliberately drifts from the training-time format. Strictly more information should not break the model badly — and the alternative is silently-wrong extractions on every beyond-5th-option pick.

The `[:5]` cap is still in `gen_format_data.py` and `compare_models.py`. Updating them requires a coordinated sweep:

1. Update both helpers to show all options
2. Regenerate training data (`gen_format_data.py`)
3. Re-run eval (numbers may shift slightly because context changes)
4. Eventually retrain a v3 SFT with the corrected context format

For now, only the harness is patched. Eval/train will be reconciled in the next training cycle.

### Lesson

The `[:5]` cap was probably introduced to keep prompt length bounded, but it costs correctness for any form with 6+ options on a single field. Since most production form fields have ≤5 options, this lay dormant in synthetic eval. As soon as we tested a form/scenario where the user could pick the 6th option, the bug surfaced as a blocker.

Generalization: **arbitrary truncation in context-building is a silent-correctness hazard.** Every `[:N]` deserves justification. If `N` exists for prompt-length reasons, document the upper bound on what's being truncated, and audit when a real value crosses that threshold.

---

## R10 — action_router false-negative on bare-statement identity claims

- **Date**: 2026-04-29
- **Session**: `logs/session-sess-1777504932259-hx4cxv.jsonl` (turns 32, 50)
- **Severity**: painful — user can't get their name into the form even when stating it directly, repeatedly.
- **Status**: deferred — model fix.

### Symptom

User typed:

| Turn | User message | Model response_text | Flags fired | Extracted |
|---|---|---|---|---|
| 32 | *"Let Sea is my full name"* | *"Got it, Sea! And could you share the rest of your personal details..."* | `[]` | (none) |
| 47 | *"my name is still not filled"* | *"No worries — we'll come back to that later."* | `[]` | (none) |
| 50 | *"no, fill it for me"* | *"Of course! Let me fill that in for you."* | `[]` | (none) |
| 53 | *"you still didn't"* | confused recovery attempt | `[]` | (none) |

Three direct identity claims, three escalations from the user, **zero name extractions**. The text_responder kept acknowledging in conversation ("Got it, Sea!", "Let me fill that in for you") while the action_router silently refused to fire `has_new_data`.

### Root cause

This is the same false-negative bias as R2 (`needs_choice`) — but here it's biting `has_new_data` on a specific subclass of inputs: **bare-statement identity claims** without a structured prefix.

Possible contributing factors:

1. **Training data bias**: identity values in atomic.jsonl probably arrived mostly via structured prefixes ("Full name: X" or as part of a multi-field dump) rather than freeform "X is my name."
2. **"Let Sea" is unusual** as a name — may not pattern-match strongly to the model's name distribution.
3. **Form state already had email** (`letsee@aa.com`) — the model may be over-reasoning that the name is *derived* from the email and therefore not "new" data. (This is plausible-but-incorrect inference; the model has no way to confirm the email's owner.)

### Why this matters more than R2

R2 (`needs_choice` false-negative) is annoying — the user has to ask "what choices do I have?" to surface them — but the conversation moves forward.

R10 (`has_new_data` false-negative on identity) is a **dead end**: the user *cannot* progress past the personal-info section by typing their name. They have to either (a) discover the right prefix phrasing, or (b) abandon. Multiple sessions could plausibly bounce off this.

### Status: deferred — model fix

Same fix paths as R2 / R5 / Experiment 9:

1. **Augment training data** with explicit (freeform identity claim → has_new_data=True + set_fields) examples. Diverse phrasings: "I'm X", "X is my name", "the name's X", "call me X".
2. **GEPA on action_router prompt** to make `has_new_data` more sensitive to direct identity claims.
3. **RL with pos-recall reward** specifically on the `has_new_data` flag for identity-mention turns.

A cheap workaround on the harness side could be: when `has_new_data=False` but the user_message matches a pattern like `r"my (full )?name is\s+\w+"`, fall back to running `data_extractor` anyway and emit the resulting set_fields. Hacky and pattern-specific, but recoverable. Worth considering only if model fixes don't land soon.

### Lesson

The `has_new_data` headline pos-recall of 89% (Experiment 9) hides a sub-distribution where it's much worse. Aggregate recall is a misleading proxy when the failure mode is concentrated on specific input patterns (here, identity claims). Worth slicing the pos/neg recall by user-message pattern in future eval reports.

---

## R11 — text_responder hallucinates field state contradicting form_state context

- **Date**: 2026-04-29
- **Session**: `logs/session-sess-1777504932259-hx4cxv.jsonl` (turn 26)
- **Severity**: painful — model gaslights the user about what's filled.
- **Status**: deferred — model fix.

### Symptom

User typed: *"i don't see my personal information filled"*.

Model's reply:
> *"I can see that your personal info is actually still missing — the **Email address** and **Phone number** are both empty. It looks like the form panel may not be showing all fields yet, or there could be a display issue."*

But what the model actually saw in `Filled fields:` (verified from lm-calls log):
```
"email": "letsee@aa.com", "program": "cs", "start_term": "spring_2027", ...
```

Email is right there. Model **contradicted its own context**.

### Root cause

text_responder is producing free-form text without strong grounding to the structured `Filled fields:` block in its context. Two compounding factors:

1. **No cross-module visibility.** text_responder doesn't see what data_extractor extracted; it only sees the raw context. If the context format isn't internalized as authoritative, the model can drift.
2. **The Filled fields blob is JSON-formatted and visually noisy.** A long single-line JSON dump may not be the easiest format for an LLM to attend to during text generation.

Compounded by R10: the user says "personal information is missing" because the *full_name* field really was empty (model couldn't extract). The model then over-generalized — *one* field is missing → *all* personal fields missing → invent a UI bug to explain it.

### Status: deferred — model fix

Possible directions:

1. **Better context formatting** for filled fields — instead of JSON dump, render as a human-readable list ("Already filled: Email = letsee@aa.com; Program = Computer Science (MS); ..."). This costs nothing on the harness side, and may get the model to attend more reliably.
2. **GEPA on text_responder prompt** to add a "before responding, verify your claims against Filled fields" step.
3. **Training data filter** to drop turns where the assistant's text contradicts the form_state.

Option 1 is testable now in the harness (modify `pipeline.py::build_context()`). The deviation from training format is small. Worth trying.

### Lesson

LLMs reading their own context isn't free — formatting matters. JSON dumps are fine for structured downstream parsing but suboptimal for natural-language attention. When the model needs to *talk about* what's filled, prefer a humanized rendering. (Same principle behind R4's natural-voice kickoff message.)

This is the second time the JSON-dump format of Filled fields has shown up as a contributing factor. Worth experimenting with a humanized version in the harness next session.

---

## R12 — training-data persona leakage (memorized identifiers surface as fabricated user history)

- **Date**: 2026-04-29
- **Session**: `logs/session-sess-1777506409520-9v4fwl.jsonl` (turns 3, 6, 9)
- **Severity**: **blocker** — model gaslights the user with another person's identity.
- **Status**: deferred — model fix (data + likely v3 SFT or RL).

### Symptom

Fresh new-applicant session. User email: `chatty@hh.com`. No previous data, no draft.

**Turn 3** — User: *"how is your day? let's take this slow"*
Model:
> *"I do have some information saved from previous sessions, but I also have a copy of my resume right here in the chat. Would you like me to use that instead?"*

Resume? Previous session? Neither exists.

**Turn 6** — User: *"what are you talking about? im first time"*
Model "apologized" and quoted what it claimed was the user's prior data:
> *"\"Full name: Alex Chen, preferred name Alex, DOB November 20, 1995, email chen@hh.com, phone +1-555-0456, US citizen, US resident.\""*

**Turn 9** — User: *"you are making things up now"*
Model doubled down:
> *"Oh no, sorry! I actually have all of that saved from our previous session"*

### Root cause

`alex` is one of the **simulator personas** in `packages/integration-tests/src/e2e/simulator/personas.ts`:

```typescript
export const alex: Persona = {
  name: 'Alex Chen',
  full_name: 'Alex Chen',
  ...
};
```

The simulator (`simulate.ts`) ran 916+ sessions through Claude using these personas to generate `atomic.jsonl`, the SFT training data. So Claude — and now SFT-v2 — saw **"Alex Chen, DOB 1995-11-20, ..."** repeated across many training turns.

The SFT model **memorized the persona identifier** and surfaces it on a fresh session when triggered by ambiguous input. This is direct training-data leakage — the model is not generalizing to "users have data," it's recalling specific training-data sequences.

The "doubling down" behavior (turn 9) is even more concerning: when corrected, the model amplifies the hallucination rather than recovering. SFT models are particularly bad at this — they have no instinct for "I might be wrong" because every training trajectory was Claude being right.

### Why this matters

- This is a hard ceiling on E2E usability. Users will not tolerate being addressed by another person's name with another person's bio.
- It's not fixable by prompting. The R4 kickoff explicitly states *"there's no information from any past applications to reuse"* — the model still confabulated. Pattern beats prompt.
- It's not fixable by GEPA. Prompts can't unmemorize.
- It's only fixable by **changing the training distribution** (filter persona-revealing patterns) or **scale** (4B / larger model has more capacity, less prone to memorizing rare strings).

### Status: deferred — model fix (training data)

Concrete fix paths:

1. **Filter atomic.jsonl** to redact persona identifiers — replace specific names ("Alex Chen") with placeholder tokens, regenerate training data, retrain v3.
2. **Diversify training data** — currently 3 personas × 5 profiles. Generate more personas to dilute memorization.
3. **Regularization during SFT** — dropout, label smoothing, smaller LoRA rank to reduce memorization capacity.
4. **Larger base model** — try Qwen3.5-4B SFT. More parameters → less likely to overfit specific persona strings.
5. **RL with hallucination penalty** — penalize outputs that contain training-persona names when the current session doesn't include them. Reward shape: detect-and-deduct.

### Lesson

When you generate synthetic training data with a small set of fixed personas, the SFT model **will** memorize them. This was foreseeable in retrospect — a few canonical names appearing in thousands of turns is exactly the recipe for memorization.

For research-context experiments this is fine and informative. For any future production-leaning effort: the training data has to either use a much larger persona pool, or use placeholder tokens that get substituted at inference.

This is the most damaging finding so far and the strongest motivator for either a v3 SFT with cleaner data or a larger base model.

---

## R13 — data_extractor fabricates field values from conversational filler

- **Date**: 2026-04-29
- **Session**: `logs/session-sess-1777506409520-9v4fwl.jsonl` (turns 15, 19)
- **Severity**: painful — silently wrong form values that the user never agreed to.
- **Status**: deferred — model fix.

### Symptom

**Turn 15**: User asked *"this is Northfield University?"* (a clarifying question — they hadn't agreed to anything). Model extracted `program=cs`. User never said CS.

**Turn 19**: User asked *"can you tell me more about it"* (filler — pure curiosity, no information provided). Model extracted:
- `start_term=fall_2026`
- `enrollment_type=full_time`

User said nothing about either.

The form panel ended up with three field values **the user had not provided and did not consent to**.

### Root cause

This is the *opposite* failure mode from R10. Where R10 is "user states X explicitly, model extracts nothing", R13 is "user says ambiguous thing, model extracts everything."

Likely reasons:

1. **Training-data bias toward extraction.** The atomic.jsonl turns where a user "asks more questions" likely had Claude *also* extract any incidental info (e.g., from conversation history) into set_fields. The SFT model learned this pattern but applies it too aggressively when there's nothing to extract.
2. **Default-value defaults.** "Fall 2026" + "Full-time" are common-case defaults in training-data extractions. The model fills them when no signal contradicts.
3. **Action_router false-positive.** Action_router fired `has_new_data=True` despite the user message containing zero new data. Mirror image of R2/R10's false-negatives — it errs in both directions, biased toward whichever case dominates training.

### Why this is dangerous

R10 (false-negative) wastes turns. R13 (false-positive) silently corrupts the form. The user might not notice until submission. This is worse than R10 in that sense.

### Status: deferred — model fix

Approaches:

1. **Action_router calibration via GEPA** — same as R2/R10. Tune `has_new_data` to fire only on actual new data.
2. **Data_extractor precision penalty in eval/RL reward** — heavily penalize TPs that don't correspond to user-provided info.
3. **Conservative-by-default training data** — generate more turns where Claude *resists* extracting from filler ("I'm not sure what you'd prefer for term — could you tell me?").

### Lesson

Pos-recall vs precision tradeoff in extraction. Our existing `compare_models.py` measures `value_match` on TP IDs but doesn't penalize hallucinated FPs separately. R13 cases would currently show as: user_message="tell me more", `set_fields=[start_term, enrollment_type]`, gold=[]. Precision=0 but our scorers may not flag this because the gold-empty case is treated as "no extraction expected." Worth adding a precision-aware metric for empty-gold cases (i.e., did the model emit ANY set_fields when it shouldn't have).
