"""eval_responder_chitchat_build.py — supplementary probe for the chitchat-steer-back
failure class (round-2 s2b: user small-talks while a field is pending; directive is
reask_pending; the student answered the pleasantry and never steered back).

Reads a `chitchat_steer` INJECTION run dir (datagen --inject --behaviors chitchat_steer
over the p4 eval snapshots):
  <run>/snapshots.jsonl  — the p4 snapshots (for the snapshot lookup + recent_history)
  <run>/train.jsonl      — the inject rows: each chitchat turn has an extractor row
                           (empty extraction) directly before its responder row.

For each inject responder row it rebuilds the case with the FIX-2 machinery — snapshot
lookup by the row's snapshot ref, user_message OVERRIDDEN with the injected pleasantry
(parsed from the row's own [[ ## user_message ## ]] block), extractor completion from
the paired inject extractor row (FIFO by (snapshot, behavior)) — then
recompute_actions_directives (prestep -> validate -> compose, no LLM) yields the
reask_pending turn. Emits one case per inject responder row in the exact shape
score_case consumes, plus (session, turn) and the teacher completion as reference.

Output: tuning/v2/eval/eval_responder_chitchat_probe.jsonl. Session gate 147-161 enforced
at build; deterministic given the inject run dir.

  Selftest (free):  tuning/v2/.venv/bin/python -m tuning.v2.eval_responder_chitchat_build --selftest
  Build:            tuning/v2/.venv/bin/python -m tuning.v2.eval_responder_chitchat_build --run <inject_run>
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .schema import load_schema
from . import eval_responder as ER

V2_DIR = Path(__file__).resolve().parent
RUN_DIR = V2_DIR / "datagen_runs"
EVAL_DIR = V2_DIR / "eval"
OUT_NAME = "eval_responder_chitchat_probe.jsonl"
SESSION_LO, SESSION_HI = 147, 161
BEHAVIOR = "chitchat_steer"


def _load(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()]


def _injected_user_message(user_content: str) -> str:
    m = re.search(r"\[\[ ## user_message ## \]\]\n(.*?)\n\n\[\[ ## ", user_content, re.DOTALL)
    return m.group(1) if m else ""


def build_probe_cases(run_dir: Path, schema=None):
    """(cases, stats). Raises on a session outside 147-161 (gate) or a missing snapshot."""
    schema = schema or load_schema()
    snaps = {(s["session"], s["turn"]): s for s in _load(run_dir / "snapshots.jsonl")}
    rows = _load(run_dir / "train.jsonl")

    pending_ext: dict = defaultdict(list)     # (snapshot_key, behavior) -> [ext completions] FIFO
    cases: list[dict] = []
    diags: list = []
    for r in rows:
        if r.get("source") != "inject" or r.get("behavior") != BEHAVIOR:
            continue
        ref = r.get("snapshot")
        gkey = ((ref["session"], ref["turn"]) if ref else None, r.get("behavior"))
        if r["module"] == "extractor":
            pending_ext[gkey].append(r["completion"])
            continue
        if r["module"] != "responder":
            continue
        # a chitchat responder turn -> a probe case
        exts = pending_ext[gkey]
        ext_completion = exts.pop(0) if exts else None
        inj_msg = _injected_user_message(r["messages"][-1]["content"])
        snap = snaps.get((ref["session"], ref["turn"])) if ref else None
        if snap is None:
            raise SystemExit(f"[probe] inject row references a missing snapshot {ref} — not building.")
        if not (SESSION_LO <= ref["session"] <= SESSION_HI):
            raise SystemExit(f"[probe] build gate: session {ref['session']} outside "
                             f"{SESSION_LO}-{SESSION_HI} — not building.")
        snap_over = {**snap, "user_message": inj_msg}
        actions, directives, fs, diag = ER.recompute_actions_directives(schema, snap_over, ext_completion)
        if diag:
            diags.append((diag, ref))
        cases.append({
            "session": ref["session"], "turn": ref["turn"],
            "user_message": inj_msg, "form_state": fs,
            "actions": actions, "directives": ER.jsonable_directives(directives),
            "completion": r["completion"],            # score_case scores this (the teacher reference)
            "teacher_completion": r["completion"],    # explicit reference label
        })

    dirset = Counter(d[0] for c in cases for d in c["directives"])
    stats = {
        "cases": len(cases),
        "sessions": sorted({c["session"] for c in cases}),
        "with_reask_pending": sum(1 for c in cases if any(d[0] == "reask_pending" for d in c["directives"])),
        "directive_kinds": dict(dirset),
        "diags": diags,
    }
    return cases, stats


def gate_sessions(cases: list[dict]) -> None:
    bad = sorted({c["session"] for c in cases if not (SESSION_LO <= c["session"] <= SESSION_HI)})
    if bad:
        raise ValueError(f"probe gate: sessions outside {SESSION_LO}-{SESSION_HI}: {bad}")


def serialize(cases: list[dict]) -> str:
    return "".join(json.dumps(c) + "\n" for c in cases)


def build(run_dir: Path, out_path: Path = None) -> dict:
    out_path = out_path or (EVAL_DIR / OUT_NAME)
    cases, stats = build_probe_cases(run_dir)
    gate_sessions(cases)
    out_path.write_text(serialize(cases))
    print(f"wrote {stats['cases']} probe cases -> {out_path}")
    print(f"  sessions: {stats['sessions'][0]}..{stats['sessions'][-1]} "
          f"(all in {SESSION_LO}-{SESSION_HI})" if stats["sessions"] else "  (no cases)")
    print(f"  with reask_pending: {stats['with_reask_pending']}/{stats['cases']}")
    print(f"  directive kinds: {stats['directive_kinds']}")
    if stats["diags"]:
        print(f"  recompute diags: {stats['diags'][:5]}")
    return stats


def selftest() -> bool:
    import tempfile
    checks: list[tuple[str, bool]] = []

    def ck(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    schema = load_schema()

    def inj_row(module, completion, inj_msg, ref, behavior=BEHAVIOR):
        usr = (f"[[ ## form_schema ## ]]\nForm\n\n[[ ## filled_fields ## ]]\n(none)\n\n"
               f"[[ ## recent_history ## ]]\n(none)\n\n[[ ## user_message ## ]]\n{inj_msg}\n\n"
               f"[[ ## actions_taken ## ]]\n(no actions this turn)\n\n[[ ## guidance ## ]]\ng\n\n"
               f"[[ ## completed ## ]]")
        return {"module": module, "source": "inject", "behavior": behavior, "session": None,
                "turn": None, "snapshot": ref, "well_formed": True, "completion": completion,
                "messages": [{"role": "system", "content": "S"}, {"role": "user", "content": usr}]}

    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        # two eval snapshots (147-161) with an unfilled pending field
        with open(run_dir / "snapshots.jsonl", "w") as f:
            for sess, turn, fld in [(150, 8, "dob"), (155, 4, "phone")]:
                f.write(json.dumps({"session": sess, "turn": turn, "form_state": {},
                                    "pending": fld, "history": [], "user_message": "orig farm msg"}) + "\n")
        MSG = "Hey there! How's your day going?"
        RESP = "[[ ## response_text ## ]]\nHaha, doing well! Now, what's your date of birth?\n\n[[ ## completed ## ]]"
        EXT = "[[ ## extractions ## ]]\n[]\n\n[[ ## completed ## ]]"
        rows = [
            inj_row("extractor", EXT, MSG, {"session": 150, "turn": 8}),
            inj_row("responder", RESP, MSG, {"session": 150, "turn": 8}),
            inj_row("extractor", EXT, "You're so helpful!", {"session": 155, "turn": 4}),
            inj_row("responder", RESP, "You're so helpful!", {"session": 155, "turn": 4}),
        ]
        with open(run_dir / "train.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

        cases, stats = build_probe_cases(run_dir, schema)
        ck("one case per inject responder row", stats["cases"] == 2)
        ck("every case carries the injected user_message (not the farm one)",
           all(c["user_message"] in (MSG, "You're so helpful!") for c in cases))
        ck("recompute yields reask_pending on every case", stats["with_reask_pending"] == 2)
        ck("case shape is score_case-consumable",
           all({"session", "turn", "user_message", "form_state", "actions", "directives",
                "completion", "teacher_completion"} <= set(c) for c in cases))
        ck("directives JSON-serialize", (json.dumps(cases) or True) is not None)
        s = ER.score_case(cases[0], schema)
        ck("score_case runs on a probe case", set(s["checks"]) ==
           {"format", "directive", "grounding", "echo", "verbosity", "repetition"})
        ck("session gate passes (all 147-161)", gate_sessions(cases) is None)
        # determinism
        cases2, _ = build_probe_cases(run_dir, schema)
        ck("two builds byte-identical", serialize(cases) == serialize(cases2))

        # gate rejects an out-of-range session (smuggle a 146 snapshot + row)
        with open(run_dir / "snapshots.jsonl", "a") as f:
            f.write(json.dumps({"session": 146, "turn": 1, "form_state": {}, "pending": "dob",
                                "history": [], "user_message": "x"}) + "\n")
        with open(run_dir / "train.jsonl", "a") as f:
            f.write(json.dumps(inj_row("extractor", EXT, MSG, {"session": 146, "turn": 1})) + "\n")
            f.write(json.dumps(inj_row("responder", RESP, MSG, {"session": 146, "turn": 1})) + "\n")
        raised = False
        try:
            build_probe_cases(run_dir, schema)
        except SystemExit:
            raised = True
        ck("build gate raises on a session outside 147-161", raised)

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n=== eval_responder_chitchat_build selftest: {passed}/{len(checks)} checks passed ===")
    return passed == len(checks)


def main():
    ap = argparse.ArgumentParser(description="Build the chitchat-steer-back probe set.")
    ap.add_argument("--selftest", action="store_true", help="offline, no model")
    ap.add_argument("--run", help="chitchat_steer injection run dir (holds train.jsonl + snapshots.jsonl)")
    ap.add_argument("--out", default="", help=f"output path (default eval/{OUT_NAME})")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if not args.run:
        ap.error("--run is required (unless --selftest)")
    run_dir = Path(args.run) if "/" in args.run else (RUN_DIR / args.run)
    build(run_dir, Path(args.out) if args.out else None)


if __name__ == "__main__":
    main()
