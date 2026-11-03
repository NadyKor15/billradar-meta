"""How many lines of a reading the device confirms, on the rows it reads itself. No model call, no network.

    python scripts/witness_measure.py            # the answers of the work packs, and the saved live reading
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

from PIL import Image

from billradar import example, pdfpages, reader, redact, table_rows
from billradar.case import Case, Source
from billradar.ledger import Step

ROOT = Path(__file__).resolve().parents[1]
PACKS = ROOT / "eval" / "packs" / "work"
LIVE = ROOT / "runs" / "live-brs1-birth-all-errors"


WRONG_BY = Decimal("1.00")
FIELDS = ("charges", "insurance_paid", "adjustment", "patient_responsibility")


def wrong_lines(line) -> list:
    """The line with each of its amounts read a dollar off: a witness that confirms these confirms anything."""
    return [(f, line.model_copy(update={f: getattr(line, f) + WRONG_BY})) for f in FIELDS if getattr(line, f)]


def report(name: str, docs: list, pages: dict) -> tuple[int, int, int, int]:
    seen = total = accepted = tried = 0
    missed = Counter()
    for d in docs:
        printed = pages.get(d.doc_id)
        if printed is None:
            continue
        w = table_rows.witness(d, printed)
        seen, total = seen + w.seen, total + w.total
        if w.unseen:
            missed[d.doc_id] = len(w.unseen)
        for line in d.lines:
            for name, bad in wrong_lines(line):
                tried += 1
                forged = d.model_copy(update={"lines": [bad if x is line else x for x in d.lines]})
                step = Step(doc_id=d.doc_id, line_no=line.line_no, field=name, printed=getattr(bad, name))
                if table_rows.confirms(forged, step, printed):  # the last word on a confirmed sum
                    accepted += 1
                    print(f"  confirmed a dollar off: {d.doc_id} line {line.line_no} code {line.code!r} {name} {step.printed}")
    print(f"{name}: {seen}/{total} = {100 * seen / max(total, 1):.1f}%  unseen by sheet: {dict(missed)}"
          f"  a dollar off, confirmed all the same: {accepted}/{tried}")
    return seen, total, accepted, tried


def sheets_of_pack(pack: Path) -> dict:
    run = example.run_pack(pack, private=True)
    pages = {sid: table_rows.rows(redact.ocr(img)) for sid, img in run.originals.items()}
    for pdf in sorted(pack.glob("*.pdf")):
        i = sorted(p.name for p in pack.glob("*.pdf")).index(pdf.name) + 1
        lines = [ln for page in pdfpages.render(pdf.read_bytes()) for ln in redact.ocr(page)]
        pages[f"D{i}"] = table_rows.rows(lines)
    return pages


def main() -> int:
    seen = total = accepted = tried = 0
    for pack in sorted(PACKS.glob("brs1-*")):
        raw = json.loads((pack / "answers" / "reading.json").read_text())
        expected = {x["doc_id"]: Source.PDF if x["doc_id"].startswith("D") else Source.PAPER for x in raw["documents"]}
        docs, _ = reader.to_documents(raw, expected)
        a, b, c, e = report(f"{pack.name} (answers)", docs, sheets_of_pack(pack))
        seen, total, accepted, tried = seen + a, total + b, accepted + c, tried + e
    print(f"ALL ANSWERS: {seen}/{total} = {100 * seen / max(total, 1):.1f}%  a dollar off, confirmed all the same: {accepted}/{tried}")
    if LIVE.exists():
        case = Case.model_validate_json((LIVE / "case.json").read_text())
        pages = {p.stem: table_rows.rows(redact.ocr(Image.open(p).convert("RGB"))) for p in sorted((LIVE / "sheets").glob("S*.jpg"))}
        report("live Spark reading, all-errors, paper sheets", [d for d in case.documents if d.doc_id in pages], pages)
    return 0


if __name__ == "__main__":
    sys.exit(main())
