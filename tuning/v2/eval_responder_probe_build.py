"""eval_responder_probe_build.py — generalized responder-probe builder (successor to
eval_responder_chitchat_build). Builds a probe case file for ANY inject behavior from
its injection run dir, in the exact shape score_case consumes.

For a behavior whose realized directive depends on the live teacher extraction (notably
`clarify_answer`), pass --require-directive <kind>: the builder recomputes each turn's
directives (no LLM, shared eval_responder.recompute_cases_from_rows) and KEEPS only the
cases where that directive actually fired — a probe case must test what it claims.

  Selftest (free):  tuning/v2/.venv/bin/python -m tuning.v2.eval_responder_probe_build --selftest
  Build:            tuning/v2/.venv/bin/python -m tuning.v2.eval_responder_probe_build \
                        --run <inject_run> --behavior clarify_answer --require-directive clarify \
                        --out tuning/v2/eval/eval_responder_clarify_probe.jsonl
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .schema import load_schema
from . import eval_responder as ER

V2_DIR = Path(__file__).resolve().parent
RUN_DIR = V2_DIR / "datagen_runs"
EVAL_DIR = V2_DIR / "eval"
SESSION_LO, SESSION_HI = 147, 161


def _load(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()]


def build_probe_cases(run_dir: Path, behavior: str, require_directive: str | None = None,
                      schema=None):
    """(cases, stats). Session gate 147-161 enforced. Deterministic (row order)."""
    schema = schema or load_schema()
    snaps = {(s["session"], s["turn"]): s for s in _load(run_dir / "snapshots.jsonl")}
    rows = _load(run_dir / "train.jsonl")

    recs = ER.recompute_cases_from_rows(rows, snaps, schema, only_behavior=behavior)
    cases: list[dict] = []
    filtered = 0
    diags: list = []
    for rec in recs:
        if rec["diag"] == "no-snapshot":
            raise SystemExit(f"[probe] {behavior}: inject row references a missing snapshot "
                             f"({rec['session']},{rec['turn']}) — not building.")
        if rec["diag"]:
            diags.append((rec["diag"], rec["session"], rec["turn"]))
        if not (SESSION_LO <= rec["session"] <= SESSION_HI):
            raise SystemExit(f"[probe] build gate: session {rec['session']} outside "
                             f"{SESSION_LO}-{SESSION_HI} — not building.")
        kinds = [d[0] for d in rec["directives"]]
        if require_directive is not None and require_directive not in kinds:
            filtered += 1
            continue
        cases.append({
            "session": rec["session"], "turn": rec["turn"],
            "user_message": rec["user_message"], "form_state": rec["form_state"],
            "actions": rec["actions"], "directives": ER.jsonable_directives(rec["directives"]),
            "completion": rec["row"]["completion"],
            "teacher_completion": rec["row"]["completion"],
        })

    stats = {
        "behavior": behavior,
        "require_directive": require_directive,
        "responder_rows": len(recs),
        "cases": len(cases),
        "filtered_out": filtered,
        "sessions": sorted({c["session"] for c in cases}),
        "directive_kinds": dict(Counter(d[0] for c in cases for d in c["directives"])),
        "diags": diags,
    }
    return cases, stats


def gate_sessions(cases: list[dict]) -> None:
    bad = sorted({c["session"] for c in cases if not (SESSION_LO <= c["session"] <= SESSION_HI)})
    if bad:
        raise ValueError(f"probe gate: sessions outside {SESSION_LO}-{SESSION_HI}: {bad}")


def serialize(cases: list[dict]) -> str:
    return "".join(json.dumps(c) + "\n" for c in cases)


def build(run_dir: Path, behavior: str, require_directive: str | None, out_path: Path) -> dict:
    cases, stats = build_probe_cases(run_dir, behavior, require_directive)
    gate_sessions(cases)
    out_path.write_text(serialize(cases))
    print(f"wrote {stats['cases']} probe cases ({behavior}"
          f"{', require '+require_directive if require_directive else ''}) -> {out_path}")
    print(f"  responder rows: {stats['responder_rows']}  kept: {stats['cases']}  "
          f"filtered (directive not realized): {stats['filtered_out']}")
    if stats["sessions"]:
        print(f"  sessions: {stats['sessions'][0]}..{stats['sessions'][-1]} (all in {SESSION_LO}-{SESSION_HI})")
    print(f"  directive kinds: {stats['directive_kinds']}")
    if stats["diags"]:
        print(f"  recompute diags: {stats['diags'][:5]}")
    return stats


# ---- selftest (offline, synthetic inject rows) -------------------------------

def _synth_run(tmp: Path, entries):
    """entries: list of (session, turn, pending, inj_msg, ext_completion|None, resp_completion).
    ext None => prestep-handled (no extractor row). Writes snapshots + train.jsonl."""
    with open(tmp / "snapshots.jsonl", "w") as f:
        seen = set()
        for sess, turn, pend, *_ in entries:
            if (sess, turn) in seen:
                continue
            seen.add((sess, turn))
            f.write(json.dumps({"session": sess, "turn": turn, "form_state": {}, "pending": pend,
                                "history": [], "user_message": "orig farm msg"}) + "\n")

    def row(module, completion, inj_msg, ref, behavior):
        usr = (f"[[ ## form_schema ## ]]\nF\n\n[[ ## filled_fields ## ]]\n(none)\n\n"
               f"[[ ## recent_history ## ]]\n(none)\n\n[[ ## user_message ## ]]\n{inj_msg}\n\n"
               f"[[ ## actions_taken ## ]]\n(no actions this turn)\n\n[[ ## guidance ## ]]\ng\n\n"
               f"[[ ## completed ## ]]")
        return {"module": module, "source": "inject", "behavior": behavior, "session": None,
                "turn": None, "snapshot": ref, "well_formed": True, "completion": completion,
                "messages": [{"role": "system", "content": "S"}, {"role": "user", "content": usr}]}
    with open(tmp / "train.jsonl", "w") as f:
        for sess, turn, pend, inj_msg, ext, resp, beh in entries:
            ref = {"session": sess, "turn": turn}
            if ext is not None:
                f.write(json.dumps(row("extractor", ext, inj_msg, ref, beh)) + "\n")
            f.write(json.dumps(row("responder", resp, inj_msg, ref, beh)) + "\n")


def selftest() -> bool:
    import tempfile
    checks: list[tuple[str, bool]] = []

    def ck(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    schema = load_schema()
    RESP = "[[ ## response_text ## ]]\nSure — and what's your date of birth?\n\n[[ ## completed ## ]]"
    EMPTY_EXT = "[[ ## extractions ## ]]\n[]\n\n[[ ## completed ## ]]"
    CLARIFY_EXT = ('[[ ## extractions ## ]]\n[{"field_id": "country_citizenship", '
                   '"value": "a small island nation"}]\n\n[[ ## completed ## ]]')

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # chitchat_steer: reask_pending; clarify_answer: one case where clarify FIRED
        # (non-matching value on the large select) and one where it did NOT (empty ext ->
        # reask_pending) — the require filter must drop the second.
        _synth_run(tmp, [
            (150, 8, "dob", "Hey, how's your day?", EMPTY_EXT, RESP, "chitchat_steer"),
            (151, 3, "country_citizenship", "A small island nation.", CLARIFY_EXT, RESP, "clarify_answer"),
            (152, 5, "country_citizenship", "Hard to say, honestly.", EMPTY_EXT, RESP, "clarify_answer"),
        ])
        cc, cstats = build_probe_cases(tmp, "chitchat_steer", schema=schema)
        ck("chitchat: one case, reask_pending realized", cstats["cases"] == 1
           and cstats["directive_kinds"].get("reask_pending") == 1)

        cl_all, _ = build_probe_cases(tmp, "clarify_answer", schema=schema)
        ck("clarify (no filter): both responder rows become cases", len(cl_all) == 2)
        cl, clstats = build_probe_cases(tmp, "clarify_answer", require_directive="clarify", schema=schema)
        ck("clarify (require clarify): only the case where clarify FIRED is kept",
           clstats["cases"] == 1 and clstats["filtered_out"] == 1)
        ck("every kept clarify case actually has a clarify directive",
           all(any(d[0] == "clarify" for d in c["directives"]) for c in cl))
        ck("kept case carries the injected user_message + score_case shape",
           cl[0]["user_message"] == "A small island nation." and
           {"session", "turn", "user_message", "form_state", "actions", "directives",
            "completion", "teacher_completion"} <= set(cl[0]))
        s = ER.score_case(cl[0], schema)
        ck("score_case consumes a probe case", set(s["checks"]) ==
           {"format", "directive", "grounding", "echo", "verbosity", "repetition"})
        ck("session gate passes", gate_sessions(cl) is None)
        cl2, _ = build_probe_cases(tmp, "clarify_answer", require_directive="clarify", schema=schema)
        ck("deterministic (byte-identical)", serialize(cl) == serialize(cl2))

        # reproduces the chitchat builder's output on the same rows
        from . import eval_responder_chitchat_build as CB
        cb_cases, _ = CB.build_probe_cases(tmp, schema=schema)
        ck("reproduces eval_responder_chitchat_build output for chitchat_steer",
           serialize(cb_cases) == serialize(cc))

        # gate rejects a smuggled out-of-range session
        _synth_run(tmp, [(146, 1, "dob", "hi", EMPTY_EXT, RESP, "chitchat_steer")])
        raised = False
        try:
            build_probe_cases(tmp, "chitchat_steer", schema=schema)
        except SystemExit:
            raised = True
        ck("build gate raises on a session outside 147-161", raised)

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n=== eval_responder_probe_build selftest: {passed}/{len(checks)} checks passed ===")
    return passed == len(checks)


def main():
    ap = argparse.ArgumentParser(description="Build a responder probe file for a given inject behavior.")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--run", help="inject run dir (train.jsonl + snapshots.jsonl)")
    ap.add_argument("--behavior", help="inject behavior name to build a probe from")
    ap.add_argument("--require-directive", default="", help="keep only cases where this directive fired "
                    "(e.g. 'clarify' for clarify_answer). Omit to keep all.")
    ap.add_argument("--out", default="", help="output jsonl (default eval/eval_responder_<behavior>_probe.jsonl)")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if not args.run or not args.behavior:
        ap.error("--run and --behavior are required (unless --selftest)")
    run_dir = Path(args.run) if "/" in args.run else (RUN_DIR / args.run)
    out = Path(args.out) if args.out else (EVAL_DIR / f"eval_responder_{args.behavior}_probe.jsonl")
    build(run_dir, args.behavior, args.require_directive or None, out)


if __name__ == "__main__":
    main()
