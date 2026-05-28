"""Generate variations for each seed in seeds.jsonl using `claude` CLI headless.

Reads the system prompt from variation_prompt.md (single source of truth).
For each seed, asks Claude Sonnet for 10 variations in a fenced JSONL block.
Validates and appends to eval_cases.jsonl.

Usage:
  python3 run_var_gen.py                        # all 28 seeds
  python3 run_var_gen.py --seed seed-P3-ex3     # smoke test on one seed
  python3 run_var_gen.py --truncate             # clear eval_cases.jsonl first
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
SEEDS_PATH = HERE / "seeds.jsonl"
OUT_PATH = HERE / "eval_cases.jsonl"
PROMPT_DOC = HERE / "variation_prompt.md"
LOG_DIR = HERE / "var_gen_logs"

USER_PROMPT_TEMPLATE = """SEED:
{seed_json}

Generate 10 variations of this seed. Each variation:
- Different surface (specific values / phrasings / persona only when needed)
- Same kind of scenario triggering the same kind of model behavior
- Each has its own correct_answer in the same shape as the seed
- Internally-consistent form_state
- Plausible conversation_history (≤6 turns)

OUTPUT: nothing but the fenced JSONL block, per the OUTPUT FORMAT in the
system prompt. Your first character must be a backtick. Do NOT write a
preamble, a summary table, or any explanation of what varies."""

REQUIRED_KEYS = ["test_id", "source", "cannot_targets", "input", "correct_answer"]
REQUIRED_INPUT_KEYS = ["form_state", "conversation_history", "user_message"]
REQUIRED_ANSWER_KEYS = ["flags", "response_text", "field_ids", "field_values",
                       "question", "options", "summary_title", "summary_content"]
REQUIRED_FLAGS = ["has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit"]


def extract_system_prompt(md_text: str) -> str:
    """Pull the SYSTEM PROMPT body from variation_prompt.md.

    The prompt sits inside the first fenced block right after the
    '## SYSTEM PROMPT' heading.
    """
    m = re.search(r"## SYSTEM PROMPT[^\n]*\n+```\n(.*?)\n```", md_text, re.DOTALL)
    if not m:
        sys.exit("Could not extract SYSTEM PROMPT from variation_prompt.md")
    return m.group(1).strip()


def call_claude(system_prompt: str, user_prompt: str, model: str = "sonnet",
                timeout: int = 600) -> str:
    """Call claude CLI headless and return the response text.

    Uses `--output-format json` and reads the `result` field — `text` format
    silently drops content for some prompts (returns only a newline).
    `--system-prompt` fully replaces the default (no CLAUDE.md, no
    auto-memory). `--tools ""` disables all tools.
    """
    cmd = [
        "claude", "-p", user_prompt,
        "--system-prompt", system_prompt,
        "--model", model,
        "--output-format", "json",
        "--tools", "",
        "--no-session-persistence",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"claude exit {result.returncode}: {result.stderr[:500]}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"claude returned non-JSON: {result.stdout[:500]} ({e})")
    if data.get("is_error"):
        raise RuntimeError(f"claude reported error: {data.get('api_error_status')}")
    return data.get("result", "")


def parse_fenced_jsonl(response: str) -> tuple[list[str], str | None]:
    """Pull out the body of the first ```jsonl ... ``` (or ```...```) block."""
    m = re.search(r"```(?:jsonl)?\s*\n(.*?)\n```", response, re.DOTALL)
    if not m:
        return [], "no fenced code block found"
    lines = [ln for ln in m.group(1).splitlines() if ln.strip()]
    return lines, None


def validate_variation(obj: dict, seed: dict) -> str | None:
    """Return None if valid, else error string."""
    for k in REQUIRED_KEYS:
        if k not in obj:
            return f"missing top-level key '{k}'"
    if not isinstance(obj["input"], dict):
        return "input must be object"
    for k in REQUIRED_INPUT_KEYS:
        if k not in obj["input"]:
            return f"missing input key '{k}'"
    if not isinstance(obj["correct_answer"], dict):
        return "correct_answer must be object"
    for k in REQUIRED_ANSWER_KEYS:
        if k not in obj["correct_answer"]:
            return f"missing correct_answer key '{k}'"
    flags = obj["correct_answer"]["flags"]
    if not isinstance(flags, dict):
        return "flags must be object"
    for f in REQUIRED_FLAGS:
        if f not in flags:
            return f"missing flag '{f}'"
        if not isinstance(flags[f], bool):
            return f"flag '{f}' must be bool, got {type(flags[f]).__name__}"
    fids = obj["correct_answer"]["field_ids"]
    fvals = obj["correct_answer"]["field_values"]
    if not isinstance(fids, list) or not isinstance(fvals, list):
        return "field_ids and field_values must be lists"
    if len(fids) != len(fvals):
        return f"field_ids ({len(fids)}) and field_values ({len(fvals)}) length mismatch"
    if obj["source"] != seed["source"]:
        return f"source mismatch: variation has {obj['source']!r}, seed has {seed['source']!r}"
    if not str(obj["test_id"]).startswith(seed["test_id"]):
        return f"test_id should start with seed's '{seed['test_id']}', got '{obj['test_id']}'"
    return None


def process_seed(seed: dict, system_prompt: str, model: str,
                 log_dir: Path, max_retries: int = 3) -> tuple[list[dict], list[str]]:
    seed_id = seed["test_id"]
    user_prompt = USER_PROMPT_TEMPLATE.format(
        seed_json=json.dumps(seed, ensure_ascii=False, indent=2)
    )
    log_dir.mkdir(parents=True, exist_ok=True)

    response = ""
    err_attempts: list[str] = []
    t0 = time.time()
    for attempt in range(1, max_retries + 1):
        try:
            response = call_claude(system_prompt, user_prompt, model=model)
        except Exception as e:
            err_attempts.append(f"attempt {attempt}: claude call failed: {e}")
            response = ""
            continue
        if response.strip():
            break
        err_attempts.append(f"attempt {attempt}: empty response")
    elapsed = time.time() - t0

    (log_dir / f"{seed_id}.txt").write_text(response)

    lines, err = parse_fenced_jsonl(response)
    errors: list[str] = list(err_attempts) if not lines else []
    if err and not lines:
        errors.append(err)
        return [], errors
    valid: list[dict] = []
    for i, line in enumerate(lines, 1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"line {i}: JSON parse: {e}")
            continue
        verr = validate_variation(obj, seed)
        if verr:
            errors.append(f"line {i} (test_id={obj.get('test_id', '?')}): {verr}")
            continue
        valid.append(obj)
    print(f"  [{seed_id}] {len(valid)}/{len(lines)} valid, {elapsed:.1f}s")
    return valid, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", help="Run only this seed test_id (smoke mode)")
    ap.add_argument("--truncate", action="store_true",
                    help="Clear eval_cases.jsonl before writing")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--out", default=str(OUT_PATH),
                    help="Output JSONL path (default: eval_cases.jsonl)")
    args = ap.parse_args()

    out_path = Path(args.out)
    system_prompt = extract_system_prompt(PROMPT_DOC.read_text())

    seeds = [json.loads(l) for l in open(SEEDS_PATH)]
    if args.seed:
        seeds = [s for s in seeds if s["test_id"] == args.seed]
        if not seeds:
            sys.exit(f"No seed with test_id={args.seed}")

    if args.truncate and out_path.exists():
        out_path.unlink()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"System prompt: {len(system_prompt)} chars")
    print(f"Seeds to process: {len(seeds)}")
    print(f"Output: {out_path}")
    print(f"Logs:   {LOG_DIR}")
    print()

    total_valid = 0
    total_errors = 0
    with open(out_path, "a") as f:
        for seed in seeds:
            valid, errors = process_seed(seed, system_prompt, args.model, LOG_DIR)
            for v in valid:
                f.write(json.dumps(v, ensure_ascii=False) + "\n")
            f.flush()
            total_valid += len(valid)
            total_errors += len(errors)
            for err in errors:
                print(f"    ! {err}")

    print(f"\nDone: {total_valid} variations written, {total_errors} errors total.")


if __name__ == "__main__":
    main()
