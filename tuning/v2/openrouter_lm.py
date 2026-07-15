"""OpenRouterLM — a DSPy LM that runs the teacher via the OpenRouter chat API.

Motivation (M4_PLAN Pilot1, 2026-07-10/13): the `claude -p` CLI teacher drifted
under the bare `sonnet` alias, has no temperature control, and — because
ClaudeLM._split flattens the messages array into one prompt string — broke
few-shot demo rendering and marker compliance. The OpenRouter API path fixes all
three: a pinned model id, temperature=0 (deterministic teacher), and the DSPy
messages array is passed through NATIVELY (no flattening), so multi-turn demos
render as real user/assistant pairs.

The default model `nvidia/nemotron-3-ultra-550b-a55b:free` is free ($0).

Caching is OFF deliberately, same rationale as ClaudeLM: the v1 silent
response-cache divergence (doc-12 Exp 12) is the kind of artifact we don't want
masking teacher behavior.

Env: V2_OR_TEACHER_MODEL (default nemotron free), V2_OR_TIMEOUT (s, default 180),
OPENROUTER_API_KEY (required at call time).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import json
import os
import time

import dspy

OR_TEACHER_MODEL = os.getenv("V2_OR_TEACHER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
TIMEOUT = int(os.getenv("V2_OR_TIMEOUT", "180"))
API_URL = "https://openrouter.ai/api/v1/chat/completions"
# HTTP statuses worth retrying on the free tier (rate limit + transient server).
_RETRY_STATUS = {429, 500, 502, 503, 504}
_BACKOFF = [2, 8, 30]  # 4 tries total: initial + these sleeps

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
# Deliberate duplication of claude_lm.py's dataclasses to keep this module
# self-contained — the two teacher backends stay decoupled.
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


class OpenRouterLM(dspy.BaseLM):
    def __init__(self, model: str = OR_TEACHER_MODEL, temperature: float = 0.0,
                 max_tokens: int = 4096, **kwargs):
        # cache=False: same rationale as ClaudeLM (no silent cache divergence).
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens,
                         cache=False, **kwargs)
        # Kept as explicit attrs: DSPy's adapters call the LM without forwarding
        # these through kwargs, so forward() reads them off the instance.
        self.temperature = temperature
        self.max_tokens = max_tokens

    def forward(self, prompt=None, messages=None, **kwargs):
        # Native pass-through: the messages array goes to the API AS-IS (no
        # _split flattening) so ChatAdapter's system/demo/user turns survive.
        if messages is None:
            messages = [{"role": "user", "content": prompt or ""}]
        text, cost, usage, resp_model = self._call_api(
            messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        # response_cost is picked up by DSPy and stored per-call in lm.history.
        return _Resp(choices=[_Choice(message=_Msg(content=text))], model=resp_model,
                     usage=usage, _hidden_params={"response_cost": cost})

    # --- helpers ---------------------------------------------------------

    def _call_api(self, messages, temperature, max_tokens):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set in the environment")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            # usage.include -> the response carries usage.cost for per-call cost.
            "usage": {"include": True},
        }
        # _post_with_retry owns error handling now: it retries retryable HTTP AND
        # error-in-body failures in one loop, and raises non-retryable body errors.
        data = self._post_with_retry(headers, body)
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"OpenRouter returned no choices: {str(data)[:500]}")

        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if not content:
            # Reasoning models: never substitute the reasoning trace for content.
            if msg.get("reasoning"):
                print("[OpenRouterLM] warning: empty content but reasoning present; "
                      "returning empty content (reasoning ignored)")
            content = ""
        usage = data.get("usage") or {}
        cost = usage.get("cost") or 0.0
        return content, float(cost), usage, data.get("model", self.model)

    def _post_with_retry(self, headers, body):
        """POST with exponential backoff on 429/5xx, honoring Retry-After. Retries
        cover BOTH HTTP-level failures AND OpenRouter's error-in-body case — an
        HTTP 200 whose JSON body carries {"error": {"code": 429/5xx, ...}} (an
        upstream ResourceExhausted lost a Pilot2 farm session). Non-retryable body
        errors raise immediately; retryable ones share this loop."""
        last_err = None
        for attempt in range(len(_BACKOFF) + 1):
            retry_after = None
            try:
                status, text, retry_after = self._post_once(headers, body)
            except Exception as e:  # network/timeout
                last_err = f"{type(e).__name__}: {str(e)[:300]}"
                status, text = None, ""
            if status is not None and status not in _RETRY_STATUS:
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    raise RuntimeError(f"OpenRouter non-JSON body (status {status}): {text[:500]}")
                err = data.get("error") if isinstance(data, dict) else None
                if not err:
                    return data
                # error-in-body: retry only if the body error code is retryable.
                try:
                    code = int(err.get("code"))  # handles 502 and "502"
                except (TypeError, ValueError):
                    code = None  # unparseable code -> non-retryable
                if code not in _RETRY_STATUS:
                    raise RuntimeError(f"OpenRouter error: {str(err)[:500]}")
                last_err = f"body error {code}: {str(err.get('message'))[:300]}"
            elif status is not None:  # a retry-status HTTP response
                last_err = f"HTTP {status}: {text[:300]}"
            # retryable: an exception, a retry-status HTTP, or a retryable body error
            if attempt < len(_BACKOFF):
                delay = retry_after if retry_after is not None else _BACKOFF[attempt]
                print(f"[OpenRouterLM] retry {attempt + 1}/{len(_BACKOFF)} in {delay}s ({last_err})")
                time.sleep(delay)
        raise RuntimeError(f"OpenRouter request failed after {len(_BACKOFF) + 1} tries: {last_err}")

    @staticmethod
    def _post_once(headers, body):
        """One POST. Returns (status, text, retry_after_seconds|None)."""
        if _HAS_REQUESTS:
            r = requests.post(API_URL, headers=headers, json=body, timeout=TIMEOUT)
            ra = r.headers.get("Retry-After")
            return r.status_code, r.text, (int(ra) if ra and ra.isdigit() else None)
        payload = json.dumps(body).encode()
        req = urllib.request.Request(API_URL, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.status, resp.read().decode(), None
        except urllib.error.HTTPError as e:
            ra = e.headers.get("Retry-After") if e.headers else None
            return e.code, e.read().decode(errors="replace"), (int(ra) if ra and ra.isdigit() else None)
