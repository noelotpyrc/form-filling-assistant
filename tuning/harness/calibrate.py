"""Calibrate a new anchor fixture for a model.

When you train a new model (SFT v3, an RL checkpoint, a different base, etc.)
and want to use it in any experiment, run this script ONCE to capture the
model's output on the canonical anchor input. The output gets saved as a new
fixture file that future experiments use to verify the harness reproduces
that model's behavior.

Why per-model anchors: the anchor's job is to catch HARNESS divergence
(wrong LM config, wrong context builder, server name-routing bugs).
Different models legitimately produce different outputs; that's not harness
divergence. Each model needs its own anchor calibrated against the harness
when it's first wired up.

Workflow:
  1. Start mlx_vlm server pointing at the new model:
       mlx_vlm server --model /path/to/new_model --port 8101

  2. Calibrate (this script):
       python -m tuning.harness.calibrate \\
           --model /path/to/new_model --port 8101 \\
           --label sft_v3 \\
           --input p1_ex3

  3. The script writes:
       tuning/harness/fixtures/anchor_p1_ex3_sft_v3.json

  4. Future experiments pass --anchor pointing at that file.

The --input flag picks an anchor "template" (input scenario). Currently we
have one canonical input (p1_ex3 from the probe log); add more by dropping
JSON files into tuning/harness/fixtures/anchor_inputs/ following the same
shape (input + _anchor_id, no `expected` block since calibration captures
that).

Required: --label distinguishes models (e.g., "sft_v2", "sft_v3", "grpo_900").
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent.parent
FIXTURES_DIR = THIS_DIR / "fixtures"

# Currently we ship one canonical anchor input (P1-ex3). To add a new one,
# create a fixture file containing just the `input` block and an `_anchor_id`.
ANCHOR_INPUTS = {
    "p1_ex3": {
        "_anchor_id": "P1-ex3",
        "input": {
            "form_state": {"email": "newapp@test.com"},
            "conversation_history": [
                {
                    "role": "user",
                    "content": (
                        "newapp@test.com is starting a brand-new Northfield University Graduate "
                        "Application. Nothing has been filled in yet, and there's no information "
                        "from any past applications to reuse. Welcome them warmly and ask which "
                        "graduate program they'd like to apply to, presenting the available "
                        "programs as choices they can pick from."
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        "Welcome aboard! 🎓 Excited to help you get started. Which graduate "
                        "program would you like to apply to?"
                    ),
                },
            ],
            "user_message": "hey thanks! how's your day going so far",
        },
    },
    "p2_ex5": {
        "_anchor_id": "P2-ex5",
        "input": {
            "form_state": {"email": "drew@test.com", "program": "cs"},
            "conversation_history": [
                {"role": "assistant",
                 "content": "Welcome, Drew! Which graduate program would you like to apply to?"},
                {"role": "user",
                 "content": "[system] User selected option: \"Computer Science (MS)\""},
                {"role": "assistant",
                 "content": "Great choice — Computer Science (MS)! 🖥️ When would you like to start?"},
            ],
            "user_message": "actually hold on, can we switch to the MBA instead? i changed my mind",
        },
    },
    "p3_ex3": {
        "_anchor_id": "P3-ex3",
        "input": {
            "form_state": {
                "email": "newapp@test.com", "program": "cs", "start_term": "fall_2026",
                "enrollment_type": "full_time", "prior_application": False,
                "full_name": "Jordan Rivera",
            },
            "conversation_history": [
                {"role": "user", "content": "[system] User selected option: \"No\""},
                {"role": "assistant",
                 "content": "Program section is all set! ✅ Now let's cover your personal info. Could you share your full legal name?"},
                {"role": "user", "content": "my name is Jordan Rivera"},
                {"role": "assistant", "content": "Nice to meet you, Jordan! What's your date of birth?"},
            ],
            "user_message": "what date format do you want? mm/dd or 4 jan 1995 style?",
        },
    },
    "p12_ex2": {
        "_anchor_id": "P12-ex2",
        "input": {
            "form_state": {
                "email": "una@test.com", "program": "cs", "start_term": "fall_2026",
                "enrollment_type": "full_time", "prior_application": False,
                "full_name": "Una Lee", "dob": "1989-04-12",
                "country_citizenship": "US", "country_residence": "US",
                "phone": "+1-415-555-2200",
            },
            "conversation_history": [
                {"role": "user", "content": "Una Lee, born April 12 1989"},
                {"role": "assistant", "content": "Saved. Citizenship and residence?"},
                {"role": "user", "content": "US for both"},
                {"role": "assistant", "content": "Saved. What's your phone?"},
                {"role": "user", "content": "+1-415-555-2200"},
                {"role": "assistant", "content": "Got it. What's your mailing address?"},
            ],
            "user_message": "you already have my address, i gave it to you earlier",
        },
    },
}


def _pred_to_expected(pred) -> dict:
    """Capture model output in the anchor's `expected` shape."""
    flag_names = ["has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit"]
    response_text = getattr(pred, "response_text", "") or ""
    return {
        "flags": {f: bool(getattr(pred, f, False)) for f in flag_names},
        "field_ids": list(getattr(pred, "field_ids", []) or []),
        "field_values": list(getattr(pred, "field_values", []) or []),
        "question": getattr(pred, "question", "") or "",
        "options": list(getattr(pred, "options", []) or []),
        "summary_title": getattr(pred, "summary_title", "") or "",
        "summary_content": getattr(pred, "summary_content", "") or "",
        # Match preflight's response_text comparison: store the first 30 chars
        # as the prefix the future preflight will assert. The model can vary
        # its tail across runs, but the opening phrase tends to be stable at
        # temperature=0.
        "response_text_starts_with": response_text[:30],
    }


def main():
    ap = argparse.ArgumentParser(description="Capture an anchor fixture for a model.")
    ap.add_argument("--model", required=True,
                    help="Model path/name as registered with the running mlx_vlm server")
    ap.add_argument("--port", type=int, default=8100, help="MLX server port")
    ap.add_argument("--label", required=True,
                    help="Short label for this model (e.g., sft_v3, grpo_900). "
                         "Becomes the suffix of the fixture filename.")
    ap.add_argument("--input", default="p1_ex3", choices=list(ANCHOR_INPUTS.keys()),
                    help="Which canonical anchor input to use")
    ap.add_argument("--out", default=None,
                    help="Output fixture path. Default: "
                         "tuning/harness/fixtures/anchor_<input>_<label>.json")
    ap.add_argument("--overwrite", action="store_true",
                    help="Overwrite an existing fixture file. By default, calibrate "
                         "refuses to overwrite — existing fixtures are committed history.")
    args = ap.parse_args()

    sys.path.insert(0, str(PROJECT_ROOT))
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    from tuning.harness.pipeline import build_context, configure_lm, get_agent

    template = ANCHOR_INPUTS[args.input]
    anchor_id = template["_anchor_id"]
    inp = template["input"]

    out_path = Path(args.out) if args.out else (
        FIXTURES_DIR / f"anchor_{args.input}_{args.label}.json"
    )
    if out_path.exists() and not args.overwrite:
        sys.exit(
            f"Refusing to overwrite existing fixture {out_path}.\n"
            f"If this is intentional, pass --overwrite. Otherwise pick a different "
            f"--label."
        )

    print(f"Calibrating: model={args.model}  port={args.port}  input={args.input}")
    configure_lm(api_base=f"http://localhost:{args.port}/v1", model=args.model)
    schema_path = PROJECT_ROOT / "packages" / "web-app" / "public" / "forms" / "masters-northfield.json"
    schema = json.loads(schema_path.read_text())

    ctx = build_context(schema, inp["form_state"], inp["conversation_history"])
    agent = get_agent()
    pred = agent(context=ctx, user_message=inp["user_message"])
    expected = _pred_to_expected(pred)

    fixture = {
        "_doc": (
            f"Anchor for experiment-hygiene smoke tests, calibrated for model "
            f"label '{args.label}'. Captured from a live run of the harness "
            f"(configure_lm + FormAssistant + build_context) at calibration "
            f"time. Future experiments must reproduce this output to be trusted. "
            f"See CLAUDE.md > Experiment hygiene."
        ),
        "_anchor_id": anchor_id,
        "_model": args.model,
        "_label": args.label,
        "_calibrated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": inp,
        "expected": expected,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n")

    print(f"\nWrote {out_path}")
    print("Captured output:")
    print(f"  flags:    " + " ".join(f"{f[:4]}={int(v)}" for f, v in expected["flags"].items()))
    if expected["field_ids"]:
        print(f"  fields:   {list(zip(expected['field_ids'], expected['field_values']))}")
    if expected["question"]:
        print(f"  question: {expected['question']}")
        print(f"  options:  {expected['options']}")
    if expected["summary_title"] or expected["summary_content"]:
        print(f"  review:   '{expected['summary_title']}' — {expected['summary_content'][:80]}")
    print(f"  response: {expected['response_text_starts_with']!r}...")
    print(f"\nFuture experiments must pass --anchor {out_path} (or symlink it as "
          f"the project's default).")


if __name__ == "__main__":
    main()
