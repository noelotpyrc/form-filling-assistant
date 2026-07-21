"""Render a datagen run's farm-session conversations as one self-contained HTML.

Offline, stdlib-only. Conversation = last snapshot's `history` + its
`user_message` + the session's final assistant reply (last farm/responder
completion, markers stripped).
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

from .program import strip_markers

CSS = """
body{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#f4f5f7;
  color:#1a1a1a;margin:0;padding:24px;line-height:1.5}
h1{font-size:20px}
.session{max-width:820px;margin:0 auto 40px;background:#fff;border-radius:12px;
  padding:16px 20px;box-shadow:0 1px 4px rgba(0,0,0,.1)}
.shead{font-size:14px;color:#444;border-bottom:1px solid #eee;padding-bottom:10px;margin-bottom:14px}
.row{display:flex;margin:8px 0}
.row.user{justify-content:flex-end}
.row.assistant{justify-content:flex-start}
.bubble{max-width:78%;padding:8px 12px;border-radius:14px;white-space:pre-wrap;
  word-break:break-word;font-size:13px}
.user .bubble{background:#2563eb;color:#fff;border-bottom-right-radius:4px}
.assistant .bubble{background:#e9ebef;color:#111;border-bottom-left-radius:4px}
.event{text-align:center;margin:8px 0}
.event span{background:#e0e0e0;color:#555;font-size:11px;padding:3px 10px;border-radius:12px}
details{margin-top:14px;font-size:12px}
summary{cursor:pointer;color:#555}
pre{background:#1e1e2e;color:#dcdce4;padding:12px;border-radius:8px;overflow:auto;font-size:12px}
"""


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _msg_html(role: str, content: str) -> str:
    # user turns opening with [system] are UI events (button clicks), not chat
    if role == "user" and content.lstrip().startswith("[system]"):
        return f'<div class="event"><span>{html.escape(content)}</span></div>'
    return (f'<div class="row {role}"><div class="bubble">'
            f'{html.escape(content)}</div></div>')


def _final_reply(rows: list[dict], session: int) -> str:
    # last farm/responder row of the session, by turn
    r = [x for x in rows if x.get("module") == "responder"
         and x.get("source") == "farm" and x.get("session") == session]
    if not r:
        return ""
    r.sort(key=lambda x: x["turn"])
    return strip_markers(r[-1].get("completion", ""))


def _session_html(session: int, snaps: list[dict], rows: list[dict],
                  meta: dict | None) -> str:
    last = max(snaps, key=lambda s: s["turn"])
    # header line from report.json farm_sessions (degrade gracefully)
    if meta:
        hdr = (f"seed {meta.get('seed', session)} · style {meta.get('style', '?')}"
               f" · {meta.get('turns', '?')} turns · filled "
               f"{meta.get('filled', '?')}/{meta.get('required', '?')}"
               f"{' · complete' if meta.get('complete') else ''}")
    else:
        hdr = f"seed {session}"
    parts = [f'<div class="session"><div class="shead">Session {session} — {hdr}</div>']
    for m in last.get("history", []):
        parts.append(_msg_html(m["role"], m["content"]))
    if last.get("user_message"):
        parts.append(_msg_html("user", last["user_message"]))
    reply = _final_reply(rows, session)
    if reply:
        parts.append(_msg_html("assistant", reply))
    # final logged form_state = state BEFORE the last turn's update
    state = json.dumps(last.get("form_state", {}), indent=2, ensure_ascii=False)
    parts.append('<details><summary>final logged form_state</summary>'
                 f'<pre>{html.escape(state)}</pre></details></div>')
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    snaps = _load(a.run_dir / "snapshots.jsonl")
    if not snaps:
        print(f"no snapshots in {a.run_dir}", file=sys.stderr)
        return 1
    rows = _load(a.run_dir / "train.jsonl")
    report = a.run_dir / "report.json"
    meta_by_seed = {}
    if report.exists():
        for m in json.loads(report.read_text()).get("farm_sessions", []):
            meta_by_seed[m.get("seed")] = m

    sessions: dict[int, list] = {}
    for s in snaps:
        sessions.setdefault(s["session"], []).append(s)

    body = [_session_html(sid, sessions[sid], rows, meta_by_seed.get(sid))
            for sid in sorted(sessions)]
    doc = (f"<!doctype html><html><head><meta charset='utf-8'>"
           f"<title>{html.escape(a.run_dir.name)} transcript</title>"
           f"<style>{CSS}</style></head><body>"
           f"<h1>{html.escape(a.run_dir.name)} — {len(sessions)} session(s)</h1>"
           f"{''.join(body)}</body></html>")

    out = a.out or (a.run_dir / "transcript.html")
    out.write_text(doc)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
