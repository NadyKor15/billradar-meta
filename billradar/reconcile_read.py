"""Two independent reads of every sheet, settled before anything is counted.

The second read sees the sheets in the other order. Where the two reads differ, the device is the witness: a reading
one printed row confirms wins. What is still open gets a third read of that sheet alone, and two reads out of three
settle it. A line that does not add up is not settled by the reads agreeing on it. What nobody can settle stays on the
sheet as a doubt: the sheet is photographed again and gives no confirmed sum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from billradar import reader, table_rows
from billradar.case import DocKind, Document, Line
from billradar.meta_client import MetaAPIError
from billradar.table_rows import Row

THIRD_READS = 6  # at most this many sheets are read a third time, per case
BILL_SUMS = ("patient_balance", "due_from_insurance", "amount_due_coupon", "fa_discount")  # no sum on a plan's statement rests on these
FOR_THE_READER = ("total_charges", "insurance_paid")  # printed totals: no sum rests on them
LINE_FIELDS = ("service_date", "code", "charges", "insurance_paid", "adjustment", "fa_discount", "patient_responsibility")
DOC_FIELDS = ("kind", "first_after_discharge", "statement_date", "service_from", "service_to", "insurance_payment_date",
              "total_charges", "insurance_paid", "fa_discount", "patient_balance", "due_from_insurance", "amount_due_coupon")


def _same_line(a: Line, b: Line) -> bool:
    return all(getattr(a, f) == getattr(b, f) for f in LINE_FIELDS)


def _printed(value, rows: list[Row]) -> bool:
    """The device reads this sum, under its name, or this date on the sheet. Never a reading confirming itself: these
    rows come from the sheet as photographed, read here."""
    if isinstance(value, Decimal):
        return table_rows.named(value, rows)
    if isinstance(value, date):
        forms = {f"{value:%m/%d/%Y}", f"{value:%m/%d/%y}", f"{value:%-m/%-d/%Y}", f"{value:%-m/%-d/%y}", f"{value:%b %d, %Y}",
                 f"{value:%b %-d, %Y}", f"{value:%B %-d, %Y}"}
        return any(form in r.text for r in rows for form in forms)
    return False


def _fields(a: Document, b: Document, printed: list[Row] = ()) -> list[str]:
    """The sheet's own fields two reads do not agree on. One read leaving out what the sheet prints is no disagreement;
    neither is a page read as "other", a balance on an insurance statement, or a total no sum stands on."""
    out = []
    for f in DOC_FIELDS:
        x, y = getattr(a, f), getattr(b, f)
        if x == y or (f == "kind" and DocKind.OTHER in (x, y)):
            continue
        if (x is None or y is None) and (f in FOR_THE_READER or _printed(y if x is None else x, printed)
                                         or (f in BILL_SUMS and DocKind.EOB in (a.kind, b.kind))):
            continue
        out.append(f"{f} {x} or {y}")
    return out


def differences(a: Document, b: Document, printed: list[Row] = ()) -> list[str]:
    """What two reads of one sheet do not agree on, in words."""
    out = _fields(a, b, printed)
    if len(a.lines) != len(b.lines):
        return out + [f"{len(a.lines)} lines or {len(b.lines)}"]
    return out + [f"line {x.line_no}" for x, y in zip(a.lines, b.lines) if not _same_line(x, y) and _better(x, y, printed) is None]


def does_not_add_up(doc: Document, printed: list[Row] = ()) -> list[str]:
    """Lines whose printed parts do not make the charge: charged = paid + taken off + discount + the patient's share.
    A line the device sees on the sheet stands: a copay collected has no field of its own, so its parts can fall short."""
    out = []
    for ln in doc.lines:
        parts = [ln.insurance_paid, ln.adjustment, ln.patient_responsibility]
        if ln.charges is None or any(p is None for p in parts):
            continue
        whole = sum((abs(p) for p in parts[:2]), Decimal(0)) + abs(ln.fa_discount or 0) + ln.patient_responsibility
        if abs(whole - ln.charges) > Decimal("0.01") and not table_rows.seen(ln, printed):
            out.append(f"line {ln.line_no}")
    return out


@dataclass
class Settled:
    doc: Document | None
    open: list[str]


def _better(x: Line, y: Line, printed: list[Row]) -> Line | None:
    """The reading of a line the device confirms. Both confirmed: the one with more printed numbers, when the other's are
    among them. None when the device cannot tell them apart."""
    seen_x, seen_y = table_rows.seen(x, printed), table_rows.seen(y, printed)
    if not (seen_x and seen_y):
        return x if seen_x else y if seen_y else None
    if any(getattr(x, f) and getattr(y, f) and getattr(x, f) != getattr(y, f) for f in ("service_date", "code")):
        return None
    nx, ny = table_rows.numbers_of(x), table_rows.numbers_of(y)
    return y if nx <= ny else x if ny <= nx else None


def _side(a: Document, b: Document, printed: list[Row]) -> Document | None:
    """The read the device confirms, line by line."""
    if len(a.lines) != len(b.lines) or _fields(a, b, printed):
        return None
    lines = [x if _same_line(x, y) else _better(x, y, printed) for x, y in zip(a.lines, b.lines)]
    if any(ln is None for ln in lines):
        return None
    return _filled(a, b).model_copy(update={"lines": lines})


def _filled(doc: Document, other: Document) -> Document:
    """What one read left out, from the read that has it: _fields has already asked the device."""
    update = {f: getattr(other, f) for f in DOC_FIELDS if getattr(doc, f) is None and getattr(other, f) is not None}
    if doc.kind == DocKind.OTHER and other.kind != DocKind.OTHER:
        update["kind"] = other.kind
    return doc.model_copy(update=update) if update else doc


def _two_of_three(a: Document, b: Document | None, c: Document | None, printed: list[Row] = ()) -> Document | None:
    """Two reads that agree. A read alone settles nothing: with no second read, the third must agree with the first."""
    if c is None:
        return None
    if not differences(a, c, printed):
        return _filled(a, c)
    return _filled(b, c) if b is not None and not differences(b, c, printed) else None


def _fill_balance(doc: Document, printed: list[Row], problems: list[str]) -> Document:
    """A balance both reads left out, printed on the sheet's last balance row and read here, on the device."""
    if doc.patient_balance is not None or "." in doc.doc_id:  # a page of a file: the file has one balance, on one page
        return doc
    last = table_rows.last_balance(printed)
    if last is None:
        return doc
    problems.append(f"{doc.doc_id}: balance {last} read on this device, both reads left it out")
    return doc.model_copy(update={"patient_balance": last, "device_balance": True})


def _second_read(client, second, sheets: list, files: list, problems: list[str]):
    """The other model when there is one; if it fails, the first model again, in the other order, and the case says so."""
    if second is not None:
        try:
            return reader.read_case(second, sheets[::-1], [], label="open:read-2")
        except MetaAPIError as exc:
            problems.append(f"second read on the open model did not run: {exc}")
    try:
        return reader.read_case(client, sheets[::-1], list(files)[::-1], label="spark:read-2")
    except MetaAPIError as exc:  # the first read stands, with a doubt on every sheet: no sum rests on one read
        problems.append(f"second read did not run: {exc}")
        return None


def _third_read(client, doc_id: str, image: bytes, problems: list[str]) -> Document | None:
    try:
        found = reader.read_case(client, [(doc_id, image)], [], label="spark:read-3").documents
    except MetaAPIError as exc:
        problems.append(f"{doc_id}: third read did not run: {exc}")
        return None
    return found[0] if found else None


def reconcile(client, docs: list[Document], sheets: list[tuple[str, bytes]], printed: dict[str, list[Row]],
              problems: list[str], files: list = (), second=None) -> list[Document]:
    """`docs` is the first read. `printed`: sheet id -> the rows the device reads on the sheet as photographed.
    `second`: another model's client for the second read."""
    read = _second_read(client, second, sheets, files, problems)
    second = {d.doc_id: d for d in read.documents} if read else {}
    images = dict(sheets)
    thirds, out = 0, []
    for doc in docs:
        rows = printed.get(doc.doc_id, [])
        other = second.get(doc.doc_id)
        settled, why = doc, []
        if other is None:
            why = ["the second read left it out"]
        elif differences(doc, other, rows):
            why = differences(doc, other, rows)
            settled = _side(doc, other, rows) or doc
            if _side(doc, other, rows):
                why = []
        else:
            settled = _side(doc, other, rows) or _filled(doc, other)
        if why and read and doc.doc_id in images and thirds < THIRD_READS:
            thirds += 1
            agreed = _two_of_three(doc, other, _third_read(client, doc.doc_id, images[doc.doc_id], problems), rows)
            if agreed is not None:
                problems.append(f"{doc.doc_id}: third read settled {'; '.join(why)}")
                settled, why = agreed, []
        settled = _fill_balance(settled, rows, problems)
        broken = does_not_add_up(settled, rows)
        doubts = [f"{doc.doc_id}: the reads disagree on {'; '.join(why)}"] if why else []
        doubts += [f"{doc.doc_id}: {', '.join(broken)} does not add up"] if broken else []
        out.append(settled.model_copy(update={"doubts": settled.doubts + doubts}) if doubts else settled)
    return out
