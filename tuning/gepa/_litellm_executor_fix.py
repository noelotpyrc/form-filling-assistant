"""Workaround for LiteLLM module-level ThreadPoolExecutor getting shut down
during DSPy's parallel evaluation (Python 3.13 + LiteLLM 1.82.6 + DSPy 3.1.3).

Symptom (without this patch):
    File "litellm/utils.py", line 1661, in wrapper
        executor.submit(ctx.run, logging_obj.success_handler, ...)
    RuntimeError: cannot schedule new futures after shutdown

LiteLLM uses a module-level `executor = ThreadPoolExecutor(...)` to dispatch
the post-call `success_handler` log call. When dspy.Evaluate runs metrics
across many threads, Python 3.13's cleanup at some point shuts down that
global executor; subsequent calls then fail at the executor.submit line,
which propagates up as a failed LLM call (silently zeroed by DSPy via
failure_score=0.0). This corrupts evals.

Import this module BEFORE creating any DSPy LM or running compile/eval:

    import tuning.gepa._litellm_executor_fix  # noqa: F401  (apply patch)

The patch:
  - Replaces `litellm.litellm_core_utils.thread_pool_executor.executor` AND
    `litellm.utils.executor` with a `_ResilientExecutor` wrapper.
  - On `.submit()`, the wrapper checks `_shutdown` and transparently re-creates
    the underlying ThreadPoolExecutor if needed. Forward-compatible for any
    other method litellm calls (e.g. `.shutdown`).
"""

from __future__ import annotations

import concurrent.futures
import sys
import threading


class _ResilientExecutor:
    """ThreadPoolExecutor wrapper that auto-revives on shutdown."""

    def __init__(self, max_workers: int = 100) -> None:
        self._max_workers = max_workers
        self._lock = threading.Lock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._revival_count = 0  # diagnostic

    def _ensure_alive(self) -> concurrent.futures.ThreadPoolExecutor:
        ex = self._executor
        if getattr(ex, "_shutdown", False):
            with self._lock:
                if getattr(self._executor, "_shutdown", False):
                    self._revival_count += 1
                    sys.stderr.write(
                        f"[_litellm_executor_fix] revived litellm executor "
                        f"(revival #{self._revival_count})\n"
                    )
                    sys.stderr.flush()
                    self._executor = concurrent.futures.ThreadPoolExecutor(
                        max_workers=self._max_workers,
                        thread_name_prefix="litellm-resilient",
                    )
                ex = self._executor
        return ex

    def submit(self, fn, /, *args, **kwargs):
        ex = self._ensure_alive()
        return ex.submit(fn, *args, **kwargs)

    def map(self, fn, *iterables, timeout=None, chunksize=1):
        ex = self._ensure_alive()
        return ex.map(fn, *iterables, timeout=timeout, chunksize=chunksize)

    def shutdown(self, wait=True, *, cancel_futures=False):
        return self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)

    def __getattr__(self, name):
        # Fall through to the underlying executor for any other access.
        return getattr(self._executor, name)


def apply() -> _ResilientExecutor:
    """Install the resilient executor in both litellm namespaces. Idempotent.

    Returns the installed _ResilientExecutor for diagnostic introspection.
    """
    import litellm.litellm_core_utils.thread_pool_executor as ltpe
    import litellm.utils as lu

    if isinstance(ltpe.executor, _ResilientExecutor):
        return ltpe.executor  # already patched

    resilient = _ResilientExecutor(max_workers=getattr(ltpe, "MAX_THREADS", 100))
    ltpe.executor = resilient
    lu.executor = resilient
    sys.stderr.write(
        "[_litellm_executor_fix] installed resilient executor in "
        "litellm.litellm_core_utils.thread_pool_executor and litellm.utils\n"
    )
    sys.stderr.flush()
    return resilient


# Apply on import so module clients only need `import tuning.gepa._litellm_executor_fix`
apply()
