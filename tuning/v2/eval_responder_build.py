"""eval_responder_build.py — doc-20 chapter-1 item 4: frozen responder eval-set builder.

Reads the frozen substrate (seeds 147-161):
  datagen_runs/eval_farm_p4/snapshots.jsonl   — the turns
  datagen_runs/eval_farm_p4_recap/train.jsonl — extractor rows (temp-0, current prompt)
                                                 for pairs, and the recaptured teacher
                                                 responder completions.

For each snapshot it RECOMPUTES (actions, directives) deterministically — the shared
eval_responder.recompute_actions_directives (prestep -> validate -> compose, no LLM,
doc-20 item 4 "recompute them, don't trust a stale capture") — and emits one case in
the exact shape eval_responder.score_case consumes, plus the (session, turn) key and
the recaptured teacher completion (item 6 scores the teacher on these directly).

Output: tuning/v2/eval/eval_responder_set.jsonl (223 cases). Deterministic: two builds
are byte-identical. Build gate FAILS if any session falls outside 147-161.

  Selftest (free):  tuning/v2/.venv/bin/python -m tuning.v2.eval_responder_build --selftest
  Build:            tuning/v2/.venv/bin/python -m tuning.v2.eval_responder_build
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

SRC_RUN = "eval_farm_p4"          # seeds 147-161
SRC_RECAP = "eval_farm_p4_recap"
OUT_NAME = "eval_responder_set.jsonl"
SESSION_LO, SESSION_HI = 147, 161
EXPECT_CASES = 223


def _load(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()]


def build_cases(run: str = SRC_RUN, recap: str = SRC_RECAP, schema=None):
    """Return (cases, stats). Raises on any recompute source mismatch (a non-prestep
    turn missing its extractor row) or a snapshot with no recaptured teacher completion
    — per doc-20, stop and surface rather than emit a broken set."""
    schema = schema or load_schema()
    snaps = _load(RUN_DIR / run / "snapshots.jsonl")
    rows = _load(RUN_DIR / recap / "train.jsonl")
    ext_map = {(r["session"], r["turn"]): r["completion"] for r in rows if r["module"] == "extractor"}
    resp_map = {(r["session"], r["turn"]): r["completion"] for r in rows if r["module"] == "responder"}

    cases, diags, missing = [], [], []
    for snap in snaps:                                   # snapshot order == deterministic
        key = (snap["session"], snap["turn"])
        actions, directives, post_fs, diag = ER.recompute_actions_directives(
            schema, snap, ext_map.get(key))
        if diag:
            diags.append((key, diag))
        teacher = resp_map.get(key)
        if teacher is None:
            missing.append(key)
            continue
        cases.append({
            "session": snap["session"],
            "turn": snap["turn"],
            "user_message": snap.get("user_message", ""),
            "form_state": post_fs,
            "actions": actions,
            "directives": ER.jsonable_directives(directives),
            "completion": teacher,            # score_case scores this (the teacher baseline)
            "teacher_completion": teacher,    # same, explicitly labeled for item 6
        })

    if diags:
        raise SystemExit(f"[build] recompute source mismatch on {len(diags)} turn(s): {diags[:5]} — "
                         f"the recap extractor rows don't line up with the snapshots; not building.")
    if missing:
        raise SystemExit(f"[build] {len(missing)} snapshot(s) have no recaptured teacher completion: "
                         f"{missing[:5]} — incomplete recap; not building.")

    stats = {
        "cases": len(cases),
        "sessions": sorted({c["session"] for c in cases}),
        "by_turn_type": dict(Counter(ER.turn_type(c) for c in cases)),
        "prestep_handled": sum(1 for s in snaps if (s["session"], s["turn"]) not in ext_map),
    }
    return cases, stats


def gate_sessions(cases: list[dict], lo: int = SESSION_LO, hi: int = SESSION_HI) -> None:
    """Build gate: FAIL if any case's session falls outside [lo, hi]."""
    bad = sorted({c["session"] for c in cases if not (lo <= c["session"] <= hi)})
    if bad:
        raise ValueError(f"build gate: sessions outside {lo}-{hi} present: {bad}")


def serialize(cases: list[dict]) -> str:
    return "".join(json.dumps(c) + "\n" for c in cases)


def build(out_path: Path = None) -> dict:
    out_path = out_path or (EVAL_DIR / OUT_NAME)
    cases, stats = build_cases()
    gate_sessions(cases)
    if stats["cases"] != EXPECT_CASES:
        raise SystemExit(f"[build] expected {EXPECT_CASES} cases, got {stats['cases']}")
    out_path.write_text(serialize(cases))
    print(f"wrote {stats['cases']} cases -> {out_path}")
    print(f"  sessions: {stats['sessions'][0]}..{stats['sessions'][-1]} "
          f"(n={len(stats['sessions'])}, gate OK: all in {SESSION_LO}-{SESSION_HI})")
    print(f"  by_turn_type: {stats['by_turn_type']}")
    print(f"  prestep-handled turns (no extractor row): {stats['prestep_handled']}")
    return stats


def selftest() -> bool:
    checks: list[tuple[str, bool]] = []

    def ck(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    schema = load_schema()
    cases, stats = build_cases(schema=schema)

    ck(f"exactly {EXPECT_CASES} cases built", stats["cases"] == EXPECT_CASES)
    ck("every session in 147-161", all(SESSION_LO <= s <= SESSION_HI for s in stats["sessions"]))

    # build gate: passes clean, fails on a smuggled out-of-range session
    try:
        gate_sessions(cases)
        ck("gate PASSES on the clean set", True)
    except ValueError:
        ck("gate PASSES on the clean set", False)
    smuggled = cases[:3] + [{**cases[0], "session": 999}]
    try:
        gate_sessions(smuggled)
        ck("gate FAILS on a smuggled out-of-range session (999)", False)
    except ValueError as e:
        ck(f"gate FAILS on a smuggled out-of-range session (detected: {e})", True)

    # determinism: two builds byte-identical
    cases2, _ = build_cases(schema=schema)
    ck("two builds are byte-identical (deterministic)", serialize(cases) == serialize(cases2))

    # shape: JSON round-trips, carries the required keys, directives serializable
    need = {"session", "turn", "user_message", "form_state", "actions",
            "directives", "completion", "teacher_completion"}
    ck("each case carries the required keys", all(need <= set(c) for c in cases))
    try:
        json.dumps(cases)
        ck("all cases JSON-serializable (clarify payloads survive)", True)
    except TypeError:
        ck("all cases JSON-serializable (clarify payloads survive)", False)

    # a built case is consumable by score_case unchanged
    s = ER.score_case(cases[0], schema)
    ck("score_case consumes a built case (returns the 6 checks)",
       set(s["checks"]) == {"format", "directive", "grounding", "echo", "verbosity", "repetition"})

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n=== eval_responder_build selftest: {passed}/{len(checks)} checks passed ===")
    return passed == len(checks)


def main():
    ap = argparse.ArgumentParser(description="Build the frozen responder eval set (doc-20 item 4).")
    ap.add_argument("--selftest", action="store_true", help="offline, no model")
    ap.add_argument("--out", default="", help=f"output path (default eval/{OUT_NAME})")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    build(Path(args.out) if args.out else None)


if __name__ == "__main__":
    main()
