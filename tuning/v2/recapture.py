"""recapture.py — doc-20 chapter-1 item 2: the replay-capture script.

The guidance tweaks (item 1) changed the Respond docstring + render_guidance, so
every responder row already in a run's train.jsonl embeds a system prompt that
serving will never send again (doc-20 §4 "The re-capture consequence"). This
module replays a run's FROZEN snapshots through the CURRENT teacher prompt and
re-captures the training targets.

It reuses datagen's plumbing exactly (doc-20 forbids a parallel capture path):
per snapshot -> datagen.rebuild_state -> agent.forward(with_response=True) ->
datagen.capture_pairs. The snapshots are the frozen substrate; only the labels
(and the prompt baked into `messages`) are regenerated. Output rows are
byte-compatible with datagen's train.jsonl, so sim_to_sft consumes them unchanged.

  Selftest (free, no model):  tuning/v2/.venv/bin/python -m tuning.v2.recapture --selftest
  Dry run ($$):               tuning/v2/.venv/bin/python -m tuning.v2.recapture \
                                  --run tuning/v2/datagen_runs/eval_farm_p3 \
                                  --out tuning/v2/datagen_runs/eval_farm_p3_recap5 \
                                  --limit 5
"""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import datagen
from .schema import Schema, load_schema
from .program import Respond, build_teacher
from .sim_to_sft import canon_responder

# Paid teacher slug is the default (doc-20 §6 decision: full forward, temp 0,
# nemotron). The :free route churns; the recapture must be reproducible.
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"

# Respond signature input fields, in ChatAdapter render order (mirrors
# datagen.BLOCK_ORDER for Extract). Used for the offline parity render.
RESP_BLOCK_ORDER = ["form_schema", "filled_fields", "recent_history",
                    "user_message", "actions_taken", "guidance"]


# ---- offline parity anchor (the datagen.expected_extractor_system pattern) ----

def expected_responder_system() -> str:
    """Offline ChatAdapter render of the CURRENT Respond signature's system prompt
    (no demos, no LM call). A captured responder row's system message must byte-equal
    this; a mismatch is the train/serve divergence doc-20 §4 warns about."""
    from dspy.adapters.chat_adapter import ChatAdapter
    dummy = {f: "" for f in RESP_BLOCK_ORDER}
    return ChatAdapter().format(Respond, [], dummy)[0]["content"]


def _expected_system(module: str) -> str:
    return (expected_responder_system() if module == "responder"
            else datagen.expected_extractor_system())


def parity_row(row: dict, expected: dict) -> tuple[bool, dict]:
    """Byte-compare one captured row's system message against the offline render for
    its module. `expected` caches {module: system_text}. Reports the first differing
    line instead of crashing (datagen._first_diff)."""
    msgs = row["messages"]
    exp = expected[row["module"]]
    roles_ok = [m["role"] for m in msgs] == ["system", "user"]
    system_ok = bool(msgs) and msgs[0]["content"] == exp
    detail = {"module": row["module"], "session": row.get("session"),
              "turn": row.get("turn"), "roles_ok": roles_ok,
              "system_byte_equal": system_ok}
    if not system_ok and msgs:
        detail["first_diff"] = datagen._first_diff(exp, msgs[0]["content"])
    return (roles_ok and system_ok), detail


def check_parity(rows: list[dict]) -> dict:
    """Parity over every captured row. A mismatch is a HARD ERROR in the report,
    not a silent drop."""
    expected = {"extractor": _expected_system("extractor"),
                "responder": _expected_system("responder")}
    mismatches = []
    for r in rows:
        ok, detail = parity_row(r, expected)
        if not ok:
            mismatches.append(detail)
    return {"checked": len(rows), "mismatches": mismatches,
            "status": "error" if mismatches else "ok"}


# ---- replay loop (datagen.run_injection plumbing, with_response=True) ----------

def replay(agent, lm, schema: Schema, snapshots: list[dict], limit: int = 0) -> tuple[list, int, int]:
    """For each snapshot: rebuild_state -> forward(with_response=True) -> capture_pairs.
    Replays EVERY snapshot in order (turn-0 empty-user-message rows included), matching
    farm_session / run_injection inclusion. Returns (rows, turns_replayed, n_turn0)."""
    rows: list[dict] = []
    turns = n_turn0 = 0
    for snap in snapshots:
        if limit and turns >= limit:
            break
        if not snap.get("user_message"):
            n_turn0 += 1
        state = datagen.rebuild_state(schema, snap)
        prev = len(lm.history)
        # identical base to farm rows (source=farm, behavior=natural, snapshot=None)
        # so the re-captured rows are structurally indistinguishable to sim_to_sft.
        agent(state=state, user_message=snap["user_message"],
              history=snap["history"], with_response=True)
        base = {"source": "farm", "behavior": "natural",
                "session": snap.get("session"), "turn": snap.get("turn"), "snapshot": None}
        new_rows, _ = datagen.capture_pairs(lm, prev, True, base)
        rows.extend(new_rows)
        turns += 1
    return rows, turns, n_turn0


# ---- report ------------------------------------------------------------------

def build_report(run_dir: Path, out_dir: Path, model: str, rows: list[dict],
                 turns: int, n_snap: int, n_turn0: int, parity: dict, lm) -> dict:
    from collections import Counter
    by_module = Counter(r["module"] for r in rows)
    ext = [r for r in rows if r["module"] == "extractor"]
    res = [r for r in rows if r["module"] == "responder"]
    resp_wf_post = sum(datagen.is_well_formed("responder", canon_responder(r["completion"])) for r in res)
    cost = sum((c.get("cost") or 0.0) for c in lm.history)
    return {
        "source_run": str(run_dir),
        "out": str(out_dir),
        "model": model,
        "temperature": 0,
        "with_response": True,
        "snapshots_total": n_snap,
        "turns_replayed": turns,
        "included": {
            "turn0_empty_user_message": n_turn0,
            "note": "all snapshot rows replayed in order (turn-0 empty-message rows "
                    "included) — matches farm_session / run_injection inclusion",
        },
        "rows_captured": len(rows),
        "by_module": dict(by_module),
        "well_formed": {
            "extractor": sum(1 for r in ext if r.get("well_formed")),
            "responder_raw": sum(1 for r in res if r.get("well_formed")),
            "responder_post_canon": resp_wf_post,
            "responder_total": len(res),
        },
        "cost_total": cost,
        "parity": parity,
    }


# ---- --out safety guards -----------------------------------------------------

def guard_out(run_dir: Path, out_dir: Path) -> str | None:
    """Return an error string if --out is unsafe, else None. Refuses out==run,
    out inside run, and an out that already holds a train.jsonl (would clobber a run)."""
    r, o = run_dir.resolve(), out_dir.resolve()
    if o == r:
        return f"--out must differ from --run (both resolve to {o})"
    if r in o.parents:
        return f"--out must not live inside --run ({o} is under {r})"
    if (o / "train.jsonl").exists():
        return f"--out already contains a train.jsonl ({o / 'train.jsonl'}) — refusing to clobber"
    return None


# ---- driver ------------------------------------------------------------------

def run(run_dir: Path, out_dir: Path, model: str, limit: int) -> dict:
    import dspy
    from .openrouter_lm import OpenRouterLM

    snap_path = run_dir / "snapshots.jsonl"
    if not snap_path.exists():
        raise SystemExit(f"--run has no snapshots.jsonl: {snap_path}")
    err = guard_out(run_dir, out_dir)
    if err:
        raise SystemExit(f"[recapture] {err}")

    snapshots = [json.loads(l) for l in open(snap_path)]
    schema = load_schema()
    lm = OpenRouterLM(model=model, temperature=0.0)
    dspy.configure(lm=lm)
    agent = build_teacher(schema)

    print(f"recapture  run={run_dir}  model={model}  temp=0  snapshots={len(snapshots)}"
          f"  limit={limit or '-'}\n", flush=True)
    rows, turns, n_turn0 = replay(agent, lm, schema, snapshots, limit)
    parity = check_parity(rows)
    report = build_report(run_dir, out_dir, model, rows, turns, len(snapshots), n_turn0, parity, lm)

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "train.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    json.dump(report, open(out_dir / "report.json", "w"), indent=2, default=str)

    print(f"turns={turns}  rows={report['rows_captured']}  by_module={report['by_module']}")
    print(f"responder well-formed: raw={report['well_formed']['responder_raw']}/"
          f"{report['well_formed']['responder_total']}  "
          f"post-canon={report['well_formed']['responder_post_canon']}/"
          f"{report['well_formed']['responder_total']}")
    print(f"parity: {parity['status']}  (checked {parity['checked']}, "
          f"{len(parity['mismatches'])} mismatch)")
    if parity["status"] == "error":
        print("!!! PARITY MISMATCH — captured prompt diverges from the current render. "
              "See report.json['parity']['mismatches'].")
    print(f"cost=${report['cost_total']:.4f}  ->  {out_dir}")
    return report


# ---- selftest (offline, no network) ------------------------------------------

@dataclass
class _Msg:
    content: str
    role: str = "assistant"
    tool_calls = None
    reasoning_content = None


@dataclass
class _Choice:
    message: _Msg
    index: int = 0
    finish_reason: str = "stop"


@dataclass
class _Resp:
    choices: list
    model: str
    usage: dict = field(default_factory=dict)
    cache_hit: bool = False
    _hidden_params: dict = field(default_factory=dict)


def _stub_lm():
    """A fake dspy LM: renders the REAL current prompt (via ChatAdapter, since the
    program formats before calling), and returns a canned completion keyed on module.
    Cycles through responder completions so one turn is malformed and one well-formed."""
    import dspy

    XC = "[[ ## extractions ## ]]\n[]\n\n[[ ## completed ## ]]"          # well-formed, empty
    RESP = ["Got it, next question?",                                    # malformed (no markers)
            "[[ ## response_text ## ]]\nSure, which program?\n\n[[ ## completed ## ]]"]  # well-formed

    class _StubLM(dspy.BaseLM):
        def __init__(self):
            super().__init__(model="stub", cache=False)
            self._ri = 0

        def forward(self, prompt=None, messages=None, **kwargs):
            sysc = "\n".join(m["content"] for m in (messages or []) if m.get("role") == "system")
            if "`response_text`" in sysc:
                text = RESP[self._ri % len(RESP)]
                self._ri += 1
            else:
                text = XC
            return _Resp(choices=[_Choice(_Msg(text))], model="stub",
                         _hidden_params={"response_cost": 0.0})

    return _StubLM()


def selftest() -> bool:
    import copy
    import dspy

    schema = load_schema()
    fid_choice = next(f.field_id for f in schema.fields if f.button_choice)

    # 2-3 hand-built snapshots on the northfield schema: turn-0 empty message,
    # a plain answer, and one with a pending target (exercises rebuild_state pending).
    snapshots = [
        {"session": 900, "turn": 0, "form_state": {}, "pending": None,
         "history": [], "user_message": ""},
        {"session": 900, "turn": 1, "form_state": {}, "pending": None,
         "history": [{"role": "assistant", "content": "Hi! What's your name?"}],
         "user_message": "I'm Ada Lovelace"},
        {"session": 900, "turn": 2, "form_state": {}, "pending": fid_choice,
         "history": [{"role": "assistant", "content": "Which program?"}],
         "user_message": "not sure yet"},
    ]

    checks: list[tuple[str, bool]] = []

    def ck(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    # --- replay with the stub, then the acceptance checks --------------------
    lm = _stub_lm()
    dspy.configure(lm=lm)
    agent = build_teacher(schema)
    rows, turns, n_turn0 = replay(agent, lm, schema, snapshots, limit=0)

    ck("replayed all 3 snapshots (turn-0 empty-message included)", turns == 3 and n_turn0 == 1)
    res = [r for r in rows if r["module"] == "responder"]
    ck("every snapshot yields a responder row", len(res) == 3)
    ck("re-captured rows are train.jsonl-compatible (keys match a farm row)",
       all({"module", "source", "behavior", "session", "turn", "snapshot",
            "messages", "completion", "cost", "well_formed", "adapter_retried",
            "retry_completion"} <= set(r) for r in rows))
    # state rebuild + capture -> rows pass is_well_formed after canon_responder
    ck("every responder row is_well_formed after canon_responder (fixes malformed too)",
       all(datagen.is_well_formed("responder", canon_responder(r["completion"])) for r in res))
    ck("at least one raw responder completion was malformed (canon actually did work)",
       any(not datagen.is_well_formed("responder", r["completion"]) for r in res))

    # --- parity byte-match: one passing, one deliberately corrupted ----------
    clean = check_parity(rows)
    ck("parity clean on freshly captured rows (0 mismatch, status ok)",
       clean["status"] == "ok" and not clean["mismatches"])

    corrupted = copy.deepcopy(rows)
    corrupted[0]["messages"][0]["content"] += "\nTAMPERED LINE"
    bad = check_parity(corrupted)
    ck("parity detects a corrupted system prompt (1 mismatch, status error, first_diff reported)",
       bad["status"] == "error" and len(bad["mismatches"]) == 1
       and "first_diff" in bad["mismatches"][0])

    # --- --out safety guards -------------------------------------------------
    run_dir = datagen.RUN_DIR / "eval_farm_p3"
    ck("guard refuses --out == --run",
       guard_out(run_dir, run_dir) is not None)
    ck("guard refuses --out inside --run",
       guard_out(run_dir, run_dir / "sub") is not None)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        fresh = Path(td) / "new_out"
        ck("guard allows a fresh empty --out dir", guard_out(run_dir, fresh) is None)
        fresh.mkdir()
        (fresh / "train.jsonl").write_text("{}\n")
        ck("guard refuses an --out that already holds a train.jsonl",
           guard_out(run_dir, fresh) is not None)

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n=== recapture selftest: {passed}/{len(checks)} checks passed ===")
    return passed == len(checks)


# ---- CLI ---------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Replay a run's snapshots through the current teacher prompt.")
    ap.add_argument("--selftest", action="store_true", help="offline, no model — hand-built cases")
    ap.add_argument("--run", help="datagen_runs dir holding snapshots.jsonl (the frozen substrate)")
    ap.add_argument("--out", help="NEW output dir; must not equal/live-inside --run, and must not already hold train.jsonl")
    ap.add_argument("--limit", type=int, default=0, help="cap turns replayed (dry runs)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"teacher slug (default {DEFAULT_MODEL})")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if not args.run or not args.out:
        ap.error("--run and --out are required (unless --selftest)")
    run(Path(args.run), Path(args.out), args.model, args.limit)


if __name__ == "__main__":
    main()
