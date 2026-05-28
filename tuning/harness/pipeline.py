"""pipeline.py — wraps FormAssistant (5-module DSPy pipeline) for the harness.

Wires up the existing `tuning.dspy.optimize_prompt.FormAssistant` to a local
mlx_vlm-served SFT model. The pipeline takes structured per-turn inputs
(form_state, form_schema, conversation_history, user_message) and returns the
DSPy Prediction with all 5-module outputs needed by composer.py.

Mirrors `tuning/sft/compare_models.py::build_context` for prompt construction
so the harness sees exactly the same context format the SFT model was trained
and evaluated on.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import dspy

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Reuse the canonical FormAssistant + signatures.
from tuning.dspy.optimize_prompt import FormAssistant  # noqa: E402

DEFAULT_LM_URL = "http://localhost:8100/v1"
DEFAULT_LM_MODEL = str(PROJECT_ROOT / "models" / "qwen35-08b-dspy-format-v2-mlx")

# ──────────────────────────────────────────────────────────────────────
# ⚠️  MLX-server model-name footgun
# ──────────────────────────────────────────────────────────────────────
# `mlx_vlm server --model <PATH>` loads ONE set of weights, but the server's
# `GET /v1/models` returns a LIST of names from an internal registry that
# DOES NOT include the loaded path. POSTing to /v1/chat/completions with
# *any* of those listed names succeeds — the server silently routes the
# request to the loaded weights, BUT applies a different chat template
# based on the requested name.
#
# The SFT model was trained with a specific chat template. Using a wrong
# model name → wrong template → off-distribution prompt at inference time
# → silently degraded behavior. No error, no warning.
#
# Therefore: ALWAYS use `DEFAULT_LM_MODEL` (the path the server was
# launched with). If you want a different model, restart the server with
# a different `--model` arg and update DEFAULT_LM_MODEL — never just
# request a different name from the registry list.
#
# The `tuning/harness/preflight.py::assert_anchor_match()` check catches
# template mismatches by diffing output against a verified probe; run it
# at the top of every costly experiment.
# ──────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════
# Context builder — must match compare_models.py::build_context exactly.
# ══════════════════════════════════════════════════════════════════════


def render_form_schema(form_schema: dict) -> str:
    """Render a parsed form schema dict as the long-string description the
    SFT model was trained on. Mirrors compare_models.py::load_form_context.

    Per R9 in doc-15: shows ALL select options (not just the first 5). The
    inherited `[:5]` cap from gen_format_data.py / compare_models.py was
    silently hiding the 6th+ options from the model, which caused wrong
    extractions when a user picked one — the model defaulted to the
    closest known value (e.g., user clicks "Mechanical Engineering" →
    model writes `program=cs` because it never saw `engineering` as a
    valid value during training-time context rendering).

    This is a deliberate drift from training-time context format. We
    accept it because hiding valid options is a strictly worse default;
    the model now has more information to work with rather than less.
    Eventual eval/train consistency requires updating the matching
    helpers in compare_models.py and gen_format_data.py too — batch with
    v3 data regeneration.
    """
    parts = [f"Form: {form_schema.get('name', '?')}", ""]
    for section in form_schema.get("schema", {}).get("sections", []):
        fields_desc = []
        for f in section.get("fields", []):
            req = " (required)" if f.get("required") else ""
            ftype = f.get("type", "")
            if ftype == "group":
                sub_fields = [sf.get("field_id", "") for sf in f.get("fields", [])]
                fields_desc.append(
                    f"  {f.get('field_id', '')} (group: {', '.join(sub_fields)}){req}"
                )
            elif ftype == "select" and f.get("options"):
                opts = [
                    o.get("label", o.get("value", "")) if isinstance(o, dict) else str(o)
                    for o in f["options"]   # show ALL options, not just [:5] — see R9
                ]
                fields_desc.append(
                    f"  {f.get('field_id', '')} (select: {', '.join(opts)}){req}"
                )
            else:
                fields_desc.append(f"  {f.get('field_id', '')} ({ftype}){req}")
        parts.append(f"{section.get('title', '')}:")
        parts.extend(fields_desc)
    return "\n".join(parts)


_FILE_MARKER_RE = re.compile(r"\[File:\s*[^\]]+\]")
_ACTIONS_BLOCK_RE = re.compile(r"\n*---actions---\n.*\Z", re.DOTALL)
DEFAULT_CHAT_TURN_CAP = 600          # normal chatty turn — minor bump from training (300)
DEFAULT_FILE_TURN_CAP = 8000         # turns containing [File: ...] blocks


def _strip_actions_block(content: str) -> str:
    """Remove the trailing `---actions---\\n```json ...` block from a turn.

    Legacy eval cases (300/300) carry tool-call JSON inside assistant turn
    content as a `---actions---` section. CANNOT seeds and variations do not.
    The SFT model was trained on the actions-free format, so we strip these
    blocks at the canonical input-building point — both production
    FormAssistant calls AND judge prompts go through here, so alignment is
    automatic across all callers.
    """
    if not content:
        return content
    return _ACTIONS_BLOCK_RE.sub("", content).rstrip()


def _truncate_history_turn(content: str, *, chat_cap: int = DEFAULT_CHAT_TURN_CAP,
                            file_cap: int = DEFAULT_FILE_TURN_CAP) -> str:
    """Truncate one conversation-history turn for inclusion in the context.

    Per R8 in doc-15: the previous flat `[:300]` cap silently destroyed
    uploaded file content after a single turn. We now detect file blocks via
    the `[File: ...]` marker convention used by the web app's sendMessage()
    and grant those turns a much larger cap (8KB by default — one resume's
    worth) so multi-turn references to uploads keep working.
    """
    if not content:
        return content
    content = _strip_actions_block(content)
    cap = file_cap if _FILE_MARKER_RE.search(content) else chat_cap
    return content if len(content) <= cap else content[:cap] + "...[truncated]"


def build_context(
    form_schema: dict,
    form_state: dict | None,
    conversation_history: list[dict] | None,
    *,
    history_window: int = 6,
    augment_state: bool = False,
) -> str:
    """Compose the `context` string the 5-module pipeline expects.

    history_window matches compare_models.py default (last 6 turns). Per-turn
    truncation is content-aware: file-upload turns (containing a `[File: …]`
    marker) get an 8KB cap so the file content survives across turns; normal
    chatty turns get a 600-char cap (minor bump from the original 300 to give
    multi-paragraph replies a bit more breathing room without straying far
    from training distribution).

    `augment_state` (default False) enables the doc-16 CANNOT #3/#5
    deterministic enrichment: a humanized "filled vs missing required" line
    plus group-field index hints. This deviates slightly from the model's
    training distribution — left off by default; the probe runner / specific
    A/B tests turn it on to measure whether the model uses the extra info.
    """
    ctx = render_form_schema(form_schema)
    if form_state:
        ctx += f"\n\nFilled fields: {json.dumps(form_state)}"

        if augment_state:
            # Lazy-import so the harness doesn't depend on state_check at import
            # time when augmentation is disabled.
            from tuning.harness.state_check import (
                compute_state_summary, compute_group_indices, humanize_group_indices,
            )
            summary = compute_state_summary(form_schema, form_state)
            ctx += f"\n\nProgress: {summary['humanized']}"
            gi = compute_group_indices(form_schema, form_state)
            gi_str = humanize_group_indices(gi)
            if gi_str:
                ctx += f"\n\nGroup entries: {gi_str}"

    if conversation_history:
        recent = conversation_history[-history_window:]
        ctx += "\n\nRecent conversation:\n"
        ctx += "\n".join(
            f"{'User' if h.get('role') == 'user' else 'Assistant'}: "
            f"{_truncate_history_turn(h.get('content') or '')}"
            for h in recent
        )
    return ctx


# ══════════════════════════════════════════════════════════════════════
# Pipeline — singleton FormAssistant with DSPy LM configured for mlx_vlm.
# ══════════════════════════════════════════════════════════════════════


_AGENT: FormAssistant | None = None
_LM_CONFIGURED = False
# Last LM config — reused when run_turn() needs to spin up a per-call LM
# at a different temperature.
_LAST_LM_KW: dict[str, Any] = {}


def configure_lm(
    api_base: str = DEFAULT_LM_URL,
    model: str = DEFAULT_LM_MODEL,
    *,
    log_dir: str | Path | None = None,
) -> None:
    """Configure DSPy to call the local mlx_vlm-served SFT model.

    Also registers our HarnessLogger callback so each turn's per-module
    raw HTTP traffic + parse events land in
    `logs/session-{session_id}.lm-calls.jsonl` (see dspy_logger.py).

    Idempotent — safe to call once at startup; subsequent calls reconfigure.
    """
    global _LM_CONFIGURED
    from tuning.harness.dspy_logger import HarnessLogger

    lm = dspy.LM(
        f"openai/{model}",
        api_base=api_base,
        api_key="dummy",  # mlx_vlm.server ignores auth
        model_type="chat",
        temperature=0.0,
        max_tokens=512,
        # Disable response caching so identical prompts can yield independent
        # samples (e.g., when the probe runner fires the same probe twice and
        # we want to see variability rather than a cached replay). In
        # production the kickoff message includes the live email/timestamp,
        # so each turn is unique and caching wouldn't help anyway.
        cache=False,
    )
    callbacks = [HarnessLogger(log_dir=log_dir or (PROJECT_ROOT / "logs"))]
    dspy.configure(lm=lm, callbacks=callbacks)
    _LM_CONFIGURED = True
    _LAST_LM_KW.update({"model_name": f"openai/{model}", "api_base": api_base})


def get_agent() -> FormAssistant:
    """Lazily instantiate a singleton FormAssistant. Call configure_lm() first."""
    global _AGENT
    if not _LM_CONFIGURED:
        configure_lm()
    if _AGENT is None:
        _AGENT = FormAssistant()
    return _AGENT


def run_turn(
    user_message: str,
    form_schema: dict,
    form_state: dict | None = None,
    conversation_history: list[dict] | None = None,
    temperature: float | None = None,
    augment_state: bool = False,
) -> dict[str, Any]:
    """Run one turn through the 5-module pipeline.

    If `temperature` is given (and differs from the global LM's temperature),
    we run inside a `dspy.context(lm=...)` block with a per-call LM that has
    the desired temperature. This is what the probe runner uses to compare
    a deterministic run (temp=0) against a stochastic run (temp=0.7).

    Returns a dict with:
      - prediction: the raw dspy.Prediction (composer.py consumes this)
      - context: the rendered context string (for logging)
      - duration_ms: total wall-clock time across all module calls
    """
    agent = get_agent()
    context = build_context(
        form_schema, form_state, conversation_history,
        augment_state=augment_state,
    )

    if temperature is not None:
        custom_lm = dspy.LM(
            f"openai/{DEFAULT_LM_MODEL}" if not _LAST_LM_KW else _LAST_LM_KW["model_name"],
            api_base=_LAST_LM_KW.get("api_base", DEFAULT_LM_URL),
            api_key="dummy",
            model_type="chat",
            temperature=float(temperature),
            max_tokens=512,
            cache=False,
        )
        with dspy.context(lm=custom_lm):
            t0 = time.time()
            prediction = agent(context=context, user_message=user_message)
            duration_ms = (time.time() - t0) * 1000
    else:
        t0 = time.time()
        prediction = agent(context=context, user_message=user_message)
        duration_ms = (time.time() - t0) * 1000

    return {
        "prediction": prediction,
        "context": context,
        "duration_ms": duration_ms,
    }


# ══════════════════════════════════════════════════════════════════════
# Smoke test — `uv run python tuning/harness/pipeline.py`
# ══════════════════════════════════════════════════════════════════════


def _smoke() -> None:
    schema_path = PROJECT_ROOT / "packages/web-app/public/forms/masters-northfield.json"
    schema = json.load(open(schema_path))

    configure_lm()
    out = run_turn(
        user_message="Hi, my name is Jane Smith and my email is jane@example.com.",
        form_schema=schema,
        form_state={},
        conversation_history=[],
    )
    pred = out["prediction"]
    print(f"\nDuration: {out['duration_ms']:.0f}ms")
    print(f"\nPrediction fields:")
    print(f"  response_text:  {pred.response_text[:200]}")
    print(f"  has_new_data:   {pred.has_new_data}")
    print(f"  needs_choice:   {pred.needs_choice}")
    print(f"  wants_review:   {pred.wants_review}")
    print(f"  wants_save:     {pred.wants_save}")
    print(f"  wants_submit:   {pred.wants_submit}")
    print(f"  field_ids:      {pred.field_ids}")
    print(f"  field_values:   {pred.field_values}")
    print(f"  question:       {pred.question}")
    print(f"  options:        {pred.options}")


if __name__ == "__main__":
    _smoke()
