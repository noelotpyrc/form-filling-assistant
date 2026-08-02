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

Eval sets: v1 (frozen, byte-identical), v2 (realistic/contract bands), v3 (REAL
farmed contexts + early/mid/late depth bands, built by eval_gen.py). v2 and v3
require --label so they cannot clobber a v1 baseline file.

  Self-test (free, no model):  tuning/v2/.venv/bin/python -m tuning.v2.eval_score --selftest
  Teacher baseline ($$):       tuning/v2/.venv/bin/python -m tuning.v2.eval_score --n 5 --label teacher_v2
    (always the canonical build_teacher(schema); it carries ONE extract demo for the
     compound convention — render it natively with --backend openrouter, since the
     claude CLI flattens demos and breaks markers)
  v3 run:                      tuning/v2/.venv/bin/python -m tuning.v2.eval_score \
                                   --eval-set v3 --label <name> --backend student --port 8101
"""
from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path

EVAL_SET = "tuning/v2/eval/eval_set.jsonl"
EVAL_SET_V2 = "tuning/v2/eval/eval_set_v2.jsonl"
EVAL_SET_V3 = "tuning/v2/eval/eval_set_v3.jsonl"
EVAL_SETS = {"v1": EVAL_SET, "v2": EVAL_SET_V2, "v3": EVAL_SET_V3}
OUT_DIR = Path("tuning/v2/eval")

# value present but no valid target -> a set here is a wrong-field-assignment
# (doc-18.1 S16), distinct from grabbing a field out of value-free noise.
# bare_ambiguous / invalid_value are v3 scenario names; neither occurs in v1 or v2,
# so band_of is unchanged for every existing case and the frozen baselines stay
# comparable.
UNPLACEABLE = {"ambiguous", "no_match", "bare_date", "bare_ambiguous", "invalid_value"}

# v3 depth bands (case["band"]) — reported as a breakdown, all of them gated.
V3_BANDS = ("early", "mid", "late")


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


def field_types(schema=None) -> dict:
    """{field_id: schema type}. Cached; loads the canonical schema when not given, so
    every caller of score_observation gets type-aware comparison for free."""
    global _FIELD_TYPES
    if schema is None:
        if _FIELD_TYPES is None:
            from .schema import load_schema
            schema = load_schema()
            _FIELD_TYPES = {f.field_id: f.type for f in schema.fields}
        return _FIELD_TYPES
    return {f.field_id: f.type for f in schema.fields}


_FIELD_TYPES = None


def _val_eq(got, exp, ftype: str | None = None) -> bool:
    """Exact string equality, EXCEPT phone: the validator canonicalizes a phone to
    digits (2026-08-02), while eval v1 (byte-frozen) and v3 (frozen with baselines)
    store the SURFACE form the user typed ("(429) 555-2786", "415.782.3311"). Phones
    therefore compare by digit string, so one canonicalization change does not force a
    rebuild of two frozen eval sets. Every other type is unchanged."""
    if isinstance(exp, bool) or isinstance(got, bool):
        return bool(got) == bool(exp)
    if ftype == "phone":
        from .validator import canon_phone
        return canon_phone(got) == canon_phone(exp)
    return str(got).strip() == str(exp).strip()


def score_observation(case: dict, obs: dict, ftypes: dict | None = None) -> dict:
    """One (case, sample) -> a scored record. `obs` = {got_sets, choice_offered,
    choice_field}. `ftypes` = {field_id: type} for type-aware value equality (phone);
    it defaults to the canonical schema's. Pure: the aggregate math is exercised by
    --selftest."""
    if ftypes is None:
        ftypes = field_types()
    band = band_of(case)
    exp_sets = case["expect"].get("sets", {})
    exp_fids, got = set(exp_sets), obs["got_sets"]
    got_fids = set(got)
    inter = exp_fids & got_fids
    value_total = len(inter)
    value_ok = sum(_val_eq(got[fid], exp_sets[fid], ftypes.get(fid)) for fid in inter)

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


def run_baseline(n: int, label: str, eval_set: str, eval_set_name: str = "v1",
                 limit: int = 0, only: str = "",
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

    ftypes = field_types(schema)   # type-aware value equality (phone -> digits)
    is_v2, is_v3 = eval_set_name == "v2", eval_set_name == "v3"
    scored, bands, raw, total_cost = [], [], [], 0.0
    for si in range(n):
        for ci, case in enumerate(cases):
            try:
                obs = run_case(agent, lm, schema, case)
            except Exception as e:
                print(f"  !! {case['id']} sample {si}: {type(e).__name__}: {str(e)[:120]}", flush=True)
                continue
            s = score_observation(case, obs, ftypes)
            scored.append(s)
            bands.append(case.get("band"))   # lockstep with scored (survives skipped cases)
            rec = {"sample": si, **s, "got_sets": obs["got_sets"], "cost": obs["cost"]}
            if is_v2 or is_v3:
                # v2: realistic / contract-synthetic. v3: early / mid / late depth.
                # Either way this is the EVAL band, not score_observation's band.
                rec["band"] = case.get("band")
            if is_v3:
                rec["source"] = case.get("source")
            raw.append(rec)
            total_cost += obs["cost"]
        print(f"  sample {si+1}/{n} done  (running ${total_cost:.2f})", flush=True)

    if is_v3:
        # v3 has ONE headline (every case is a real context, all gated) plus a
        # depth-band breakdown: early 0-3 / mid 4-7 / late 8+ filled fields.
        agg = aggregate(scored)
        stab = stability(scored)
        by_band = {b: [s for s, bd in zip(scored, bands) if bd == b] for b in V3_BANDS}
        result = {"label": label, "model": lm.model, "n": n, "eval_set": "v3",
                  "cost_usd": round(total_cost, 4),
                  "metrics": agg,
                  "metrics_by_band": {b: aggregate(rows) for b, rows in by_band.items() if rows},
                  "band_counts": {b: len(rows) for b, rows in by_band.items()},
                  "stability": stab, "raw": raw}
        out = OUT_DIR / f"baseline-{label}.json"
        json.dump(result, open(out, "w"), indent=2, default=str)
        print_report(agg, stab, total_cost, scored,
                     header="Tier-1 (v3, all real contexts) — HEADLINE", show_cost=False)
        for b, rows in by_band.items():
            if not rows:
                continue
            print_report(aggregate(rows), stability(rows), total_cost, rows,
                         header=f"depth band: {b} ({len(rows)} obs)", show_cost=False)
        print(f"\ncost: ${total_cost:.2f}")
        print(f"\nwrote {out}")
        return

    if is_v2:
        # split on the eval band: realistic is the headline (gated vs criteria);
        # contract-synthetic is the v1-shape stress contract, reported not gated.
        real = [s for s, b in zip(scored, bands) if b == "realistic"]
        synth = [s for s, b in zip(scored, bands) if b == "contract-synthetic"]
        agg_r, agg_c = aggregate(real), aggregate(synth)
        stab_r = stability(real)
        result = {"label": label, "model": lm.model, "n": n, "eval_set": "v2",
                  "cost_usd": round(total_cost, 4),
                  "metrics_realistic": agg_r, "metrics_contract": agg_c,
                  "metrics": agg_r,   # headline alias for downstream that reads .metrics
                  "stability": stab_r, "raw": raw}
        out = OUT_DIR / f"baseline-{label}.json"
        json.dump(result, open(out, "w"), indent=2, default=str)
        print_report(agg_r, stab_r, total_cost, real,
                     header="Tier-1 (realistic band) — HEADLINE, gated vs criteria", show_cost=False)
        print_report(agg_c, stability(synth), total_cost, synth,
                     header="Contract band (synthetic) — reported, NOT gated", show_cost=False)
        print(f"\ncost: ${total_cost:.2f}")
        print(f"\nwrote {out}")
        return

    agg = aggregate(scored)
    stab = stability(scored)
    result = {"label": label, "model": lm.model, "n": n, "eval_set": eval_set,
              "cost_usd": round(total_cost, 4), "metrics": agg, "stability": stab, "raw": raw}
    out = OUT_DIR / f"baseline-{label}.json"
    json.dump(result, open(out, "w"), indent=2, default=str)
    print_report(agg, stab, total_cost, scored)
    print(f"\nwrote {out}")


def print_report(agg, stab, cost, scored, header="Tier-1 extractor metrics", show_cost=True):
    p = lambda r: "n/a" if r["rate"] is None else f"{r['rate']*100:5.1f}% (n={r['n']})"
    print(f"\n=== {header} ===")
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
    if show_cost:
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
        # phone: the validator stores digits, the frozen eval sets store the surface
        # form -> same number in any format is a MATCH ...
        (C("pending_phone", {"sets": {"phone": "(429) 555-2786"}}), O({"phone": "4295552786"}), True),
        (C("pending_phone", {"sets": {"phone": "+49 30 901820"}}), O({"phone": "+4930901820"}), True),
        # ... and a different number is still a MISS (the gate is not weakened)
        (C("pending_phone", {"sets": {"phone": "(429) 555-2786"}}), O({"phone": "4295552787"}), False),
    ]
    scored = []
    for case, obs, want_pass in checks:
        s = score_observation(case, obs)
        scored.append(s)
        assert s["passed"] == want_pass, f"{case['id']}: passed={s['passed']} want {want_pass}"

    # the two v3 scenario names join the unplaceable band; every v1/v2 name keeps
    # the band it had, so the frozen baselines stay comparable.
    assert band_of(C("bare_ambiguous", {"empty": True})) == "unplaceable"
    assert band_of(C("invalid_value", {"empty": True})) == "unplaceable"
    for scn in ("chitchat", "trap", "third_party", "restraint", "refusal",
                "narrative_trap", "third_party_fact"):
        assert band_of(C(scn, {"empty": True})) == "no_value", scn
    assert band_of(C("ambiguous", {"empty": True})) == "unplaceable"

    agg = aggregate(scored)
    # tp: single_name#1 (1) + bool (1) = 2; fp: trap(1)+bare_date(1) = 2; fn: 2 missed (#2 set wrong field? no)
    # #1 got==exp tp1; #2 got full_name (tp1) value wrong; #3 fn1; bool tp1; trap fp1; bare_date fp1
    c = agg["field_counts"]
    assert c == {"tp": 6, "fp": 2, "fn": 1}, c
    # 6 tp value-checks, 4 ok: full_name "Y" and the wrong phone digits are the misses
    assert abs(agg["value_match"] - 4 / 6) < 1e-9, agg["value_match"]
    # phone equality is by digits, both directions
    assert _val_eq("4157823311", "415.782.3311", "phone")
    assert _val_eq("+4930901820", "+49 30 901820", "phone")
    assert not _val_eq("4157823311", "415.782.3312", "phone")
    assert not _val_eq("4157823311", "415.782.3311")      # no type -> exact string
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
    ap.add_argument("--label", default=None,
                    help="output label (default teacher_v1 for v1; REQUIRED for v2 so it can't clobber v1 baselines)")
    ap.add_argument("--eval-set", choices=["v1", "v2", "v3"], default="v1",
                    help="v1 = frozen byte-identical set; v2 = realistic history + band split; "
                         "v3 = real farmed contexts + depth bands (see eval_gen.py)")
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
    # validate args before any LM construction (mirrors datagen's --behaviors check)
    if args.eval_set in ("v2", "v3") and not args.label:
        ap.error(f"--label is required with --eval-set {args.eval_set} "
                 "(a default would clobber the v1 baseline files)")
    label = args.label or "teacher_v1"
    path = EVAL_SETS[args.eval_set]
    run_baseline(args.n, label, path, args.eval_set, args.limit, args.only,
                 args.backend, args.model, args.port)


if __name__ == "__main__":
    main()
