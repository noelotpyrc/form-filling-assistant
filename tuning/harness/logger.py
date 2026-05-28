"""logger.py — append-only session-trace JSONL writer.

Matches the schema already produced server-side by the production agent
(see logs/session-*.jsonl). Reading the existing format and writing to it
verbatim means existing analysis tooling keeps working — and it gives us a
single canonical trace format whether the session was driven by Claude or
by the local SFT harness.

Schema per turn (one line per event):

    {"type":"user_message",      "session_id":..., "ts":..., "role":"user", "message":"..."}
    {"type":"model_input",       "session_id":..., "ts":..., "user_message":..., "form_state_snapshot":..., "context_chars":N}
    {"type":"model_output",      "session_id":..., "ts":..., "raw_text":..., "parsed_actions":[...], "duration_ms":N, "cost_usd":0.0, "module_outputs":{...}}
    {"type":"form_state_update", "session_id":..., "ts":..., "field_updates":{...}, "source":"model"}

`module_outputs` is an additive field beyond the existing schema — it stores
each of the 5-module raw outputs (action_router, text_responder, etc.) so we
can debug which module produced what. Existing analyzers ignore unknown keys.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _ts_now() -> str:
    """ISO-8601 UTC timestamp with milliseconds, matching existing logs."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class SessionLogger:
    """Append-only writer for one session's trace.

    Files are named `session-{session_id}.jsonl`. Each call appends one event.
    Safe to instantiate per-request — file is opened in append mode every time.
    """

    def __init__(self, session_id: str, log_dir: str | Path = "logs"):
        self.session_id = session_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.log_dir / f"session-{session_id}.jsonl"

    # ── Internal append ──

    def _append(self, event: dict[str, Any]) -> None:
        event = {
            "session_id": self.session_id,
            "ts": _ts_now(),
            **event,
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

    # ── Public events ──

    def user_message(self, message: str) -> None:
        self._append({
            "type": "user_message",
            "role": "user",
            "message": message,
        })

    def model_input(
        self,
        user_message: str,
        form_state_snapshot: dict[str, Any] | None,
        context: str,
    ) -> None:
        self._append({
            "type": "model_input",
            "user_message": user_message,
            "form_state_snapshot": form_state_snapshot or {},
            "context_chars": len(context or ""),
        })

    def model_output(
        self,
        raw_text: str,
        parsed_actions: list[dict],
        duration_ms: float,
        module_outputs: dict[str, Any] | None = None,
    ) -> None:
        self._append({
            "type": "model_output",
            "raw_text": raw_text,
            "parsed_actions": parsed_actions or [],
            "duration_ms": duration_ms,
            "cost_usd": 0.0,  # local model — no $ cost
            "module_outputs": module_outputs or {},
        })

    def form_state_update(
        self,
        field_updates: dict[str, Any],
        source: str = "model",
    ) -> None:
        self._append({
            "type": "form_state_update",
            "field_updates": field_updates or {},
            "source": source,
        })

    def error(self, message: str, details: dict[str, Any] | None = None) -> None:
        self._append({
            "type": "error",
            "message": message,
            "details": details or {},
        })


def project_logs_dir() -> Path:
    """Resolve the repo's logs/ dir from anywhere in the source tree."""
    return Path(__file__).resolve().parent.parent.parent / "logs"
