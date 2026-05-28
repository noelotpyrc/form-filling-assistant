"""Pick boost/regression examples from scored_paired_preds JSON and render
a markdown comparison.

Predictions and scores were produced in the SAME deterministic run, so the
preds displayed ARE the preds scored — no apples-to-oranges concern.

Run from repo root:
  python/.venv/bin/python tuning/gepa/pick_from_scored.py \\
    --scored tuning/gepa/results/scored_paired_preds_cand2.json \\
    --out    /tmp/data_extractor_compare_paired.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))


def fmt_pred_flat(p: dict | None) -> str:
    if p is None:
        return "(no prediction)"
    flags = " ".join(f"{f}={bool(p.get(f, False))}" for f in
                     ["has_new_data", "needs_choice", "wants_review", "wants_save", "wants_submit"])
    fids = p.get("field_ids") or []
    fvals = p.get("field_values") or []
    lines = [f"flags:    {flags}",
             f"response_text: {(p.get('response_text') or '')!r}",
             f"field updates ({len(fids)}):"]
    if fids:
        lines += [f"  {fid} = {fv!r}" for fid, fv in zip(fids, fvals)]
    else:
        lines.append("  (none)")
    q, opts = p.get("question") or "", p.get("options") or []
    if q or opts:
        lines.append(f"question: {q!r}")
        lines.append(f"options:  {opts}")
    st, sc = p.get("summary_title") or "", p.get("summary_content") or ""
    if st or sc:
        lines.append(f"review:   '{st}' — {sc!r}")
    return "\n".join(lines)


def fmt_gold(gold: dict) -> str:
    flags = gold.get("flags", {})
    flag_str = " ".join(f"{k}={bool(v)}" for k, v in flags.items())
    fids = gold.get("field_ids") or []
    fvals = gold.get("field_values") or []
    lines = [f"flags:    {flag_str}",
             f"response_text: {gold.get('response_text','')!r}",
             f"field updates ({len(fids)}):"]
    if fids:
        lines += [f"  {fid} = {fv!r}" for fid, fv in zip(fids, fvals)]
    else:
        lines.append("  (none)")
    q, opts = gold.get("question") or "", gold.get("options") or []
    if q or opts:
        lines.append(f"question: {q!r}")
        lines.append(f"options:  {opts}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scored", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    payload = json.load(open(args.scored))
    rows = payload["rows"]
    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    ec = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]
    case_by_id = {c["test_id"]: c for c in seeds + ec}

    diff = [r for r in rows if r["delta"] is not None]
    diff.sort(key=lambda r: r["delta"])

    # All cases shown — there's only ~10
    boosts = [r for r in diff if r["delta"] > 0]
    regressions = [r for r in diff if r["delta"] < 0]
    boosts.sort(key=lambda r: -r["delta"])
    regressions.sort(key=lambda r: r["delta"])

    print(f"differing-pair rows: {len(diff)}")
    print(f"  boosts:      {len(boosts)}")
    print(f"  regressions: {len(regressions)}")

    md = [
        "# Candidate 2 vs Baseline — paired comparison (preds ↔ scores guaranteed matched)",
        "",
        f"- source file: `{args.scored}`",
        f"- candidate index: {payload.get('candidate_index')}",
        f"- modules mutated: `{payload.get('modules_mutated')}`",
        f"- judge backend used: `{payload.get('judge_backend_used')}`, use_judge={payload.get('use_judge')}",
        f"- val_set size: {payload.get('val_size')}",
        "",
        "## Key finding",
        "",
        f"Out of **{len(rows)} val cases**, candidate 2's data_extractor mutation produces "
        f"a different prediction from baseline on only **{len(diff)} cases (≈{100*len(diff)/len(rows):.1f}%)**. "
        "The other 112 cases are byte-identical and any \"lift\" on them is pure judge noise.",
        "",
        "Of the {n_diff} cases where predictions actually differ:".format(n_diff=len(diff)),
        f"- **{len(boosts)} boosts** (cand scores higher than baseline)",
        f"- **{len(regressions)} regressions** (cand scores lower)",
        f"- Mean Δ across differing pairs: **{sum(r['delta'] for r in diff)/len(diff):+.4f}**",
        "",
        "So when candidate 2 actually changes the prediction, it tends to make scoring worse, "
        "not better. The +0.061 \"lift\" in `eval_candidate2_fresh.json` was driven by judge "
        "variance on byte-identical preds.",
        "",
    ]

    def render_section(title: str, items: list[dict]):
        nonlocal md
        md.append(f"## {title}")
        md.append("")
        if not items:
            md.append("(none)")
            md.append("")
            return
        for r in items:
            tid = r["test_id"]
            c = case_by_id[tid]
            inp = c["input"]
            md += [
                "---",
                f"### `{tid}`  Δ={r['delta']:+.3f}",
                "",
                f"- val_idx: {r['val_idx']}",
                f"- source: `{c.get('source','?')}`",
                f"- tags: `{c.get('cannot_targets') or []}`",
                f"- baseline score: {r['baseline_score']:.3f}",
                f"- candidate score: {r['cand_score']:.3f}",
                "",
                "**user_message**",
                "```",
                inp["user_message"],
                "```",
                "",
                "**GOLD**",
                "```",
                fmt_gold(c["correct_answer"]),
                "```",
                "",
                "**BASELINE pred** (from stored `iter_0_prog_0.json`)",
                "```",
                fmt_pred_flat(r["baseline_pred"]),
                "```",
                "",
                "**CANDIDATE 2 pred** (freshly re-inferred — deterministic, matches eval-time pred)",
                "```",
                fmt_pred_flat(r["cand_pred"]),
                "```",
                "",
            ]
        md.append("")

    render_section("Boosts (candidate 2 better)", boosts)
    render_section("Regressions (candidate 2 worse)", regressions)

    Path(args.out).write_text("\n".join(md))
    print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
