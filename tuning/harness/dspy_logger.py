"""dspy_logger.py — capture per-module / per-LM-call traces via DSPy callbacks.

Closes the per-module raw-HTTP visibility gap (see doc-15). DSPy ships a
public callback API (`dspy.utils.callback.BaseCallback`); we register one
globally via `dspy.configure(callbacks=[...])` and dump every event to
`logs/session-{session_id}.lm-calls.jsonl`.

What we capture per turn (5 module calls × 4 phases):

    {phase: module_start,        module: ActionRouterSignature,  inputs: {context, user_message}}
    {phase: lm_start,             messages: [{role, content}, ...]}            # raw HTTP outbound
    {phase: lm_end,               raw_response: [...], exception: null}        # raw HTTP inbound
    {phase: adapter_parse_end,    outputs: {...}, exception: AdapterParseError}# parsing result/failure
    {phase: module_end,           outputs: <Prediction>, exception: null}

Module name comes from `instance.signature.__name__` (dspy.Predict carries
its signature class) so we know whether action_router / text_responder /
data_extractor / choice_builder / review_builder produced each event.

Session binding uses contextvars so the callback knows which JSONL file to
append to. `serve.py` calls `set_session_context(session_id)` before each
turn and resets after.

This file is harness-only — no DSPy modifications, no FormAssistant
modifications. The published callback hook does all the work.
"""

from __future__ import annotations

import json
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dspy.utils.callback import BaseCallback


# ── Session binding ──────────────────────────────────────────────────────
# The callback runs synchronously inside DSPy's call stack, on whatever
# thread DSPy executes the module. We bind via ContextVar so async/threaded
# servers correctly route events to the right session log.
_SESSION_ID: ContextVar[str | None] = ContextVar("harness_session_id", default=None)


def set_session_context(session_id: str):
    """Bind the active session_id for callback writes. Returns a token to
    pass to reset_session_context() in a finally block."""
    return _SESSION_ID.set(session_id)


def reset_session_context(token) -> None:
    _SESSION_ID.reset(token)


# ── Helpers ──────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _module_name(instance: Any) -> str:
    """Best-effort module identifier. dspy.Predict instances expose .signature."""
    sig = getattr(instance, "signature", None)
    if sig is not None:
        name = getattr(sig, "__name__", None)
        if name:
            return name
    cls = type(instance).__name__
    return cls


def _exc_info(exc: Exception | None) -> dict[str, Any] | None:
    if exc is None:
        return None
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    }


def _safe(obj: Any) -> Any:
    """Best-effort JSON-serializable snapshot of a dspy.Prediction/dict/list."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _safe(v) for k, v in obj.items()}
    # dspy.Prediction has a .toDict() in some versions; otherwise iterate fields
    to_dict = getattr(obj, "toDict", None) or getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            return _safe(to_dict())
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        return {k: _safe(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return repr(obj)


# ── The callback ─────────────────────────────────────────────────────────


class HarnessLogger(BaseCallback):
    """Append-only per-turn LM-call log. One JSONL line per callback event.

    Events are interleaved chronologically inside a turn — group by call_id
    to reconstruct individual module / LM / adapter calls.
    """

    def __init__(self, log_dir: str | Path = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _path(self) -> Path | None:
        sid = _SESSION_ID.get()
        if not sid:
            return None
        return self.log_dir / f"session-{sid}.lm-calls.jsonl"

    def _append(self, event: dict) -> None:
        path = self._path()
        if path is None:
            return  # outside a session context — drop silently
        try:
            with open(path, "a") as f:
                f.write(json.dumps(event, default=str) + "\n")
        except Exception:
            # Never let a logging failure break the turn.
            pass

    # ── Module level (one per dspy.Predict call) ──

    def on_module_start(self, call_id, instance, inputs):
        self._append({
            "ts": _now(),
            "call_id": call_id,
            "phase": "module_start",
            "module": _module_name(instance),
            "inputs": _safe(inputs),
        })

    def on_module_end(self, call_id, outputs, exception):
        self._append({
            "ts": _now(),
            "call_id": call_id,
            "phase": "module_end",
            "outputs": _safe(outputs),
            "exception": _exc_info(exception),
        })

    # ── LM level (one per HTTP call to mlx_vlm) ──

    def on_lm_start(self, call_id, instance, inputs):
        # `inputs` is a dict of kwargs; the messages list is the most useful field.
        messages = None
        if isinstance(inputs, dict):
            messages = inputs.get("messages") or inputs.get("prompt")
        self._append({
            "ts": _now(),
            "call_id": call_id,
            "phase": "lm_start",
            "messages": _safe(messages),
        })

    def on_lm_end(self, call_id, outputs, exception):
        self._append({
            "ts": _now(),
            "call_id": call_id,
            "phase": "lm_end",
            "raw_response": _safe(outputs),
            "exception": _exc_info(exception),
        })

    # ── Adapter parse (where AdapterParseError fires) ──

    def on_adapter_parse_start(self, call_id, instance, inputs):
        self._append({
            "ts": _now(),
            "call_id": call_id,
            "phase": "adapter_parse_start",
            "inputs": _safe(inputs),
        })

    def on_adapter_parse_end(self, call_id, outputs, exception):
        self._append({
            "ts": _now(),
            "call_id": call_id,
            "phase": "adapter_parse_end",
            "outputs": _safe(outputs),
            "exception": _exc_info(exception),
        })
