"""Reads photographed sheets and PDFs into typed documents.

The model only transcribes: it returns the text exactly as printed. Amounts and dates become numbers here, in plain
code; whatever does not parse is dropped and recorded as a doubt. No network or disk access: the client does that."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from billradar.case import Document, DocKind, Line, Source, parse_date, parse_money
from billradar.meta_client import MetaAPIError, MetaClient, data_url

MODEL = "muse-spark-1.3"

_s = {"type": "string"}
_b = {"type": "boolean"}
_i = {"type": "integer"}


def _strict(props: dict) -> dict:
    """A closed object whose every property is required (strict Responses mode)."""
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


LINE_SCHEMA = _strict({
    "line_no": _i,
    "service_date": _s,
    "code": _s,
    "description": _s,
    "charges": _s,
    "insurance_paid": _s,
    "adjustment": _s,
    "fa_discount": _s,
    "patient_responsibility": _s,
    "claim_ref": _s,
    "denial_codes": _s,
})

DOC_SCHEMA = _strict({
    "doc_id": _s,
    "kind": {"type": "string", "enum": [k.value for k in DocKind]},
    "patient": _s,
    "provider": _s,
    "account_ref": _s,
    "claim_ref": _s,
    "statement_date": _s,
    "service_from": _s,
    "service_to": _s,
    "first_after_discharge": _b,
    "insurance_payment_date": _s,
    "total_charges": _s,
    "insurance_paid": _s,
    "fa_discount": _s,
    "patient_balance": _s,
    "due_from_insurance": _s,
    "amount_due_coupon": _s,
    "member_ref": _s,
    "page_no": _i,
    "page_count": _i,
    "unreadable": _b,
    "lines": {"type": "array", "items": LINE_SCHEMA},
})

SCHEMA = _strict({"documents": {"type": "array", "items": DOC_SCHEMA}})

INSTRUCTIONS = """You read the medical payment papers of one family for BillRadar, an assistant that works with hospital bills and insurance statements. You transcribe what is printed; you give no medical advice.

What you receive and what you return
- The material is of two kinds: photographs of paper sheets, identified S1, S2, ... and digital files, identified D1, D2, ...
- Return one record for every sheet and every file, using the identifier you were given (S... or D...) unchanged.
- Never invent a document that was not among those sent, and never skip one that was.

Document type
Set `kind` to one of exactly these six values:
- `hospital_statement`: a bill or statement that shows a balance (an amount remaining).
- `itemized_bill`: a bill with line-by-line charges.
- `eob`: an Explanation of Benefits from an insurance plan. Such a document carries a printed note that it is not a bill ("this is not a bill").
- `fa_letter`: a financial assistance decision.
- `payment_receipt`
- `other`

People, organizations and references
- `patient`: the patient as printed on the document. If a token such as [PATIENT_1] is printed instead of a name, copy the token exactly but put it in the value without the square brackets: PATIENT_1. The brackets come off only here.
- `provider` on a bill: the organization that sends the bill, that is, the name in the letterhead at the top of the sheet. It is not the place where a service was given, even if the text names one.
- `provider` on an EOB: the provider named in connection with that claim.
- `account_ref` and `claim_ref`: copy exactly as printed, including tokens such as [ACCT_1], with their square brackets as printed.
- `member_ref`: the insurance member ID printed in this document; tokens are copied exactly, as printed.

Dates and amounts
- Write every date as YYYY-MM-DD. If a date is not printed or cannot be read, use the empty string "".
- Copy every amount as the text printed on the paper, for example "$1,240.00" or "(312.40)". If an amount is not printed, use the empty string "".
- Never compute an amount.
- A credit or an overpayment is printed in parentheses or marked CR. Copy it as printed, for example "(25.00)".

Document-level fields
- `first_after_discharge`: true only if the sheet itself says that it is the first bill or the first statement after the hospital stay.
- `insurance_payment_date`: the date on which the insurance plan paid, if it is printed (it appears on EOBs).
- `fa_discount`: the financial assistance or charity discount shown on the bill, if there is one.
- `page_no` and `page_count`: taken from a mark such as "Page 2 of 5" (the first number is `page_no`, the second is `page_count`). If no such mark is printed, both are 0.
- `unreadable`: true when glare, blur, a fold, a covered part of the sheet or a cut-off edge makes the amounts on that sheet impossible to read. In that case copy only what you can read and do not guess the rest; the family will take a new photo.

Balances
- `patient_balance` is the "balance due" or "your balance" printed in the sheet's own table or summary. Never take it from the payment coupon, even if the two amounts differ.
- If the sheet prints several such lines, take the last one. A printed "$0.00" is a real value: copy it; it is not empty.
- If the sheet splits the balance into "amount due from insurance" and "amount due from patient", then `patient_balance` is the patient part ("$0.00" if that part is empty) and the insurance part goes into `due_from_insurance`.
- In every other case `due_from_insurance` is the empty string "".
- `amount_due_coupon`: the amount in the payment coupon ("PAY THIS AMOUNT" or "amount enclosed"), if the sheet has such a coupon.
- Copy each of these amounts as printed, even when they disagree with one another.

Lines
- `lines` holds every printed charge or claim line of the document, in order. Take `line_no` as printed; if it is not printed, count from 1.
- Fill in a line only with the numbers printed in that line's own table row. A column that is left empty in that row stays "".
- A totals or summary block under the lines (for example "Insurance adjusted", "Amount you owe", "Subtotal") belongs to the document as a whole, never to a line.
- `patient_responsibility` on a line: on an EOB line, what the plan says the patient may owe; on a bill line, what this bill asks the patient to pay for that line.
- `denial_codes` on a line: the remark, reason or denial codes printed for that line, as printed, for example "X17" or "X05, X42". If there are none, use the empty string "".

Copy what is printed. Correct nothing, round nothing, guess nothing.
"""


@dataclass
class ReadResult:
    documents: list[Document]
    problems: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    seconds: float = 0.0
    replayed: bool = True


def request_body(sheets: list[tuple[str, bytes]], files: list[tuple[str, str, bytes]],
                 effort: str = "low", max_output_tokens: int = 32000, model: str = MODEL) -> dict:
    def said(s: str) -> dict:
        return {"type": "input_text", "text": s}

    captioned = [
        (f"Sheet {n}:", {"type": "input_image", "image_url": data_url(jpeg, "image/jpeg")}) for n, jpeg in sheets
    ] + [
        (f"File {n} ({name}):", {"type": "input_file", "filename": name, "file_data": data_url(pdf, "application/pdf")})
        for n, name, pdf in files
    ]
    roster = ", ".join([n for n, _ in sheets] + [n for n, _, _ in files])
    user_parts = [said(f"Documents in this case: {roster}. Images and files follow in this order.")]
    user_parts.extend(piece for caption, media in captioned for piece in (said(caption), media))

    body = {"model": model, "store": False, "stream": True}
    body["reasoning"] = {"effort": effort}
    body["max_output_tokens"] = max_output_tokens
    body["text"] = {"format": {"type": "json_schema", "name": "billradar_case", "schema": SCHEMA, "strict": True}}
    body["input"] = [
        {"role": "developer", "content": [said(INSTRUCTIONS)]},
        {"role": "user", "content": user_parts},
    ]
    return body


_MONEY = ("charges", "insurance_paid", "adjustment", "fa_discount", "patient_responsibility")
_DOC_MONEY = ("total_charges", "insurance_paid", "fa_discount", "patient_balance", "due_from_insurance", "amount_due_coupon")
_DOC_DATES = ("statement_date", "service_from", "service_to", "insurance_payment_date")


def _money(raw: dict, key: str, where: str, problems: list[str]):
    text = raw.get(key, "")
    if not text.strip(" $"):
        # an empty form box, or a bare "$": nothing was printed
        return None
    value = parse_money(text)
    if value is None:
        problems.append(f"{where}: {key} {text!r} is not an amount; left empty")
    return value


def _its_own(line: Line, where: str, moved: list[str]) -> Line:
    """No part of a charge can be larger than the charge. A number that is has come from a subtotal printed under the
    lines ("Insurance adjusted -$7,919.78" on a $4,944.00 line): it is not this line's, and neither is its share."""
    parts = (line.insurance_paid, line.adjustment, line.patient_responsibility)
    if not line.charges or line.charges <= 0 or all(p is None or abs(p) <= line.charges for p in parts):
        return line
    moved.append(f"{where}: a number larger than the line's charge came from a subtotal, not this line; left empty")
    return line.model_copy(update={"insurance_paid": None, "adjustment": None, "patient_responsibility": None})


def _one_dash(name: str) -> str:
    """One office, one spelling: the printed en or em dash in "Little Harbor Pediatrics - PA" reads either way."""
    return re.sub(r"\s*[\u2013\u2014]\s*", " - ", name)


SPAN = re.compile(r"^\s*(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\s*(?:-|\u2013|\u2014|to)\s*(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\s*$")


def _date(raw: dict, key: str, where: str, problems: list[str]):
    text = raw.get(key, "")
    if text == "":
        return None
    found = parse_date(text)
    if found is None:
        # a printed span ("02/11/2025-02/13/2025"): the service date is its start, the end only has to exist
        span = SPAN.match(text)
        if span and parse_date(span.group(2)) is not None:
            found = parse_date(span.group(1))
    if found is None:
        problems.append(f"{where}: {key} {text!r} is not a date; left empty")
    return found


def _read_line(raw: dict, n: int, where_doc: str, problems: list[str]) -> Line:
    where = f"{where_doc} line {raw.get('line_no') or n}"
    when = _date(raw, "service_date", where, problems)
    amounts = {k: _money(raw, k, where, problems) for k in _MONEY}
    return Line(
        line_no=raw.get("line_no") or n,
        service_date=when,
        code=raw.get("code", "").strip(),
        description=raw.get("description", "").strip(),
        claim_ref=raw.get("claim_ref", "").strip(),
        denial_codes=raw.get("denial_codes", "").strip(),
        **amounts,
    )


def to_documents(payload: dict, expected: dict[str, Source]) -> tuple[list[Document], list[str]]:
    found: dict[str, Document] = {}
    problems: list[str] = []
    for raw in payload.get("documents", []):
        doc_id = raw["doc_id"].strip()
        if doc_id not in expected:
            problems.append(f"model returned unknown document {doc_id!r}; ignored")
            continue
        if doc_id in found:
            problems.append(f"model returned {doc_id} twice; second copy ignored")
            continue
        kind = DocKind(raw.get("kind", "other"))
        doubts: list[str] = []
        lines = [_read_line(r, n, doc_id, doubts) for n, r in enumerate(raw.get("lines", []), start=1)]
        subtotal_notes: list[str] = []
        lines = [_its_own(ln, f"{doc_id} line {ln.line_no}", subtotal_notes) for ln in lines]
        dates = {k: _date(raw, k, doc_id, doubts) for k in _DOC_DATES}
        sums = {k: _money(raw, k, doc_id, doubts) for k in _DOC_MONEY}
        found[doc_id] = Document(
            doc_id=doc_id,
            kind=kind,
            source=expected[doc_id],
            patient=raw.get("patient", "").strip().strip("[]"),
            provider=_one_dash(raw.get("provider", "").strip()),
            account_ref=raw.get("account_ref", "").strip(),
            claim_ref=raw.get("claim_ref", "").strip(),
            member_ref=raw.get("member_ref", "").strip(),
            first_after_discharge=bool(raw.get("first_after_discharge")),
            unreadable=bool(raw.get("unreadable")),
            page_no=raw.get("page_no") or None,
            page_count=raw.get("page_count") or None,
            lines=lines,
            doubts=list(doubts),
            **dates,
            **sums,
        )
        problems.extend(doubts)
        problems.extend(subtotal_notes)
    missing = [i for i in expected if i not in found]
    if missing:
        problems.append(f"model did not return {', '.join(missing)}")
    return [found[i] for i in expected if i in found], problems


def batches(sheets: list, files: list, max_images: int | None) -> list[tuple[list, list]]:
    """One request when the model takes every image at once (Muse Spark: 50). A model with a smaller limit per
    prompt gets the sheets in groups of that size, the files with the last group."""
    if not max_images or len(sheets) <= max_images:
        return [(sheets, files)]
    groups = [sheets[i:i + max_images] for i in range(0, len(sheets), max_images)]
    return [(g, files if i == len(groups) - 1 else []) for i, g in enumerate(groups)]


def _answer_documents(text: str) -> list:
    """The `documents` list of one model answer; anything that is not a JSON object is a client-facing error."""
    try:
        return json.loads(text).get("documents", [])
    except (ValueError, AttributeError) as e:
        raise MetaAPIError(f"Spark answer is not JSON ({e}); first 200 chars: {text[:200]!r}") from e


def read_case(client: MetaClient, sheets: list[tuple[str, bytes]], files: list[tuple[str, str, bytes]],
              effort: str = "low", label: str = "spark:read") -> ReadResult:
    expected = dict.fromkeys((i for i, _ in sheets), Source.PAPER)
    expected.update(dict.fromkeys((i for i, _, _ in files), Source.PDF))
    model = getattr(client, "read_model", None) or MODEL
    merged: list = []
    replies = []
    for group in batches(sheets, files, getattr(client, "max_images", None)):
        body = request_body(*group, effort=effort, model=model)
        replies.append(client.respond(body, label=label))
        merged.extend(_answer_documents(replies[-1].text))
    try:
        documents, problems = to_documents({"documents": merged}, expected)
    except (ValueError, AttributeError, TypeError) as e:
        raise MetaAPIError(f"the model's answer does not fit the schema: {e}") from e
    return ReadResult(
        documents=documents,
        problems=problems,
        usage={k: sum(r.usage.get(k, 0) for r in replies) for k in ("input_tokens", "output_tokens")},
        seconds=round(sum(r.seconds for r in replies), 2),
        replayed=all(r.replayed for r in replies),
    )
