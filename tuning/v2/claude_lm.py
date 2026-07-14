"""ClaudeLM — a DSPy LM that runs the teacher via the `claude -p` CLI.

The whole repo authenticates through the Claude CLI (web app, sim,
judge_claude_headless.py), so the teacher uses it too rather than the API. This
keeps the teacher inside the same DSPy program the student will run — only the
LM swaps (doc-18 §4).

Caching is OFF deliberately: the v1 silent response-cache divergence
(doc-12 Exp 12) is exactly the kind of artifact we don't want masking teacher
behavior.

Env: CLAUDE_BIN, V2_TEACHER_MODEL (default sonnet), V2_TEACHER_FALLBACK,
V2_CLAUDE_TIMEOUT (s).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import json
import os
import subprocess

import dspy

CLAUDE_BIN = os.getenv("CLAUDE_BIN", "claude")
# Pinned (2026-07-13): the bare "sonnet" alias drifted under us (June runs = older
# sonnet; July = claude-sonnet-5, with different marker-format compliance). Pin the
# resolved id so eval/sim/serve stop floating; bump deliberately, then re-baseline.
TEACHER_MODEL = os.getenv("V2_TEACHER_MODEL", "claude-sonnet-5")
TEACHER_FALLBACK = os.getenv("V2_TEACHER_FALLBACK", "claude-sonnet-5")
TIMEOUT = int(os.getenv("V2_CLAUDE_TIMEOUT", "180"))


# Minimal OpenAI-chat-shaped response for DSPy's legacy forward contract
# (DSPy 3.3 dropped litellm; _process_completion only reads .choices[].message.content).
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


class ClaudeLM(dspy.BaseLM):
    def __init__(self, model: str = TEACHER_MODEL, fallback_model: str = TEACHER_FALLBACK, **kwargs):
        super().__init__(model=model, cache=False, **kwargs)
        self.fallback_model = fallback_model

    def forward(self, prompt=None, messages=None, **kwargs):
        system, user = self._split(prompt, messages)
        text, cost = self._call_cli(system, user)
        # response_cost is picked up by DSPy and stored per-call in lm.history
        return _Resp(choices=[_Choice(message=_Msg(content=text))], model=self.model,
                     _hidden_params={"response_cost": cost})

    # --- helpers ---------------------------------------------------------

    @staticmethod
    def _split(prompt, messages):
        """Flatten DSPy messages into (system_prompt, user_prompt). Non-system
        turns are concatenated with role markers so few-shot demos survive."""
        if messages:
            system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
            parts = []
            for m in messages:
                if m.get("role") == "system":
                    continue
                c = m.get("content", "")
                parts.append(c if m.get("role") == "user" else f"[assistant]\n{c}")
            return system, "\n\n".join(parts)
        return "", prompt or ""

    def _call_cli(self, system: str, user: str) -> tuple[str, float]:
        cmd = [CLAUDE_BIN, "-p", user, "--model", self.model, "--output-format", "json"]
        if self.fallback_model:
            cmd += ["--fallback-model", self.fallback_model]
        if system:
            cmd += ["--system-prompt", system]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
        if proc.returncode != 0:
            raise RuntimeError(f"claude failed rc={proc.returncode}: {proc.stderr[:500]}")
        data = json.loads(proc.stdout)
        if data.get("is_error"):
            raise RuntimeError(f"claude returned error: {str(data)[:500]}")
        return data.get("result", ""), float(data.get("total_cost_usd") or 0.0)
