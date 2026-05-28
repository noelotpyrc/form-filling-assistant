"""Two-layer rubric for the LLM judge.

Layer 1 — UNIVERSAL_GOOD: positive criteria applied to every case (what
makes any turn good, regardless of scenario).

Layer 2 — CATEGORY_BAD: one negative anti-pattern per CANNOT category,
applied when the case's `cannot_targets` includes that tag.

`get_rubric_for_case(case)` = UNIVERSAL_GOOD + union of CATEGORY_BAD items
for each tag in case["cannot_targets"]. Multi-tag seeds get the union.

All items are phrased yes-positive (yes = correct behavior). Scoring:
module score = weighted_yes / total_weight.
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────────
# Layer 1: universal "good answer" — applied to every case
# ─────────────────────────────────────────────────────────────────────────

UNIVERSAL_GOOD: list[dict] = [
    {
        "id": "intent_acknowledged",
        "weight": 1.5,
        "ask": "Does the response acknowledge or address what the user actually "
               "said in their most recent message — rather than skipping past it, "
               "ignoring it, or answering a different question?",
    },
    {
        "id": "internally_consistent",
        "weight": 2.0,
        "ask": "Are response_text, field_ids/field_values, flags, and "
               "question/options internally consistent? For example: if "
               "response_text says a value was saved, field_ids reflects that "
               "field; if needs_choice=True, question and options are populated; "
               "if has_new_data=False, field_ids is empty.",
    },
    {
        "id": "grounded_in_input",
        "weight": 2.0,
        "ask": "Does the response avoid inventing facts, values, names, or "
               "details that aren't present in user_message, "
               "conversation_history, or form_state?",
    },
    {
        "id": "appropriate_tone",
        "weight": 0.5,
        "ask": "Is the response's tone appropriate for the turn — warm and "
               "professional, not pushy when the user wants to pause/break, "
               "not overly formal when the user is being casual, empathetic "
               "when the user expresses frustration or fatigue?",
    },
    {
        "id": "correct_modules",
        "weight": 1.5,
        "ask": "Do the action flags match what the turn requires? "
               "has_new_data=True only when fields are being committed; "
               "needs_choice=True only when a multiple-choice question is being "
               "posed (with question + options populated); wants_review=True "
               "only when summarizing the application; wants_save/wants_submit "
               "only when the user requested those actions.",
    },
]


# ─────────────────────────────────────────────────────────────────────────
# Layer 2: per-CANNOT "bad answer" — one item per category, applied when
# the case's cannot_targets includes that tag.
# ─────────────────────────────────────────────────────────────────────────

CATEGORY_BAD: dict[str, dict] = {

    "#1_vibe": {
        "id": "honors_social_signal",
        "weight": 2.5,
        "ask": "Does the response acknowledge the user's social signal "
               "(chitchat, frustration, fatigue, request for a break, casual "
               "remark) BEFORE — or instead of — pushing straight to the next "
               "form question? A bare 'Please answer X' response that ignores "
               "the user's emotional or conversational cue should fail.",
    },

    "#2_text_action_disconnect": {
        "id": "text_matches_action",
        "weight": 2.5,
        "ask": "Are field_ids consistent with the action response_text claims "
               "was performed? Specifically, if response_text describes "
               "saving / updating / switching / replacing a particular field, "
               "does field_ids contain that field — not an unrelated one or "
               "nothing at all?",
    },

    "#3_state_check": {
        "id": "accurate_state_report",
        "weight": 2.5,
        "ask": "Does the response correctly describe what is already filled in "
               "form_state vs what is still missing? It should NOT claim a "
               "section is complete when fields are empty, NOT miss listing "
               "filled sections, and NOT describe a field as holding a value "
               "different from what form_state actually contains.",
    },

    "#4_commits_regardless": {
        "id": "no_unprompted_commit",
        "weight": 2.5,
        "ask": "When the user did NOT explicitly provide a data value in this "
               "turn (they asked a question, made a clarification request, sent "
               "chitchat, or otherwise didn't give field data), does the "
               "prediction correctly stay non-committal — meaning has_new_data="
               "False AND field_ids is empty AND field_values is empty? "
               "Conversely, if the user DID provide data, this item only asks "
               "that the prediction not invent extra values they didn't give. "
               "Opinionated wording or suggested formats in response_text are "
               "fine as long as nothing is actually committed.",
    },

    "#5_group_indices": {
        "id": "correct_group_target",
        "weight": 2.5,
        "ask": "Does the response write to the correct slot in an array / "
               "group field? When the user describes ADDING a new item "
               "(e.g., a second job, another recommender), it should append "
               "rather than overwrite the existing item. When the user "
               "references editing a specific sub-item (e.g., 'fix Prof. "
               "Walsh's email'), it should target that specific sub-item "
               "and leave the others unchanged.",
    },

    "#7_wrong_field_value": {
        "id": "correct_field_value_pairing",
        "weight": 2.5,
        "ask": "Does the response correctly assign each value to the field it "
               "belongs to — without swapping (e.g., employer name placed into "
               "the title field, or one recommender's email applied to a "
               "different recommender)?",
    },

    "#8_training_data_hallucination": {
        "id": "no_training_data_leak",
        "weight": 2.5,
        "ask": "Does the response avoid surfacing persona names, school names, "
               "program details, rankings, faculty, or other identifying "
               "details that are NOT present in user_message, "
               "conversation_history, or form_state? E.g., no inventing "
               "'Stanford' / 'MIT' when the schema names a different school, "
               "no fake person names, no fabricated program curriculum.",
    },
}


# ─────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────

def get_rubric_for_case(case: dict) -> list[dict]:
    """Return rubric items for a case = UNIVERSAL_GOOD + per-tag CATEGORY_BAD."""
    items = list(UNIVERSAL_GOOD)
    seen: set[str] = set()
    for tag in case.get("cannot_targets", []):
        if tag in CATEGORY_BAD and tag not in seen:
            items.append(CATEGORY_BAD[tag])
            seen.add(tag)
    return items


# ─────────────────────────────────────────────────────────────────────────
# CLI: validate every cannot_targets tag has a CATEGORY_BAD entry
# ─────────────────────────────────────────────────────────────────────────

def _validate():
    import json
    from pathlib import Path
    seeds_path = Path(__file__).parent / "seeds.jsonl"
    seeds = [json.loads(l) for l in open(seeds_path)]
    all_tags = {t for s in seeds for t in s.get("cannot_targets", [])}
    missing = all_tags - set(CATEGORY_BAD)
    if missing:
        print(f"Missing CATEGORY_BAD entries for tags: {sorted(missing)}")
        return
    print(f"All {len(all_tags)} tags have CATEGORY_BAD entries.")
    print(f"Universal items: {len(UNIVERSAL_GOOD)}")
    print(f"Category items:  {len(CATEGORY_BAD)}")
    print()
    print("Per-seed rubric size:")
    for s in seeds:
        n = len(get_rubric_for_case(s))
        tags = ",".join(s.get("cannot_targets", []))
        print(f"  {s['test_id']:30s} {n} items   tags={tags}")


if __name__ == "__main__":
    _validate()
