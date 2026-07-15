"""StudentLM — a DSPy LM that runs the SFT student via a locally served MLX model.

The student is served with an OpenAI-compatible endpoint on localhost
(`mlx_vlm server --model /path/to/student --port 8100` → `/v1/chat/completions`),
so this LM just POSTs the DSPy messages array NATIVELY (same pass-through as
OpenRouterLM — no _split flattening, so ChatAdapter's system/demo/user turns
survive) and reads back `choices[0].message.content`.

Cost is recorded as $0.0 per call (a local model, no API meter) so the same
`lm.history` cost accounting used by eval/data-gen keeps working. Caching is OFF
for the same reason as the teacher LMs (no silent cache divergence).

Env: V2_STUDENT_PORT (default 8100), V2_STUDENT_MODEL (default "student"; sent in
the body — MLX servers may ignore it), V2_STUDENT_TIMEOUT (s, default 120).
No auth (localhost).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import json
import os
import time

import dspy

STUDENT_PORT = int(os.getenv("V2_STUDENT_PORT", "8100"))
STUDENT_MODEL = os.getenv("V2_STUDENT_MODEL", "student")
TIMEOUT = int(os.getenv("V2_STUDENT_TIMEOUT", "120"))
_CHAT_PATH = "/v1/chat/completions"

# HTTP client: prefer `requests` (present in this venv); fall back to stdlib
# urllib so the module stays dependency-free (we never pip install here).
try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except ImportError:  # pragma: no cover - venv has requests
    import urllib.error
    import urllib.request
    _HAS_REQUESTS = False


# Minimal OpenAI-chat-shaped response for DSPy's legacy forward contract
# (DSPy 3.3 dropped litellm; _process_completion only reads .choices[].message.content).
# Deliberate duplication of {claude,openrouter}_lm.py's dataclasses to keep this
# module self-contained — the LM backends stay decoupled.
@dataclass
class _Msg:
    content: str
    role: str = "assistant"
    tool_calls = None
    reasoning_content = None


@dataclass
class _Choice:
    message: _Msg
    index: int = 0
    finish_reason: str = "stop"


@dataclass
class _Resp:
    choices: list
    model: str
    usage: dict = field(default_factory=dict)
    cache_hit: bool = False
    _hidden_params: dict = field(default_factory=dict)


class StudentLM(dspy.BaseLM):
    def __init__(self, model: str = STUDENT_MODEL, port: int = STUDENT_PORT,
                 base_url: str | None = None, temperature: float = 0.0,
                 max_tokens: int = 4096, **kwargs):
        # cache=False: same rationale as the teacher LMs (no silent cache divergence).
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens,
                         cache=False, **kwargs)
        # Kept as explicit attrs: DSPy's adapters call the LM without forwarding
        # these through kwargs, so forward() reads them off the instance.
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.base_url = (base_url or f"http://localhost:{port}").rstrip("/")

    def forward(self, prompt=None, messages=None, **kwargs):
        # Native pass-through: the messages array goes to the server AS-IS (no
        # _split flattening) so ChatAdapter's system/demo/user turns survive.
        if messages is None:
            messages = [{"role": "user", "content": prompt or ""}]
        text, resp_model = self._call_api(
            messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        # Local model: no meter -> cost 0.0 (kept in lm.history for uniform accounting).
        return _Resp(choices=[_Choice(message=_Msg(content=text))], model=resp_model,
                     _hidden_params={"response_cost": 0.0})

    # --- helpers ---------------------------------------------------------

    def _call_api(self, messages, temperature, max_tokens):
        url = self.base_url + _CHAT_PATH
        headers = {"Content-Type": "application/json"}
        body = {
            "model": self.model,  # MLX servers may ignore this; harmless to send.
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # One simple retry: a local server only ever 5xx's transiently (loading, OOM).
        status, text = self._post_once(url, headers, body)
        if status is not None and status >= 500:
            print(f"[StudentLM] retry once (HTTP {status})")
            time.sleep(1)
            status, text = self._post_once(url, headers, body)
        if status is None or status >= 400:
            raise RuntimeError(f"StudentLM request failed (status {status}): {text[:500]}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise RuntimeError(f"StudentLM non-JSON body (status {status}): {text[:500]}")

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"StudentLM returned no choices: {str(data)[:500]}")
        content = (choices[0].get("message") or {}).get("content") or ""
        return content, data.get("model", self.model)

    @staticmethod
    def _post_once(url, headers, body):
        """One POST. Returns (status|None, text). status is None on a transport error."""
        if _HAS_REQUESTS:
            try:
                r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
                return r.status_code, r.text
            except Exception as e:  # network/timeout
                return None, f"{type(e).__name__}: {str(e)[:300]}"
        payload = json.dumps(body).encode()
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(errors="replace")
        except Exception as e:  # network/timeout
            return None, f"{type(e).__name__}: {str(e)[:300]}"


# ---- self-test (free, no model): a stdlib stub server on an ephemeral port ----

def selftest():
    import http.server
    import threading

    # A valid extractor chat completion (ChatAdapter parses the `extractions`
    # marker into list[Extraction]); the stub returns it for any request.
    canned = ('[[ ## extractions ## ]]\n'
              '[{"field_id": "full_name", "value": "Jordan Chen"}]\n\n'
              '[[ ## completed ## ]]')
    counter = {"server": 0, "global": 0}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            counter["server"] += 1
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            payload = json.dumps({
                "id": "stub", "model": "stub-student",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": canned}}],
                "usage": {},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *a):  # silence per-request stderr logging
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        lm = StudentLM(port=port)

        # 1) direct lm call: content round-trips, one history entry, cost 0.0.
        outputs = lm(messages=[{"role": "user", "content": "hi"}])
        assert outputs and outputs[0] == canned, outputs
        assert lm.history[-1]["cost"] == 0.0, lm.history[-1]["cost"]
        assert lm.history[-1]["outputs"] == outputs
        assert counter["server"] == 1, counter

        # 2) per-predictor override: global LM points elsewhere (a counter that
        # must stay 0); extract.lm = stub. The call must route to the stub.
        from .program import FormAssistant, assign_lms

        class _GlobalLM(dspy.BaseLM):
            def __init__(self):
                super().__init__(model="global-should-not-be-called", cache=False)

            def forward(self, prompt=None, messages=None, **kwargs):
                counter["global"] += 1
                return _Resp(choices=[_Choice(message=_Msg(content=canned))],
                             model="global", _hidden_params={"response_cost": 0.0})

        dspy.configure(lm=_GlobalLM())
        program = FormAssistant()
        assign_lms(program, extract_lm=lm)
        before = counter["server"]
        pred = program.extract(form_schema="(schema)", filled_fields="(none)",
                               recent_history="(none)", user_message="I'm Jordan Chen")
        assert counter["server"] == before + 1, counter          # stub was hit
        assert counter["global"] == 0, counter                    # override respected
        assert pred.extractions[0].field_id == "full_name", pred.extractions
        assert pred.extractions[0].value == "Jordan Chen", pred.extractions
    finally:
        srv.shutdown()
    print(f"selftest: all assertions passed (server calls={counter['server']}, "
          f"global calls={counter['global']})")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
