"""v2 serving harness — FastAPI on :8200, same request/SSE contract as the v1
harness, so the web app's /api/generate-local (?backend=local) drives it
unchanged. Only the LM behind FormAssistant swaps (teacher now; student later).

`pending` is harness-only state (doc-18.1): the request carries form_state +
history (browser-authoritative), and the harness keeps a per-session pending
store across turns.

Run:  tuning/v2/.venv/bin/python -m tuning.v2.serve
Offline check:  tuning/v2/.venv/bin/python -m tuning.v2.serve --selftest
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

from .schema import parse_schema
from .state import TurnState, Pending
from .program import FormAssistant, assign_lms
from .student_lm import StudentLM

PORT = int(os.getenv("PORT", "8200"))

# doc-21 chapter 3: serve the two students, per-predictor (extractor + responder),
# not the teacher. Paths are the leon-work local defaults, env-overridable.
EXTRACT_MODEL = os.getenv("V2_SERVE_EXTRACT_MODEL",
                          "/Users/lliao/work/form-filling-models/qwen35-08b-v2-r3-oracle-mlx")
EXTRACT_PORT = int(os.getenv("V2_SERVE_EXTRACT_PORT", "8100"))
RESPOND_MODEL = os.getenv("V2_SERVE_RESPOND_MODEL",
                          "/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2cresp-mlx")
RESPOND_PORT = int(os.getenv("V2_SERVE_RESPOND_PORT", "8104"))

_AGENT: FormAssistant | None = None
_PENDING: dict[str, Pending | None] = {}   # session_id -> pending (harness-only)


def build_agent() -> FormAssistant:
    """FormAssistant with the extractor + responder students wired per-predictor
    (assign_lms). No network at construction time — the servers are hit per request."""
    extract_lm = StudentLM(model=EXTRACT_MODEL, port=EXTRACT_PORT, temperature=0)
    respond_lm = StudentLM(model=RESPOND_MODEL, port=RESPOND_PORT, temperature=0)
    dspy.configure(lm=respond_lm)     # global default; assign_lms overrides per-predictor
    agent = FormAssistant()
    assign_lms(agent, extract_lm=extract_lm, respond_lm=respond_lm)
    return agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _AGENT
    _AGENT = build_agent()
    print(f"[v2-harness] ready on :{PORT}  extractor={EXTRACT_MODEL}@{EXTRACT_PORT}  "
          f"responder={RESPOND_MODEL}@{RESPOND_PORT}")
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


def selftest() -> None:
    """Offline: the two students are wired per-predictor and the request/SSE contract is
    unchanged. No network — StudentLM construction and assign_lms hit nothing."""
    agent = build_agent()
    assert isinstance(agent.extract.lm, StudentLM) and isinstance(agent.respond.lm, StudentLM)
    assert agent.extract.lm is not agent.respond.lm
    assert agent.extract.lm.model == EXTRACT_MODEL and agent.extract.lm.base_url.endswith(f":{EXTRACT_PORT}")
    assert agent.respond.lm.model == RESPOND_MODEL and agent.respond.lm.base_url.endswith(f":{RESPOND_PORT}")
    assert agent.extract.lm.temperature == 0 and agent.respond.lm.temperature == 0
    # request contract untouched
    assert set(GenerateRequest.model_fields) == {
        "session_id", "user_message", "form_state", "form_schema",
        "conversation_history", "temperature", "augment_state"}, set(GenerateRequest.model_fields)
    # SSE framing untouched
    assert _sse("done", {"session_id": "x"}) == 'event: done\ndata: {"session_id": "x"}\n\n'
    print(f"serve selftest: student wiring (extract={EXTRACT_MODEL}@{EXTRACT_PORT}, "
          f"respond={RESPOND_MODEL}@{RESPOND_PORT}) + request/SSE contract intact")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        selftest()
    else:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=PORT)
