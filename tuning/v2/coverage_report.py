"""coverage_report.py — doc-22 companion: the directive-kind x source coverage matrix.

Given a bridged run's SOURCE dir (train.jsonl + snapshots.jsonl — the sft_data reshaped
rows drop the directives, so directive kinds are RECOMPUTED here, once, via the shared
eval_responder.recompute_cases_from_rows) and any set of eval/probe case files, prints:

  - per directive kind: training-row count and eval/probe-case count
  - per inject behavior: its rows broken down by realized directive kind
  - a zero-coverage flag for any REACHABLE directive kind with no training AND no eval
    coverage (the gap the matrix review is meant to surface).

  Selftest (free):  tuning/v2/.venv/bin/python -m tuning.v2.coverage_report --selftest
  Run:              tuning/v2/.venv/bin/python -m tuning.v2.coverage_report \
                        --run datagen_runs/responder_s2b_merged \
                        --eval eval/eval_responder_set.jsonl eval/eval_responder_chitchat_probe.jsonl
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .schema import load_schema
from . import eval_responder as ER

V2_DIR = Path(__file__).resolve().parent
RUN_DIR = V2_DIR / "datagen_runs"

# directive kinds compose can emit (doc-18.1) — the reachable set we check for gaps.
REACHABLE = ["ack", "fix", "clarify", "reask_pending", "ask_target", "submit_blocked",
             "terminal", "dormant_set"]
NATURAL = "(none/natural)"


def _load(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()]


def _kinds(directives) -> set:
    return {d[0] for d in directives} or {NATURAL}


def compute(run_dir: Path | None, eval_files: list[Path], schema=None) -> dict:
    schema = schema or load_schema()
    train_kind: Counter = Counter()
    by_source: Counter = Counter()
    inject_by_beh: dict = defaultdict(Counter)
    no_snapshot = 0
    if run_dir is not None:
        snaps = {(s["session"], s["turn"]): s for s in _load(run_dir / "snapshots.jsonl")}
        recs = ER.recompute_cases_from_rows(_load(run_dir / "train.jsonl"), snaps, schema)
        for rec in recs:
            if rec["directives"] is None:
                no_snapshot += 1
                continue
            ks = _kinds(rec["directives"])
            for k in ks:
                train_kind[k] += 1
            by_source[rec["source"]] += 1
            if rec["source"] == "inject":
                for k in ks:
                    inject_by_beh[rec["behavior"]][k] += 1

    eval_kind: Counter = Counter()
    eval_by_file: dict = {}
    for ef in eval_files:
        fc: Counter = Counter()
        for c in _load(ef):
            for k in _kinds(c["directives"]):
                eval_kind[k] += 1
                fc[k] += 1
        eval_by_file[ef.name] = dict(fc)

    all_kinds = list(dict.fromkeys(REACHABLE + sorted(set(train_kind) | set(eval_kind))))
    zero_cov = [k for k in REACHABLE if train_kind.get(k, 0) == 0 and eval_kind.get(k, 0) == 0]
    return {
        "kinds": all_kinds,
        "train_kind": dict(train_kind),
        "eval_kind": dict(eval_kind),
        "by_source": dict(by_source),
        "inject_by_behavior": {b: dict(c) for b, c in inject_by_beh.items()},
        "eval_by_file": eval_by_file,
        "zero_coverage_reachable": zero_cov,
        "no_snapshot_rows": no_snapshot,
    }


def print_report(rep: dict) -> None:
    print("=== directive-kind x source coverage ===")
    print(f"  {'directive kind':16} {'training':>9} {'eval/probe':>11}")
    for k in rep["kinds"]:
        t, e = rep["train_kind"].get(k, 0), rep["eval_kind"].get(k, 0)
        flag = "  <-- ZERO COVERAGE" if k in rep["zero_coverage_reachable"] else ""
        print(f"  {k:16} {t:>9} {e:>11}{flag}")
    print(f"\n  training rows by source: {rep['by_source']}"
          + (f"  (+{rep['no_snapshot_rows']} unjoinable)" if rep["no_snapshot_rows"] else ""))
    if rep["inject_by_behavior"]:
        print("\n  inject behaviors by realized directive kind:")
        for beh, c in sorted(rep["inject_by_behavior"].items()):
            print(f"    {beh:20} {c}")
    if rep["eval_by_file"]:
        print("\n  eval/probe files by directive kind:")
        for name, c in rep["eval_by_file"].items():
            print(f"    {name:44} {c}")
    if rep["zero_coverage_reachable"]:
        print(f"\n  !!! ZERO-COVERAGE reachable kinds: {rep['zero_coverage_reachable']}")
    else:
        print("\n  all reachable directive kinds have coverage.")


def selftest() -> bool:
    import tempfile
    checks: list[tuple[str, bool]] = []

    def ck(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    schema = load_schema()
    RESP = "[[ ## response_text ## ]]\nok\n\n[[ ## completed ## ]]"
    EMPTY = "[[ ## extractions ## ]]\n[]\n\n[[ ## completed ## ]]"

    def resp_row(source, behavior, session, turn, snapshot=None):
        usr = ("[[ ## form_schema ## ]]\nF\n\n[[ ## user_message ## ]]\nhi there\n\n"
               "[[ ## actions_taken ## ]]\n(no actions this turn)\n\n[[ ## completed ## ]]")
        return {"module": "responder", "source": source, "behavior": behavior,
                "session": session, "turn": turn, "snapshot": snapshot, "completion": RESP,
                "messages": [{"role": "system", "content": "S"}, {"role": "user", "content": usr}]}

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # a farm turn at a pending state (-> reask_pending, since the injected msg is chitchat-y
        # and extractor is empty) and an inject submit_blocked turn.
        with open(tmp / "snapshots.jsonl", "w") as f:
            f.write(json.dumps({"session": 5, "turn": 2, "form_state": {}, "pending": "dob",
                                "history": [], "user_message": "hi there"}) + "\n")
            f.write(json.dumps({"session": 6, "turn": 1, "form_state": {}, "pending": None,
                                "history": [], "user_message": "submit please"}) + "\n")
        with open(tmp / "train.jsonl", "w") as f:
            f.write(json.dumps(resp_row("farm", "natural", 5, 2)) + "\n")
            # inject submit_blocked: extractor (empty) precedes responder; injected msg submits
            for mod, comp in (("extractor", EMPTY), ("responder", RESP)):
                usr = ("[[ ## form_schema ## ]]\nF\n\n[[ ## user_message ## ]]\nCan I submit now?\n\n"
                       "[[ ## actions_taken ## ]]\n(x)\n\n[[ ## completed ## ]]")
                f.write(json.dumps({"module": mod, "source": "inject", "behavior": "submit_blocked",
                                    "session": None, "turn": None, "snapshot": {"session": 6, "turn": 1},
                                    "completion": comp,
                                    "messages": [{"role": "system", "content": "S"},
                                                 {"role": "user", "content": usr}]}) + "\n")
        # an eval/probe file carrying a clarify + a terminal case
        ef = tmp / "probe.jsonl"
        with open(ef, "w") as f:
            f.write(json.dumps({"session": 150, "turn": 1, "user_message": "x", "form_state": {},
                                "actions": [], "directives": [["clarify", {"field_id": "country_citizenship"}]],
                                "completion": RESP}) + "\n")
            f.write(json.dumps({"session": 151, "turn": 9, "user_message": "y", "form_state": {},
                                "actions": [], "directives": [["terminal", None]],
                                "completion": RESP}) + "\n")

        rep = compute(tmp, [ef], schema)
        ck("farm turn recomputed to reask_pending (training)", rep["train_kind"].get("reask_pending", 0) == 1)
        ck("inject submit_blocked counted in training", rep["train_kind"].get("submit_blocked", 0) == 1)
        ck("inject behavior breakdown present",
           rep["inject_by_behavior"].get("submit_blocked", {}).get("submit_blocked") == 1)
        ck("eval clarify + terminal counted", rep["eval_kind"].get("clarify") == 1
           and rep["eval_kind"].get("terminal") == 1)
        # ack and fix have no coverage anywhere -> flagged
        ck("zero-coverage reachable kinds flagged (ack, fix)",
           "ack" in rep["zero_coverage_reachable"] and "fix" in rep["zero_coverage_reachable"])
        ck("covered kinds NOT flagged",
           all(k not in rep["zero_coverage_reachable"]
               for k in ("reask_pending", "submit_blocked", "clarify", "terminal")))
        print_report(rep)   # smoke the printer

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n=== coverage_report selftest: {passed}/{len(checks)} checks passed ===")
    return passed == len(checks)


def main():
    ap = argparse.ArgumentParser(description="Directive-kind x source coverage matrix (doc-22 tool).")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--run", default="", help="bridged run's SOURCE dir (train.jsonl + snapshots.jsonl); "
                    "directive kinds are recomputed from it (sft_data reshaped rows drop directives)")
    ap.add_argument("--eval", nargs="*", default=[], help="eval/probe case jsonl files")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    run_dir = None
    if args.run:
        run_dir = Path(args.run) if "/" in args.run else (RUN_DIR / args.run)
    eval_files = [Path(e) if "/" in e else (V2_DIR / e) for e in args.eval]
    if run_dir is None and not eval_files:
        ap.error("pass --run and/or --eval")
    print_report(compute(run_dir, eval_files))


if __name__ == "__main__":
    main()
