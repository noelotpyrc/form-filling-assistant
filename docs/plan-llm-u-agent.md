# Plan: LLM U Agent — Candidate Action Generation

## Goal

Get LLM U to produce N ranked candidate actions per turn in a structured format. Use real runs to understand the distribution of candidates before building any controller logic.

## Phase 1: Prompt tuning — get LLM U to produce good candidates

**Input to LLM U each turn:**
- Screen view (from A→U adapter)
- Persona data (relevant fields for this form)
- Behavior profile (personality traits)
- "Give your top N most realistic reactions"

**Output format:**
```json
{
  "candidates": [
    {
      "rank": 1,
      "intent": "react_to_suggestion",
      "reasoning": "assistant asked which program, my persona is ME",
      "actions": [{ "action": "select_choice", "label": "Mechanical Engineering (MS)" }]
    },
    {
      "rank": 2,
      "intent": "ask_question",
      "reasoning": "could ask about program details before choosing",
      "actions": [{ "action": "message", "text": "what's the difference between MS and PhD?" }]
    },
    {
      "rank": 3,
      "intent": "provide_info",
      "reasoning": "could skip the choice and just state preference in chat",
      "actions": [{ "action": "message", "text": "I want to do mechanical engineering" }]
    }
  ]
}
```

**What we're tuning for:**
- Candidates are plausible (no hallucinated UI elements, no actions the screen doesn't support)
- Rank ordering makes sense for the persona + profile
- Intents are diverse (not 3 variations of the same thing)
- Combos appear naturally when realistic (e.g., fill some fields + send a message)

**How to validate:**
- Run against recorded sessions — compare LLM U's rank-1 candidate to what the real user actually did
- Spot check: do the rank 2-3 candidates feel like things a real person might have done instead?
- Check across profiles: does a "thorough" persona produce different candidate sets than "impatient"?

**Deliverables:**
- Working LLM U prompt that produces structured candidates
- A batch of candidate sets from multiple sessions (different personas × profiles × forms)
- Analysis: how often does rank-1 match real user behavior? How diverse are the candidate sets?

## Phase 2: Controller design — informed by Phase 1 data

Decide what (if any) controller logic is needed based on what we observe in Phase 1 candidate data. Possible questions the data will answer:

- Do we even need a controller, or is rank-1 always good enough?
- Are there turns where LLM U produces bad candidates that need filtering?
- Does the behavior profile actually shift the distribution, or do we need controller-side weighting?
- How often do combos appear? Do we need to cap them?
- Are there intent categories the LLM never produces that we want to force?

**Not designing this now.** The controller shape should emerge from the data, not from speculation.

## Intent vocabulary (starting point, will evolve)

- `react_to_suggestion` — respond to ask_choice, show_fields, show_button
- `provide_info` — proactively share personal data
- `ask_question` — ask about a field, process, or requirement
- `correct_mistake` — fix something the assistant got wrong
- `fill_fields` — directly edit form fields
- `upload_file` — attach a document
- `small_talk` — off-topic or social message
- `stop` — end the session

## Open questions

- What's the right N? Start with 3, adjust based on output quality.
- Should LLM U generate full natural language text for all N, or just for rank-1? (Full text for all N is simpler, costs ~2-3x more tokens per turn. Decide after seeing token usage.)
- Multi-turn context: LLM U needs conversation history to avoid repeating itself. Use `--resume` (same as LLM A), or include last K turns in prompt?
