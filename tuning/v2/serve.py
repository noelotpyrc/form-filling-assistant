"""v2 serving harness — FastAPI on :8200, same request/SSE contract as the v1
harness, so the web app's /api/generate-local (?backend=local) drives it
unchanged. Only the LM behind FormAssistant swaps (teacher now; student later).

`pending` is harness-only state (doc-18.1): the request carries form_state +
history (browser-authoritative), and the harness keeps a per-session pending
store across turns.

Run:  tuning/v2/.venv/bin/python -m tuning.v2.serve
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Any
import asyncio
import json
import os
import time

import dspy
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .claude_lm import ClaudeLM
from .schema import parse_schema
from .state import TurnState, Pending
from .program import FormAssistant

PORT = int(os.getenv("PORT", "8200"))

_AGENT: FormAssistant | None = None
_PENDING: dict[str, Pending | None] = {}   # session_id -> pending (harness-only)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _AGENT
    dspy.configure(lm=ClaudeLM())
    _AGENT = FormAssistant()
    print(f"[v2-harness] ready on :{PORT}  teacher={os.getenv('V2_TEACHER_MODEL', 'sonnet')}")
    yield


app = FastAPI(title="form-filling-assistant v2 harness", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    session_id: str
    user_message: str
    form_state: dict[str, Any] = Field(default_factory=dict)
    form_schema: dict[str, Any]
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    temperature: float | None = None     # accepted for contract parity; CLI teacher ignores it
    augment_state: bool = False           # accepted; v2 has no augmentation path


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.get("/health")
def health():
    return {"ok": True, "harness": "v2"}


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    async def stream():
        try:
            schema = parse_schema(req.form_schema)
            state = TurnState(
                schema=schema,
                form_state=dict(req.form_state),               # browser-authoritative
                pending=_PENDING.get(req.session_id),           # harness-authoritative
            )

            def _run():  # 2 serial claude calls — keep off the event loop
                return _AGENT(state=state, user_message=req.user_message,
                              history=req.conversation_history)

            t0 = time.time()
            out = await asyncio.get_running_loop().run_in_executor(None, _run)
            duration_ms = (time.time() - t0) * 1000
            _PENDING[req.session_id] = state.pending            # persist pending for next turn

            if out.text:
                yield _sse("text", {"text": out.text})
            if out.actions:
                block = f"\n\n---actions---\n```json\n{json.dumps(out.actions, indent=2)}\n```"
                yield _sse("text", {"text": block})
            yield _sse("done", {"session_id": req.session_id,
                                "duration_ms": duration_ms, "cost_usd": 0.0})
        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
