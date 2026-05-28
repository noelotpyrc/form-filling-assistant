"""probe_runner.py — run probe scenarios against the local SFT harness.

Reads each `tuning/harness/probes/P*.md`, parses out the probe blocks
(form_state, conversation_history, user_message), POSTs each one to the
harness `/api/generate` endpoint twice, and writes a sibling result file
under `tuning/harness/probes/runs/` with the original probe content +
appended per-run module outputs and composed response.

Usage:

    # Run everything (all P*.md, 2 runs each)
    /path/to/.venv/bin/python tuning/harness/probe_runner.py

    # Just one phase
    /path/to/.venv/bin/python tuning/harness/probe_runner.py P1

    # Multiple phases
    /path/to/.venv/bin/python tuning/harness/probe_runner.py P1 P3 P5

    # More runs per probe
    /path/to/.venv/bin/python tuning/harness/probe_runner.py P1 --runs 3

Prereqs: harness running on :8200, mlx_vlm running on :8100.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROBES_DIR = PROJECT_ROOT / "tuning" / "harness" / "probes"
RUNS_DIR = PROBES_DIR / "runs"
LOGS_DIR = PROJECT_ROOT / "logs"
HARNESS_URL = "http://localhost:8200"
SCHEMA_PATH = PROJECT_ROOT / "packages" / "web-app" / "public" / "forms" / "masters-northfield.json"

DEFAULT_TEMPERATURES: list[float] = [0.0, 0.7]
TIMEOUT_S = 180


# ══════════════════════════════════════════════════════════════════════
# Markdown parsing
# ══════════════════════════════════════════════════════════════════════

H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
PROBE_TITLE_RE = re.compile(r"^(P\d+-ex\d+)\s+(?:—|--)\s+(.+)$")

# Match `**label**` followed by optional inline prose (parenthesized
# clarifications, italics, etc.) up to the colon, then the next fenced
# ```[json]? block.
LABELED_BLOCK_RE = re.compile(
    r"\*\*(\w+)\*\*[^\n:]*:[^\n]*\n+\s*```(?:json)?\s*\n(.*?)\n```",
    re.DOTALL,
)

# Match `**form_state** ... same ... PX-exY` references where the form_state
# is shorthand for "use this other probe's form_state". Lets us avoid
# duplicating large JSON blocks when probes share state. Tolerates a few
# words between "same" and the ID ("same comprehensive fill as P11-ex1").
REFERENCE_RE = re.compile(
    r"\*\*form_state\*\*[^\n]*?\bsame\b[^*\n)]*?(P\d+-ex\d+)",
    re.IGNORECASE,
)


def parse_probe_file(path: Path) -> list[dict]:
    """Extract probe records from one P*.md file."""
    text = path.read_text()
    headings = list(H2_RE.finditer(text))
    probes: list[dict] = []
    for i, m in enumerate(headings):
        next_start = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        section = text[m.start():next_start]
        title_line = m.group(1).strip()
        probe_match = PROBE_TITLE_RE.match(title_line)
        if not probe_match:
            continue   # not a probe (e.g. "## Notes on this batch")

        probe_id = probe_match.group(1)
        probe_title = probe_match.group(2).strip()

        blocks = {b.group(1): b.group(2) for b in LABELED_BLOCK_RE.finditer(section)}

        form_state = _safe_json(blocks.get("form_state"), default={}, label=f"{probe_id}.form_state")
        history = _safe_json(blocks.get("conversation_history"), default=[], label=f"{probe_id}.history")
        user_message = (blocks.get("user_message") or "").strip()

        # Detect "same as PX-exY" cross-reference if form_state has no inline JSON.
        form_state_ref = None
        if not form_state:
            ref_match = REFERENCE_RE.search(section)
            if ref_match:
                form_state_ref = ref_match.group(1)

        probes.append({
            "id": probe_id,
            "title": probe_title,
            "form_state": form_state,
            "form_state_ref": form_state_ref,
            "conversation_history": history,
            "user_message": user_message,
        })
    return probes


def resolve_form_state_refs(probe_files_to_probes: dict) -> None:
    """Mutate probes in place: where form_state is empty and form_state_ref is set,
    copy the referenced probe's form_state. Operates across all files."""
    by_id = {}
    for probes in probe_files_to_probes.values():
        for p in probes:
            by_id[p["id"]] = p
    for probes in probe_files_to_probes.values():
        for p in probes:
            if p["form_state"] or not p.get("form_state_ref"):
                continue
            ref = p["form_state_ref"]
            target = by_id.get(ref)
            if target and target["form_state"]:
                p["form_state"] = target["form_state"]
            else:
                print(f"  ⚠  {p['id']}: form_state ref '{ref}' could not be resolved",
                      file=sys.stderr)


def _safe_json(raw: str | None, *, default, label: str):
    if raw is None or not raw.strip():
        return default
    try:
        return json.loads(raw)
    except Exception as e:
        print(f"  ⚠  JSON parse error in {label}: {e}", file=sys.stderr)
        return default


# ══════════════════════════════════════════════════════════════════════
# Harness execution
# ══════════════════════════════════════════════════════════════════════

def run_probe_once(
    probe: dict, schema: dict, run_idx: int, temperature: float, augment_state: bool = False,
) -> dict:
    """POST one probe to /api/generate, return the run result."""
    aug_tag = "_aug" if augment_state else ""
    session_id = f"probe-{probe['id']}-r{run_idx}-t{temperature}{aug_tag}-{int(time.time())}"
    body = {
        "session_id": session_id,
        "user_message": probe["user_message"],
        "form_state": probe["form_state"],
        "form_schema": schema,
        "conversation_history": probe["conversation_history"],
        "temperature": temperature,
        "augment_state": augment_state,
    }
    t0 = time.time()
    resp = requests.post(
        f"{HARNESS_URL}/api/generate",
        json=body,
        stream=True,
        timeout=TIMEOUT_S,
    )

    composed_parts: list[str] = []
    event_type: str | None = None
    duration_ms: float | None = None
    error_msg: str | None = None

    for raw in resp.iter_lines(decode_unicode=True):
        if raw is None or raw == "":
            continue
        if raw.startswith("event: "):
            event_type = raw[7:].strip()
        elif raw.startswith("data: "):
            try:
                data = json.loads(raw[6:])
            except Exception:
                continue
            if event_type == "text":
                composed_parts.append(data.get("text", ""))
            elif event_type == "done":
                duration_ms = data.get("duration_ms")
            elif event_type == "error":
                error_msg = data.get("message")

    composed = "".join(composed_parts)
    if duration_ms is None:
        duration_ms = (time.time() - t0) * 1000

    # Pull module_outputs from the harness's session log (it writes one
    # `model_output` event per turn with all 5 modules' fields).
    module_outputs = _read_module_outputs(session_id)

    return {
        "session_id": session_id,
        "temperature": temperature,
        "duration_ms": duration_ms,
        "composed": composed,
        "module_outputs": module_outputs,
        "error": error_msg,
    }


def _read_module_outputs(session_id: str) -> dict:
    log_path = LOGS_DIR / f"session-{session_id}.jsonl"
    if not log_path.exists():
        return {}
    for line in log_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("type") == "model_output":
            return ev.get("module_outputs") or {}
    return {}


# ══════════════════════════════════════════════════════════════════════
# Result formatting
# ══════════════════════════════════════════════════════════════════════

ROUTE_FLAGS = ("has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit")


def _fmt_value(v) -> str:
    """Compact, readable rendering for inline values."""
    if isinstance(v, str):
        return json.dumps(v)
    return f"`{json.dumps(v, ensure_ascii=False)}`"


def format_run_block(run_idx: int, run: dict) -> str:
    mo = run.get("module_outputs") or {}
    err = run.get("error")
    dur_s = (run.get("duration_ms") or 0) / 1000
    temp = run.get("temperature")
    temp_str = f"temp={temp}" if temp is not None else "temp=default"

    lines = [f"### Run {run_idx} — {temp_str} — {dur_s:.1f}s", ""]

    if err:
        lines.append(f"> ❌ Error: {err}")
        lines.append("")
        return "\n".join(lines)

    # action_router
    lines.append("**action_router:**")
    for flag in ROUTE_FLAGS:
        lines.append(f"- `{flag}` = {_fmt_value(mo.get(flag))}")
    lines.append("")

    # text_responder
    lines.append("**text_responder:**")
    lines.append(f"- `response_text` = {_fmt_value(mo.get('response_text', ''))}")
    lines.append("")

    # data_extractor (conditional on has_new_data)
    if mo.get("has_new_data"):
        lines.append("**data_extractor:** _(triggered by `has_new_data`)_")
        lines.append(f"- `field_ids` = {_fmt_value(mo.get('field_ids', []))}")
        lines.append(f"- `field_values` = {_fmt_value(mo.get('field_values', []))}")
        lines.append("")

    # choice_builder (conditional on needs_choice)
    if mo.get("needs_choice"):
        lines.append("**choice_builder:** _(triggered by `needs_choice`)_")
        lines.append(f"- `question` = {_fmt_value(mo.get('question', ''))}")
        lines.append(f"- `options` = {_fmt_value(mo.get('options', []))}")
        lines.append("")

    # review_builder (conditional on wants_review)
    if mo.get("wants_review"):
        lines.append("**review_builder:** _(triggered by `wants_review`)_")
        lines.append(f"- `summary_title` = {_fmt_value(mo.get('summary_title', ''))}")
        lines.append(f"- `summary_content` = {_fmt_value(mo.get('summary_content', ''))}")
        lines.append("")

    # Composed final output
    lines.append("**Composed final output (what the browser receives):**")
    lines.append("```")
    lines.append(run.get("composed") or "")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def write_runs_file(input_path: Path, probe_runs: dict, out_path: Path) -> None:
    """Reproduce the input markdown verbatim, but append per-probe runs
    after each probe block (before the next H2 heading). Non-probe sections
    (preamble, Notes) are passed through unchanged."""
    text = input_path.read_text()
    headings = list(H2_RE.finditer(text))

    parts: list[str] = []
    if headings:
        parts.append(text[:headings[0].start()])
    else:
        parts.append(text)

    for i, m in enumerate(headings):
        next_start = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        section = text[m.start():next_start]
        title = m.group(1).strip()
        probe_match = PROBE_TITLE_RE.match(title)
        if probe_match:
            probe_id = probe_match.group(1)
            parts.append(section.rstrip() + "\n\n")
            runs = probe_runs.get(probe_id, [])
            for run_idx, run in enumerate(runs, 1):
                parts.append("---\n\n")
                parts.append(format_run_block(run_idx, run))
                parts.append("\n")
            parts.append("\n")
        else:
            parts.append(section)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(parts))


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "phases",
        nargs="*",
        help="Phase IDs to run (e.g. P1 P3 P5). Default: all P*.md files.",
    )
    parser.add_argument(
        "--temps",
        nargs="+",
        type=float,
        default=DEFAULT_TEMPERATURES,
        help=f"Sampling temperatures, one run per temp (default {DEFAULT_TEMPERATURES}).",
    )
    parser.add_argument(
        "--augment-state",
        action="store_true",
        help="Turn on doc-16 #3/#5 context enrichment (humanized filled/missing + group index hints) for these runs.",
    )
    args = parser.parse_args()

    if not SCHEMA_PATH.exists():
        print(f"Schema not found: {SCHEMA_PATH}", file=sys.stderr)
        return 1
    schema = json.loads(SCHEMA_PATH.read_text())

    # Quick health check before kicking off many requests.
    try:
        h = requests.get(f"{HARNESS_URL}/health", timeout=5)
        if not h.ok:
            print(f"Harness /health returned {h.status_code}", file=sys.stderr)
            return 2
    except Exception as e:
        print(f"Harness not reachable at {HARNESS_URL}: {e}", file=sys.stderr)
        return 2

    probe_files = sorted(PROBES_DIR.glob("P*.md"))
    # Skip the runs/ dir which would also match the glob
    probe_files = [p for p in probe_files if p.parent == PROBES_DIR]
    if args.phases:
        wanted = {p.upper() for p in args.phases}
        probe_files = [
            f for f in probe_files
            if f.stem.split("-")[0].upper() in wanted
        ]

    if not probe_files:
        print("No probe files matched.")
        return 1

    print(f"[probe_runner] {len(probe_files)} file(s), temps={args.temps} (one run per temp)")
    print(f"[probe_runner] harness: {HARNESS_URL}")
    print(f"[probe_runner] runs dir: {RUNS_DIR}")
    print()

    # Parse everything first so cross-probe form_state references resolve
    # (e.g., P1-ex5 says "form_state: same as P1-ex2"). We need ALL probe
    # files in the working set — even ones not requested for execution —
    # so references stay resolvable.
    all_files = sorted(p for p in PROBES_DIR.glob("P*.md") if p.parent == PROBES_DIR)
    probes_by_file_all = {f: parse_probe_file(f) for f in all_files}
    resolve_form_state_refs(probes_by_file_all)

    overall_t0 = time.time()
    for probe_file in probe_files:
        probes = probes_by_file_all[probe_file]
        print(f"── {probe_file.name}: {len(probes)} probe(s) ──")
        probe_runs: dict[str, list[dict]] = {}
        for probe in probes:
            print(f"  • {probe['id']}  {probe['title'][:50]}")
            runs: list[dict] = []
            for r, temp in enumerate(args.temps, 1):
                try:
                    run = run_probe_once(
                        probe, schema, r, temperature=float(temp),
                        augment_state=args.augment_state,
                    )
                    runs.append(run)
                    flags_summary = ",".join(
                        f for f in ROUTE_FLAGS if (run.get("module_outputs") or {}).get(f)
                    ) or "[none]"
                    err = " ❌" if run.get("error") else ""
                    print(f"      r{r} (temp={temp}): {run['duration_ms']/1000:.1f}s  flags={flags_summary}{err}")
                except Exception as e:
                    print(f"      r{r} (temp={temp}): ERROR {e}")
                    runs.append({"composed": "", "module_outputs": {}, "duration_ms": 0, "error": str(e), "temperature": float(temp)})
            probe_runs[probe["id"]] = runs

        out_path = RUNS_DIR / probe_file.name
        write_runs_file(probe_file, probe_runs, out_path)
        print(f"  → {out_path.relative_to(PROJECT_ROOT)}")
        print()

    print(f"[probe_runner] done in {time.time() - overall_t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
