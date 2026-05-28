"""Pick boost/decrease examples from gen_and_score output.

Consumes the JSON written by `gen_and_score.py` — which guarantees that the
prediction shown and the score were produced in the SAME inference run.
Picks top-N boosts and top-N regressions by Δ, renders into a markdown
comparison file.

Optionally filters to data-extractor-active cases (gold has has_new_data=True
with non-empty field_ids).

Run from repo root:
  python tuning/gepa/pick_from_paired.py \\
    --paired tuning/gepa/results/gen_and_score_cand2.json \\
    --boosts 5 --regressions 5 \\
    --data-extractor-only \\
    --out /tmp/data_extractor_compare_paired.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent))


def fmt_pred(p: dict | None) -> str:
    if p is None:
        return "(no prediction — inference error)"
    flag_str = " ".join(f"{k}={bool(v)}" for k, v in (p.get("flags") or {}).items())
    fids = p.get("field_ids") or []
    fvals = p.get("field_values") or []
    lines = [f"flags:    {flag_str}",
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
    ap.add_argument("--paired", required=True, help="JSON from gen_and_score.py")
    ap.add_argument("--boosts", type=int, default=5)
    ap.add_argument("--regressions", type=int, default=5)
    ap.add_argument("--data-extractor-only", action="store_true",
                    help="Filter to cases where gold has_new_data=True with non-empty fields")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    payload = json.load(open(args.paired))
    rows = payload["rows"]
    print(f"Loaded {len(rows)} paired rows from {args.paired}")

    # Need access to gold answers — load eval cases by id
    seeds = [json.loads(l) for l in open(Path(__file__).parent / "seeds.jsonl")]
    ec = [json.loads(l) for l in open(Path(__file__).parent / "eval_cases.jsonl")]
    case_by_id = {c["test_id"]: c for c in seeds + ec}

    eligible = []
    for r in rows:
        c = case_by_id.get(r["test_id"])
        if not c:
            continue
        if args.data_extractor_only:
            ca = c["correct_answer"]
            if not (ca["flags"].get("has_new_data") and (ca.get("field_ids") or [])):
                continue
        eligible.append((r, c))
    print(f"Eligible after filter: {len(eligible)}")

    eligible.sort(key=lambda x: x[0]["delta"])
    regressions = eligible[:args.regressions]
    boosts = list(reversed(eligible[-args.boosts:]))

    picks: list[tuple[str, dict, dict]] = []
    for r, c in boosts:
        picks.append(("BOOST", r, c))
    for r, c in regressions:
        picks.append(("REGRESSION", r, c))

    print(f"Picked: {len(boosts)} boosts, {len(regressions)} regressions")
    for k, r, _ in picks:
        print(f"  {k:11s} {r['test_id']:38s} base={r['baseline_score']:.3f}  cand={r['cand_score']:.3f}  Δ={r['delta']:+.3f}")

    md = ["# Paired comparison: baseline vs candidate (predictions ↔ scores guaranteed matched)", "",
          f"Source: `{args.paired}`",
          f"Judge: `{payload.get('judge_backend')}`  use_judge={payload.get('use_judge')}",
          f"Mutated modules: `{payload.get('modules_mutated')}`",
          ""]
    md += [f"Top {args.boosts} cases where candidate **improved** vs baseline, "
           f"then top {args.regressions} **regressions**. "
           "Both predictions and scores produced in the SAME inference pass.",
           ""]

    for kind, r, c in picks:
        inp = c["input"]
        md += [
            "---",
            f"## {kind} — `{r['test_id']}` (Δ={r['delta']:+.3f})",
            "",
            f"- source: `{c.get('source','?')}`",
            f"- tags: `{c.get('cannot_targets') or []}`",
            f"- baseline score: {r['baseline_score']:.3f}",
            f"- candidate score: {r['cand_score']:.3f}",
        ]
        if r.get("baseline_error"):
            md.append(f"- baseline error: `{r['baseline_error']}`")
        if r.get("cand_error"):
            md.append(f"- candidate error: `{r['cand_error']}`")
        md += [
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
            "**BASELINE**",
            "```",
            fmt_pred(r["baseline_pred"]),
            "```",
            "",
            "**CANDIDATE**",
            "```",
            fmt_pred(r["cand_pred"]),
            "```",
            "",
        ]

    Path(args.out).write_text("\n".join(md))
    print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
