"""lifecycle.py — talk to packages/persistence-server for save_draft / submit_final.

The SFT model can't invoke MCP tools, so any non-conversational lifecycle
work has to happen here. Phase 1 only needs the two POST endpoints
(`POST /api/drafts`, `POST /api/submissions`); other lifecycle (file
uploads, validate_fields, vault) is out of scope.

The persistence-server schema (see packages/persistence-server/src/index.ts):

  POST /api/drafts       {email, form_id, data}  →  {draft_id, email, updated_at}
  POST /api/submissions  {email, form_id, data}  →  {submission_id, reference_number, submitted_at}

Defaults to localhost:3005 (the persistence-server default port). Override
via `PERSISTENCE_URL` env var if needed.
"""

from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_PERSISTENCE_URL = os.environ.get("PERSISTENCE_URL", "http://localhost:3005")


def save_draft(
    email: str,
    form_id: str,
    data: dict[str, Any],
    *,
    base_url: str = DEFAULT_PERSISTENCE_URL,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """POST /api/drafts. Returns server response on success."""
    resp = requests.post(
        f"{base_url}/api/drafts",
        json={"email": email, "form_id": form_id, "data": data},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def submit_final(
    email: str,
    form_id: str,
    data: dict[str, Any],
    *,
    base_url: str = DEFAULT_PERSISTENCE_URL,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """POST /api/submissions. Returns server response on success."""
    resp = requests.post(
        f"{base_url}/api/submissions",
        json={"email": email, "form_id": form_id, "data": data},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def health_check(base_url: str = DEFAULT_PERSISTENCE_URL, timeout: float = 2.0) -> bool:
    """Best-effort liveness check; returns False on any error."""
    try:
        resp = requests.get(f"{base_url}/health", timeout=timeout)
        return resp.ok
    except Exception:
        return False
