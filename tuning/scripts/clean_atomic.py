#!/usr/bin/env python3
"""
Clean atomic training data to mitigate upstream web-app + simulator bugs.

Bugs (documented in docs/doc-14-training-data-issues.md):
  1. Web app never emits `[system] User clicked: Save Draft/Submit`
  2. Simulator decomposes one user action (message + click_button) into two
     sequential LLM A calls, synthesizing a phantom `[system] User clicked`
     turn between them.

This script applies text-level surgery to the extracted atomic.jsonl so the
current training round isn't poisoned by the combined effect of these bugs.
Upstream fixes are deferred.

Operations (in order):
  - Drop sub_turn > 0 rows (Issue C, 25 rows): the phantom click follow-up turns.
  - Drop sub_turn = 0 rows whose user_message IS a phantom click (23 rows):
    edge cases where the simulator produced a phantom at turn boundary.
  - Drop sub_turn = 0 rows with empty assistant_output that are NOT save/submit
    related (2 rows): hazardous empty outputs unrelated to the button bug.
  - Rewrite Issue A (7 rows): assistant_output that leaked a `[system] User
    clicked` prefix. Replace with canned "press the button yourself" template.
  - Rewrite Issue B (15 rows): empty assistant_output where user verbally asked
    for save. Same canned template.
  - Clean conversation_history on ALL surviving rows (Issue D): remove phantom
    click user-entries + their paired assistant entries; strip [system] User
    clicked prefix from any assistant entry.

Usage:
    python tuning/scripts/clean_atomic.py              # in-place with archive
    python tuning/scripts/clean_atomic.py --dry-run    # report only
"""

import json
import shutil
import argparse
import re
from pathlib import Path


# ── Canned replacement templates ──
# Emphasize LLM A CANNOT save/submit directly — user must click the button.

SAVE_DRAFT_TEMPLATE_TEXT = (
    "I can't save the draft for you directly — you'll need to click the "
    "**Save Draft** button in the panel below to save it yourself. Go ahead "
    "when you're ready, and I'll confirm once it goes through."
)

SAVE_DRAFT_TEMPLATE_OUTPUT = (
    SAVE_DRAFT_TEMPLATE_TEXT
    + "\n\n---actions---\n```json\n"
    + '[{"type": "show_button", "button": "save_draft"}]'
    + "\n```"
)

SAVE_DRAFT_PARSED_ACTIONS = [{"type": "show_button", "button": "save_draft"}]

SUBMIT_TEMPLATE_TEXT = (
    "I can't submit the application for you — you'll need to click the "
    "**Submit Application** button yourself to confirm. Once you press it, "
    "I'll get the confirmation back."
)

SUBMIT_TEMPLATE_OUTPUT = (
    SUBMIT_TEMPLATE_TEXT
    + "\n\n---actions---\n```json\n"
    + '[{"type": "show_button", "button": "submit"}]'
    + "\n```"
)

SUBMIT_PARSED_ACTIONS = [{"type": "show_button", "button": "submit"}]


PHANTOM_CLICK_RE = re.compile(r"^\s*\[system\] User clicked: ")


def classify_button(user_msg: str, assistant_output: str) -> str | None:
    """Decide save_draft vs submit from the row's text content."""
    # Leaked prefix is the most reliable signal
    if assistant_output.lstrip().startswith("[system] User clicked: Submit"):
        return "submit"
    if assistant_output.lstrip().startswith("[system] User clicked: Save Draft"):
        return "save_draft"
    # Fall back to user_message
    um = user_msg.lower()
    if "submit" in um:
        return "submit"
    if "save" in um or "draft" in um:
        return "save_draft"
    return None


def rewrite_row(row: dict, button: str) -> dict:
    """Replace the assistant output with a canned 'press the button' response."""
    if button == "submit":
        text = SUBMIT_TEMPLATE_TEXT
        output = SUBMIT_TEMPLATE_OUTPUT
        parsed = list(SUBMIT_PARSED_ACTIONS)
    else:
        text = SAVE_DRAFT_TEMPLATE_TEXT
        output = SAVE_DRAFT_TEMPLATE_OUTPUT
        parsed = list(SAVE_DRAFT_PARSED_ACTIONS)

    row["assistant_output"] = output
    row["assistant_text"] = text
    row["parsed_actions"] = parsed
    row["action_types"] = [a["type"] for a in parsed]
    row["has_delimiter"] = True
    row["has_actions"] = True
    row["fields_set"] = []
    row["fields_set_count"] = 0
    return row


def clean_history(history: list[dict]) -> list[dict]:
    """Strip phantom `[system] User clicked` artifacts from conversation_history.

    Rules:
      1. Drop user entries starting with `[system] User clicked: `.
      2. If the dropped user entry is followed by an assistant entry whose
         content is empty or starts with `[system]`, drop that too (paired
         phantom follow-up response).
      3. For any assistant entry whose content still has a leading
         `[system] User clicked: X\n\n...` prefix (Issue A residue),
         strip everything up to the first blank-line break.
    """
    cleaned: list[dict] = []
    i = 0
    n = len(history)
    while i < n:
        msg = history[i]
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "user" and PHANTOM_CLICK_RE.match(content):
            # Skip this phantom user entry
            i += 1
            # Also skip a paired assistant entry if it looks phantom
            if i < n and history[i].get("role") == "assistant":
                ac = history[i].get("content", "")
                if ac.strip() == "" or ac.lstrip().startswith("[system]"):
                    i += 1
            continue

        if role == "assistant" and PHANTOM_CLICK_RE.match(content):
            # Strip leaked [system] User clicked prefix — keep what follows
            # the first blank-line break AFTER the prefix line.
            stripped = content.lstrip()  # drop any leading \n\n
            parts = stripped.split("\n\n", 1)
            if len(parts) == 2:
                new_content = parts[1].lstrip()
                if new_content:
                    cleaned.append({"role": "assistant", "content": new_content})
            # else: whole message is just the leaked prefix — drop it
            i += 1
            continue

        cleaned.append(msg)
        i += 1

    return cleaned


def _apply_issue_e_backfill(
    rows: list[dict],
    min_jump_size: int = 10,
) -> tuple[list[dict], int, int]:
    """Back-fill sparse-state review rows using the mid-session 'jump' snapshot.

    Bug 3 (doc-14): returning-user sim sessions fail to pre-load the saved
    draft fields into the form state at turn 0. The data materializes mid-
    session (typically turn 4-6). For any turn before that jump whose AI
    emits a review/preview but whose form_state_before is sparse (< 3 filled
    fields), we copy the jump-point's form_state_before into the row so the
    synthetic review target is meaningful.

    Rows where the session has no usable later state (truncated session, or
    profile-load never happened) are dropped.

    Returns (new_rows, backfilled_count, dropped_count).
    """
    from collections import defaultdict

    by_session: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_session[row.get("session_id", "")].append(row)

    # Sort each session's turns in order
    for sid in by_session:
        by_session[sid].sort(key=lambda r: (r["turn"], r.get("sub_turn", 0)))

    def is_sparse_review(r: dict) -> bool:
        acts = set(r.get("action_types", []))
        wants_review = "show_preview" in acts or "show_fields" in acts
        return wants_review and len(r.get("form_state_before", {})) < 3

    backfilled = 0
    to_drop: set[int] = set()  # object ids of rows to drop

    for sid, session_rows in by_session.items():
        # Find the first jump-point: earliest turn with >= min_jump_size filled fields
        jump_row = None
        for r in session_rows:
            if len(r.get("form_state_before", {})) >= min_jump_size:
                jump_row = r
                break

        for r in session_rows:
            if not is_sparse_review(r):
                continue

            if jump_row is None:
                # No baseline anywhere in session — drop this row
                to_drop.add(id(r))
                continue

            # Only back-fill if sparse row is BEFORE the jump
            r_key = (r["turn"], r.get("sub_turn", 0))
            j_key = (jump_row["turn"], jump_row.get("sub_turn", 0))
            if r_key < j_key:
                r["form_state_before"] = dict(jump_row["form_state_before"])
                r["form_state_field_count"] = len(r["form_state_before"])
                backfilled += 1
            # If sparse row is AT or AFTER the jump, leave it alone (shouldn't
            # happen in practice given sparse = < 3 fields and jump = >= 10).

    new_rows = [r for r in rows if id(r) not in to_drop]
    return new_rows, backfilled, len(to_drop)


def recategorize(turn: dict) -> str:
    """Mirror extract.py's categorize_turn() on possibly-rewritten rows."""
    action_types = turn["action_types"]
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="tuning/data/atomic.jsonl",
        help="Input atomic jsonl (extracted from sims)",
    )
    parser.add_argument(
        "--archive",
        default="tuning/data/atomic_raw.jsonl",
        help="Where to archive the original file before overwriting",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print stats without writing anything",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    archive_path = Path(args.archive)

    rows = [json.loads(l) for l in in_path.open() if l.strip()]
    total = len(rows)

    # ── Classify ──
    kept: list[dict] = []
    dropped_c = 0          # sub_turn > 0
    dropped_b_phantom = 0  # sub_turn = 0 but user is phantom click
    dropped_b_unknown = 0  # sub_turn = 0, empty output, unclassifiable
    rewrote_a = 0          # leaked prefix rewrite
    rewrote_b = 0          # empty-output rewrite

    for row in rows:
        # Issue C
        if row["sub_turn"] > 0:
            dropped_c += 1
            continue

        ao = row["assistant_output"]
        um = row["user_message"]

        # Drop ALL rows where user_message is a phantom click event. Covers
        # two cases: (a) sub_turn=0 rows created when simulator produced the
        # phantom at turn boundary, with empty output; (b) same setup but
        # with a non-empty assistant output that either hallucinates a save
        # success, waits for confirmation, or leaks a different [system]
        # prefix. All of these teach the model to respond to an event the
        # web app never emits in production.
        if um.startswith("[system] User clicked: "):
            dropped_b_phantom += 1
            continue

        # Issue A: leaked prefix
        if ao.lstrip().startswith("[system] User clicked:"):
            btn = classify_button(um, ao)
            if btn is None:
                btn = "save_draft"  # fallback
            rewrite_row(row, btn)
            rewrote_a += 1
        # Issue B: empty output
        elif ao.strip() == "":
            btn = classify_button(um, ao)
            if btn is None:
                # Empty output on a non-save/submit turn — hazardous, drop
                dropped_b_unknown += 1
                continue
            rewrite_row(row, btn)
            rewrote_b += 1

        # Clean conversation_history on all surviving rows (Issue D)
        new_history = clean_history(row["conversation_history"])
        row["conversation_history"] = new_history
        row["conversation_history_length"] = len(new_history)

        # Recategorize (categories may have shifted after rewrite)
        row["category"] = recategorize(row)

        kept.append(row)

    # ── Issue E: back-fill sparse-state review rows from mid-session jump ──
    # Bug 3 in doc-14: returning-user sessions don't pre-load draft fields at
    # turn 0. The data "suddenly appears" mid-session (around turn 4-6).
    # For review turns that happen BEFORE that jump, copy the jump-point
    # snapshot into them so the review actually has something to summarize.
    # Drop rows where no usable later state exists in the session.
    kept, backfilled_e, dropped_e = _apply_issue_e_backfill(kept)

    # ── Stats ──
    print(f"Input:  {in_path}  ({total} rows)")
    print()
    print("Classification:")
    print(f"  dropped — Issue C (sub_turn > 0):                 {dropped_c:>4d}")
    print(f"  dropped — sub_turn=0 phantom user_message:        {dropped_b_phantom:>4d}")
    print(f"  dropped — sub_turn=0 empty on non-save turn:      {dropped_b_unknown:>4d}")
    print(f"  rewrote — Issue A (leaked prefix):                {rewrote_a:>4d}")
    print(f"  rewrote — Issue B (empty on verbal save request): {rewrote_b:>4d}")
    print(f"  kept as-is:                                       {total - dropped_c - dropped_b_phantom - dropped_b_unknown - rewrote_a - rewrote_b:>4d}")
    print()
    print(f"  backfilled — Issue E (sparse review, session jump): {backfilled_e:>4d}")
    print(f"  dropped    — Issue E (no usable later state):       {dropped_e:>4d}")
    print(f"  SURVIVORS:                                          {len(kept):>4d}")
    print()

    # Count conversation_history changes
    histories_touched = 0
    for row in kept:
        # We don't track per-row whether history changed; just report total
        pass
    # Simple diagnostic: any phantom-click substring left?
    leftover_phantom = 0
    for row in kept:
        for m in row["conversation_history"]:
            if PHANTOM_CLICK_RE.match(m.get("content", "")):
                leftover_phantom += 1
                break
    print(f"Conversation-history phantom residue after cleanup: {leftover_phantom} rows")
    print()

    # Recheck the canonical hazards are gone
    still_leak = sum(1 for r in kept if r["assistant_output"].lstrip().startswith("[system] User clicked:"))
    still_empty = sum(1 for r in kept if r["assistant_output"].strip() == "")
    still_subturn = sum(1 for r in kept if r["sub_turn"] > 0)
    print("Post-cleanup hazards (should all be 0):")
    print(f"  assistant_output leak prefix: {still_leak}")
    print(f"  empty assistant_output:       {still_empty}")
    print(f"  sub_turn > 0:                 {still_subturn}")
    print()

    if args.dry_run:
        print("[dry-run] no files written.")
        return

    # Archive original
    if not archive_path.exists():
        shutil.copy2(in_path, archive_path)
        print(f"Archived original → {archive_path}")
    else:
        print(f"Archive already exists at {archive_path} — leaving untouched.")

    # Write cleaned
    with in_path.open("w") as f:
        for row in kept:
            f.write(json.dumps(row) + "\n")
    print(f"Wrote {len(kept)} cleaned rows → {in_path}")


if __name__ == "__main__":
    main()
