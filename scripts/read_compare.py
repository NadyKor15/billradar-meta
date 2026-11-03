"""Muse Spark 1.3 against Muse Spark Open as the second read: the same covered sheets, scored field by field against the
pack's answers. Live calls: run it only with a word from the owner, through docs/billradar-build/with-meta-key.sh.

    python scripts/read_compare.py brs1-birth-all-errors [more packs]      # writes runs/read-compare-<pack>.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from billradar import example
from billradar import open_reader, pipeline, reader
from billradar.case import Source

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("code", "charges", "insurance_paid", "adjustment", "patient_responsibility")
DOC_FIELDS = ("patient_balance", "amount_due_coupon", "statement_date")


def scored(docs: list, truth: dict) -> dict:
    """Fields read right against the answers: lines by position, on sheets the answers hold."""
    right = total = wrong_money = 0
    for d in docs:
        want = truth.get(d.doc_id)
        if want is None:
            continue
        for f in DOC_FIELDS:
            total += 1
            right += getattr(d, f) == getattr(want, f)
        for got, exp in zip(d.lines, want.lines):
            for f in FIELDS:
                total += 1
                same = getattr(got, f) == getattr(exp, f)
                right += same
                wrong_money += (not same and getattr(got, f) is not None and getattr(exp, f) is not None and f != "code")
        total += abs(len(d.lines) - len(want.lines)) * len(FIELDS)
    return {"right": right, "total": total, "share": round(right / max(total, 1), 4), "wrong_amounts": wrong_money}


def one(client, name: str, sheets: list, truth: dict) -> dict:
    started = time.monotonic()
    read = reader.read_case(client, sheets, [], label=f"compare:{name}")
    return {"model": name, "seconds": round(time.monotonic() - started, 1), "problems": len(read.problems),
            "usage": read.usage, **scored(read.documents, truth)}


def recorded_reads(expected: dict, truth: dict) -> list[dict]:
    """The live Spark reads of this pack, from their recordings: scored without paying for them again."""
    out = []
    for path in sorted((ROOT / "tests" / "fixtures" / "recordings").glob("muse-spark-1.3-*.jsonl")):
        text = "".join(e.get("delta", "") for e in map(json.loads, path.read_text().splitlines())
                       if isinstance(e, dict) and e.get("type") == "response.output_text.delta")
        try:
            raw = json.loads(text)
        except ValueError:
            continue
        documents = raw.get("documents") if isinstance(raw, dict) else None
        if not documents or len(documents) < 10:
            continue
        known = [d for d in documents if d.get("doc_id") in truth]
        docs = reader.to_documents({"documents": known}, {d["doc_id"]: expected[d["doc_id"]] for d in known})[0]
        out.append({"model": f"muse-spark-1.3 recorded {path.stem[-6:]}", "seconds": 0, "problems": 0, "usage": {}, **scored(docs, truth)})
    return out


def main(packs: list[str]) -> int:
    if not (os.environ.get("BILLRADAR_LIVE") == "1" and os.environ.get("BASETEN_API_KEY") and os.environ.get("MODEL_API_KEY")):
        print("needs BILLRADAR_LIVE=1, MODEL_API_KEY and BASETEN_API_KEY")
        return 2
    os.environ["BILLRADAR_LIVE"] = "0"  # the sheets are cut and covered from the pack's own answers
    for name in packs:
        pack = ROOT / "eval" / "packs" / "work" / name
        run = example.run_pack(pack, private=True)
        sheets = [(s.doc_id, pipeline._jpeg(s.image)) for s in run.sheets]
        raw = json.loads((pack / "answers" / "reading.json").read_text())
        expected = {x["doc_id"]: Source.PDF if x["doc_id"].startswith("D") else Source.PAPER for x in raw["documents"]}
        truth = {d.doc_id: d for d in reader.to_documents(raw, expected)[0]}
        os.environ["BILLRADAR_LIVE"] = "1"
        os.environ["BILLRADAR_SECOND_READER"] = "open"
        out = recorded_reads(expected, truth) + [one(open_reader.second_reader(), "muse-spark-open", sheets, truth)]
        (ROOT / "runs" / f"read-compare-{name}.json").write_text(json.dumps(out, indent=2))
        for row in out:
            print(name, json.dumps({k: row[k] for k in ("model", "share", "right", "total", "wrong_amounts", "seconds", "problems")}))
        os.environ["BILLRADAR_LIVE"] = "0"
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["brs1-birth-all-errors"]))
