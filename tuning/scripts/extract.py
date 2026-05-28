#!/usr/bin/env python3
"""
Extract atomic training data from simulation JSONL logs.

Each LLM A turn becomes one atomic record containing:
- System prompt context (static + dynamic form state)
- Conversation history (all prior turns)
- User message for this turn
- Claude's output (ground truth)
- Metadata (session, persona, profile, turn number, cost)

Usage:
    python tuning/scripts/extract.py                          # from sims/
    python tuning/scripts/extract.py --sims-dir /path/to/sims # custom dir
    python tuning/scripts/extract.py --min-fields 5           # filter threshold
"""

import json
import os
import sys
import argparse
from pathlib import Path


def extract_session(filepath: str, min_fields: int = 5) -> list[dict]:
    """Extract atomic turns from a single session JSONL file."""
    entries = []
    for line in open(filepath):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    # Check session quality
    end = next((e for e in entries if e.get("type") == "session_end"), None)
    if not end or end.get("fields_filled", 0) < min_fields:
        return []

    # Extract metadata from state_init
    init = next((e for e in entries if e.get("type") == "state_init"), None)
    if not init:
        return []

    session_id = Path(filepath).stem
    meta = {
        "session_id": session_id,
        "form_id": init.get("form_id", ""),
        "form_name": init.get("form_name", ""),
        "persona": init.get("persona", ""),
        "profile": init.get("profile", ""),
        "session_config": init.get("session_config", {}),
    }

    # Index entries by turn
    a_inputs = {}
    a_outputs = {}
    state_updates = {}

    for e in entries:
        t = e.get("turn")
        if t is None:
            continue
        etype = e.get("type")
        if etype == "llm_a_input":
            a_inputs.setdefault(t, []).append(e)
        elif etype == "llm_a_output":
            a_outputs.setdefault(t, []).append(e)
        elif etype == "state_update":
            state_updates.setdefault(t, []).append(e)

    # Build atomic turns
    atomic_turns = []
    form_state_before: dict = {}
    conversation_history: list[dict] = []

    for turn in sorted(a_outputs.keys()):
        outputs = a_outputs[turn]
        inputs = a_inputs.get(turn, [])

        for i, a_out in enumerate(outputs):
            # Match with corresponding input (usually 1:1, but button responses can add extra)
            a_in = inputs[i] if i < len(inputs) else (inputs[0] if inputs else None)
            user_message = a_in.get("user_message", "") if a_in else ""
            raw_text = a_out.get("raw_text", "")
            parsed_actions = a_out.get("parsed_actions", [])
            action_types = [a.get("type", "") for a in parsed_actions]

            # Check for ---actions--- delimiter
            has_delimiter = "---actions---" in raw_text

            # Extract text portion (before delimiter)
            if has_delimiter:
                text_portion = raw_text.split("---actions---")[0].strip()
            else:
                text_portion = raw_text.strip()

            # Count fields set in this turn's actions
            fields_set = []
            for action in parsed_actions:
                if action.get("type") == "set_fields":
                    for f in action.get("fields", []):
                        fid = f.get("field_id", "")
                        if fid:
                            fields_set.append(fid)

            atomic = {
                **meta,
                "turn": turn,
                "sub_turn": i,  # 0 for main response, 1+ for button follow-ups
                "user_message": user_message,
                "assistant_output": raw_text,
                "assistant_text": text_portion,
                "parsed_actions": parsed_actions,
                "action_types": action_types,
                "has_delimiter": has_delimiter,
                "has_actions": len(action_types) > 0,
                "fields_set": fields_set,
                "fields_set_count": len(fields_set),
                "form_state_before": dict(form_state_before),
                "form_state_field_count": len(form_state_before),
                "conversation_history": list(conversation_history),
                "conversation_history_length": len(conversation_history),
                "cost_usd": a_out.get("cost_usd", 0),
                "duration_ms": a_out.get("duration_ms", 0),
            }
            atomic_turns.append(atomic)

            # Update conversation history
            if user_message:
                conversation_history.append(
                    {"role": "user", "content": user_message}
                )
            if raw_text:
                conversation_history.append(
                    {"role": "assistant", "content": raw_text}
                )

        # Update form state from this turn's state_updates
        for su in state_updates.get(turn, []):
            fv = su.get("form_values")
            if fv is not None:
                form_state_before = dict(fv)

    return atomic_turns


def categorize_turn(turn: dict) -> str:
    """Categorize a turn by complexity for sampling."""
    action_types = turn["action_types"]
    user_msg = turn["user_message"].lower()
    t = turn["turn"]

    if t == 0:
        return "greeting"
    if not turn["has_actions"]:
        return "question_no_actions"
    if "[system] User selected option" in turn["user_message"]:
        return "choice_selection"
    if "[File:" in turn["user_message"]:
        return "file_handling"
    if turn["fields_set_count"] >= 3:
        return "multi_field"
    if turn["fields_set_count"] == 1:
        return "single_field"
    if "ask_choice" in action_types and "set_fields" not in action_types:
        return "ask_choice_only"
    if "show_button" in action_types:
        return "submit_flow"
    return "other"


def main():
    parser = argparse.ArgumentParser(description="Extract atomic training data from simulation logs")
    parser.add_argument("--sims-dir", default="sims", help="Directory containing JSONL session logs")
    parser.add_argument("--output", default="tuning/data/atomic.jsonl", help="Output JSONL file")
    parser.add_argument("--min-fields", type=int, default=5, help="Minimum fields_filled to include a session")
    parser.add_argument("--stats", action="store_true", help="Print stats only, don't write output")
    args = parser.parse_args()

    sims_dir = args.sims_dir
    all_turns = []
    session_count = 0
    skipped = 0

    for fname in sorted(os.listdir(sims_dir)):
        if not fname.endswith(".jsonl"):
            continue
        filepath = os.path.join(sims_dir, fname)
        turns = extract_session(filepath, min_fields=args.min_fields)
        if turns:
            all_turns.extend(turns)
            session_count += 1
        else:
            skipped += 1

    # Add category to each turn
    for turn in all_turns:
        turn["category"] = categorize_turn(turn)

    # Print stats
    print(f"Sessions: {session_count} used, {skipped} skipped")
    print(f"Total atomic turns: {len(all_turns)}")
    print()

    # Stats by category
    cats = {}
    for t in all_turns:
        c = t["category"]
        cats[c] = cats.get(c, 0) + 1
    print("By category:")
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {c:25s} {n:4d} ({100*n/len(all_turns):.1f}%)")
    print()

    # Stats by action type
    action_counts = {}
    for t in all_turns:
        for at in t["action_types"]:
            action_counts[at] = action_counts.get(at, 0) + 1
    no_action = sum(1 for t in all_turns if not t["has_actions"])
    print("Action type distribution:")
    print(f"  {'(no actions)':25s} {no_action:4d} ({100*no_action/len(all_turns):.1f}%)")
    for at, n in sorted(action_counts.items(), key=lambda x: -x[1]):
        print(f"  {at:25s} {n:4d}")
    print()

    # Stats by persona × profile
    combos = {}
    for t in all_turns:
        key = f"{t['persona']}-{t['profile']}"
        combos.setdefault(key, {"turns": 0, "actions": {}})
        combos[key]["turns"] += 1
        for at in t["action_types"]:
            combos[key]["actions"][at] = combos[key]["actions"].get(at, 0) + 1
    print("By persona × profile:")
    for key in sorted(combos.keys()):
        c = combos[key]
        acts = ", ".join(f"{k}={v}" for k, v in sorted(c["actions"].items(), key=lambda x: -x[1])[:4])
        print(f"  {key:30s} {c['turns']:3d} turns | {acts}")
    print()

    # Stats by delimiter/format compliance
    with_delim = sum(1 for t in all_turns if t["has_delimiter"])
    print(f"Format compliance: {with_delim}/{len(all_turns)} turns have ---actions--- delimiter ({100*with_delim/len(all_turns):.1f}%)")

    if args.stats:
        return

    # Write output
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        for turn in all_turns:
            f.write(json.dumps(turn) + "\n")
    print(f"\nWrote {len(all_turns)} turns to {args.output}")


if __name__ == "__main__":
    main()
