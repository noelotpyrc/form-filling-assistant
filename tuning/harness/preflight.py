"""Preflight anchor check — enforces CLAUDE.md > Experiment hygiene.

Any entry point that launches a costly experimental run (>5 min wall, >$1
spend) must call `assert_anchor_match()` at startup. The function loads a
fixture (default: P1-ex3 probe baseline), runs the configured pipeline on
its input, and aborts the run if the prediction diverges from the recorded
expected output.

This catches the class of bug where the experimental harness silently
diverges from the production reference (different LM config, different
context builder, different model name routed to the same loaded weights,
different default truncation, etc.). Without this check, the experiment's
"improvement" numbers measure harness divergence instead of the actual
experimental change.

Usage:
    from tuning.harness.preflight import assert_anchor_match
    assert_anchor_match()  # exits non-zero on mismatch
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DEFAULT_ANCHOR = FIXTURES_DIR / "anchor_p1_ex3_sft_v2.json"
# All SFT v2 anchors — covers multiple failure-mode scenarios so preflight
# catches harness divergence that might happen to leave P1-ex3 intact.
DEFAULT_ANCHORS: list[Path] = [
    FIXTURES_DIR / "anchor_p1_ex3_sft_v2.json",
    FIXTURES_DIR / "anchor_p2_ex5_sft_v2.json",
    FIXTURES_DIR / "anchor_p3_ex3_sft_v2.json",
    FIXTURES_DIR / "anchor_p12_ex2_sft_v2.json",
]
SCHEMA_PATH = PROJECT_ROOT / "packages" / "web-app" / "public" / "forms" / "masters-northfield.json"

FLAG_NAMES = ["has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit"]


def _diff_lines(expected: dict, actual: dict) -> list[str]:
    """Return a list of human-readable mismatches (empty if all good)."""
    diffs: list[str] = []

    exp_flags = expected["flags"]
    for f in FLAG_NAMES:
        e = bool(exp_flags.get(f, False))
        a = bool(actual.get(f, False))
        if e != a:
            diffs.append(f"flag.{f}: expected {e}, got {a}")

    if expected["field_ids"] != actual.get("field_ids", []):
        diffs.append(f"field_ids: expected {expected['field_ids']}, got {actual.get('field_ids', [])}")
    if expected["field_values"] != actual.get("field_values", []):
        diffs.append(f"field_values: expected {expected['field_values']}, got {actual.get('field_values', [])}")

    if expected["question"] != actual.get("question", ""):
        diffs.append(f"question: expected {expected['question']!r}, got {actual.get('question', '')!r}")
    if expected["options"] != actual.get("options", []):
        diffs.append(f"options: expected {expected['options']}, got {actual.get('options', [])}")

    if expected["summary_title"] != actual.get("summary_title", ""):
        diffs.append(f"summary_title: expected {expected['summary_title']!r}, got {actual.get('summary_title', '')!r}")
    if expected["summary_content"] != actual.get("summary_content", ""):
        diffs.append(f"summary_content: expected {expected['summary_content']!r}, got {actual.get('summary_content', '')!r}")

    prefix = expected.get("response_text_starts_with")
    actual_rt = actual.get("response_text", "") or ""
    if prefix and not actual_rt.startswith(prefix):
        diffs.append(f"response_text: expected to start with {prefix!r}, got {actual_rt[:80]!r}")

    return diffs


def _pred_to_dict(pred: Any) -> dict:
    return {
        **{f: bool(getattr(pred, f, False)) for f in FLAG_NAMES},
        "response_text": getattr(pred, "response_text", "") or "",
        "field_ids": list(getattr(pred, "field_ids", []) or []),
        "field_values": list(getattr(pred, "field_values", []) or []),
        "question": getattr(pred, "question", "") or "",
        "options": list(getattr(pred, "options", []) or []),
        "summary_title": getattr(pred, "summary_title", "") or "",
        "summary_content": getattr(pred, "summary_content", "") or "",
    }


def assert_anchor_match(
    anchor_path: str | Path = DEFAULT_ANCHOR,
    *,
    schema_path: str | Path = SCHEMA_PATH,
    abort_on_fail: bool = True,
) -> bool:
    """Run the anchor's input through the configured pipeline and compare.

    Returns True if anchor matches; on mismatch prints the diff and exits
    non-zero (abort_on_fail=True) or returns False.

    Caller must have already configured DSPy via
    `tuning.harness.pipeline.configure_lm()`. This function does NOT
    reconfigure — it asserts that the *currently configured* pipeline
    reproduces the anchor.

    Anchors are model-specific. The fixture's `_model` field records which
    weights produced the expected output. If you've configured a different
    model, you need a different anchor — see tuning/harness/calibrate.py.
    """
    from tuning.harness.pipeline import build_context, get_agent

    anchor = json.loads(Path(anchor_path).read_text())
    schema = json.loads(Path(schema_path).read_text())

    inp = anchor["input"]
    expected = anchor["expected"]
    anchor_id = anchor.get("_anchor_id", Path(anchor_path).stem)
    model_label = anchor.get("_model", "(unspecified)")

    print(f"[preflight] anchor={anchor_id}  model={model_label}")
    print(f"[preflight] fixture={Path(anchor_path).name}")
    ctx = build_context(schema, inp["form_state"], inp["conversation_history"])
    agent = get_agent()
    pred = agent(context=ctx, user_message=inp["user_message"])
    actual = _pred_to_dict(pred)

    diffs = _diff_lines(expected, actual)
    if diffs:
        msg = (
            f"\n[preflight] ANCHOR MISMATCH on {anchor_id}: experimental harness "
            f"diverges from the recorded reference output.\n"
            "  This means an 'improvement' measured by this run will reflect harness\n"
            "  divergence, not the experimental change. See CLAUDE.md > Experiment\n"
            "  hygiene. Common causes: missing max_tokens / cache flag, wrong model\n"
            "  name, different context builder, mismatched truncation.\n"
            "\n  Diffs:\n"
        )
        for d in diffs:
            msg += f"    - {d}\n"
        if abort_on_fail:
            sys.exit(msg)
        print(msg)
        return False

    print(f"[preflight] OK — anchor matches.")
    return True


def assert_anchors_match(
    anchor_paths: list[str | Path] = DEFAULT_ANCHORS,
    *,
    schema_path: str | Path = SCHEMA_PATH,
    abort_on_fail: bool = True,
) -> bool:
    """Check every fixture in `anchor_paths`. Aborts on the first mismatch.

    Multiple anchors catch a wider class of harness divergence — e.g. a
    config drift that happens to leave one scenario intact but breaks
    others.
    """
    for p in anchor_paths:
        ok = assert_anchor_match(p, schema_path=schema_path,
                                 abort_on_fail=abort_on_fail)
        if not ok:
            return False
    return True
