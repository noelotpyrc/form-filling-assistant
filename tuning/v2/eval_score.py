"""M3a Tier-1 scorer — run the harness on the frozen eval set, score the
extractor against ground truth (doc-18 §6).

Drives the SAME entry point as production (FormAssistant.forward, extract ->
validate -> compose), so the metric is not a parallel-rig artifact. Runs
extractor-only by default (with_response=False skips the 2nd teacher call ->
~half the cost); the extract path is byte-identical either way.

Metrics (doc-18 §6):
  field precision / recall / F1   did we set exactly the right field_ids
  value-match                     for correctly-set fields, right canonical value
  empty-correct                   empty-expect cases: set nothing
  over-attribution rate           no-value band: grabbed a field from noise
  wrong-field-assignment rate     unplaceable band (doc-18.1 S16): placed a
                                  real-looking value on a field it shouldn't
  choice-correct                  offered the expected field's choices
plus a per-scenario breakdown and a violations dump for spot-verification (gold).

The teacher is non-deterministic (no temp/seed), so each case is run --n times;
every (case, sample) is one observation. We report pooled rates plus per-case
stability (how often the N samples agree) to surface flakiness.

  Self-test (free, no model):  tuning/v2/.venv/bin/python -m tuning.v2.eval_score --selftest
  Teacher baseline ($$):       tuning/v2/.venv/bin/python -m tuning.v2.eval_score --n 5 --label teacher_v2
    (always the canonical build_teacher(schema); it carries ONE extract demo for the
     compound convention — render it natively with --backend openrouter, since the
     claude CLI flattens demos and breaks markers)
"""
from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path

EVAL_SET = "tuning/v2/eval/eval_set.jsonl"
OUT_DIR = Path("tuning/v2/eval")

# value present but no valid target -> a set here is a wrong-field-assignment
# (doc-18.1 S16), distinct from grabbing a field out of value-free noise.
UNPLACEABLE = {"ambiguous", "no_match", "bare_date"}


# ---- pure scoring (no model; covered by --selftest) ----------------------

def band_of(case: dict) -> str:
    e = case["expect"]
    if e.get("sets"):
        return "positive"
    if e.get("choice"):
        return "choice"
    if e.get("empty"):
        return "unplaceable" if case["scenario"] in UNPLACEABLE else "no_value"
    return "other"


def _val_eq(got, exp) -> bool:
    if isinstance(exp, bool) or isinstance(got, bool):
        return bool(got) == bool(exp)
    return str(got).strip() == str(exp).strip()


def score_observation(case: dict, obs: dict) -> dict:
    """One (case, sample) -> a scored record. `obs` = {got_sets, choice_offered,
    choice_field}. Pure: the aggregate math is exercised by --selftest."""
    band = band_of(case)
    exp_sets = case["expect"].get("sets", {})
    exp_fids, got = set(exp_sets), obs["got_sets"]
    got_fids = set(got)
    inter = exp_fids & got_fids
    value_total = len(inter)
    value_ok = sum(_val_eq(got[fid], exp_sets[fid]) for fid in inter)

    if band == "positive":
        passed = got_fids == exp_fids and value_ok == value_total
    elif band == "choice":
        want = set(case["expect"]["choice"])
        passed = obs["choice_offered"] and obs["choice_field"] in want and not got_fids
    else:  # no_value / unplaceable / other -> must set nothing
        passed = not got_fids

    return {
        "id": case["id"], "scenario": case["scenario"], "band": band, "passed": passed,
        "tp": len(inter), "fp": len(got_fids - exp_fids), "fn": len(exp_fids - got_fids),
        "value_ok": value_ok, "value_total": value_total,
        "set_something": bool(got_fids),
        "violation": dict(got) if band in ("no_value", "unplaceable") and got_fids else None,
        "choice_field": obs.get("choice_field"),
    }


def _rate(items, pred):
    items = list(items)
    return {"rate": sum(1 for x in items if pred(x)) / len(items), "n": len(items)} if items \
        else {"rate": None, "n": 0}


def aggregate(scored: list[dict]) -> dict:
    tp = sum(s["tp"] for s in scored)
    fp = sum(s["fp"] for s in scored)
    fn = sum(s["fn"] for s in scored)
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    vt = sum(s["value_total"] for s in scored)
    vo = sum(s["value_ok"] for s in scored)

    band = lambda b: [s for s in scored if s["band"] == b]
    empties = band("no_value") + band("unplaceable")
    by_scn = defaultdict(list)
    for s in scored:
        by_scn[s["scenario"]].append(s)

    return {
        "n_observations": len(scored),
        "field_precision": prec, "field_recall": rec, "field_f1": f1,
        "field_counts": {"tp": tp, "fp": fp, "fn": fn},
        "value_match": (vo / vt if vt else 1.0), "value_n": vt,
        "empty_correct": _rate(empties, lambda s: not s["set_something"]),
        "over_attribution": _rate(band("no_value"), lambda s: s["set_something"]),
        "wrong_field_assignment": _rate(band("unplaceable"), lambda s: s["set_something"]),
        "choice_correct": _rate(band("choice"), lambda s: s["passed"]),
        "by_scenario": {scn: _rate(rows, lambda s: s["passed"]) for scn, rows in sorted(by_scn.items())},
    }


def stability(scored: list[dict]) -> dict:
    """Per-case agreement across the N samples (non-determinism surfacing)."""
    by_id = defaultdict(list)
    for s in scored:
        by_id[s["id"]].append(s["passed"])
    agree = {cid: (all(v) or not any(v)) for cid, v in by_id.items()}
    flaky = sorted(cid for cid, ok in agree.items() if not ok)
    return {"cases": len(agree), "fully_agree": sum(agree.values()), "flaky": flaky}


# ---- model execution -----------------------------------------------------

def run_case(agent, lm, schema, case: dict) -> dict:
    from .state import TurnState, Pending
    pending = Pending(case["pending"]) if case.get("pending") else None
    state = TurnState(schema=schema, form_state=dict(case.get("form_state", {})), pending=pending)
    prev = len(lm.history)
    pred = agent(state=state, user_message=case["user_message"],
                 history=case.get("conversation_history", []), with_response=False)
    cost = sum((c.get("cost") or 0.0) for c in lm.history[prev:])
    got_sets, choice_offered = {}, False
    for a in pred.actions:
        if a["type"] == "set_fields":
            for f in a["fields"]:
                got_sets[f["field_id"]] = f["value"]
        elif a["type"] == "ask_choice":
            choice_offered = True
    choice_field = state.pending.target if (choice_offered and state.pending) else None
    return {"got_sets": got_sets, "choice_offered": choice_offered,
            "choice_field": choice_field, "cost": cost}


def run_baseline(n: int, label: str, eval_set: str, limit: int = 0, only: str = "",
                 backend: str = "claude", model: str = "", port: int = 0):
    import dspy
    from .schema import load_schema
    from .program import build_teacher

    cases = [json.loads(l) for l in open(eval_set)]
    if only:
        keep = set(only.split(","))
        cases = [c for c in cases if c["scenario"] in keep]
    if limit:
        cases = cases[:limit]
    if backend == "student":
        from .student_lm import StudentLM
        kw = {}
        if model:
            kw["model"] = model   # else StudentLM's default ("student")
        if port:
            kw["port"] = port
        lm = StudentLM(**kw)
    elif backend == "openrouter":
        from .openrouter_lm import OpenRouterLM
        lm = OpenRouterLM(model=model) if model else OpenRouterLM()
    else:
        from .claude_lm import ClaudeLM
        lm = ClaudeLM(model=model) if model else ClaudeLM()
    dspy.configure(lm=lm)
    schema = load_schema()
    if backend == "student":
        # Demo-free: the student is SFT'd on demo-stripped prompts (P1 capture), so
        # evaluating it with the teacher's in-context demo would be a train/serve mismatch.
        from .program import FormAssistant
        agent, program = FormAssistant(), "student-bare"
    else:
        # canonical teacher (one compound extract demo; native via openrouter)
        agent, program = build_teacher(schema), "teacher"
    print(f"backend={backend}  model={lm.model}  port={port or '-'}  program={program}"
          f"  cases={len(cases)}  n={n}  -> {len(cases)*n} extractor calls\n", flush=True)

    scored, raw, total_cost = [], [], 0.0
    for si in range(n):
        for ci, case in enumerate(cases):
            try:
                obs = run_case(agent, lm, schema, case)
            except Exception as e:
                print(f"  !! {case['id']} sample {si}: {type(e).__name__}: {str(e)[:120]}", flush=True)
                continue
            s = score_observation(case, obs)
            scored.append(s)
            raw.append({"sample": si, **s, "got_sets": obs["got_sets"], "cost": obs["cost"]})
            total_cost += obs["cost"]
        print(f"  sample {si+1}/{n} done  (running ${total_cost:.2f})", flush=True)

    agg = aggregate(scored)
    stab = stability(scored)
    result = {"label": label, "model": lm.model, "n": n, "eval_set": eval_set,
              "cost_usd": round(total_cost, 4), "metrics": agg, "stability": stab, "raw": raw}
    out = OUT_DIR / f"baseline-{label}.json"
    json.dump(result, open(out, "w"), indent=2, default=str)
    print_report(agg, stab, total_cost, scored)
    print(f"\nwrote {out}")


def print_report(agg, stab, cost, scored):
    p = lambda r: "n/a" if r["rate"] is None else f"{r['rate']*100:5.1f}% (n={r['n']})"
    print("\n=== Tier-1 extractor metrics ===")
    print(f"field F1:        {agg['field_f1']*100:5.1f}%  (P {agg['field_precision']*100:.1f} / "
          f"R {agg['field_recall']*100:.1f}; tp={agg['field_counts']['tp']} "
          f"fp={agg['field_counts']['fp']} fn={agg['field_counts']['fn']})")
    print(f"value-match:     {agg['value_match']*100:5.1f}%  (n={agg['value_n']})")
    print(f"empty-correct:   {p(agg['empty_correct'])}")
    print(f"over-attribution:{p(agg['over_attribution'])}   <- no-value band, lower is better")
    print(f"wrong-field:     {p(agg['wrong_field_assignment'])}   <- unplaceable band (S16), lower is better")
    print(f"choice-correct:  {p(agg['choice_correct'])}")
    print("\nper-scenario pass rate:")
    for scn, r in agg["by_scenario"].items():
        print(f"  {scn:22} {p(r)}")
    print(f"\nstability: {stab['fully_agree']}/{stab['cases']} cases agree across samples"
          + (f"; flaky: {', '.join(stab['flaky'])}" if stab["flaky"] else ""))
    # violations (gold spot-check material)
    viols = [(s["id"], s["violation"]) for s in scored if s.get("violation")]
    if viols:
        print(f"\nover-set / wrong-field violations ({len(viols)} obs):")
        for cid, v in viols[:20]:
            print(f"  {cid}: set {v}")
    print(f"\ncost: ${cost:.2f}")


# ---- self-test (pure, no spend) ------------------------------------------

def selftest():
    def C(scenario, expect):
        return {"id": scenario, "scenario": scenario, "expect": expect}
    def O(got=None, choice=False, cf=None):
        return {"got_sets": got or {}, "choice_offered": choice, "choice_field": cf}

    checks = [
        # positive: exact -> pass, tp1
        (C("single_name", {"sets": {"full_name": "X"}}), O({"full_name": "X"}), True),
        # positive wrong value -> fail, value mismatch
        (C("single_name", {"sets": {"full_name": "X"}}), O({"full_name": "Y"}), False),
        # positive missed -> fail, fn1
        (C("single_name", {"sets": {"full_name": "X"}}), O({}), False),
        # bool value-match
        (C("boolean", {"sets": {"prior_application": False}}), O({"prior_application": False}), True),
        # no_value: empty -> pass
        (C("chitchat", {"empty": True}), O({}), True),
        # no_value: grabbed -> over-attribution, fail, violation
        (C("trap", {"empty": True}), O({"mailing_address": "Denver"}), False),
        # unplaceable: set -> wrong-field, fail
        (C("bare_date", {"empty": True}), O({"dob": "2000-08-10"}), False),
        # choice: offered right field -> pass
        (C("asks", {"choice": ["program"]}), O(choice=True, cf="program"), True),
        # choice: offered wrong field -> fail
        (C("asks", {"choice": ["program"]}), O(choice=True, cf="dob"), False),
    ]
    scored = []
    for case, obs, want_pass in checks:
        s = score_observation(case, obs)
        scored.append(s)
        assert s["passed"] == want_pass, f"{case['id']}: passed={s['passed']} want {want_pass}"

    agg = aggregate(scored)
    # tp: single_name#1 (1) + bool (1) = 2; fp: trap(1)+bare_date(1) = 2; fn: 2 missed (#2 set wrong field? no)
    # #1 got==exp tp1; #2 got full_name (tp1) value wrong; #3 fn1; bool tp1; trap fp1; bare_date fp1
    c = agg["field_counts"]
    assert c == {"tp": 3, "fp": 2, "fn": 1}, c
    assert abs(agg["value_match"] - 2 / 3) < 1e-9, agg["value_match"]   # 3 tp value-checks, 2 ok (Y wrong)
    # no-value band = {chitchat clean, trap grabbed} -> 1 of 2 over-attributed
    assert agg["over_attribution"]["rate"] == 0.5 and agg["over_attribution"]["n"] == 2
    assert agg["wrong_field_assignment"]["rate"] == 1.0 and agg["wrong_field_assignment"]["n"] == 1
    assert agg["empty_correct"]["rate"] == 1 / 3 and agg["empty_correct"]["n"] == 3
    assert agg["choice_correct"]["rate"] == 0.5 and agg["choice_correct"]["n"] == 2
    # stability: duplicate one id across "samples"
    stab = stability(scored + [score_observation(checks[0][0], O({"full_name": "Z"}))])
    assert "single_name" in stab["flaky"], stab
    print("selftest: all assertions passed")
    print_report(agg, stability(scored), 0.0, scored)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--n", type=int, default=5, help="samples per case (teacher is non-deterministic)")
    ap.add_argument("--label", default="teacher_v1")
    ap.add_argument("--eval-set", default=EVAL_SET)
    ap.add_argument("--limit", type=int, default=0, help="cap to first N cases (smoke)")
    ap.add_argument("--only", default="", help="comma-separated scenarios to run (band check)")
    ap.add_argument("--backend", choices=["claude", "openrouter", "student"], default="claude",
                    help="LM backend (default claude = unchanged; student = served MLX SFT model)")
    ap.add_argument("--model", default="", help="override the model id passed to the backend LM")
    ap.add_argument("--port", type=int, default=0, help="port for the student backend (default StudentLM's 8100)")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    run_baseline(args.n, args.label, args.eval_set, args.limit, args.only,
                 args.backend, args.model, args.port)


if __name__ == "__main__":
    main()
