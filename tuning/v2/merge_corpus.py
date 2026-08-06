"""merge_corpus.py — build a single-file-per-split SFT corpus that unions an EXTRACTOR
corpus with a RESPONDER corpus (item 6 prep: the merged-model comparison).

The Modal SFT trainer reads ONE file per split (SFT_TRAIN_DATA / SFT_VAL_DATA), and its
convert() reads only `messages`. But sim_to_sft writes PER-MODULE files
(train_extractor.jsonl / train_responder.jsonl / …). This joins the extractor and
responder splits into `merged_all/{train,val}.jsonl` — a plain union (extractor rows
then responder rows, in file order), no dedup, deterministic.

  Selftest (free):  tuning/v2/.venv/bin/python -m tuning.v2.merge_corpus --selftest
  Build:            tuning/v2/.venv/bin/python -m tuning.v2.merge_corpus \
                        --extractor-run r3_oracle_merged --responder-run responder_s2d_merged
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

V2_DIR = Path(__file__).resolve().parent
SFT_DIR = V2_DIR / "sft_data"


def _load(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()]


def merge(extractor_dir: Path, responder_dir: Path, out_dir: Path) -> dict:
    """Write out_dir/{train,val}.jsonl = union of the extractor + responder split files.
    Returns a stats dict. Deterministic: extractor rows first, then responder rows."""
    parts = {
        "train": (extractor_dir / "train_extractor.jsonl", responder_dir / "train_responder.jsonl"),
        "val": (extractor_dir / "val_extractor.jsonl", responder_dir / "val_responder.jsonl"),
    }
    for split, (ep, rp) in parts.items():
        for p in (ep, rp):
            if not p.exists():
                raise SystemExit(f"[merge] missing input file: {p}")

    out_dir.mkdir(parents=True, exist_ok=True)
    stats: dict = {"extractor_run": str(extractor_dir), "responder_run": str(responder_dir),
                   "out": str(out_dir), "splits": {}}
    for split, (ep, rp) in parts.items():
        ext, rsp = _load(ep), _load(rp)
        rows = ext + rsp                               # union, no dedup, deterministic order
        with open(out_dir / f"{split}.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        stats["splits"][split] = {"extractor": len(ext), "responder": len(rsp), "total": len(rows)}
        # invariant: the union count is exactly the sum of the parts (no drops, no dedup)
        assert len(rows) == len(ext) + len(rsp)
    json.dump(stats, open(out_dir / "report.json", "w"), indent=2)
    return stats


def selftest() -> bool:
    import tempfile
    checks: list[tuple[str, bool]] = []

    def ck(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    def row(tag, i):
        return {"module": tag, "source": "x", "behavior": "b",
                "messages": [{"role": "system", "content": "S"},
                             {"role": "user", "content": f"{tag}-{i}"},
                             {"role": "assistant", "content": "a"}]}

    with tempfile.TemporaryDirectory() as td:
        ext_dir, rsp_dir, out_dir = Path(td) / "ext", Path(td) / "rsp", Path(td) / "merged"
        ext_dir.mkdir(); rsp_dir.mkdir()
        # extractor: 3 train / 1 val ; responder: 2 train / 1 val ; include a DUPLICATE
        # row across sources to prove no dedup.
        dup = row("dup", 0)
        (ext_dir / "train_extractor.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in [row("ext", 0), row("ext", 1), dup]))
        (ext_dir / "val_extractor.jsonl").write_text(json.dumps(row("ext", 9)) + "\n")
        (rsp_dir / "train_responder.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in [row("rsp", 0), dup]))
        (rsp_dir / "val_responder.jsonl").write_text(json.dumps(row("rsp", 9)) + "\n")

        stats = merge(ext_dir, rsp_dir, out_dir)
        train = _load(out_dir / "train.jsonl")
        val = _load(out_dir / "val.jsonl")
        ck("train count = extractor + responder (3 + 2 = 5)", len(train) == 5)
        ck("val count = extractor + responder (1 + 1 = 2)", len(val) == 2)
        ck("stats report the per-source counts",
           stats["splits"]["train"] == {"extractor": 3, "responder": 2, "total": 5})
        ck("no dedup: the duplicate row appears twice", sum(1 for r in train if r["module"] == "dup") == 2)
        ck("deterministic order: extractor rows precede responder rows",
           [r["module"] for r in train] == ["ext", "ext", "dup", "rsp", "dup"])
        ck("rows carry messages (trainer convert() reads only that)", all("messages" in r for r in train))
        # deterministic across rebuilds
        merge(ext_dir, rsp_dir, out_dir)
        ck("byte-identical on rebuild", (out_dir / "train.jsonl").read_text() ==
           "".join(json.dumps(r) + "\n" for r in train))

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n=== merge_corpus selftest: {passed}/{len(checks)} checks passed ===")
    return passed == len(checks)


def main():
    ap = argparse.ArgumentParser(description="Union an extractor + responder SFT corpus into one file per split.")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--extractor-run", default="r3_oracle_merged",
                    help="sft_data dir with train_extractor.jsonl / val_extractor.jsonl")
    ap.add_argument("--responder-run", help="sft_data dir with train_responder.jsonl / val_responder.jsonl")
    ap.add_argument("--out", default="", help="output dir (default sft_data/merged_all)")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if not args.responder_run:
        ap.error("--responder-run is required (unless --selftest)")
    ext_dir = Path(args.extractor_run) if "/" in args.extractor_run else (SFT_DIR / args.extractor_run)
    rsp_dir = Path(args.responder_run) if "/" in args.responder_run else (SFT_DIR / args.responder_run)
    out_dir = Path(args.out) if args.out else (SFT_DIR / "merged_all")
    stats = merge(ext_dir, rsp_dir, out_dir)
    print(f"wrote {out_dir}/train.jsonl + val.jsonl")
    for split, c in stats["splits"].items():
        print(f"  {split}: {c['extractor']} extractor + {c['responder']} responder = {c['total']}")


if __name__ == "__main__":
    main()
