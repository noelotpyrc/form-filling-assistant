"""M2 pilot report — coverage + correctness + cleanliness over a sim run dir.

Produces the M2 gate metrics (doc-18 §8): per-scenario quota, completion rate,
training-example counts, malformed-marker rate (informs M4 canonicalization),
hallucinated-field rate (would teach the student to invent fields), and persona
diversity. Run:  tuning/v2/.venv/bin/python -m tuning.v2.sim_report <run-dir>
"""
from __future__ import annotations
import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .schema import load_schema

SCHEMA = load_schema()
VALID = set(SCHEMA.by_id)
N_REQUIRED = sum(1 for f in SCHEMA.fields if f.required)


def _between(c: str, field: str):
    head = f"[[ ## {field} ## ]]"
    if head not in c or "[[ ## completed" not in c:
        return None  # malformed: missing markers
    body = c.split(head, 1)[1].split("[[ ## completed", 1)[0].strip()
    return body


def _parse_list(body: str):
    for loader in (json.loads, ast.literal_eval):
        try:
            v = loader(body)
            return v if isinstance(v, list) else None
        except Exception:
            continue
    return None


def main():
    run = Path(sys.argv[1] if len(sys.argv) > 1 else "tuning/v2/sims/pilot1")
    rows = [json.loads(l) for l in open(run / "train.jsonl")]
    transcripts = [json.load(open(p)) for p in sorted(run.glob("transcript-*.json"))]

    # --- sessions / coverage / cost ---
    print(f"=== run: {run} ===")
    print(f"sessions: {len(transcripts)}")
    by_scn = defaultdict(list)
    for t in transcripts:
        by_scn[t["scenario"]].append(t)
    cost = sum(t.get("cost_usd", 0) for t in transcripts)
    print(f"cost: ${cost:.2f}  (avg ${cost/max(1,len(transcripts)):.3f}/session)")
    print("\nper-scenario:")
    for scn in sorted(by_scn):
        ts = by_scn[scn]
        comp = sum(len(t["filled"]) >= N_REQUIRED for t in ts)
        avg_turns = sum(t["turns"] for t in ts) / len(ts)
        print(f"  {scn:10} sessions={len(ts)}  completed={comp}/{len(ts)}  avg_turns={avg_turns:.1f}")

    # --- training examples ---
    mods = Counter(r["module"] for r in rows)
    print(f"\ntraining examples: {len(rows)}  ({dict(mods)})")

    # --- cleanliness: malformed markers ---
    ext = [r for r in rows if r["module"] == "extractor"]
    resp = [r for r in rows if r["module"] == "responder"]
    ext_bad = sum(_between(r["completion"], "extractions") is None for r in ext)
    resp_bad = sum(_between(r["completion"], "response_text") is None for r in resp)
    print(f"\nmalformed markers:")
    print(f"  extractor {ext_bad}/{len(ext)} ({100*ext_bad/max(1,len(ext)):.1f}%)")
    print(f"  responder {resp_bad}/{len(resp)} ({100*resp_bad/max(1,len(resp)):.1f}%)")

    # --- correctness: hallucinated field_ids in extractor targets ---
    hall_rows = 0
    hall_ids = Counter()
    for r in ext:
        body = _between(r["completion"], "extractions")
        items = _parse_list(body) if body else None
        if not items:
            continue
        bad = [it.get("field_id") for it in items
               if isinstance(it, dict) and it.get("field_id") not in VALID and it.get("field_id") is not None]
        if bad:
            hall_rows += 1
            hall_ids.update(bad)
    print(f"\nhallucinated field_ids: {hall_rows}/{len(ext)} extractor examples"
          + (f"  {dict(hall_ids)}" if hall_ids else ""))

    # --- diversity ---
    names = {t["persona"]["full_name"] for t in transcripts}
    print(f"\ndiversity: {len(names)} distinct applicants / {len(transcripts)} sessions; "
          f"styles={dict(Counter(t['style'] for t in transcripts))}")


if __name__ == "__main__":
    main()
