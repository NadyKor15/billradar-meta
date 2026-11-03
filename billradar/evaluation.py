"""Measure one model on the same papers by three routes: a plain question, a strong request, the full pipeline.

Each pack has an answer key written before any run. Keys for held-back packs are sealed: their hash goes into a ledger
before the first run, and scoring refuses a key whose hash is not there. This module builds the model request bodies,
turns the two model routes into common predictions, scores them against a key and prints a Markdown table.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, fields
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, Field

from billradar import policy
from billradar.checks import Kind, Report
from billradar.meta_client import data_url
from billradar.policies import source

SHOWN_WHEN_DOUBTED = {Kind.F2, Kind.E3, Kind.E4, Kind.P1}
NOT_SCORED = {Kind.NM, Kind.B2}  # a note, and an action for the family (send the baby's insurance): no planted error in the keys
CLASSES = [k.value for k in Kind if k not in NOT_SCORED]
MODEL = "muse-spark-1.3"
SIMPLE_QUESTION = """Here are my hospital bills and the letters from my insurance company. Is there anything wrong in them? Can I pay less?"""


class KeyItem(BaseModel):
    cls: str
    sheets: list[str] = Field(default_factory=list)  # e.g. ["S1", "S2"]; any overlap counts
    amount: Decimal | None = None
    deadline: date | None = None
    note: str = ""


class Key(BaseModel):
    pack_id: str
    split: str  # "work" or "holdout"
    items: list[KeyItem]


class Prediction(BaseModel):
    cls: str
    sheets: list[str] = Field(default_factory=list)
    amount: Decimal | None = None
    deadline: date | None = None



def key_hash(path: Path) -> str:
    """SHA-256 of the key's canonical JSON, so formatting and key order do not change it."""
    canonical = json.dumps(json.loads(path.read_text(encoding="utf-8")), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _seal_line(path: Path) -> str:
    return f"{key_hash(path)}  {path.parent.name}/{path.name}"


def seal(paths: list[Path], ledger: Path) -> list[str]:
    lines = [_seal_line(p) for p in sorted(paths)]
    # Hashes are all computed before the ledger is opened, so a bad key leaves it untouched.
    with ledger.open("a", encoding="utf-8") as out:
        out.write("\n".join(lines) + "\n")
    return lines


def check_seal(path: Path, ledger: Path) -> bool:
    wanted = _seal_line(path)  # first, so a missing or broken key fails even without a ledger
    if not ledger.exists():
        return False
    return wanted in ledger.read_text(encoding="utf-8").splitlines()



def from_report(report: Report) -> list[Prediction]:
    """What the family is shown as found. A date or a note marked "worth checking" is shown, so it counts; a doubted
    amount is shown without its sum, so it does not."""
    shown = report.findings + [f for f in report.worth_asking if f.kind in SHOWN_WHEN_DOUBTED]
    return [Prediction(cls=f.kind.value, sheets=sorted({e.doc_id for e in f.evidence}), amount=f.amount,
                       deadline=f.deadline) for f in shown if f.kind not in NOT_SCORED]


STRONG_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["findings"],
    "properties": {"findings": {"type": "array", "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["cls", "sheets", "amount", "deadline", "explanation"],
        "properties": {
            "cls": {"type": "string", "enum": list(CLASSES)},
            "sheets": {"type": "array", "items": {"type": "string"}},
            "amount": {"type": "string"},
            "deadline": {"type": "string"},
            "explanation": {"type": "string"},
        },
    }}},
}

STRONG_INSTRUCTIONS = """You help a family find the money they are owed on their hospital bills and insurance statements. You give no medical advice.

What you receive
- Photographs of the family's paper sheets, identified S1, S2, ... and digital files, identified D1, ...
- The hospital's full financial assistance policy.
- The federal rule on the application period.
- The household's data: its size, annual income, savings and insurance.

Your task
Check every class listed below. For everything you find in a class, report it together with the sheets on which you found it.

Classes
- `E1`: a bill line asks the patient for more than the insurer's explanation of benefits (EOB) says the patient owes for the same service. `amount` is the difference.
- `E2`: the same service is billed twice (the same date, the same code, the same charge). `amount` is the sum the patient is asked to pay for the second one.
- `E3`: a credit or an overpayment is left on a bill. `amount` is the size of the credit.
- `E4`: one sheet shows two different amounts to pay.
- `B1`: a newborn's care is billed under the mother's insurance ID.
- `P1`: pages of a statement are missing. Go by the page mark, such as "Page N of M".
- `F1`: the household qualifies under the policy (apply the federal poverty guidelines for the year 2026), and the bill shows no financial assistance discount. `amount` is the discount on that bill.
- `F2`: the last day to apply for financial assistance, calculated the way the policy and the federal rule define it together. Give it in `deadline`, written as YYYY-MM-DD.
- `F3`: a discount is on one bill of the same hospital stay (the mother's bill) but is missing from another (the baby's bill). `amount` is the missing discount.

Format and limits
- Write `amount` as a number in text, like "1054.00". If there is no amount, use the empty string "".
- Report only what the papers and the policy support.
"""


def _text(text: str) -> dict:
    return {"type": "input_text", "text": text}


def _media(sheets: list[tuple[str, bytes]], files: list[tuple[str, str, bytes]]) -> list[dict]:
    """Sheets first, then files; each object is preceded by a caption naming it."""
    parts: list[dict] = []
    for sheet_id, jpeg in sheets:
        parts.append(_text(f"Sheet {sheet_id}:"))
        parts.append({"type": "input_image", "image_url": data_url(jpeg, "image/jpeg")})
    for file_id, name, pdf in files:
        parts.append(_text(f"File {file_id} ({name}):"))
        parts.append({"type": "input_file", "filename": name, "file_data": data_url(pdf, "application/pdf")})
    return parts


def _request(max_tokens: int, schema_name: str | None = None, schema: dict | None = None) -> dict:
    """The settings shared by every request; a schema name and schema turn on strict structured output."""
    body = {"model": MODEL, "store": False, "stream": True, "reasoning": {"effort": "medium"},
            "max_output_tokens": max_tokens}
    if schema_name is not None:
        body["text"] = {"format": {"type": "json_schema", "name": schema_name, "schema": schema, "strict": True}}
    return body


def simple_body(sheets, files) -> dict:
    body = _request(16000)
    body["input"] = [{"role": "user", "content": [_text(SIMPLE_QUESTION)] + _media(sheets, files)}]
    return body


def strong_body(sheets, files, policy_id: str, household: dict) -> dict:
    policy_pdf = Path(source.pdf_path(policy_id)).read_bytes()
    federal_rule = source.page_texts("federal-501r")[0][:20000]
    body = _request(32000, "strong_baseline", STRONG_SCHEMA)
    # The developer message holds only the stable part, so it can be cached between runs.
    body["input"] = [
        {"role": "developer", "content": [
            _text(STRONG_INSTRUCTIONS),
            _text("Federal rule (26 CFR 1.501(r)-1):\n" + federal_rule)]},
        {"role": "user", "content": [
            {"type": "input_file", "filename": f"{policy_id}.pdf",
             "file_data": data_url(policy_pdf, "application/pdf")},
            _text("Household: " + json.dumps(household))] + _media(sheets, files)},
    ]
    return body


def _predict(cls: str, sheets: list[str], amount: str | None, deadline: str | None) -> Prediction:
    # Deferred import, to avoid an import cycle.
    from billradar.case import parse_date, parse_money
    return Prediction(cls=cls, sheets=sheets, amount=parse_money(amount), deadline=parse_date(deadline))


def from_strong(text: str) -> list[Prediction]:
    findings = json.loads(text).get("findings", [])
    return [_predict(f["cls"], list(f.get("sheets", [])), f.get("amount"), f.get("deadline")) for f in findings]


JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items", "other_money_claims"],
    "properties": {
        "items": {"type": "array", "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["index", "found", "amount", "deadline"],
            "properties": {
                "index": {"type": "integer"},
                "found": {"type": "boolean"},
                "amount": {"type": "string"},
                "deadline": {"type": "string"},
            },
        }},
        "other_money_claims": {"type": "integer"},
    },
}

_JUDGE_TASK = (
    "For each known issue: did the answer clearly point it out (found), and if it gave an amount or date for it, "
    "copy it. Then count other claims of money owed to the family that are not in the list (other_money_claims)."
)


def _listing_line(index: int, item: KeyItem) -> str:
    where = ", ".join(item.sheets) if item.sheets else "-"
    return str(index) + ". [" + item.cls + "] sheets " + where + "; " + item.note


def judge_body(answer: str, key: Key) -> dict:
    listing = "\n".join(_listing_line(i, item) for i, item in enumerate(key.items))
    prompt = "".join([
        "An assistant answered a family about their hospital papers. Answer:\n<<<\n", answer, "\n>>>\n\n",
        "Known issues in these papers:\n", listing, "\n\n",
        _JUDGE_TASK,
    ])
    return _request(8000, "judge", JUDGE_SCHEMA) | {"input": [{"role": "user", "content": [_text(prompt)]}]}


def from_judge(text: str, key: Key) -> tuple[list[Prediction], int]:
    verdict = json.loads(text)
    preds = []
    for entry in verdict.get("items", []):
        if not entry.get("found") or entry.get("index") is None:
            continue
        index = int(entry["index"])
        if not 0 <= index < len(key.items):
            continue
        item = key.items[index]
        preds.append(_predict(item.cls, list(item.sheets), entry.get("amount"), entry.get("deadline")))
    return preds, int(verdict.get("other_money_claims", 0))



@dataclass
class ClassScore:
    n: int = 0
    found: int = 0
    false: int = 0
    wrong_amount: int = 0
    no_amount: int = 0  # found, but said no amount where the key has one
    wrong_deadline: int = 0


@dataclass
class Score:
    by_class: dict[str, ClassScore] = field(default_factory=dict)
    extra_false: int = 0  # unmatched money claims the judge counted (simple path)

    def add(self, other: "Score") -> None:
        for cls, theirs in other.by_class.items():
            mine = self.by_class.setdefault(cls, ClassScore())
            for counter in fields(ClassScore):
                setattr(mine, counter.name, getattr(mine, counter.name) + getattr(theirs, counter.name))
        self.extra_false += other.extra_false


_AMOUNT_TOLERANCE = Decimal("1.00")


def _fits(item: KeyItem, pred: Prediction) -> bool:
    """Same class, and the sheets agree unless either side names none."""
    return item.cls == pred.cls and (not item.sheets or not pred.sheets or bool(set(item.sheets) & set(pred.sheets)))


def _pair_up(items: list[KeyItem], preds: list[Prediction]) -> list[int | None]:
    """For each key item, the index of the first still-free fitting prediction (None if there is none)."""
    taken: set[int] = set()
    pairing: list[int | None] = []
    for item in items:
        choice = None
        for i, pred in enumerate(preds):
            if i not in taken and _fits(item, pred):
                choice = i
                taken.add(i)
                break
        pairing.append(choice)
    return pairing


def _grade(item: KeyItem, pred: Prediction, counts: ClassScore) -> None:
    counts.found += 1
    if item.amount is not None:
        if pred.amount is None:
            counts.no_amount += 1
        elif abs(pred.amount - item.amount) > _AMOUNT_TOLERANCE:
            counts.wrong_amount += 1
    if item.deadline is not None and pred.deadline != item.deadline:
        counts.wrong_deadline += 1


def score(key: Key, preds: list[Prediction], extra_false: int = 0) -> Score:
    result = Score(extra_false=extra_false)
    pairing = _pair_up(key.items, preds)
    for item, match in zip(key.items, pairing):
        counts = result.by_class.setdefault(item.cls, ClassScore())
        counts.n += 1
        if match is not None:
            _grade(item, preds[match], counts)
    used = {m for m in pairing if m is not None}
    for i, pred in enumerate(preds):
        if i not in used:
            result.by_class.setdefault(pred.cls, ClassScore()).false += 1
    return result


def table(results: dict[str, Score]) -> str:
    paths = list(results)
    scores = list(results.values())
    # list.index raises ValueError for a class outside CLASSES; that is deliberate and not caught.
    classes = sorted({cls for r in scores for cls in r.by_class}, key=CLASSES.index)

    def cell(r: Score, cls: str) -> str:
        c = r.by_class.get(cls, ClassScore())
        extras = [f"{count} {label}" for count, label in
                  ((c.false, "false"), (c.wrong_amount, "wrong $"), (c.no_amount, "no $"),
                   (c.wrong_deadline, "wrong date")) if count]
        return f"{c.found} of {c.n}" + (f" ({', '.join(extras)})" if extras else "")

    rows = ["| Class | " + " | ".join(paths) + " |", "|---|" + "---|" * len(paths)]
    rows += [f"| {cls} | " + " | ".join(cell(r, cls) for r in scores) + " |" for cls in classes]
    if any(r.extra_false for r in scores):
        rows.append("| other money claims not in the key | " + " | ".join(str(r.extra_false) for r in scores) + " |")
    totals = numbers(results)
    rows.append("| All classes | " + " | ".join(
        f"{totals[p]['found']} of {totals[p]['n']} ({totals[p]['percent']}%)" for p in paths) + " |")
    return "\n".join(rows)


def numbers(results: dict[str, Score]) -> dict[str, dict]:
    """The headline per path, with its base next to it: found k of n, and everything that went wrong."""
    out = {}
    for path, r in results.items():
        cs = list(r.by_class.values())
        n, found = sum(c.n for c in cs), sum(c.found for c in cs)
        out[path] = {"n": n, "found": found, "percent": round(100 * found / n) if n else 0,
                     "false": sum(c.false for c in cs) + r.extra_false, "wrong_amount": sum(c.wrong_amount for c in cs),
                     "no_amount": sum(c.no_amount for c in cs), "wrong_deadline": sum(c.wrong_deadline for c in cs)}
    return out


def verified_policy(policy_id: str) -> bool:
    """True when every quote of the policy stands on its stated page of the downloaded text."""
    return all(policy.verify_fragment(frag).found for frag in policy.load(policy_id).fragments.values())
