#!/usr/bin/env python3
"""
Evaluate models against test cases via OpenAI-compatible API (MLX server).

For each test case:
1. Build messages (system prompt + conversation history + user message)
2. Send to model API
3. Score the output on format compliance, action match, field accuracy
4. Write per-turn results + aggregate stats

Usage:
    # Eval SmolLM2-360M (assumes MLX server on port 8081)
    python tuning/eval/run_eval.py --model smollm2-360m --port 8081

    # Eval Qwen2.5-0.5B (assumes MLX server on port 8082)
    python tuning/eval/run_eval.py --model qwen25-05b --port 8082

    # Custom settings
    python tuning/eval/run_eval.py --model smollm2-360m --port 8081 --max-tokens 1024 --single-turn

    # Stats only from existing results
    python tuning/eval/run_eval.py --stats-only tuning/eval/results/smollm2-360m-*.jsonl
"""

import json
import os
import sys
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime


# ── System prompt ──
# Load from the web-app's system-prompt.js? No — we use a pre-built static prompt.
# The eval measures model capability, not prompt quality, so we use the same prompt
# that the simulation used.

FORM_SCHEMA_PATH = "packages/web-app/public/forms/masters-northfield.json"


def load_system_prompt() -> str:
    """Build the static system prompt from the form schema."""
    # We load the JS module via a simplified Python port
    # Just read the form and build a minimal but complete prompt
    form = json.load(open(FORM_SCHEMA_PATH))

    parts = []
    parts.append(
        "You are a form-filling assistant that helps users complete forms through conversation. "
        "Users interact with you via a chat interface with a form panel on the right side.\n\n"
        "You guide users through the form section by section, collecting their information "
        "conversationally. You control what appears in the form panel through structured actions."
    )

    parts.append("""
## Output Format: Text + Actions

Every response you give has two parts:
1. **Text** — your conversational message to the user (always present)
2. **Actions** — structured commands that control the form panel (optional)

When you need to include actions, place them AFTER your text, separated by the delimiter `---actions---`, followed by a JSON array in a fenced code block:

```
Your conversational text here...

---actions---
```json
[
  { "type": "set_fields", "fields": [{ "field_id": "full_name", "value": "John Smith" }] }
]
```
```

If you have NO actions to emit, just write your text with no delimiter.

### Available Action Types

**set_fields** — Set form field values.
**show_fields** — Focus a section in the form panel.
**ask_choice** — Render clickable option buttons in the chat.
**show_preview** — Render a structured summary card.
**show_button** — Show save_draft or submit button.

### Multiple actions per response
You can emit multiple actions in one response as a JSON array.
""")

    parts.append(f"""
## Current Form: {form['name']}

### Form Schema
```json
{json.dumps(form['schema'], indent=2)}
```
""")

    parts.append("""
## Behavior Guidelines

- Be conversational — this is a chat, not a form.
- Auto-fill when possible — when you know field values, fill them in automatically.
- Group fields — for group fields (like degrees, jobs), collect one entry at a time.
""")

    return "\n".join(parts)


def call_model(
    port: int,
    model_name: str,
    messages: list[dict],
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> dict:
    """Call the MLX server's OpenAI-compatible API."""
    url = f"http://localhost:{port}/v1/chat/completions"
    payload = json.dumps({
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": str(e), "duration_ms": 0}
    except Exception as e:
        return {"error": str(e), "duration_ms": 0}

    duration_ms = int((time.time() - start) * 1000)
    result["duration_ms"] = duration_ms
    return result


def score_output(output: str, expected: dict) -> dict:
    """Score a model's output against expected values."""
    scores = {}

    # Level 1: Format compliance
    scores["has_text"] = len(output.strip()) > 10
    scores["has_delimiter"] = "---actions---" in output
    scores["valid_json"] = False
    scores["action_types_valid"] = False
    parsed_actions = []

    if scores["has_delimiter"]:
        actions_part = output.split("---actions---", 1)[1].strip()
        # Strip markdown fences
        import re
        json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)```", actions_part)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = actions_part.strip().lstrip("`").rstrip("`").strip()

        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                parsed_actions = parsed
                scores["valid_json"] = True
            elif isinstance(parsed, dict) and "type" in parsed:
                parsed_actions = [parsed]
                scores["valid_json"] = True
        except json.JSONDecodeError:
            pass

    valid_types = {"set_fields", "ask_choice", "show_fields", "show_preview", "show_button"}
    if parsed_actions:
        model_types = [a.get("type", "") for a in parsed_actions]
        scores["action_types_valid"] = all(t in valid_types for t in model_types)
    elif not scores["has_delimiter"]:
        # No actions expected and none produced — valid
        scores["action_types_valid"] = not expected.get("expected_has_actions", False)

    # Level 2: Action match
    expected_types = expected.get("expected_action_types", [])
    model_types = [a.get("type", "") for a in parsed_actions]
    scores["action_type_match"] = sorted(model_types) == sorted(expected_types)
    scores["expected_action_types"] = expected_types
    scores["model_action_types"] = model_types

    # Level 3: Field accuracy (for set_fields only)
    expected_fields = set(expected.get("expected_fields_set", []))
    model_fields = set()
    for a in parsed_actions:
        if a.get("type") == "set_fields":
            for f in a.get("fields", []):
                fid = f.get("field_id", "")
                if fid:
                    model_fields.add(fid)

    if expected_fields:
        intersection = expected_fields & model_fields
        scores["field_recall"] = len(intersection) / len(expected_fields) if expected_fields else 0
        scores["field_precision"] = len(intersection) / len(model_fields) if model_fields else 0
    else:
        scores["field_recall"] = None
        scores["field_precision"] = None

    scores["expected_fields"] = sorted(expected_fields)
    scores["model_fields"] = sorted(model_fields)

    # Composite score (0-1)
    format_score = (
        (0.25 if scores["has_text"] else 0)
        + (0.25 if scores["has_delimiter"] == expected.get("expected_has_delimiter", True) else 0)
        + (0.25 if scores["valid_json"] or not expected.get("expected_has_actions", False) else 0)
        + (0.25 if scores["action_types_valid"] else 0)
    )
    scores["format_score"] = format_score
    scores["parsed_actions"] = parsed_actions

    return scores


def run_eval(
    test_cases_path: str,
    port: int,
    model_name: str,
    model_label: str,
    max_tokens: int = 1024,
    single_turn: bool = False,
) -> list[dict]:
    """Run evaluation on all test cases."""
    system_prompt = load_system_prompt()

    cases = [json.loads(l) for l in open(test_cases_path) if l.strip()]
    results = []

    print(f"Evaluating {model_label} on {len(cases)} test cases...")
    print(f"  Server: localhost:{port}")
    print(f"  Model: {model_name}")
    print(f"  Max tokens: {max_tokens}")
    print(f"  Mode: {'single-turn' if single_turn else 'multi-turn'}")
    print()

    for i, case in enumerate(cases):
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        # Add form state context if available
        form_state = case.get("form_state_before", {})
        if form_state:
            state_msg = f"## Current Form State (filled fields)\n```json\n{json.dumps(form_state, indent=2)}\n```"
            messages[0]["content"] += "\n\n" + state_msg

        # Add conversation history (multi-turn)
        if not single_turn:
            for h in case.get("conversation_history", []):
                messages.append({"role": h["role"], "content": h["content"]})

        # Add current user message
        messages.append({"role": "user", "content": case["user_message"]})

        # Call model
        print(f"  [{i+1}/{len(cases)}] {case['category']:25s} turn={case['turn']}", end="", flush=True)
        response = call_model(port, model_name, messages, max_tokens=max_tokens)

        if "error" in response:
            print(f" ERROR: {response['error']}")
            result = {
                **case,
                "model_output": "",
                "error": response["error"],
                "scores": {"format_score": 0},
                "duration_ms": 0,
            }
            results.append(result)
            continue

        # Extract output
        choice = response.get("choices", [{}])[0]
        model_output = choice.get("message", {}).get("content", "")
        duration_ms = response.get("duration_ms", 0)
        usage = response.get("usage", {})

        # Score
        scores = score_output(model_output, case)

        status = "✓" if scores["format_score"] >= 0.75 else ("~" if scores["format_score"] >= 0.5 else "✗")
        print(f" {status} format={scores['format_score']:.2f} actions={scores['action_type_match']} ({duration_ms}ms)")

        result = {
            **case,
            "model_output": model_output,
            "model_output_length": len(model_output),
            "scores": scores,
            "duration_ms": duration_ms,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }
        results.append(result)

    return results


def print_stats(results: list[dict], model_label: str):
    """Print aggregate statistics."""
    n = len(results)
    if n == 0:
        print("No results to analyze.")
        return

    errors = sum(1 for r in results if r.get("error"))
    valid = [r for r in results if not r.get("error")]

    print(f"\n{'='*60}")
    print(f"  {model_label} — {n} test cases ({errors} errors)")
    print(f"{'='*60}")

    if not valid:
        print("  All cases errored.")
        return

    # Format compliance
    has_text = sum(1 for r in valid if r["scores"].get("has_text"))
    has_delim = sum(1 for r in valid if r["scores"].get("has_delimiter"))
    valid_json_count = sum(1 for r in valid if r["scores"].get("valid_json"))
    types_valid = sum(1 for r in valid if r["scores"].get("action_types_valid"))
    avg_format = sum(r["scores"].get("format_score", 0) for r in valid) / len(valid)

    print(f"\n  Format Compliance:")
    print(f"    Has text:          {has_text:3d}/{len(valid)} ({100*has_text/len(valid):.0f}%)")
    print(f"    Has delimiter:     {has_delim:3d}/{len(valid)} ({100*has_delim/len(valid):.0f}%)")
    print(f"    Valid JSON:        {valid_json_count:3d}/{len(valid)} ({100*valid_json_count/len(valid):.0f}%)")
    print(f"    Valid action types:{types_valid:3d}/{len(valid)} ({100*types_valid/len(valid):.0f}%)")
    print(f"    Avg format score:  {avg_format:.2f}")

    # Action match
    action_match = sum(1 for r in valid if r["scores"].get("action_type_match"))
    print(f"\n  Action Match:")
    print(f"    Type match:        {action_match:3d}/{len(valid)} ({100*action_match/len(valid):.0f}%)")

    # Field accuracy (only for turns with expected fields)
    field_cases = [r for r in valid if r["scores"].get("field_recall") is not None]
    if field_cases:
        avg_recall = sum(r["scores"]["field_recall"] for r in field_cases) / len(field_cases)
        avg_precision = sum(r["scores"]["field_precision"] for r in field_cases) / len(field_cases)
        print(f"\n  Field Accuracy ({len(field_cases)} cases with set_fields):")
        print(f"    Avg recall:        {avg_recall:.2f}")
        print(f"    Avg precision:     {avg_precision:.2f}")

    # By category
    from collections import defaultdict
    by_cat = defaultdict(list)
    for r in valid:
        by_cat[r["category"]].append(r)

    print(f"\n  By Category:")
    for cat in sorted(by_cat.keys()):
        cat_results = by_cat[cat]
        cat_format = sum(r["scores"].get("format_score", 0) for r in cat_results) / len(cat_results)
        cat_match = sum(1 for r in cat_results if r["scores"].get("action_type_match"))
        print(f"    {cat:25s} n={len(cat_results):2d} format={cat_format:.2f} action_match={cat_match}/{len(cat_results)}")

    # Timing
    durations = [r["duration_ms"] for r in valid if r["duration_ms"] > 0]
    if durations:
        avg_ms = sum(durations) / len(durations)
        print(f"\n  Timing:")
        print(f"    Avg per turn:      {avg_ms:.0f}ms")
        print(f"    Total:             {sum(durations)/1000:.1f}s")


def main():
    parser = argparse.ArgumentParser(description="Evaluate models against test cases")
    parser.add_argument("--model", required=True, help="Model label (e.g. smollm2-360m, qwen25-05b)")
    parser.add_argument("--port", type=int, default=8081, help="MLX server port")
    parser.add_argument("--model-name", help="HuggingFace model name for API (auto-detected if omitted)")
    parser.add_argument("--test-cases", default="tuning/data/test-cases.jsonl", help="Test cases file")
    parser.add_argument("--output-dir", default="tuning/eval/results", help="Output directory")
    parser.add_argument("--max-tokens", type=int, default=1024, help="Max generation tokens")
    parser.add_argument("--single-turn", action="store_true", help="Exclude conversation history")
    parser.add_argument("--stats-only", nargs="?", const=True, help="Print stats from existing results file")
    args = parser.parse_args()

    # Model name mapping
    MODEL_NAMES = {
        "smollm2-360m": "mlx-community/SmolLM2-360M-Instruct",
        "qwen25-05b": "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
    }
    model_name = args.model_name or MODEL_NAMES.get(args.model, args.model)

    # Stats-only mode
    if args.stats_only:
        if args.stats_only is True:
            # Find latest results file for this model
            results_dir = args.output_dir
            files = sorted(Path(results_dir).glob(f"{args.model}-*.jsonl"))
            if not files:
                print(f"No results found for {args.model} in {results_dir}")
                return
            results_file = str(files[-1])
        else:
            results_file = args.stats_only
        results = [json.loads(l) for l in open(results_file) if l.strip()]
        print_stats(results, args.model)
        return

    # Run eval
    results = run_eval(
        args.test_cases,
        args.port,
        model_name,
        args.model,
        max_tokens=args.max_tokens,
        single_turn=args.single_turn,
    )

    # Save results
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    output_path = f"{args.output_dir}/{args.model}-{ts}.jsonl"
    with open(output_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    print(f"\nResults saved to {output_path}")

    # Print stats
    print_stats(results, args.model)


if __name__ == "__main__":
    main()
