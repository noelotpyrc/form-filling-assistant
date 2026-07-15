"""M4 P2 — SFT format bridge + responder target canonicalization.

Turns a datagen run's `train.jsonl` (rows of `{module, source, behavior, session,
turn, snapshot, messages, completion, ...}`, the shape `datagen.py` emits) into the
trainer's input shape: rows of `{module, source, behavior, messages}` where
`messages` is the original demo-stripped `[system, user]` with the target appended
as a final `{"role": "assistant", "content": <target>}` (the last message is the
SFT label; `train_sft_format_modal.py`'s convert() reads only `messages`, tolerating
the extra metadata keys).

Two transforms, one per module:
  - extractor: pass `completion` through UNCHANGED (structured target; a malformed
    one is not reconstructable-with-certainty and the observed rate is 0%). A
    malformed extractor row is DROPPED, counted, and loudly warned — never silent.
  - responder: canonicalize EVERY completion uniformly (no branch on which marker
    is missing) by re-wrapping the shared `program.strip_markers()` prose —
    `canon = "[[ ## response_text ## ]]\n" + strip_markers(c) + "\n\n[[ ## completed ## ]]"`.
    This both fixes the ~1/3 malformed and normalizes whitespace on already-well-
    formed targets — uniform targets are the point. Each canon row is asserted to
    pass `datagen.is_well_formed("responder", ...)`.

Split: seeded, GROUP-AWARE train/val at the GROUP level (a group is entirely in
train or entirely in val), where a group = the persona/session a row came from
(farm -> `session`; injected-with-snapshot -> `snapshot.session`; injected
constructed-context -> its own singleton group). This blocks near-duplicate leakage
across the split. Outputs per-module files (separate SFT artifacts per predictor):
`train_{module}.jsonl` / `val_{module}.jsonl`, plus `report.json`.

Run:
  selftest (free):  tuning/v2/.venv/bin/python -m tuning.v2.sim_to_sft --selftest
  bridge pilot2:    tuning/v2/.venv/bin/python -m tuning.v2.sim_to_sft --run pilot2
  bridge a file:    tuning/v2/.venv/bin/python -m tuning.v2.sim_to_sft --in path/to/train.jsonl --out-dir tuning/v2/sft_data/foo
Outputs (gitignored): tuning/v2/sft_data/<run>/{train,val}_{extractor,responder}.jsonl + report.json
"""
from __future__ import annotations
import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from .program import strip_markers
from . import datagen  # is_well_formed (the shared post-canon marker check)

V2_DIR = Path(__file__).resolve().parent
RUN_DIR = V2_DIR / "datagen_runs"
OUT_ROOT = V2_DIR / "sft_data"
DEFAULT_IN = RUN_DIR / "pilot2" / "train.jsonl"
MODULES = ("extractor", "responder")


# ======================================================================
# core transform
# ======================================================================

def canon_responder(completion: str) -> str:
    """Uniform responder target: re-wrap the shared strip_markers() prose in the
    canonical response_text/completed scaffold. Idempotent (strip_markers removes any
    already-present markers before re-wrapping) and fixes any missing/partial marker."""
    return f"[[ ## response_text ## ]]\n{strip_markers(completion)}\n\n[[ ## completed ## ]]"


def group_key(row: dict, idx: int):
    """The persona/session a row belongs to (split unit). Farm rows and injected rows
    derived from the SAME farm snapshot share a session -> same group (prevents a
    persona's context leaking across train/val). Constructed injections (no snapshot,
    no session) are context-light singletons -> each its own group."""
    if row["source"] == "farm":
        return ("session", row["session"])
    snap = row.get("snapshot")
    if snap is not None:
        return ("session", snap["session"])
    return ("singleton", idx)


def reshape(row: dict, target: str) -> dict:
    """Output row: original demo-stripped [system, user] messages (untouched) with the
    target appended as the assistant label. Only {module, source, behavior, messages}
    are kept — the trainer reads `messages`, tolerating module/source/behavior."""
    return {"module": row["module"], "source": row["source"], "behavior": row["behavior"],
            "messages": list(row["messages"]) + [{"role": "assistant", "content": target}]}


def transform(rows: list[dict]) -> tuple[list[tuple[dict, tuple]], list[dict], Counter]:
    """(out_rows_with_group, dropped_extractor_rows, responder_canon_stats).
    out_rows_with_group is a list of (reshaped_row, group_key)."""
    out: list[tuple[dict, tuple]] = []
    dropped: list[dict] = []
    canon_stats: Counter = Counter()   # "fixed" (was malformed) / "normalized" (was well-formed)

    for idx, row in enumerate(rows):
        module = row["module"]
        gk = group_key(row, idx)
        if module == "extractor":
            if not row.get("well_formed"):
                dropped.append({"idx": idx, "source": row["source"], "behavior": row["behavior"]})
                continue
            target = row["completion"]
        elif module == "responder":
            was_wf = datagen.is_well_formed("responder", row["completion"])
            target = canon_responder(row["completion"])
            assert datagen.is_well_formed("responder", target), \
                f"responder still malformed post-canon: {target!r}"
            canon_stats["normalized" if was_wf else "fixed"] += 1
        else:
            print(f"\n!!! WARNING: row {idx} has unknown module {module!r} — DROPPING !!!")
            dropped.append({"idx": idx, "module": module})
            continue
        out.append((reshape(row, target), gk))

    if dropped_ext := [d for d in dropped if d.get("module") != "responder"]:
        # extractor drops should be 0 (observed 0% malformed). Never silent.
        n = len(dropped_ext)
        print("\n" + "!" * 68)
        print(f"!!! WARNING: DROPPED {n} malformed extractor row(s) (unreconstructable) !!!")
        for d in dropped_ext:
            print(f"!!!   idx={d.get('idx')} source={d.get('source')} behavior={d.get('behavior')}")
        print("!" * 68)
    return out, dropped, canon_stats


# ======================================================================
# group-aware split
# ======================================================================

def split_groups(group_keys: list[tuple], val_ratio: float, seed: int) -> tuple[set, list]:
    """Assign whole groups to val. Deterministic: sort keys, seeded-shuffle, take the
    first round(val_ratio * n) as val. Returns (val_group_set, ordered_all_keys)."""
    keys = sorted(set(group_keys), key=lambda k: (k[0], k[1]))
    shuffled = keys[:]
    random.Random(seed).shuffle(shuffled)
    n_val = round(val_ratio * len(shuffled))
    return set(shuffled[:n_val]), keys


# ======================================================================
# report
# ======================================================================

def build_report(in_path, out_dir, rows, out_rows, dropped, canon_stats,
                 val_groups, all_keys, file_counts, val_ratio, seed) -> dict:
    def _grpstr(k):
        return f"{k[0]}:{k[1]}"
    group_sizes = Counter(gk for _, gk in out_rows)
    return {
        "input": str(in_path),
        "out_dir": str(out_dir),
        "val_ratio": val_ratio,
        "seed": seed,
        "rows_in": {
            "total": len(rows),
            "by_module": dict(Counter(r["module"] for r in rows)),
            "by_source_module": {f"{s}/{m}": n for (s, m), n
                                 in sorted(Counter((r["source"], r["module"]) for r in rows).items())},
            "by_behavior": dict(Counter(r["behavior"] for r in rows)),
        },
        "rows_out": {
            "total": len(out_rows),
            "by_module": dict(Counter(r["module"] for r, _ in out_rows)),
        },
        "responder_canon": {"fixed": canon_stats.get("fixed", 0),
                            "normalized": canon_stats.get("normalized", 0),
                            "total": sum(canon_stats.values())},
        "extractor_drops": {"count": len([d for d in dropped if d.get("module") != "responder"]),
                            "rows": [d for d in dropped if d.get("module") != "responder"]},
        "split": {
            "n_groups": len(all_keys),
            "n_val_groups": len(val_groups),
            "val_groups": sorted(_grpstr(k) for k in val_groups),
            "files": file_counts,
        },
        "groups": {_grpstr(k): {"rows": group_sizes.get(k, 0),
                               "split": "val" if k in val_groups else "train"}
                   for k in all_keys},
    }


def print_report(rep: dict):
    print("\n=== sim_to_sft report ===")
    print(f"input : {rep['input']}")
    print(f"out   : {rep['out_dir']}")
    ri = rep["rows_in"]
    print(f"\nrows in : {ri['total']}  by_module={ri['by_module']}")
    print(f"  by source/module: {ri['by_source_module']}")
    print(f"  by behavior: {ri['by_behavior']}")
    ro = rep["rows_out"]
    print(f"rows out: {ro['total']}  by_module={ro['by_module']}")

    rc = rep["responder_canon"]
    print(f"\nresponder canonicalization: {rc['total']} total  "
          f"({rc['fixed']} malformed->fixed, {rc['normalized']} well-formed->normalized)")
    ed = rep["extractor_drops"]
    print(f"extractor drops: {ed['count']} (expected 0)")

    sp = rep["split"]
    print(f"\nsplit (val_ratio={rep['val_ratio']}, seed={rep['seed']}): "
          f"{sp['n_groups']} groups, {sp['n_val_groups']} -> val")
    print(f"  val groups: {sp['val_groups']}")
    print("  files:")
    for name in ("train_extractor", "val_extractor", "train_responder", "val_responder"):
        print(f"    {name+'.jsonl':24} {sp['files'].get(name, 0)}")
    print("  group assignment:")
    for k, g in rep["groups"].items():
        print(f"    {k:16} rows={g['rows']:3}  -> {g['split']}")


# ======================================================================
# driver
# ======================================================================

def bridge(in_path: Path, out_dir: Path, val_ratio: float, seed: int) -> dict:
    rows = [json.loads(l) for l in open(in_path) if l.strip()]
    out_rows, dropped, canon_stats = transform(rows)
    val_groups, all_keys = split_groups([gk for _, gk in out_rows], val_ratio, seed)

    out_dir.mkdir(parents=True, exist_ok=True)
    file_counts: dict[str, int] = {}
    for module in MODULES:
        for split, in_val in (("train", False), ("val", True)):
            sel = [r for r, gk in out_rows
                   if r["module"] == module and (gk in val_groups) == in_val]
            name = f"{split}_{module}"
            with open(out_dir / f"{name}.jsonl", "w") as f:
                for r in sel:
                    f.write(json.dumps(r) + "\n")
            file_counts[name] = len(sel)

    rep = build_report(in_path, out_dir, rows, out_rows, dropped, canon_stats,
                       val_groups, all_keys, file_counts, val_ratio, seed)
    json.dump(rep, open(out_dir / "report.json", "w"), indent=2)
    return rep


# ======================================================================
# selftest (pure, synthetic rows — no LLM, no files)
# ======================================================================

def selftest():
    SYS = {"role": "system", "content": "SYSTEM PROMPT"}

    def mk(module, completion, source="inject", behavior="b", session=None,
           snapshot=None, well_formed=True, user="USER MSG"):
        return {"module": module, "source": source, "behavior": behavior,
                "session": session, "snapshot": snapshot, "well_formed": well_formed,
                "completion": completion,
                "messages": [dict(SYS), {"role": "user", "content": user}]}

    # --- reshape: assistant appended, roles [system, user, assistant], originals intact ---
    r = mk("extractor", "[[ ## extractions ## ]]\n[]\n\n[[ ## completed ## ]]")
    out, dropped, cs = transform([r])
    assert len(out) == 1 and not dropped
    orow = out[0][0]
    assert [m["role"] for m in orow["messages"]] == ["system", "user", "assistant"]
    assert orow["messages"][0]["content"] == "SYSTEM PROMPT"       # original untouched
    assert orow["messages"][1]["content"] == "USER MSG"
    assert orow["messages"][-1]["content"] == r["completion"]      # extractor: verbatim
    assert set(orow) == {"module", "source", "behavior", "messages"}
    assert r["messages"][-1]["role"] == "user"                     # did not mutate input

    # --- canonicalization: malformed / bare-prose / well-formed all -> full scaffold ---
    def canon_ok(c):
        out, _, _ = transform([mk("responder", c)])
        target = out[0][0]["messages"][-1]["content"]
        assert datagen.is_well_formed("responder", target), target
        assert target.startswith("[[ ## response_text ## ]]\n")
        assert target.endswith("\n\n[[ ## completed ## ]]")
        return target

    malformed = "Sure, got it!\n\n[[ ## completed ## ]]"           # completed-marker only, no response_text
    bare = "Just some prose, no markers at all."                   # bare prose
    wellformed = "[[ ## response_text ## ]]\nHello there.\n\n[[ ## completed ## ]]"
    assert not datagen.is_well_formed("responder", malformed)
    assert not datagen.is_well_formed("responder", bare)
    assert datagen.is_well_formed("responder", wellformed)
    for c in (malformed, bare, wellformed):
        target = canon_ok(c)
        assert canon_responder(canon_responder(c)) == canon_responder(c)   # idempotence
        assert canon_responder(target) == target                           # canon of canon
    # canon stat labels: malformed -> fixed, well-formed -> normalized
    _, _, cs = transform([mk("responder", malformed), mk("responder", bare),
                          mk("responder", wellformed)])
    assert cs["fixed"] == 2 and cs["normalized"] == 1, cs

    # --- extractor malformed -> dropped + counted (never becomes a row) ---
    good = mk("extractor", "[[ ## extractions ## ]]\n[]\n\n[[ ## completed ## ]]", well_formed=True)
    bad = mk("extractor", "oops no markers", well_formed=False)
    out, dropped, cs = transform([good, bad])
    assert len(out) == 1 and out[0][0]["messages"][-1]["content"] == good["completion"]
    assert len(dropped) == 1 and dropped[0]["idx"] == 1

    # --- split: group-aware, no straddle, deterministic ---
    rows = []
    # 3 farm sessions, 2 rows each
    for s in (10, 11, 12):
        rows.append(mk("extractor", "[[ ## extractions ## ]]\n[]\n\n[[ ## completed ## ]]",
                       source="farm", session=s))
        rows.append(mk("responder", "hi", source="farm", session=s))
    # injected rows sharing a farm snapshot -> must group with that session
    rows.append(mk("extractor", "[[ ## extractions ## ]]\n[]\n\n[[ ## completed ## ]]",
                   source="inject", snapshot={"session": 10, "turn": 3}))
    # constructed singletons (no snapshot, no session)
    for _ in range(6):
        rows.append(mk("extractor", "[[ ## extractions ## ]]\n[]\n\n[[ ## completed ## ]]",
                       source="inject", snapshot=None))
    out, _, _ = transform(rows)
    val_groups, all_keys = split_groups([gk for _, gk in out], 0.15, 0)
    # 3 session groups + 6 singleton groups = 9 (the inject-snapshot row folds into session 10)
    assert len(all_keys) == 9, all_keys
    assert ("session", 10) in all_keys
    assert len([k for k in all_keys if k[0] == "singleton"]) == 6
    # no group straddles: every group maps to a single split
    split_of = {}
    for r, gk in out:
        s = "val" if gk in val_groups else "train"
        assert split_of.setdefault(gk, s) == s, f"group {gk} straddles"
    # the inject-snapshot(session 10) row lands with session 10's farm rows
    s10 = [(r, gk) for r, gk in out if gk == ("session", 10)]
    assert len(s10) == 3 and all(gk == ("session", 10) for _, gk in s10)
    # determinism: same seed -> identical val set; different call -> same result
    v2, _ = split_groups([gk for _, gk in out], 0.15, 0)
    assert v2 == val_groups
    # a different seed generally differs but must still be a valid subset of the keys
    v3, _ = split_groups([gk for _, gk in out], 0.15, 1)
    assert v3 <= set(all_keys)

    print("selftest: all assertions passed")


# ======================================================================
# CLI
# ======================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default="", help="path to a datagen train.jsonl")
    ap.add_argument("--run", default="", help="datagen run name (uses datagen_runs/<run>/train.jsonl)")
    ap.add_argument("--out-dir", default="", help="output dir (default sft_data/<run>/)")
    ap.add_argument("--val-ratio", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    if args.run:
        in_path = RUN_DIR / args.run / "train.jsonl"
        run_name = args.run
    elif args.in_path:
        in_path = Path(args.in_path)
        run_name = in_path.parent.name
    else:
        in_path = DEFAULT_IN
        run_name = DEFAULT_IN.parent.name
    if not in_path.exists():
        ap.error(f"input not found: {in_path}")
    out_dir = Path(args.out_dir) if args.out_dir else OUT_ROOT / run_name

    rep = bridge(in_path, out_dir, args.val_ratio, args.seed)
    print_report(rep)
    print(f"\nwritten to {out_dir}/")


if __name__ == "__main__":
    main()
