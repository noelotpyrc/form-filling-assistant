"""serve.py — HTTP harness for the local SFT model.

Runs the 5-module DSPy pipeline against mlx_vlm at :8100, composes the
output into the legacy `text + ---actions--- + JSON` format the web app's
action-parser.js expects, and streams it back as SSE.

Endpoints:

    POST /api/generate    Run one turn through the SFT pipeline (SSE response)
    POST /api/save-draft  Persist current form state to persistence-server
    POST /api/submit      Submit form state to persistence-server (final)
    GET  /health          Liveness check

Run:

    cd python
    LM_URL=http://localhost:8100/v1 \\
    LM_MODEL=./models/qwen35-08b-dspy-format-v2-mlx \\
    PERSISTENCE_URL=http://localhost:3005 \\
    uv run uvicorn tuning.harness.serve:app --port 8200 --reload
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tuning.harness import composer, dspy_logger, lifecycle, logger, pipeline  # noqa: E402

# ══════════════════════════════════════════════════════════════════════
# Config (env-overridable)
# ══════════════════════════════════════════════════════════════════════

LM_URL = os.environ.get("LM_URL", pipeline.DEFAULT_LM_URL)
LM_MODEL = os.environ.get("LM_MODEL", pipeline.DEFAULT_LM_MODEL)
PERSISTENCE_URL = os.environ.get("PERSISTENCE_URL", lifecycle.DEFAULT_PERSISTENCE_URL)
LOG_DIR = os.environ.get("LOG_DIR", str(logger.project_logs_dir()))


# ══════════════════════════════════════════════════════════════════════
# Request/response schemas
# ══════════════════════════════════════════════════════════════════════


class GenerateRequest(BaseModel):
    session_id: str = Field(..., description="Browser-generated session id")
    user_message: str = Field(..., description="The user's message this turn")
    form_state: dict[str, Any] = Field(default_factory=dict)
    form_schema: dict[str, Any] = Field(..., description="Parsed form schema JSON")
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    temperature: float | None = Field(
        default=None,
        description="Optional sampling temperature override. If unset, the harness uses the configured default (typically 0.0). The probe runner uses this to compare deterministic vs stochastic runs.",
    )
    augment_state: bool = Field(
        default=False,
        description="Enable doc-16 CANNOT #3/#5 deterministic context enrichment (humanized filled-vs-missing summary + group index hints). Off by default; turn on for A/B tests of whether the model uses the extra info.",
    )


class PersistRequest(BaseModel):
    email: str
    form_id: str
    data: dict[str, Any]


# ══════════════════════════════════════════════════════════════════════
# Lifespan — configure DSPy LM once at startup
# ══════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[harness] LM_URL={LM_URL}")
    print(f"[harness] LM_MODEL={LM_MODEL}")
    print(f"[harness] PERSISTENCE_URL={PERSISTENCE_URL}")
    print(f"[harness] LOG_DIR={LOG_DIR}")
    pipeline.configure_lm(api_base=LM_URL, model=LM_MODEL, log_dir=LOG_DIR)
    # Warm up the agent (instantiates the dspy.Module; doesn't call the model).
    pipeline.get_agent()
    print("[harness] ready")
    yield


app = FastAPI(title="form-filling-assistant local harness", lifespan=lifespan)

# Allow the web app (any port) to call us directly during dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════
# Health
# ══════════════════════════════════════════════════════════════════════


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "lm_url": LM_URL,
        "lm_model": LM_MODEL,
        "persistence_reachable": lifecycle.health_check(PERSISTENCE_URL),
    }


# ══════════════════════════════════════════════════════════════════════
# /api/generate — SSE stream matching the web app's existing contract
# ══════════════════════════════════════════════════════════════════════


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format one SSE message. Matches the format chat-provider.js parses."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _prediction_to_dict(pred: Any) -> dict[str, Any]:
    """Snapshot a dspy.Prediction's fields for logging."""
    fields = (
        "response_text", "has_new_data", "needs_choice", "wants_review",
        "wants_save", "wants_submit", "field_ids", "field_values",
        "question", "options", "summary_title", "summary_content",
    )
    out: dict[str, Any] = {}
    for f in fields:
        v = getattr(pred, f, None)
        if hasattr(v, "tolist"):
            v = v.tolist()
        out[f] = v
    return out


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    """Run the SFT pipeline for one turn and stream the result back as SSE.

    Stream:
      event: text  data: {"text": "<response_text>"}
      event: text  data: {"text": "\\n\\n---actions---\\n```json\\n[...]\\n```"}   (if any actions)
      event: done  data: {"session_id":..., "duration_ms":N, "cost_usd":0.0}

    Errors during inference yield:
      event: error data: {"message": "..."}
    """
    sess_log = logger.SessionLogger(req.session_id, log_dir=LOG_DIR)

    async def event_stream():
        try:
            sess_log.user_message(req.user_message)

            # Run pipeline in a thread so we don't block the event loop on
            # the serial 5x model calls (~8s wall on M-series).
            #
            # ContextVars don't auto-propagate to executor threads, so we
            # bind/reset the session_id inside the worker callable. This
            # way DSPy's callback (HarnessLogger) — which runs synchronously
            # inside the worker thread — sees the correct session_id and
            # routes events to the right .lm-calls.jsonl file.
            def _run_with_context():
                token = dspy_logger.set_session_context(req.session_id)
                try:
                    return pipeline.run_turn(
                        user_message=req.user_message,
                        form_schema=req.form_schema,
                        form_state=req.form_state,
                        conversation_history=req.conversation_history,
                        temperature=req.temperature,
                        augment_state=req.augment_state,
                    )
                finally:
                    dspy_logger.reset_session_context(token)

            t0 = time.time()
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, _run_with_context)
            duration_ms = (time.time() - t0) * 1000

            prediction = result["prediction"]
            context = result["context"]

            sess_log.model_input(req.user_message, req.form_state, context)

            # Compose into legacy format
            text, actions, full_response, dropped_fields = composer.compose(
                prediction, schema=req.form_schema
            )
            if dropped_fields:
                # Don't crash the user's turn; just record what was discarded.
                sess_log.error(
                    f"composer dropped {len(dropped_fields)} set_fields entry/entries that failed schema validation",
                    {"dropped": dropped_fields},
                )

            # Log the model output (composed) and any field updates
            sess_log.model_output(
                raw_text=full_response,
                parsed_actions=actions,
                duration_ms=duration_ms,
                module_outputs=_prediction_to_dict(prediction),
            )
            if any(a.get("type") == "set_fields" for a in actions):
                field_updates: dict[str, Any] = {}
                for a in actions:
                    if a.get("type") == "set_fields":
                        for f in a.get("fields", []):
                            field_updates[f["field_id"]] = f["value"]
                if field_updates:
                    sess_log.form_state_update(field_updates, source="model")

            # Send text first (the conversational reply renders immediately).
            if text:
                yield _sse("text", {"text": text})
            # Then the actions block (parsed by browser, applied to form panel).
            if actions:
                actions_block = (
                    f"\n\n---actions---\n"
                    f"```json\n{json.dumps(actions, indent=2)}\n```"
                )
                yield _sse("text", {"text": actions_block})

            yield _sse("done", {
                "session_id": req.session_id,
                "duration_ms": duration_ms,
                "cost_usd": 0.0,
            })
        except Exception as e:
            sess_log.error(str(e), {"type": type(e).__name__})
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable any proxy buffering
        },
    )


# ══════════════════════════════════════════════════════════════════════
# /api/save-draft and /api/submit — out-of-band lifecycle endpoints.
#
# The model can't emit submit_draft/submit_final actions, so the web app
# calls these directly when the user clicks the Save Draft / Submit
# buttons (the model just renders the buttons via show_button actions).
# ══════════════════════════════════════════════════════════════════════


@app.post("/api/save-draft")
async def save_draft(req: PersistRequest) -> dict[str, Any]:
    try:
        return lifecycle.save_draft(req.email, req.form_id, req.data, base_url=PERSISTENCE_URL)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"persistence-server error: {e}")


@app.post("/api/submit")
async def submit(req: PersistRequest) -> dict[str, Any]:
    try:
        return lifecycle.submit_final(req.email, req.form_id, req.data, base_url=PERSISTENCE_URL)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"persistence-server error: {e}")
