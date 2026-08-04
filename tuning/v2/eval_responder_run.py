"""eval_responder_run.py — doc-20 item 8 (Tier-1 half): run the tuned student
responder over the frozen 223 and score it with the accepted Tier-1 scorer.

Per case (eval/eval_responder_set.jsonl) it rebuilds the SERVE-TIME responder inputs
exactly as program.forward does (program.py respond call): form_schema, filled_fields
(render_filled on the case's post-turn form_state — the same post-update render serving
does), recent_history (joined back from eval_farm_p4/snapshots.jsonl by (session,turn),
since the case doesn't carry it), user_message, actions_taken=summarize_actions(actions),
guidance=render_guidance(directives). It calls the student responder (StudentLM,
dspy.Predict(Respond), temp 0, demo-free), keeps the RAW completion, and scores a copy
of the case with completion=raw (raw, not canon — format must measure the student's own
markers, the pre-committed >=99 line).

Writes incrementally (a per-case .progress.jsonl) so a mid-run crash loses nothing
(doc-21 lose-everything-at-90% gap), then emits the artifact JSON + a hand-readable
failure dump .md.

  Selftest (offline, stub LM):  tuning/v2/.venv/bin/python -m tuning.v2.eval_responder_run --selftest
  Run ($0, local student):      tuning/v2/.venv/bin/python -m tuning.v2.eval_responder_run
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import context
from .schema import load_schema
from .program import Respond, summarize_actions, render_guidance, strip_markers
from . import eval_responder as ER

V2_DIR = Path(__file__).resolve().parent
EVAL_SET = V2_DIR / "eval" / "eval_responder_set.jsonl"
SNAPSHOTS = V2_DIR / "datagen_runs" / "eval_farm_p4" / "snapshots.jsonl"
REF_ARTIFACT = V2_DIR / "eval" / "baseline-teacher_responder_tier1_frozen223.json"
OUT_DIR = V2_DIR / "eval"

MODEL = os.getenv("V2_RESP_EVAL_MODEL",
                  "/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2resp-mlx")
PORT = int(os.getenv("V2_RESP_EVAL_PORT", "8102"))
LABEL = os.getenv("V2_RESP_EVAL_LABEL", "student_s2resp_responder_tier1_frozen223")

# The served model does not halt on the ChatML turn terminator (the mlx server isn't
# enforcing the stop token), so a raw completion runs on past the assistant turn into a
# hallucinated continuation. The student's ACTUAL turn output is the text up to the first
# terminator; clip there (a correctly-configured server would stop there) and cap
# generation so a non-stopping server can't make each call take 20s.
_TURN_STOPS = ("<|im_end|>", "<|endoftext|>")
RUN_MAX_TOKENS = 512   # any real responder reply is <100 tokens; bounds the runaway


def _clip_to_turn(raw: str) -> tuple[str, bool]:
    """Cut a completion at the first ChatML turn terminator. Returns (clipped, ran_over)."""
    cut = len(raw)
    for s in _TURN_STOPS:
        i = raw.find(s)
        if i != -1:
            cut = min(cut, i)
    return raw[:cut], (cut < len(raw))


class _ClarifyShim:
    """render_guidance reads payload.field_id on a clarify directive; the case carries
    it as a JSON dict {"field_id": …} (item-3 flag #3). Wrap it so render_guidance works
    unchanged — do NOT edit program.py."""
    __slots__ = ("field_id",)

    def __init__(self, fid):
        self.field_id = fid


def _directives_for_guidance(directives: list) -> list:
    """JSON directives -> (kind, payload) with clarify's dict wrapped in a shim."""
    out = []
    for kind, payload in directives:
        if kind == "clarify":
            fid = payload.get("field_id") if isinstance(payload, dict) else getattr(payload, "field_id", None)
            out.append((kind, _ClarifyShim(fid)))
        else:
            out.append((kind, payload))
    return out


def build_responder_inputs(schema, case: dict, snap: dict) -> dict:
    """The six Respond inputs, rebuilt exactly as program.forward's respond call."""
    return {
        "form_schema": context.render_schema(schema),
        "filled_fields": context.render_filled(schema, case["form_state"]),   # post-turn state
        "recent_history": context.render_history(snap["history"]),            # from the snapshot
        # the CASE's user_message (the injected one for probes); == snap's for the frozen set,
        # so this is a no-op there and the frozen baseline is unchanged.
        "user_message": case.get("user_message", snap.get("user_message", "")),
        "actions_taken": summarize_actions(schema, case["actions"]),
        "guidance": render_guidance(schema, _directives_for_guidance(case["directives"])),
    }


def _per_case_entry(case: dict, scored: dict) -> dict:
    """Artifact per_case row, mirroring the teacher baseline: reason only when a check fails."""
    checks = {}
    for k, v in scored["checks"].items():
        checks[k] = {"pass": v["pass"]} if v["pass"] else {"pass": False, "reason": v["reason"]}
    return {"session": case["session"], "turn": case["turn"], "turn_type": scored["turn_type"],
            "tokens": scored["tokens"], "passed": scored["passed"], "checks": checks}


def _sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _scorer_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=V2_DIR).decode().strip()
    except Exception:
        return "unknown"


# ---- the run -----------------------------------------------------------------

def run(limit: int = 0, cases_path: Path = None, label: str = None) -> dict:
    import dspy
    from .student_lm import StudentLM

    cases_path = Path(cases_path) if cases_path else EVAL_SET
    label = label or LABEL
    schema = load_schema()
    cases = [json.loads(l) for l in open(cases_path)]
    if limit:
        cases = cases[:limit]
    snapmap = {(s["session"], s["turn"]): s for s in (json.loads(l) for l in open(SNAPSHOTS))}

    # H3 quirk: request-body model field AND V2_STUDENT_MODEL must both be the path.
    os.environ["V2_STUDENT_MODEL"] = MODEL
    lm = StudentLM(model=MODEL, port=PORT, temperature=0.0, max_tokens=RUN_MAX_TOKENS)
    dspy.configure(lm=lm)
    respond = dspy.Predict(Respond)   # demo-free

    progress_path = OUT_DIR / f"{label}.progress.jsonl"
    pf = open(progress_path, "w")

    per_case, fail_records, join_fail, empties, ran_over = [], [], [], [], []
    t0 = time.time()
    for i, case in enumerate(cases):
        key = (case["session"], case["turn"])
        snap = snapmap.get(key)
        if snap is None:
            join_fail.append(key)
            continue
        inputs = build_responder_inputs(schema, case, snap)
        prev = len(lm.history)
        try:
            respond(**inputs)
        except Exception:
            pass   # AdapterParseError / malformed markers — the raw is still in history
        hist = lm.history[prev:]
        raw_full = hist[0]["outputs"][0] if (hist and hist[0].get("outputs")) else ""
        raw, over = _clip_to_turn(raw_full)   # student's actual turn output (server won't stop)
        if over:
            ran_over.append(key)
        if not raw.strip():
            empties.append(key)

        scored = ER.score_case({**case, "completion": raw}, schema)
        entry = _per_case_entry(case, scored)
        per_case.append(entry)
        prose = strip_markers(raw)
        if not scored["passed"]:
            fail_records.append({
                "session": case["session"], "turn": case["turn"],
                "failed_checks": [k for k, v in scored["checks"].items() if not v["pass"]],
                "reasons": {k: v["reason"] for k, v in scored["checks"].items() if not v["pass"]},
                "directives": case["directives"],
                "prose": prose,
            })
        # incremental: full record (superset of the artifact row) per line
        pf.write(json.dumps({**entry, "prose": prose, "directives": case["directives"]}) + "\n")
        pf.flush()
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(cases)} done", flush=True)
    pf.close()
    wall = time.time() - t0

    agg = ER.aggregate(per_case)
    ref = json.load(open(REF_ARTIFACT))
    artifact = {
        "label": label,
        "date": "2026-08-04",
        "eval_set": str(cases_path),
        "eval_set_sha256_16": _sha16(cases_path),
        "n_cases": len(per_case),
        "scored_completion": "raw student completion from the served model (format scored RAW — "
                             "the student must emit clean markers itself; the pre-committed >=99 line)",
        "completions_model": f"{MODEL} (temp 0, served localhost:{PORT}, 2026-08-03)",
        "scorer_commit": _scorer_commit(),
        "scorer_note": "eval_responder.py is uncommitted in the working tree at run time "
                       "(directive-check amendment); scorer_commit is repo HEAD, not the scorer file itself",
        "provenance": {"model": MODEL, "port": PORT, "host": "localhost", "cost_usd": 0.0},
        "budgets": ref["budgets"],
        "reference_thresholds": ref["reference_thresholds"],   # verbatim, incl. note
        "aggregate": agg,
        "per_case": per_case,
        "cost_usd": 0.0,
        "run_diagnostics": {"wall_seconds": round(wall, 1),
                            "history_join_failures": [list(k) for k in join_fail],
                            "empty_student_outputs": [list(k) for k in empties],
                            "clipped_at_turn_terminator": len(ran_over),
                            "clip_note": "the served model did not halt on <|im_end|>; each raw "
                                         "completion was clipped at the first ChatML turn terminator "
                                         "(the student's actual turn output). A stop-token fix is server-side."},
    }
    art_path = OUT_DIR / f"baseline-{label}.json"
    json.dump(artifact, open(art_path, "w"), indent=2, default=str)
    md_path = OUT_DIR / f"REPORT_{label.replace('_responder_tier1_frozen223', '')}_tier1_failures.md"
    _write_failure_md(md_path, artifact, fail_records)

    _print_summary(artifact, ref, fail_records, join_fail, empties, wall, art_path, md_path, progress_path)
    if ran_over:
        print(f"NOTE: {len(ran_over)}/{len(per_case)} completions ran past <|im_end|> and were "
              f"clipped to the student's actual turn output (server stop-token not enforced).")
    return artifact


def _write_failure_md(path: Path, artifact: dict, fails: list) -> None:
    order = ["format", "directive", "grounding", "echo", "verbosity", "repetition"]
    agg = artifact["aggregate"]
    lines = [f"# Tier-1 failures — {artifact['label']}", "",
             f"Model: `{artifact['provenance']['model']}` (port {artifact['provenance']['port']}, $0)  ",
             f"Eval set: {artifact['n_cases']} cases, sha16 `{artifact['eval_set_sha256_16']}`  ",
             f"Overall pass: **{agg['passed']}/{agg['n']}**  ", ""]
    lines.append("| check | pass | rate |")
    lines.append("|---|---|---|")
    for c in order:
        d = agg["by_check"][c]
        lines.append(f"| {c} | {d['pass']}/{agg['n']} | {d['rate']:.1%} |")
    lines.append("")
    for fam in order:
        fam_fails = [f for f in fails if fam in f["failed_checks"]]
        if not fam_fails:
            continue
        lines.append(f"## {fam} — {len(fam_fails)} failing case(s)")
        lines.append("")
        for f in fam_fails:
            lines.append(f"### s{f['session']} t{f['turn']}  ({', '.join(f['failed_checks'])})")
            lines.append(f"- directives: `{f['directives']}`")
            lines.append(f"- {fam} reason: {f['reasons'][fam]}")
            lines.append(f"- student prose:")
            lines.append("")
            lines.append("  > " + (f["prose"].replace(chr(10), chr(10) + "  > ") or "(empty)"))
            lines.append("")
    path.write_text("\n".join(lines))


def _print_summary(artifact, ref, fails, join_fail, empties, wall, art_path, md_path, progress_path):
    agg, ragg = artifact["aggregate"], ref["aggregate"]
    print("\n=== student vs teacher (Tier-1, frozen 223) ===")
    _fams = ("format", "directive", "grounding", "echo", "verbosity", "repetition")
    print(f"  {'check':12} {'student':>16} {'teacher':>16}")
    for c in _fams:
        s = agg["by_check"].get(c)
        t = ragg["by_check"].get(c)     # the frozen teacher artifact predates 'repetition'
        if s is None:
            continue
        tcol = f"{t['pass']:>3}/{ragg['n']} {t['rate']:>7.1%}" if t else f"{'n/a':>12}"
        print(f"  {c:12} {s['pass']:>3}/{agg['n']} {s['rate']:>7.1%}   {tcol}")
    print(f"  {'OVERALL':12} {agg['passed']:>3}/{agg['n']} {agg['passed']/agg['n']:>7.1%}   "
          f"{ragg['passed']:>3}/{ragg['n']} {ragg['passed']/ragg['n']:>7.1%}")
    fam_counts = {c: sum(1 for f in fails if c in f["failed_checks"]) for c in _fams}
    print(f"\nfailure counts per family: {fam_counts}")
    print(f"history-join failures: {len(join_fail)}   empty student outputs: {len(empties)}")
    print(f"wall: {wall:.1f}s")
    print(f"artifact: {art_path}\nfailure md: {md_path}\nprogress: {progress_path}")


# ---- selftest (offline, stub LM) ---------------------------------------------

def selftest() -> bool:
    import dspy
    schema = load_schema()
    checks: list[tuple[str, bool]] = []

    def ck(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    # a case with a clarify dict payload (exercises the shim through render_guidance)
    clarify_case = {
        "session": 900, "turn": 2, "user_message": "not sure",
        "form_state": {}, "actions": [],
        "directives": [["clarify", {"field_id": "program"}]],
    }
    ask_case = {
        "session": 900, "turn": 0, "user_message": "hi",
        "form_state": {}, "actions": [{"type": "ask_choice", "question": "Program of Interest?", "options": []}],
        "directives": [["ask_target", "program"]],
    }
    snap = {"session": 900, "turn": 0, "history": [], "user_message": "hi"}

    # shim: render_guidance consumes the clarify dict without crashing, produces a line
    g = render_guidance(schema, _directives_for_guidance(clarify_case["directives"]))
    ck("clarify-dict shim: render_guidance produces a clarify line", "clarif" in g.lower())
    ck("build_responder_inputs returns the 6 serve-time fields",
       set(build_responder_inputs(schema, ask_case, snap)) ==
       {"form_schema", "filled_fields", "recent_history", "user_message", "actions_taken", "guidance"})

    # probe wiring: the CASE's user_message wins over the snapshot's (injected != farm),
    # while recent_history still comes from the snapshot. Also duplicate (session,turn)
    # across cases is fine because the runner is keyed by case index, not the snapshot key.
    probe_case = {"session": 150, "turn": 8, "user_message": "Hey there! How's your day going?",
                  "form_state": {}, "actions": [], "directives": [["reask_pending", "dob"]]}
    farm_snap = {"session": 150, "turn": 8, "history": [{"role": "assistant", "content": "What's your DOB?"}],
                 "user_message": "my name is Ada"}
    inp = build_responder_inputs(schema, probe_case, farm_snap)
    ck("probe: build uses the case's (injected) user_message, not the snapshot's",
       inp["user_message"] == "Hey there! How's your day going?")
    ck("probe: recent_history still comes from the snapshot",
       "What's your DOB?" in inp["recent_history"])

    # stub LM: canned raw completions, keyed by call order
    RAW = ["[[ ## response_text ## ]]\nWhich program of interest?\n\n[[ ## completed ## ]]",  # clean
           "Just prose, no markers"]                                                          # malformed

    class _StubLM(dspy.BaseLM):
        def __init__(self):
            super().__init__(model="stub", cache=False)
            self.i = 0

        def forward(self, prompt=None, messages=None, **kwargs):
            from dataclasses import dataclass, field as _f

            @dataclass
            class _M:
                content: str
                role: str = "assistant"
                tool_calls = None
                reasoning_content = None

            @dataclass
            class _C:
                message: _M
                index: int = 0
                finish_reason: str = "stop"

            @dataclass
            class _R:
                choices: list
                model: str
                usage: dict = _f(default_factory=dict)
                _hidden_params: dict = _f(default_factory=dict)
            txt = RAW[min(self.i, len(RAW) - 1)]
            self.i += 1
            return _R(choices=[_C(_M(txt))], model="stub", _hidden_params={"response_cost": 0.0})

    lm = _StubLM()
    dspy.configure(lm=lm)
    respond = dspy.Predict(Respond)

    # case 1: clean markers -> format passes, raw captured with markers
    prev = len(lm.history)
    try:
        respond(**build_responder_inputs(schema, ask_case, snap))
    except Exception:
        pass
    raw1 = lm.history[prev]["outputs"][0]
    s1 = ER.score_case({**ask_case, "completion": raw1}, schema)
    ck("clean student output: raw keeps markers + format passes",
       "[[ ## response_text ## ]]" in raw1 and s1["checks"]["format"]["pass"])

    # case 2: malformed markers -> raw captured (not lost), format fails
    prev = len(lm.history)
    try:
        respond(**build_responder_inputs(schema, ask_case, snap))
    except Exception:
        pass
    raw2 = lm.history[prev]["outputs"][0]
    s2 = ER.score_case({**ask_case, "completion": raw2}, schema)
    ck("malformed student output: raw still captured, format fails",
       raw2 == "Just prose, no markers" and not s2["checks"]["format"]["pass"])

    ck("_per_case_entry mirrors the teacher shape (reason only on failure)",
       set(_per_case_entry(ask_case, s2)["checks"]["format"]) == {"pass", "reason"}
       and set(_per_case_entry(ask_case, s1)["checks"]["format"]) == {"pass"})

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n=== eval_responder_run selftest: {passed}/{len(checks)} checks passed ===")
    return passed == len(checks)


def main():
    ap = argparse.ArgumentParser(description="Run the tuned student responder over the frozen 223 (doc-20 item 8).")
    ap.add_argument("--selftest", action="store_true", help="offline, stub LM")
    ap.add_argument("--limit", type=int, default=0, help="cap cases (smoke)")
    ap.add_argument("--cases", default="", help="case file to score (default the frozen 223); "
                    "e.g. the chitchat probe. Cases join history from the same p4 snapshots.")
    ap.add_argument("--label", default="", help="artifact label (default the frozen-223 label)")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    run(args.limit, Path(args.cases) if args.cases else None, args.label or None)


if __name__ == "__main__":
    main()
