"""LLM judge for rubric-based scoring of text_responder outputs.

Default model: gpt-5 via OpenAI API. Configurable via env vars:
  JUDGE_MODEL    — model id (default: gpt-5)
  JUDGE_BASE_URL — API base URL (e.g. https://openrouter.ai/api/v1)
  OPENAI_API_KEY / OPENROUTER_API_KEY — credentials

All rubric items for one case are batched into a single judge call.
"""

from __future__ import annotations

import json
import os
import sys
import time

DEFAULT_MODEL = "gpt-5"


def _client():
    import openai
    base_url = os.getenv("JUDGE_BASE_URL")
    if base_url and "openrouter" in base_url:
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    else:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("No API key found in OPENAI_API_KEY or OPENROUTER_API_KEY")
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return openai.OpenAI(**kwargs)


def _fmt_pred_block(label: str, p: dict) -> str:
    """Render the full 5-module prediction block."""
    flags = p.get("flags") or {f: p.get(f, False) for f in
                                 ["has_new_data", "needs_choice", "wants_review",
                                  "wants_save", "wants_submit"]}
    flag_str = " ".join(f"{k}={bool(v)}" for k, v in flags.items())

    fields = []
    fids = p.get("field_ids") or []
    fvals = p.get("field_values") or []
    for fid, fv in zip(fids, fvals):
        fields.append(f"      {fid} = {fv!r}")
    fields_block = "\n".join(fields) if fields else "      (none)"

    lines = [
        f"{label}:",
        f"  flags:      {flag_str}",
        f"  response_text: {p.get('response_text', '')!r}",
        f"  field updates ({len(fids)}):",
        fields_block,
    ]
    q = p.get("question") or ""
    opts = p.get("options") or []
    if q or opts:
        lines.append(f"  question:   {q!r}")
        lines.append(f"  options:    {opts}")
    st = p.get("summary_title") or ""
    sc = p.get("summary_content") or ""
    if st or sc:
        lines.append(f"  review:     '{st}' — {sc!r}")
    return "\n".join(lines)


def _build_prompt(case: dict, predicted: dict,
                  rubric_items: list[dict]) -> str:
    """Compose the holistic judge prompt.

    The judge sees the entire turn (input + full gold + full prediction)
    so rubric items can reason about any module's output — including
    cross-module consistency like 'does response_text match what
    field_ids actually did?'
    """
    inp = case["input"]
    fs = inp.get("form_state", {})
    history = inp.get("conversation_history", [])
    history_block = (
        "\n".join(f"  [{t['role']}] {t['content']}" for t in history)
        if history else "  (none)"
    )
    gold = case["correct_answer"]
    items_block = "\n".join(
        f"{i+1}. {item['ask']}" for i, item in enumerate(rubric_items)
    )

    return (
        "You evaluate a form-filling assistant on a single turn. The "
        "assistant produces FIVE module outputs that together define the "
        "turn's behavior: action flags (5 booleans), response_text, "
        "field updates (field_ids + values), an optional multiple-choice "
        "question + options, and an optional review summary.\n"
        "\n"
        "Judge the PREDICTED turn against the rubric. Use the GOLD turn "
        "as one reference for correct behavior — the predicted turn can "
        "phrase things differently and still be correct.\n"
        "\n"
        "CONTEXT\n"
        f"form_state: {json.dumps(fs, ensure_ascii=False)}\n"
        f"conversation history:\n{history_block}\n"
        f"user message: {inp['user_message']}\n"
        "\n"
        f"{_fmt_pred_block('GOLD', gold)}\n"
        "\n"
        f"{_fmt_pred_block('PREDICTED', predicted)}\n"
        "\n"
        f"Questions:\n{items_block}\n"
        "\n"
        f'Reply with ONLY a JSON array of "yes" or "no" strings, length {len(rubric_items)}, '
        "in question order. No prose, no fence, no explanation."
    )


def _parse_answers(text: str, expected_n: int) -> list[bool]:
    text = text.strip()
    # Strip optional markdown fence
    if text.startswith("```"):
        # ```json ... ``` or ``` ... ```
        text = text.split("```", 2)[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
        text = text.rstrip("`").strip()
    answers = json.loads(text)
    if not isinstance(answers, list):
        raise ValueError(f"expected array, got {type(answers).__name__}")
    if len(answers) != expected_n:
        raise ValueError(f"got {len(answers)} answers, expected {expected_n}")
    return [str(a).strip().lower().startswith("y") for a in answers]


# Retry policy: judge is critical signal. Try up to JUDGE_MAX_ATTEMPTS,
# back off between attempts. After the last attempt fails, raise — the
# caller (the metric) MUST NOT silently fall back to a no-judge score.
# See: tuning/gepa/INCIDENT_2026-05-15_judge_silent_fallback.md
JUDGE_MAX_ATTEMPTS = int(os.getenv("JUDGE_MAX_ATTEMPTS", "3"))
JUDGE_RETRY_BACKOFF_SEC = (
    float(os.getenv("JUDGE_RETRY_BACKOFF_1", "5")),
    float(os.getenv("JUDGE_RETRY_BACKOFF_2", "15")),
)


class JudgeRetriesExhausted(RuntimeError):
    """Raised when the judge has failed JUDGE_MAX_ATTEMPTS times in a row.

    Distinct exception class so callers (optimize.py's metric wrapper) can
    differentiate judge infrastructure failures from other metric errors,
    and trigger a graceful halt (e.g., touch gepa.stop) instead of letting
    DSPy substitute failure_score=0.0 silently.
    """
    def __init__(self, attempts: int, last_exc: BaseException):
        super().__init__(
            f"Judge failed all {attempts} attempts. "
            f"Last error: {type(last_exc).__name__}: {str(last_exc)[:200]}"
        )
        self.attempts = attempts
        self.last_exc = last_exc


def _judge_case_once(case: dict, predicted: dict,
                     rubric_items: list[dict], model: str | None) -> list[bool]:
    """Single judge attempt. Backend dispatch via env `JUDGE_BACKEND`."""
    backend = os.getenv("JUDGE_BACKEND", "openai").lower()
    if backend == "claude_headless":
        from judge_claude_headless import judge_case as _claude_judge_case
        return _claude_judge_case(case, predicted, rubric_items, model=model)
    if backend == "openrouter":
        from judge_openrouter import judge_case as _openrouter_judge_case
        return _openrouter_judge_case(case, predicted, rubric_items, model=model)

    if not rubric_items:
        return []
    client = _client()
    prompt = _build_prompt(case, predicted, rubric_items)
    model = model or os.getenv("JUDGE_MODEL", DEFAULT_MODEL)
    # Default to temperature=0 (greedy decoding) for near-deterministic judging.
    # Override with env JUDGE_TEMPERATURE for exploration.
    temperature = float(os.getenv("JUDGE_TEMPERATURE", "0"))
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    text = resp.choices[0].message.content
    return _parse_answers(text, len(rubric_items))


def judge_case(case: dict, predicted: dict,
               rubric_items: list[dict], model: str | None = None) -> list[bool]:
    """Call the judge with retries; raise if all attempts fail.

    `predicted` is the full prediction dict (5 module outputs); judge sees
    it all so rubric items can reason about flags/fields/options/etc., not
    just response_text.

    Retry policy (see INCIDENT_2026-05-15_judge_silent_fallback.md):
    judge is the dominant signal for text_responder (weight 0.55 in the
    composite). A silent fallback to programmatic-only scoring would
    inflate failed cases by ~0.55. We retry up to JUDGE_MAX_ATTEMPTS,
    back off between attempts, and on final failure raise to halt the run.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, JUDGE_MAX_ATTEMPTS + 1):
        try:
            return _judge_case_once(case, predicted, rubric_items, model)
        except BaseException as e:  # noqa: BLE001
            last_exc = e
            if attempt < JUDGE_MAX_ATTEMPTS:
                # Backoff index = attempt - 1 (0-indexed), clamp to last entry
                idx = min(attempt - 1, len(JUDGE_RETRY_BACKOFF_SEC) - 1)
                sleep_sec = JUDGE_RETRY_BACKOFF_SEC[idx]
                sys.stderr.write(
                    f"[judge_case] attempt {attempt}/{JUDGE_MAX_ATTEMPTS} "
                    f"failed: {type(e).__name__}: {str(e)[:200]}. "
                    f"Retrying in {sleep_sec:.1f}s…\n"
                )
                sys.stderr.flush()
                time.sleep(sleep_sec)
            else:
                sys.stderr.write(
                    f"[judge_case] all {JUDGE_MAX_ATTEMPTS} attempts failed; "
                    f"giving up. Last error: {type(e).__name__}: {str(e)[:200]}\n"
                )
                sys.stderr.flush()
    raise JudgeRetriesExhausted(JUDGE_MAX_ATTEMPTS, last_exc) from last_exc  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────
# CLI smoke test
# ─────────────────────────────────────────────────────────────────────────

def _cli():
    import argparse
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from rubrics import get_rubric_for_case  # noqa

    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="seed-P3-ex3")
    ap.add_argument("--mode", choices=["gold", "fabricated"], default="gold")
    args = ap.parse_args()

    seeds = [json.loads(l) for l in open(
        Path(__file__).parent / "seeds.jsonl"
    )]
    case = next(s for s in seeds if s["test_id"] == args.seed)
    rubric = get_rubric_for_case(case)

    if args.mode == "gold":
        predicted = dict(case["correct_answer"])  # mirror gold as the prediction
    else:
        # Fabricated: claim to commit a value the user never gave
        predicted = {
            "flags": {"has_new_data": True, "needs_choice": False, "wants_review": False,
                       "wants_save": False, "wants_submit": False},
            "response_text": "Got it, saved your DOB as 1995-01-04. What's your email?",
            "field_ids": ["dob"], "field_values": ["1995-01-04"],
            "question": "", "options": [],
            "summary_title": "", "summary_content": "",
        }

    print(f"Seed: {args.seed}  mode: {args.mode}")
    print(f"Predicted response: {predicted['response_text']}\n")
    print(f"Rubric items ({len(rubric)}):")
    for i, item in enumerate(rubric, 1):
        print(f"  {i}. {item['ask']}")
    print()
    answers = judge_case(case, predicted, rubric)
    print(f"Judge answers: {answers}")
    for item, ans in zip(rubric, answers):
        mark = "✓" if ans else "✗"
        print(f"  {mark} [{item['weight']}] {item['id']}: {'yes' if ans else 'no'}")


if __name__ == "__main__":
    _cli()
