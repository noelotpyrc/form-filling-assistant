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
    INJECT extractor rows are additionally CURATED (see CURATION): a row whose
    parsed extraction list violates its behavior's designed convention is DROPPED
    (quota shortfall, not label editing). Farm extractor rows are organic teacher
    judgment and are never curated.
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
across the split. The val cut is ROW-WEIGHTED (groups accumulated until their row
budget hits val_ratio of all rows) so val mirrors corpus composition — a group-count
cut let small singleton groups crowd out the few heavyweight farm sessions. Outputs per-module files (separate SFT artifacts per predictor):
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
import re
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
# inject-extractor convention curation
# ======================================================================
# Inject extractor rows are SYNTHESIZED to a convention we know a priori: each
# behavior template dictates the exact extraction shape the student should emit.
# So a row whose parsed extraction list violates that shape is a datagen quota
# shortfall (the generator produced an off-spec sample) — we DROP it. This is
# NOT label editing: we never rewrite a completion, only decline to keep a
# violating one. Farm extractor rows are organic teacher judgment with no
# a-priori convention and are NEVER curated (nor are responder rows). Behaviors
# absent from the table (e.g. invalid_value, and any unknown/future behavior)
# carry no constraint and pass through untouched.
CURATION = {
    # empty: extraction list must be []
    "chitchat": "empty", "restraint_question": "empty", "trap": "empty",
    "third_party": "empty", "refusal": "empty",
    # null_only: non-empty, every pair's field_id is null
    "bare_date": "null_only", "bare_ambiguous": "null_only",
    # engaged_only: non-empty, every pair has a field_id and value == ""
    "deflect": "engaged_only", "deflect_free": "engaged_only",
    "asks_about_field": "engaged_only",
    # valued: at least one pair with non-null field_id and non-empty value
    "typed_choice": "valued", "precedence": "valued", "correction": "valued",
    "compound": "valued", "bulk": "valued", "partial_select": "valued",
    "cross_select": "valued", "wrapped_value": "valued", "boolean_phrase": "valued",
    # valued_or_engaged: non-empty, every pair has a non-null field_id (value free)
    "no_match": "valued_or_engaged",
    # valued_2: >=2 pairs each with a non-null field_id and a non-empty value
    "compound_volunteer": "valued_2",
    # pending_bind: the null-fallback / pending-bind shape for a bare answer. COMPROMISE
    # (see curation_passes): the bridge row does NOT carry the case's pending field id
    # (constructed inject rows have snapshot=None, no pending recorded), so the exact
    # "field_id == pending" rule is not enforceable. Weaker deterministic rule used.
    "pending_bare": "pending_bind",
}

_EXTRACT_RE = re.compile(r"\[\[ ## extractions ## \]\](.*?)\[\[ ## completed", re.DOTALL)


def parse_extractions(completion: str):
    """The extraction list between the markers, or None if absent/unparseable."""
    m = _EXTRACT_RE.search(completion)
    if not m:
        return None
    try:
        data = json.loads(m.group(1).strip())
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, list) else None


def curation_passes(rule: str, pairs: list) -> bool:
    """Does the parsed extraction list satisfy the behavior's convention rule?"""
    def fid(p): return p.get("field_id") if isinstance(p, dict) else None
    def val(p): return p.get("value") if isinstance(p, dict) else None
    if rule == "empty":
        return len(pairs) == 0
    if rule == "null_only":
        return len(pairs) > 0 and all(fid(p) is None for p in pairs)
    if rule == "engaged_only":
        return len(pairs) > 0 and all(fid(p) is not None and val(p) == "" for p in pairs)
    if rule == "valued":
        return any(fid(p) is not None and val(p) not in (None, "") for p in pairs)
    if rule == "valued_2":
        return sum(1 for p in pairs if fid(p) is not None and val(p) not in (None, "")) >= 2
    if rule == "pending_bind":
        # COMPROMISE: the row does not carry the case's pending field id, so we cannot
        # enforce "field_id == the pending field". Weaker deterministic rule: exactly one
        # pair, non-empty value, and field_id is null (the {null,value} fallback) OR one of
        # the pending-eligible ids {full_name, phone, email, dob} (the pending-bind).
        if len(pairs) != 1:
            return False
        p = pairs[0]
        return val(p) not in (None, "") and fid(p) in (None, "full_name", "phone", "email", "dob")
    if rule == "valued_or_engaged":
        return len(pairs) > 0 and all(fid(p) is not None for p in pairs)
    return True  # unknown rule -> no constraint


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


def transform(rows: list[dict], veto=None) -> tuple[list[tuple[dict, tuple]], list[dict], Counter, dict]:
    """(out_rows_with_group, dropped_rows, responder_canon_stats, curation).
    out_rows_with_group is a list of (reshaped_row, group_key). `curation` maps
    behavior -> Counter(kept / dropped / unparseable) for inject-extractor rows.

    `veto` (doc-20 item 5, Tier-1 responder curation): a callable row -> (drop, reason).
    When given, a responder row it vetoes is DROPPED and logged (into `dropped`, with
    module="responder") instead of canonicalized — teacher writes, code vetoes, exactly
    like the inject-extractor CURATION path. When None (the default, and every existing
    caller), the responder path is unchanged and byte-identical."""
    out: list[tuple[dict, tuple]] = []
    dropped: list[dict] = []
    canon_stats: Counter = Counter()   # "fixed" (was malformed) / "normalized" (was well-formed)
    curation: dict[str, Counter] = defaultdict(Counter)  # behavior -> kept/dropped/unparseable

    for idx, row in enumerate(rows):
        module = row["module"]
        gk = group_key(row, idx)
        if module == "extractor":
            if not row.get("well_formed"):
                dropped.append({"idx": idx, "source": row["source"], "behavior": row["behavior"]})
                continue
            # INJECT extractor rows: curate against the behavior's convention.
            rule = CURATION.get(row["behavior"]) if row["source"] == "inject" else None
            if rule is not None:
                pairs = parse_extractions(row["completion"])
                if pairs is None:
                    curation[row["behavior"]]["unparseable"] += 1
                    curation[row["behavior"]]["dropped"] += 1
                    continue
                if not curation_passes(rule, pairs):
                    curation[row["behavior"]]["dropped"] += 1
                    continue
                curation[row["behavior"]]["kept"] += 1
            target = row["completion"]
        elif module == "responder":
            if veto is not None:
                drop, reason = veto(row)
                if drop:
                    dropped.append({"idx": idx, "module": "responder", "source": row["source"],
                                    "behavior": row["behavior"], "session": row.get("session"),
                                    "turn": row.get("turn"), "reason": reason})
                    continue
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
    return out, dropped, canon_stats, dict(curation)


# ======================================================================
# group-aware split
# ======================================================================

def split_groups(group_keys: list[tuple], val_ratio: float, seed: int) -> tuple[set, list]:
    """Assign whole groups to val, ROW-WEIGHTED so val mirrors corpus composition.
    `group_keys` is the per-row list of group keys (one entry per out row), so its
    Counter is the group->row_count map. Deterministic: sort unique keys, seeded-
    shuffle, then greedily take groups from the front until the cumulative ROW count
    reaches val_ratio of all rows (slight overshoot on the last group is fine).
    Group-count-uniform selection let a swarm of small singleton groups crowd out the
    few heavyweight farm sessions (val drew only singletons); weighting the stop
    condition by rows keeps both represented. Returns (val_group_set, ordered_all_keys)."""
    sizes = Counter(group_keys)
    keys = sorted(sizes, key=lambda k: (k[0], k[1]))
    shuffled = keys[:]
    random.Random(seed).shuffle(shuffled)
    target = val_ratio * len(group_keys)
    val, cum = set(), 0
    for k in shuffled:
        if cum >= target:
            break
        val.add(k)
        cum += sizes[k]
    return val, keys


# ======================================================================
# report
# ======================================================================

def build_report(in_path, out_dir, rows, out_rows, dropped, canon_stats, curation,
                 val_groups, all_keys, file_counts, val_ratio, seed) -> dict:
    def _grpstr(k):
        return f"{k[0]}:{k[1]}"
    group_sizes = Counter(gk for _, gk in out_rows)
    cur_by_behavior = {b: {"kept": c.get("kept", 0), "dropped": c.get("dropped", 0),
                           "unparseable": c.get("unparseable", 0), "rule": CURATION.get(b)}
                       for b, c in sorted(curation.items())}
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
        "responder_drops": {"count": len([d for d in dropped if d.get("module") == "responder"]),
                            "rows": [d for d in dropped if d.get("module") == "responder"]},
        "inject_extractor_curation": {
            "by_behavior": cur_by_behavior,
            "total_kept": sum(c["kept"] for c in cur_by_behavior.values()),
            "total_dropped": sum(c["dropped"] for c in cur_by_behavior.values()),
            "total_unparseable": sum(c["unparseable"] for c in cur_by_behavior.values()),
        },
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
    rd = rep.get("responder_drops", {"count": 0, "rows": []})
    print(f"responder Tier-1 drops: {rd['count']}")
    if rd["rows"]:
        print(f"  {'session:turn':16} {'behavior':16} reason")
        for d in rd["rows"]:
            print(f"  {str(d.get('session'))+':'+str(d.get('turn')):16} "
                  f"{str(d.get('behavior')):16} {d.get('reason', '')}")

    cur = rep["inject_extractor_curation"]
    print("\n" + "=" * 68)
    print("!!! INJECT-EXTRACTOR CONVENTION CURATION (violations DROPPED) !!!")
    print("=" * 68)
    print(f"  {'behavior':22} {'rule':18} {'kept':>5} {'dropped':>8} {'unparse':>8}")
    for b, c in cur["by_behavior"].items():
        print(f"  {b:22} {str(c['rule']):18} {c['kept']:>5} {c['dropped']:>8} {c['unparseable']:>8}")
    print("  " + "-" * 64)
    print(f"  {'TOTAL':22} {'':18} {cur['total_kept']:>5} {cur['total_dropped']:>8} "
          f"{cur['total_unparseable']:>8}")
    print("=" * 68)

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

def _responder_veto(rows: list[dict], snapshots_path: Path):
    """Build the Tier-1 responder veto (doc-20 item 5). Recomputes each turn's
    (actions, directives) from its snapshot + the run's extractor rows (no LLM),
    scores the teacher completion, and drops rows that fail Tier-1. Imported lazily so
    the extractor path and the selftest never pull eval_responder."""
    from .schema import load_schema
    from . import eval_responder as ER
    schema = load_schema()
    snaps = {(s["session"], s["turn"]): s
             for s in (json.loads(l) for l in open(snapshots_path) if l.strip())}
    ext_map = {(r["session"], r["turn"]): r["completion"]
               for r in rows if r["module"] == "extractor"}

    def veto(row):
        key = (row.get("session"), row.get("turn"))
        snap = snaps.get(key)
        if snap is None:                       # no snapshot -> cannot score; keep (conservative)
            return False, ""
        actions, directives, fs, _ = ER.recompute_actions_directives(schema, snap, ext_map.get(key))
        # Score the CANONICALIZED target — that is the training label. canon_responder
        # fixes markers by construction (doc-20 §2: format is repaired for targets, not
        # vetoed), so the veto acts on the prose-level checks (directive/grounding/echo/
        # verbosity), not on the teacher's raw marker slips.
        case = {"form_state": fs, "user_message": snap.get("user_message", ""),
                "actions": actions, "directives": directives, "completion": canon_responder(row["completion"])}
        s = ER.score_case(case, schema)
        if s["passed"]:
            return False, ""
        reason = "; ".join(f"{k}:{v['reason']}" for k, v in s["checks"].items() if not v["pass"])
        return True, reason
    return veto


def bridge(in_path: Path, out_dir: Path, val_ratio: float, seed: int, snapshots_path: Path = None) -> dict:
    rows = [json.loads(l) for l in open(in_path) if l.strip()]
    veto = _responder_veto(rows, snapshots_path) if snapshots_path else None
    out_rows, dropped, canon_stats, curation = transform(rows, veto)
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

    rep = build_report(in_path, out_dir, rows, out_rows, dropped, canon_stats, curation,
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
    out, dropped, cs, _ = transform([r])
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
        out, _, _, _ = transform([mk("responder", c)])
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
    _, _, cs, _ = transform([mk("responder", malformed), mk("responder", bare),
                          mk("responder", wellformed)])
    assert cs["fixed"] == 2 and cs["normalized"] == 1, cs

    # --- extractor malformed -> dropped + counted (never becomes a row) ---
    good = mk("extractor", "[[ ## extractions ## ]]\n[]\n\n[[ ## completed ## ]]", well_formed=True)
    bad = mk("extractor", "oops no markers", well_formed=False)
    out, dropped, cs, _ = transform([good, bad])
    assert len(out) == 1 and out[0][0]["messages"][-1]["content"] == good["completion"]
    assert len(dropped) == 1 and dropped[0]["idx"] == 1

    # --- responder Tier-1 veto (doc-20 item 5): one dropped, one kept ---
    keep_row = mk("responder", "[[ ## response_text ## ]]\nSure!\n\n[[ ## completed ## ]]",
                  session=1, behavior="natural")
    drop_row = mk("responder", "[[ ## response_text ## ]]\nBAD\n\n[[ ## completed ## ]]",
                  session=2, behavior="natural")
    def _stub_veto(row):
        return ("BAD" in row["completion"], "tier1: stub failure")
    out_v, dropped_v, _, _ = transform([keep_row, drop_row], veto=_stub_veto)
    assert len(out_v) == 1, out_v                                   # kept row survives, canonicalized
    assert out_v[0][0]["module"] == "responder"
    rd = [d for d in dropped_v if d.get("module") == "responder"]
    assert len(rd) == 1 and rd[0]["reason"] == "tier1: stub failure" and rd[0]["session"] == 2, rd
    # veto=None (default) drops nothing — existing behavior byte-identical
    out_n, dropped_n, _, _ = transform([keep_row, drop_row])
    assert len(out_n) == 2 and not any(d.get("module") == "responder" for d in dropped_n)

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
    out, _, _, _ = transform(rows)
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

    # --- new curation rules: pending_bind / valued_2 (+ valued sanity) ---
    # pending_bind: exactly 1 pair, non-empty value, fid null OR pending-eligible
    assert curation_passes("pending_bind", [{"field_id": "email", "value": "a@b.com"}])
    assert curation_passes("pending_bind", [{"field_id": None, "value": "Maria Lee"}])
    assert not curation_passes("pending_bind", [])                                    # empty
    assert not curation_passes("pending_bind", [{"field_id": "email", "value": ""}])  # empty value
    assert not curation_passes("pending_bind", [{"field_id": "program", "value": "x"}])  # ineligible fid
    assert not curation_passes("pending_bind", [{"field_id": None, "value": "a"},
                                                {"field_id": None, "value": "b"}])    # >1 pair
    # valued_2: >=2 pairs each non-null fid + non-empty value
    assert curation_passes("valued_2", [{"field_id": "full_name", "value": "Maria Lee"},
                                        {"field_id": "email", "value": "m@e.com"}])
    assert not curation_passes("valued_2", [{"field_id": "full_name", "value": "Maria Lee"}])  # only 1
    assert not curation_passes("valued_2", [{"field_id": "full_name", "value": "Maria Lee"},
                                            {"field_id": None, "value": "x"}])         # 2nd null fid
    # valued (boolean_phrase): >=1 valued pair
    assert curation_passes("valued", [{"field_id": "prior_application", "value": "No"}])
    assert not curation_passes("valued", [{"field_id": None, "value": "x"}])

    # --- CURATION wiring through transform (inject extractor rows) ---
    def ext(behavior, body, well_formed=True):
        c = f"[[ ## extractions ## ]]\n{body}\n\n[[ ## completed ## ]]"
        return mk("extractor", c, source="inject", behavior=behavior, well_formed=well_formed)

    o, _, _, cur = transform([ext("pending_bare", '[{"field_id": null, "value": "Maria Lee"}]'),
                              ext("pending_bare", "[]")])
    assert len(o) == 1 and cur["pending_bare"]["kept"] == 1 and cur["pending_bare"]["dropped"] == 1
    o, _, _, cur = transform([
        ext("compound_volunteer", '[{"field_id":"full_name","value":"Maria Lee"},'
                                  '{"field_id":"email","value":"m@e.com"}]'),
        ext("compound_volunteer", '[{"field_id":"full_name","value":"Maria Lee"}]')])
    assert cur["compound_volunteer"]["kept"] == 1 and cur["compound_volunteer"]["dropped"] == 1
    o, _, _, cur = transform([ext("boolean_phrase", '[{"field_id":"prior_application","value":"No"}]'),
                              ext("boolean_phrase", '[{"field_id":null,"value":""}]')])
    assert cur["boolean_phrase"]["kept"] == 1 and cur["boolean_phrase"]["dropped"] == 1

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
    ap.add_argument("--snapshots", default="",
                    help="snapshots.jsonl enabling the Tier-1 responder veto (doc-20 item 5); "
                         "omit to keep the responder path uncurated")
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

    snaps_path = Path(args.snapshots) if args.snapshots else None
    rep = bridge(in_path, out_dir, args.val_ratio, args.seed, snaps_path)
    print_report(rep)
    print(f"\nwritten to {out_dir}/")


if __name__ == "__main__":
    main()
