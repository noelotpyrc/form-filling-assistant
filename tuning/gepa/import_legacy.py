"""Convert tuning/data/test-cases.jsonl (300 legacy cases) → eval_cases.jsonl.

Maps the old action-block schema into the (input + correct_answer) shape:
  set_fields   → has_new_data + field_ids/field_values
  ask_choice   → needs_choice + question/options
  show_preview → wants_review + summary_title/summary_content
  show_fields  → wants_review (section name as content)
  show_button  → wants_save (save_draft) / wants_submit (submit)
  no actions   → all flags false (text-only response)

Legacy cases get:
  test_id = "legacy-{old_test_id}"
  source  = "legacy-{category}"           (no per-seed rubric; baseline only)
  cannot_targets = []

Run: python3 tuning/gepa/import_legacy.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LEGACY_PATH = Path(__file__).parent.parent / "data" / "test-cases.jsonl"
OUT_PATH = Path(__file__).parent / "eval_cases.jsonl"

ACTIONS_PATTERN = re.compile(
    r"\n*---actions---\n```(?:json)?\n(.*?)\n```\n*", re.DOTALL
)


def parse_actions_and_prose(expected_output: str) -> tuple[str, list[dict]]:
    """Strip the ---actions--- block; return (prose, actions)."""
    m = ACTIONS_PATTERN.search(expected_output)
    if not m:
        return expected_output.strip(), []
    try:
        actions = json.loads(m.group(1))
        if not isinstance(actions, list):
            actions = [actions]
    except json.JSONDecodeError:
        actions = []
    prose = (expected_output[: m.start()] + expected_output[m.end():]).strip()
    return prose, actions


def actions_to_answer(actions: list[dict]) -> dict:
    flags = {f: False for f in
             ["has_new_data", "needs_choice", "wants_review",
              "wants_save", "wants_submit"]}
    field_ids: list[str] = []
    field_values: list[str] = []
    question = ""
    options: list[str] = []
    summary_title = ""
    summary_content = ""

    for a in actions:
        t = a.get("type")
        if t == "set_fields":
            flags["has_new_data"] = True
            for f in a.get("fields", []):
                field_ids.append(f["field_id"])
                v = f.get("value", "")
                field_values.append(str(v))
        elif t == "ask_choice":
            flags["needs_choice"] = True
            if a.get("question"):
                question = a["question"]
            for o in a.get("options", []):
                if isinstance(o, dict):
                    options.append(o.get("label") or o.get("value", ""))
                else:
                    options.append(str(o))
        elif t == "show_preview":
            flags["wants_review"] = True
            if a.get("title"):
                summary_title = a["title"]
            sections = a.get("sections", [])
            parts: list[str] = []
            for sec in sections:
                sec_title = sec.get("title", "")
                items = sec.get("fields") or sec.get("items") or []
                items_str = "; ".join(
                    f"{i.get('label', '')}: {i.get('value', '')}"
                    if isinstance(i, dict) else str(i)
                    for i in items
                )
                parts.append(f"{sec_title}: {items_str}" if sec_title else items_str)
            if parts:
                summary_content = " | ".join(parts)
        elif t == "show_fields":
            flags["wants_review"] = True
            sec = a.get("section", "")
            fields_list = a.get("fields", [])
            if sec and not summary_title:
                summary_title = sec
            if fields_list:
                if not summary_title:
                    summary_title = "Fields"
                summary_content = " | ".join(
                    f"{f.get('field_id', '')}"
                    + (f"[{f['entry_index']}]" if "entry_index" in f else "")
                    for f in fields_list
                ) or summary_content
            elif sec and not summary_content:
                summary_content = f"Section: {sec}"
        elif t == "show_button":
            b = a.get("button", "")
            if b == "save_draft":
                flags["wants_save"] = True
            elif b == "submit":
                flags["wants_submit"] = True

    return {
        "flags": flags,
        "response_text": "",  # filled by caller
        "field_ids": field_ids,
        "field_values": field_values,
        "question": question,
        "options": options,
        "summary_title": summary_title,
        "summary_content": summary_content,
    }


def convert_case(legacy: dict) -> dict:
    prose, actions = parse_actions_and_prose(legacy["expected_output"])
    answer = actions_to_answer(actions)
    answer["response_text"] = prose
    return {
        "test_id": f"legacy-{legacy['test_id']}",
        "source": f"legacy-{legacy['category']}",
        "cannot_targets": [],
        "input": {
            "form_state": legacy.get("form_state_before", {}),
            "conversation_history": legacy.get("conversation_history", []),
            "user_message": legacy.get("user_message", ""),
        },
        "correct_answer": answer,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Convert and validate; don't append to eval_cases.jsonl")
    args = ap.parse_args()

    legacy = [json.loads(l) for l in open(LEGACY_PATH)]
    converted = [convert_case(c) for c in legacy]
    print(f"Converted {len(converted)} legacy cases")

    # Distribution checks
    from collections import Counter
    flag_combos: Counter = Counter()
    for c in converted:
        flags = c["correct_answer"]["flags"]
        combo = tuple(k for k, v in flags.items() if v) or ("(text-only)",)
        flag_combos[combo] += 1
    print("\nFlag combinations after conversion:")
    for combo, n in flag_combos.most_common():
        print(f"  {', '.join(combo):50s} {n}")

    by_source: Counter = Counter(c["source"] for c in converted)
    print("\nBy source category:")
    for s, n in by_source.most_common():
        print(f"  {s:30s} {n}")

    if args.dry_run:
        print("\n--dry-run: not writing.")
        return

    with open(OUT_PATH, "a") as f:
        for c in converted:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"\nAppended to {OUT_PATH} (now {sum(1 for _ in open(OUT_PATH))} total lines)")


if __name__ == "__main__":
    main()
