"""What a family sees on the case screen, built only from the case and the check report.

No models and no network here; the only outside read is the hospital policy files, for quotes and income bands.
Amounts and dates turn into screen words ("$1,500", "Mar 1, 2026", "sheet 3"), each finding gets one plain line,
papers get captions, and the screen gets its headline, its apply-by line, its finding cards and its lists of papers.
Numbers and dates are never worked out again: they come from the finding (`math`, `amount`, `deadline`) and the
profile, so the screen cannot say more than the checks found.
"""

from __future__ import annotations

import re

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import ROUND_DOWN, Decimal

from billradar import days, policy
from billradar.case import Case, Document, DocKind, Role, Source
from billradar.checks import Finding, Kind, Report

KIND_LABEL = {
    DocKind.HOSPITAL_STATEMENT: "Hospital statement",
    DocKind.ITEMIZED_BILL: "Itemized bill",
    DocKind.EOB: "EOB",
    DocKind.FA_LETTER: "Financial assistance letter",
    DocKind.PAYMENT_RECEIPT: "Payment",
    DocKind.OTHER: "Document",
}
TONE = {Kind.F1: "good", Kind.F2: "time", Kind.F3: "problem", Kind.E1: "problem", Kind.E2: "problem",
        Kind.E3: "good", Kind.E4: "problem", Kind.B1: "problem", Kind.B2: "time", Kind.P1: "time", Kind.NM: "quiet"}
SHEET_COLORS = 6


@dataclass
class Chip:
    label: str
    kind: str  # "sheet", "policy", "profile"
    color: int | None = None  # sheet color index
    title: str = ""


@dataclass
class Card:
    kind: str
    tone: str
    title: str
    detail: str  # one or two short lines, like the picked screen
    chips: list[Chip]
    pill: str = ""
    full: str = ""  # the whole explanation from the checks, on hover / expand


@dataclass
class DocRow:
    doc_id: str
    number: str
    color: int | None
    label: str


@dataclass
class Screen:
    case_title: str
    letterhead: str
    headline: str
    subline: str
    cards: list[Card]
    quiet: list[Card]
    paper: list[DocRow]
    digital: list[DocRow]
    overlays: list[str] = field(default_factory=list)
    replayed: bool = True


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _stamp(day: date) -> str:
    """Month name, day without a zero, year; always English."""
    return f"{_MONTHS[day.month - 1]} {day.day}, {day.year}"


def money(x: Decimal) -> str:
    # a whole amount drops its cents; the sign stays after the dollar sign
    return "$" + format(x, ",.0f" if x == x.to_integral_value() else ",.2f")


def up_to(total: Decimal) -> str:
    """Whole dollars rounded down: "up to" must never promise more than the checks found. Under a dollar, the sum itself."""
    return money(total.to_integral_value(rounding=ROUND_DOWN)) if total >= 1 else money(total)


def person(case: Case, token: str) -> str:
    from billradar.appeal import norm_token
    wanted = norm_token(token)
    for who in case.profile.people:
        if norm_token(who.token) != wanted:
            continue
        if who.name:
            return who.name
        if who.role == Role.MOTHER:
            return "Mom"
        if who.role == Role.NEWBORN:
            return "Baby"
        return token
    return token or "—"


def doc_label(case: Case, d: Document) -> str:
    if d.first_after_discharge and d.statement_date:
        return f"First bill after discharge · {_stamp(d.statement_date)}"
    parts = [KIND_LABEL[d.kind], person(case, d.patient)]
    balance = d.patient_balance
    if d.kind == DocKind.EOB and d.lines:
        parts.append(d.lines[-1].description)
    elif balance is not None:
        # a bill that is all due from insurance is not the family's debt
        if balance != 0 and d.owed == 0:
            parts.append(f"{money(balance)} due from insurance")
        else:
            parts.append(money(balance))
    return " · ".join(p for p in parts if p)


def _policy_chip(ref: str) -> Chip:
    policy_id, fragment_id = ref.split("#", 1)
    frag = policy.load(policy_id).fragment(fragment_id)
    label = "Federal rule" if policy_id.startswith("federal") else f"Policy p.{frag.page}"
    return Chip(label, "policy", None, frag.quote)


def _sheet(doc_id: str) -> str:
    return ("sheet " if doc_id[:1] == "S" else "file ") + doc_id[1:]


def _tier_range(policy_id: str, pct: Decimal) -> str:
    pol = policy.load(policy_id)
    tier = pol.tier_for(pct)
    if tier is None:
        return ""
    at = pol.tiers.index(tier)
    ends = f"{tier.max_fpl_pct}% → {tier.discount_pct}% off"
    if at == 0:
        return "up to " + ends
    return f"{pol.tiers[at - 1].max_fpl_pct + 1}–" + ends


# rule name (after "policy:" / "federal:" in `math`) -> words for the family
_RULE_WORDS = {
    "one year after service": "1 year after your care",
    "12 months after last insurance payment": "12 months after your insurance paid",
    "days after first bill": "the first bill after discharge",
    "240 days after first bill": "240 days from the first bill after discharge",
}
_FROM_FIRST_BILL = ("days after first bill", "240 days after first bill")
_AFTER_PAYMENT = "12 months after last insurance payment"


def _apply_by_line(f: Finding, case: Case) -> str:
    """F2: which rule the deadline was counted from, and the first bill's date."""
    rules = [(k, v) for k, v in f.math.items() if k.startswith(("policy:", "federal:"))]
    if not rules:
        raise ValueError("no dated rule in math")
    winner = rules[0]
    for rule in rules[1:]:
        if rule[1] > winner[1]:  # ISO dates compare as text; a tie keeps the earlier entry
            winner = rule
    name = winner[0].split(":", 1)[1].strip()
    paid_note = ""
    paid_sheet = f.math.get("paid_sheet")
    if paid_sheet:
        paid_on = date.fromisoformat(f.math["paid_on"])
        paid_note = f" ({_sheet(paid_sheet)}, {_stamp(paid_on)})"
    first = case.doc(f.evidence[0].doc_id).statement_date if f.evidence else None
    base = _RULE_WORDS.get(name) or winner[0][:1].upper() + winner[0][1:]  # unknown: the whole key, capitalised
    if name in _FROM_FIRST_BILL:
        return base[:1].upper() + base[1:] + (f" ({_stamp(first)})" if first else "") + "."
    text = base + (paid_note if name == _AFTER_PAYMENT else "") + "."
    if first:
        text += f" First bill after discharge: {_stamp(first)}."
    federal = next((v for k, v in rules if k.startswith("federal:")), None)
    if federal and not winner[0].startswith("federal:") and f.deadline:
        text += (f" The federal minimum is {_stamp(date.fromisoformat(federal))}; the hospital's policy gives you until "
                 f"{_stamp(f.deadline)}, and the later date counts.")
    return text


def _newborn_line(math: dict[str, str]) -> str:
    text = f"Newborn care ({math['codes']}) is on mom's insurance ID."
    denied = math.get("denied_lines", "0")
    if denied != "0":
        text += f" {denied} line{'' if denied == '1' else 's'}"
        if math.get("denied_total"):
            text += f", {money(Decimal(math['denied_total']))},"
        text += " denied."
    text += " Ask to bill it under the baby."
    if math.get("baby_bill"):
        text += f" The baby's bill ({_sheet(math['baby_bill'])}) shows an insurance credit no statement explains."
    return text


def short(f: Finding, case: Case, policy_id: str) -> str:
    kind, math, ev = f.kind, f.math, f.evidence
    if kind == Kind.F1:
        if "fpl_pct" in math:
            pct = math["fpl_pct"]
            band = _tier_range(policy_id, Decimal(pct))
            profile = case.profile
            return (f"Household of {profile.household_size} · income {money(profile.annual_income)} · "
                    f"{pct}% of the poverty line. Policy: {band}.")
        if "cap" in math:
            return f"The policy caps what you pay at {money(Decimal(math['cap']))} a year."
    elif kind == Kind.F2:
        return _apply_by_line(f, case)
    elif kind == Kind.F3 and len(ev) == 2:
        return (f"Same stay. A discount on {_sheet(ev[0].doc_id)}, none on {_sheet(ev[1].doc_id)}. "
                f"At your income the policy gives {math.get('discount_pct', '')}% off.")
    elif kind == Kind.E1 and len(ev) == 2:
        text = f"Line {ev[0].line_no} on {_sheet(ev[0].doc_id)} vs. patient responsibility on {_sheet(ev[1].doc_id)}."
        if f.amount is not None and "share_left_after_discount" in math:
            text += f" Your discount already covers part of it: {money(f.amount)} of it is yours."
        return text
    elif kind == Kind.E2 and len(ev) >= 2:
        return (f"Code {math['code']} twice on {_sheet(ev[0].doc_id)} (lines {ev[0].line_no} and {ev[1].line_no}), "
                "same day, same price.")
    elif kind == Kind.E3:
        return f.detail if "applied_on" in math else "A credit sits on the account. Ask for it back."
    elif kind == Kind.E4:
        owed, coupon = Decimal(math["patient_balance"]), Decimal(math["amount_due_coupon"])
        return f"Balance {money(owed)}, but the coupon asks {money(coupon)}. Ask before you pay."
    elif kind == Kind.B1:
        return _newborn_line(math)
    elif kind == Kind.P1:
        return f"Missing pages: {', '.join(math['missing'].split(','))} of {math['page_count']}. Totals may be on them."
    return f.detail


def _paper_chips(f: Finding, colors: dict[str, int]) -> list[Chip]:
    chips, seen = [], set()
    for e in f.evidence:
        if e.doc_id in seen:
            continue
        seen.add(e.doc_id)
        label = ("Sheet " if e.doc_id.startswith("S") else "File ") + e.doc_id[1:]
        if e.line_no:
            label += f" · line {e.line_no}"
        chips.append(Chip(label, "sheet", colors.get(e.doc_id), e.note))
    return chips


def _ref_chips(f: Finding) -> list[Chip]:
    chips = []
    for ref in f.policy_refs:
        chip = _policy_chip(ref)
        if all(chip.label != c.label for c in chips):
            chips.append(chip)
    return chips


_PILL = {Kind.F1: "About {} off", Kind.F3: "{} not applied", Kind.E3: "{} back to you"}


def card(f: Finding, colors: dict[str, int], case: Case | None = None, policy_id: str = "") -> Card:
    title, detail = f.title, f.detail
    if case is not None:
        detail = short(f, case, policy_id)
        if f.kind == Kind.F3 and len(f.evidence) == 2:
            first, second = [person(case, case.doc(e.doc_id).patient) for e in f.evidence]  # list: keep StopIteration
            title = f"Discount on {first}'s bill, not on {'the baby' if second == 'Baby' else second}'s"
    pill = _PILL.get(f.kind, "{}").format(money(f.amount)) if f.amount is not None else ""
    chips = _paper_chips(f, colors) + _ref_chips(f)
    if f.kind == Kind.F1 and "fpl_pct" in f.math:
        chips.append(Chip("Profile", "profile", None, "household size and income, kept on your computer"))
    return Card(kind=f.kind.value, tone=TONE.get(f.kind, "quiet"), title=title, detail=detail, chips=chips,
                pill=pill, full=f.detail)


_CARD_ORDER = (Kind.F1, Kind.F2, Kind.F3, Kind.E1, Kind.E2, Kind.B1, Kind.E4, Kind.E3, Kind.P1)


def _unread_words(unreadable: list[str]) -> tuple[str, str]:
    """The papers that could not be read, and what to do about them."""
    names = [("file " if u[0] == "D" else "sheet ") + u[1:] for u in unreadable]
    again = "add it again" if all(u[0] == "D" for u in unreadable) else "take a new photo"
    return ", ".join(names), again


def _case_title(case: Case) -> str:
    mother = next((p for p in case.profile.people if p.role == Role.MOTHER), None)
    title = f"{person(case, mother.token)}'s case" if mother else "Your case"
    if any(p.role == Role.NEWBORN for p in case.profile.people):
        title = title.replace("case", "birth case")
    return title


def _count_line(papers: int, digital: int) -> str:
    text = f"Found {papers} paper sheet{'' if papers == 1 else 's'}"
    if digital:
        text += f" + {digital} digital file{'' if digital == 1 else 's'}"
    return text


def build(case: Case, report: Report, overlays: list[str], replayed: bool = True, unreadable: list[str] | None = None) -> Screen:
    unreadable = unreadable or []
    lost, again = _unread_words(unreadable)  # always worked out, as the list may hold a bad entry
    total = report.total_may_come_off
    if total > 0:
        headline = f"Up to {up_to(total)} may come off your bills"
    elif unreadable:
        headline = f"We could not read {lost}: {again}"
    else:
        headline = "We checked every sheet"

    colors: dict[str, int] = {}
    shade = 0
    for d in case.documents:
        if d.source == Source.PAPER:
            colors[d.doc_id] = shade % SHEET_COLORS
            shade += 1
    paper_docs = [d for d in case.documents if d.source == Source.PAPER]
    digital_docs = [d for d in case.documents if d.source != Source.PAPER]

    subline = [_count_line(len(paper_docs), len(digital_docs))]
    if report.apply_by:
        if days.passed(report.apply_by, case.today):
            subline.append(f"the last day to apply passed on {_stamp(report.apply_by)}")
        else:
            late = "" if report.apply_by_sure else f", {days.CHECK_DATE}"
            subline.append(f"apply by {_stamp(report.apply_by)}{late}")

    ranked = sorted(report.findings, key=lambda f: _CARD_ORDER.index(f.kind) if f.kind in _CARD_ORDER else len(_CARD_ORDER))
    return Screen(
        case_title=_case_title(case), letterhead=case.letterhead, headline=headline, subline=" · ".join(subline),
        cards=[card(f, colors, case, report.policy_id) for f in ranked],
        quiet=[card(f, colors) for f in report.no_money],
        paper=[DocRow(d.doc_id, d.doc_id[1:], colors[d.doc_id], doc_label(case, d)) for d in paper_docs],
        digital=[DocRow(d.doc_id, d.doc_id[1:], None, doc_label(case, d)) for d in digital_docs],
        overlays=overlays, replayed=replayed)


# ---- who did what: model labels per step and per finding (provider from the run, never hard-wired) ----

# role -> label, per provider. A run says which provider answered in problems.json ("provider", default
# "meta") and may override single labels ("models": {"read": "..."}). Roles: find (sheets on the photo),
# read (all sheets into one case), review (read-only second look at findings and letters).
MODEL_LABELS = {
    "meta": {"find": "SAM 3.1", "read": "Muse Spark", "review": "Muse Wonder"},
}


@dataclass
class ModelTag:
    label: str
    role: str  # find | read | review | code | device
    replayed: bool = False

    @property
    def title(self) -> str:
        what = {"find": "found the sheets on the photo", "read": "read the sheets",
                "review": "reviewed the findings, read-only", "code": "computed in code from the sheets and the policy",
                "device": "done on your computer"}[self.role]
        return f"{self.label}: {what}" + (" (replayed answers, not a live call)" if self.replayed else "")


def labels_for(run_meta: dict) -> dict[str, str]:
    provider = run_meta.get("provider", "meta")
    base = dict(MODEL_LABELS.get(provider, {}))
    base.update(run_meta.get("models") or {})
    return base


def _review_line(run_meta: dict, name: str) -> str:
    """What the second look said, counted from its own verdicts in the run."""
    said = (run_meta.get("checker") or {}).get("review") or {}
    total = sum(said.values())
    if not total:
        return "Findings and letters"
    line = (f"{name} reviewed {total} items: {said.get('confirmed', 0)} confirmed, {said.get('problem', 0)} flagged, "
            f"{said.get('cannot_tell', 0)} it could not check from the papers")
    return line + (f", {said['overruled']} overruled by code" if said.get("overruled") else "")


def _reviewed(run_meta: dict) -> bool:
    """Only when the review model really answered: its verdicts are counted, or its notes are in the checker's issues."""
    checker = run_meta.get("checker") or {}
    # the review note starts with the name of the model that ran (verifier.checker_name)
    return bool(checker.get("reviewed") or checker.get("review")) or any("Muse Wonder" in i.get("what", "") for i in checker.get("issues", []))


def models_for(f: Finding, run_meta: dict) -> list[ModelTag]:
    """The models that really took part in this finding: who found its sheets, who read them, who reviewed it."""
    labels, replayed = labels_for(run_meta), run_meta.get("replayed", True)
    ran = run_meta.get("timings") or {}  # a case read without photos (or not by a model) never ran these steps
    docs = {e.doc_id for e in f.evidence}
    tags = []
    if any(d.startswith("S") for d in docs) and "find" in labels and "sam" in ran:
        tags.append(ModelTag(labels["find"], "find", replayed))
    if docs and "read" in labels and "spark" in ran:
        if tags and tags[-1].label == labels["read"]:  # one model found and read the sheets: one chip that says so
            tags[-1] = ModelTag(f"{labels['read']} · found & read", "find", replayed)
        elif labels.get("find") == labels["read"]:  # same model, only the reading here (a PDF): say which step
            tags.append(ModelTag(f"{labels['read']} · read", "read", replayed))
        else:
            tags.append(ModelTag(labels["read"], "read", replayed))
    if _reviewed(run_meta) and "review" in labels:
        tags.append(ModelTag(labels["review"], "review", replayed))
    return tags


@dataclass
class Step:
    n: int
    title: str
    tag: ModelTag
    detail: str


def steps(case: Case, run_meta: dict, sheets: int) -> list[Step]:
    """How this case was made, step by step, with who did each step."""
    labels, replayed = labels_for(run_meta), run_meta.get("replayed", True)
    t = run_meta.get("timings") or {}
    digital = sum(1 for d in case.documents if d.source != Source.PAPER)
    if "sam" not in t and "spark" not in t:  # no photos and no model reading in this run
        return [Step(1, "Papers already read", ModelTag("Sample data", "code"),
                     f"{len(case.documents)} documents, typed in for this example"),
                Step(2, "Checked every quote and amount", ModelTag("Code checker", "code"),
                     f"{(run_meta.get('checker') or {}).get('checked', 0)} items re-done from the papers")]
    out = [
        Step(1, "Found every sheet", ModelTag(labels.get("find", "—"), "find", replayed),
             f"{sheets} sheet{'s' if sheets != 1 else ''} on the photos" + (f" · {t['sam']:.1f} s" if t.get("sam") else "")),
        Step(2, "Hid names", ModelTag("On your computer", "device"),
             "Names and account numbers covered before upload" if run_meta.get("redacted")
             else "This run read the sample papers uncovered. The covered copy is on the tab next to the sheets"),
        Step(3, "Read and connected all sheets", ModelTag(labels.get("read", "—"), "read", replayed),
             f"{len(case.documents)} documents into one case" + (f" ({digital} digital)" if digital else "")),
        Step(4, "Checked every quote and amount", ModelTag("Code checker", "code"),
             f"{(run_meta.get('checker') or {}).get('checked', 0)} items re-done from the sheets"),
    ]
    if _reviewed(run_meta) and "review" in labels:
        out.append(Step(5, "Second look, read-only", ModelTag(labels["review"], "review", replayed),
                        _review_line(run_meta, labels["review"])))
    return out


# ---- the case screen in style D: findings as rows, with a level and who found them ----

LEVEL_HIGH, LEVEL_CHECK, LEVEL_OK = "serious", "worth checking", "ok"
CAPTION = {Kind.E1: "Potential overcharge", Kind.E2: "Potential overcharge", Kind.F1: "May come off",
           Kind.F3: "Not applied yet", Kind.E3: "Back to you"}
BORDERLINE_NEXT = {Kind.F1: "Send the application", Kind.F3: "Ask why the discount is missing",
                   Kind.B1: "Ask to bill it under the baby", Kind.P1: "Ask for the missing pages",
                   Kind.I1: "Letter ready: request itemized bill", Kind.E1: "Ask the billing office",
                   Kind.E2: "Ask to remove the double", Kind.E3: "Check it stays taken off",
                   Kind.N1: "Ask your insurance", Kind.C1: "Ask for the cash price", Kind.C2: "Ask the plan",
                   Kind.A1: "Ask your plan", Kind.B2: "Send the baby's insurance"}
NO_AMOUNT = {Kind.B2: ("Send the baby's insurance", "No statement covers the baby"), Kind.B1: ("May be reprocessed", "Newborn coverage may apply"),
             Kind.E4: ("Ask before you pay", "Two amounts on one sheet"),
             Kind.P1: ("Ask for the pages", "Totals may be on them")}


@dataclass
class Row:
    kind: str
    level: str  # serious | worth checking | ok
    label: str  # CONFIRMED · WORTH CHECKING · CHECKED — NO MONEY HERE
    title: str
    where: str  # "Sheet 10, lines 3–4"
    detail: str
    models: list[ModelTag]
    value: str  # right column, big
    caption: str
    full: str = ""
    laws: list[Chip] = field(default_factory=list)
    refs: list[Chip] = field(default_factory=list)  # the policy pages whose quotes back this finding
    explain: str = ""
    confidence: float | None = None
    unsure: str = ""  # why the checker is not sure (borderline)
    lines: list[str] = field(default_factory=list)  # every line it points to, in plain words
    how: list[str] = field(default_factory=list)  # the printed values a sum stands on: "how it was worked out"
    paper: str = ""  # the first sheet or file this finding stands on: the arrow on the card opens it
    marked: str = ""  # the sheet with this finding's line marked (billradar.highlight)

    @property
    def sure(self) -> str:
        """The confidence scale: green >= 0.9, yellow 0.7-0.89, orange below (worth checking)."""
        if self.confidence is None:
            return ""
        return "high" if self.confidence >= 0.9 else ("mid" if self.confidence >= 0.7 else "low")


def _where(f: Finding) -> str:
    by_doc: dict[str, list[int]] = {}
    for e in f.evidence:
        by_doc.setdefault(e.doc_id, [])
        if e.line_no:
            by_doc[e.doc_id].append(e.line_no)
    parts = []
    for doc, lines in by_doc.items():
        name = f"Sheet {doc[1:]}" if doc.startswith("S") else f"File {doc[1:]}"
        lines = sorted(set(lines))
        if len(lines) == 1:
            name += f", line {lines[0]}"
        elif lines:
            name += f", lines {lines[0]}–{lines[-1]}" if lines == list(range(lines[0], lines[-1] + 1)) \
                else ", lines " + ", ".join(map(str, lines))
        parts.append(name)
    return " · ".join(parts)


def _law_chips(f: Finding) -> list[Chip]:
    chips = []
    for ref in getattr(f, "laws", None) or []:
        try:
            chips.append(source_chip(ref))
        except Exception:  # a law id the sources do not know: show the id, never invent a quote
            chips.append(Chip(ref.split("#", 1)[-1], "policy"))
    return chips


def passed_title(f: Finding, today) -> str:
    """The heading of a date gone by; "" while it is open."""
    return days.passed_title(f.kind, f.deadline, today)


SAYS_IT_ALREADY = {Kind.E2, Kind.P1}  # the card's own line is the plain words: "Code 01960 twice on sheet 8, same day, same price."


def row(f: Finding, case: Case, policy_id: str, run_meta: dict) -> Row:
    severity = getattr(f, "severity", None)
    borderline = severity == "borderline"
    if f.kind == Kind.NM:
        level, label = LEVEL_OK, "Checked — no money here"
    elif borderline:
        level, label = LEVEL_CHECK, "Worth checking"
    else:
        level, label = LEVEL_HIGH, "Confirmed"
    if f.kind == Kind.NM:
        value, caption = ("Outside this policy" if "outside the hospital" in f.title else "No issue found"), ""
    elif f.deadline and days.passed(f.deadline, case.today):
        value, caption = f"{f.deadline:%b %-d, %Y}", "This date has passed"
    elif borderline and f.kind == Kind.F2 and f.deadline:  # a date is not an amount: show it, to be checked
        value, caption = f"{f.deadline:%b %-d, %Y}", "Last day to apply, check it with the hospital"
    elif borderline:  # no amount until it is confirmed; the next step fits the finding
        value, caption = "No amount yet", BORDERLINE_NEXT.get(f.kind, "Ask for the itemized bill")
    elif f.amount is not None:
        value, caption = f"${f.amount:,.2f}", CAPTION.get(f.kind, "")
    elif f.kind == Kind.F2 and f.deadline:
        value, caption = f"{f.deadline:%b %-d, %Y}", "Last day to apply"
    else:
        value, caption = NO_AMOUNT.get(f.kind, ("", ""))
    detail = short(f, case, policy_id) if f.kind != Kind.NM else _nm_detail(f, case)
    title = passed_title(f, case.today) or f.title
    if f.kind == Kind.F3 and len(f.evidence) == 2:
        title = card(f, {}, case, policy_id).title
    refs = []
    for ref in f.policy_refs:
        c = _policy_chip(ref)
        if c.label not in [r.label for r in refs]:
            refs.append(c)
    from billradar.i18n import plain
    title, detail = plain(title, case), plain(detail, case)  # tokens the model saw, in words for the family
    return Row(f.kind.value, level, label, title, _where(f), detail, models_for(f, run_meta), value, caption,
               detail if f.kind == Kind.NM else plain(f.detail, case) + (  # NM: the offices named once, on hover too
                   f" {days.left(f.deadline, case.today)}" if f.deadline else ""),
               _law_chips(f), refs, "" if f.kind in SAYS_IT_ALREADY else plain(getattr(f, "explain", None) or "", case),
               getattr(f, "confidence", None), plain(_unsure(f.math.get("why_unsure", "")), case), _plain_lines(f, case),
               worked_out(f), f.evidence[0].doc_id if f.evidence else "")


def _nm_detail(f: Finding, case: Case) -> str:
    from billradar import finding_text
    return finding_text.text(f, case, "en")[1]


def _unsure(why: str) -> str:
    """Why a finding is not confirmed, in words the card can stand behind. The second read's own text can name dates
    and sheets the code has already worked out otherwise (the F2 card once said "an unknown date" next to the code's
    "Mar 21, 2026"): the card says who doubted it and points to the case data, where its words are kept as given."""
    out = []
    for part in re.split(r"; (?=Muse Wonder:)", why):  # one entry per doubt; a reason may hold "; " itself
        if part.startswith("Muse Wonder:"):
            part = "Muse Wonder flagged this on its second look; its notes are in the case data"
        if part not in out:
            out.append(part)
    said_all = "; ".join(out)
    return said_all if not said_all or said_all[-1] in ".!?" else said_all + "."


def worked_out(f: Finding) -> list[str]:
    """Where a confirmed sum comes from, value by value: read from its trace, the same one the checker follows."""
    if f.amount is None:
        return []
    out = []
    for step in f.trace:
        paper = f"{'Sheet' if step.doc_id.startswith('S') else 'File'} {step.doc_id[1:]}"
        where = f"{paper}, line {step.line_no}" if step.line_no else paper
        out.append(f"{where}: {step.role} ${abs(step.printed):,.2f}")
    return out


def _plain_lines(f: Finding, case: Case) -> list[str]:
    from billradar import explain
    out = []
    for e in f.evidence:
        if not e.line_no:
            continue
        try:
            doc = case.doc(e.doc_id)
        except StopIteration:
            continue
        ln = next((x for x in doc.lines if x.line_no == e.line_no), None)
        if ln is not None:
            text = f"{'Sheet' if e.doc_id.startswith('S') else 'File'} {e.doc_id[1:]}, line {e.line_no}: {explain.line(ln)}"
            if text not in out:
                out.append(text)
    return out


@dataclass
class Board:
    rows: list[Row]
    serious: int
    checking: int
    quiet: int


def board(case: Case, report: Report, run_meta: dict, marked: dict[int, str] | None = None) -> Board:
    """`marked`: a finding's place in findings + worth_asking -> the address of its marked sheet."""
    marked = marked or {}
    order = {Kind.E2: 0, Kind.E1: 1, Kind.B1: 2, Kind.F1: 3, Kind.F3: 4, Kind.E3: 5, Kind.E4: 6, Kind.P1: 7, Kind.F2: 8}
    found = sorted(enumerate(report.findings), key=lambda x: (getattr(x[1], "severity", None) == "borderline", order.get(x[1].kind, 9)))
    rows = [replace(row(f, case, report.policy_id, run_meta), marked=marked.get(i, "")) for i, f in found]
    # "Worth checking": borderline items without an amount, kept apart from confirmed ones
    asking = [f.model_copy(update={"severity": "borderline"}) for f in getattr(report, "worth_asking", None) or []]
    rows += [replace(row(f, case, report.policy_id, run_meta), marked=marked.get(len(report.findings) + i, ""))
             for i, f in enumerate(asking)]
    rows += [row(f, case, report.policy_id, run_meta) for f in report.no_money]
    return Board(rows, sum(r.level == LEVEL_HIGH for r in rows), sum(r.level == LEVEL_CHECK for r in rows),
                 sum(r.level == LEVEL_OK for r in rows))


def service_span(case: Case) -> str:
    from billradar.checks import hospital_bills
    docs = ([d for d in hospital_bills(case) if d.service_from] or [d for d in case.bills() if d.service_from]
            or [d for d in case.documents if d.service_from])  # the stay itself, not a doctor's later visit
    starts = [d.service_from for d in docs]
    ends = [d.service_to or d.service_from for d in docs]
    if not starts:
        return ""
    a, b = min(starts), max(ends)
    if a == b:
        return f"{a:%b %-d, %Y}"
    if a.year == b.year and a.month == b.month:
        return f"{a:%b %-d}–{b:%-d, %Y}"
    return f"{a:%b %-d, %Y} – {b:%b %-d, %Y}"


# ---- static pages: which model does what, and how far along it is (keep in step with the code) ----

READY, PLANNED = "in the app", "planned"


@dataclass
class ModelStatus:
    model: str
    does: str
    status: str


MODEL_STATUS = [
    ModelStatus("SAM 3.1", "Finds every sheet on the photo of the table, follows the sheets through a video of it, and "
                "confirms a marked line on the covered sheet.", READY),
    ModelStatus("Muse Spark", "Reads all sheets and files in one go, connects them into one case, answers questions "
                "about it, picks the prepared answer during a call, and fills in the online appeal form on a copy of the insurer's "
                "portal; you press Send yourself.", READY),
    ModelStatus("Muse Wonder", "Takes a second, read-only look at the findings and letters.", READY),
    ModelStatus("Muse Voice Transcribe", "Listens during a call with both sides' consent, and takes spoken questions "
                "and notes, in English or Spanish.", READY),
    ModelStatus("Muse Image", "Draws the case as one picture; the numbers on it are written by code.", READY),
]


def model_status() -> list[ModelStatus]:
    return MODEL_STATUS


@dataclass
class HomeStep:
    title: str
    model: str


def steps_static() -> list[HomeStep]:
    from billradar import providers
    m = providers.labels()
    return [HomeStep("Find every sheet", m["find"]), HomeStep("Hide names", "On your computer"),
            HomeStep("Read and connect", m["read"]), HomeStep("Check quotes and amounts", "Code checker"),
            HomeStep("Letters and forms", "You sign")]


def source_chip(ref: str) -> Chip:
    """A small label for one source: the hospital policy page, the plan document page, or the rule's name."""
    from billradar import plans, writer
    src = writer.source_of(ref)
    if plans.is_ref(ref):
        return Chip(f"Plan document p.{src['page']}", "policy", title=src["quote"])
    if not writer.paged(ref) or ref.startswith("federal"):
        return Chip(src["title"].split(",")[0], "policy", title=src["quote"])
    return Chip(f"Policy p.{src['page']}", "policy", title=src["quote"])


@dataclass
class AppealPanel:
    plan: str
    denial_date: str
    deadline: str
    days: int | None
    passed: bool = False


def appeal_panel(case: Case, letter) -> AppealPanel | None:
    """The right-hand panel on an appeal letter: when the plan denied it and the last day to appeal."""
    from billradar import appeal, plans
    if not letter.kind.startswith("appeal-"):
        return None
    for d in appeal.denials(case):
        if appeal.letter_kind(d) == letter.kind:
            dl = appeal.deadline(plans.load(d.plan_id), d)
            return AppealPanel(plans.load(d.plan_id).title, f"{d.denial_date:%b %-d, %Y}" if d.denial_date else "",
                               f"{dl.day:%b %-d, %Y}" if dl else "", (dl.day - d.denial_date).days if dl and d.denial_date else None,
                               bool(dl and days.passed(dl.day, case.today)))
    return None


LETTER_NAMES = {"itemized": "Request for itemized bill", "apply-discount": "Apply the discount to the baby's bill",
                "application": "Financial assistance application", "dispute": "Fix an amount on the bill"}


def letter_name(kind: str) -> str:
    return "Insurance appeal" if kind.startswith("appeal-") else LETTER_NAMES.get(kind, kind.replace("-", " ").capitalize())


def mark_quotes(text: str):
    """Quoted words (“…”) highlighted, everything else escaped: the quote is what the source says."""
    import re

    from markupsafe import Markup, escape
    parts = re.split(r"(“[^”]+”)", text)
    return Markup("".join(f'<span class="quoted">{escape(p)}</span>' if p.startswith("“") else str(escape(p))
                          for p in parts))


@dataclass
class ReceiptRow:
    step: str
    model: str
    calls: int
    tokens: int
    usd: float
    seconds: float | None  # None for a replay: the recording keeps the cost, not the time it took


def receipt_rows(receipt: dict | None) -> list[ReceiptRow]:
    """The case receipt grouped by step and model, in the order the steps ran."""
    if not receipt:
        return []
    out: dict[tuple[str, str], ReceiptRow] = {}
    for r in receipt["rows"]:
        k = (r["step"], r["model"])
        row = out.setdefault(k, ReceiptRow(r["step"], _model_name(r["model"]), 0, 0, 0.0, 0.0 if r["live"] else None))
        row.calls += 1
        row.tokens += r["input_tokens"] + r["output_tokens"]
        row.usd += r["usd"]
        if row.seconds is not None:
            row.seconds += r["seconds"]
    return list(out.values())


def _model_name(model_id: str) -> str:
    from billradar import providers
    return providers._short(model_id)


STORY_CARDS = {"E2": "Billed twice", "B1": "Baby on mom's insurance", "F1": "Financial help you qualify for",
               "E1": "More than insurance says", "E3": "A credit left on the account", "F3": "Discount on mom, not on baby"}


STORY_STAGE = 1.44, 44, 8  # episode 1: stage width/height, photo card width and top in % of the stage


def story_found(found: dict, sheet_url) -> dict:
    """Episode 1 and 2 from scripts/story_assets.py: the photo card with the boxes SAM 3.1 drew, each sheet starting
    where its box is, and the request text the second read got, with its tokens marked."""
    import re as _re
    ar, card_w, card_top = STORY_STAGE
    w, h = found["photo"]["width"], found["photo"]["height"]
    card_h = card_w * ar * h / w
    sheets = [{"sheet": b["sheet"], "src": sheet_url(b["sheet"]), "n": i,
               "x0": round(card_w * b["box"][0] / w, 2), "y0": round(card_top + card_h * b["box"][1] / h, 2),
               "w0": round(card_w * (b["box"][2] - b["box"][0]) / w, 2), "box": b["box"]}
              for i, b in enumerate(found["boxes"], start=1)]
    parts = [(t, bool(_re.fullmatch(r"\[?[A-Z]+_\d+\]?", t)))
             for t in _re.split(r"(\[[A-Z]+_\d+\]|\b(?:PATIENT|MEMBER)_\d+\b)", found["sent"]["excerpt"]) if t]
    return {"w": w, "h": h, "card_w": card_w, "card_top": card_top, "card_h": round(card_h, 2), "ar": ar,
            "sheets": sheets, "find_model": found["find_model"], "find_recording": found["find_recording"],
            "sent_model": found["sent"]["model"], "sent_recording": found["sent"]["recording"], "sent_parts": parts}


def story_proof(case: Case, report) -> dict:
    """The episodes' proof, from the report: the sheets a finding stands on, its own title, the policy's own words."""
    from billradar import writer
    known = report.findings + report.no_money
    first = lambda kind: next((f for f in known if f.kind.value == kind), None)  # noqa: E731
    sheets = lambda f: list(dict.fromkeys(e.doc_id for e in f.evidence)) if f else []  # noqa: E731
    out: dict = {"sheet_ids": [d.doc_id for d in case.documents if d.source == Source.PAPER]}
    if sheets(first("B1")) and sheets(first("B2")):
        out["link"] = {"a": {"sheet": sheets(first("B1"))[0], "box": None}, "b": {"sheet": sheets(first("B2"))[0], "box": None},
                       "label": first("B1").title}
    out["review"] = [{"title": f.title, "sheets": sheets(f), "verdict": "confirmed"}
                     for f in (first(k) for k in ("E2", "B1", "F1")) if f]
    out["review"] += [{"title": f.title, "sheets": sheets(f), "verdict": "worth"} for f in report.worth_asking[:1]]
    f1 = first("F1")
    plain = [s for s in map(writer.source_of, f1.policy_refs if f1 else []) if "Memorial" not in s["quote"] and s["quote"].rstrip().endswith(".")]
    if plain:  # a whole sentence, without the real hospital's name beside the fictional one on screen
        out["quote"] = {"text": plain[0]["quote"], "title": plain[0]["title"], "url": plain[0]["url"]}
    return out


def story(case: Case, report, letter, sheet_urls: list[str]) -> dict:
    """What the scroll story on the home page shows: the example case's own names, numbers and letter."""
    import re as _re
    tokens = case.profile.local.tokens
    mother = next((p.name for p in case.profile.people if p.role.value == "mother" and p.name), "")
    clean = lambda s: _re.sub(r"\s+", " ", _re.sub(r"\[[A-Z_0-9]+\]", "", s or "")).strip()
    lines = []
    for doc in case.bills():
        rows = [(clean(ln.description).title(), ln.charges) for ln in doc.lines if ln.charges and clean(ln.description)]
        if len(rows) >= 4:
            lines = [(d[:34], money(c)) for d, c in rows[:5]]
            break
    present = {f.kind.value for f in report.findings}
    icons = {"B1": "baby", "F1": "coin", "F3": "baby"}
    kinds = [{"label": STORY_CARDS[k], "icon": icons.get(k, "docs")}
             for k in ("E2", "B1", "F1", "E1", "E3", "F3") if k in present]  # the frames' order first
    body = " ".join(p.text for p in letter.paragraphs[:2]) if letter else ""
    head, sep, rest = body.partition(": ")
    if sep and "; " in rest:  # a long list of accounts: the two the story shows (mother's and baby's bill), as lines
        items, _, tail = rest.partition(". ")
        items = items.split("; ")
        shown = [i for i in items if any(v and v in i for v in (tokens.get("ACCT_1"), tokens.get("ACCT_2")))] or [items[0], items[-1]]
        more = len(items) - len(shown)
        body = head + ":\n· " + "\n· ".join(shown) + (f"\n· and {more} more account{'s' if more != 1 else ''}" if more else "") + ("\n" + tail if tail else "")
    return {"hospital": case.letterhead, "patient": mother, "member": tokens.get("MEMBER_1", ""),
            "account": tokens.get("ACCT_1", ""), "address": tokens.get("ADDR_1", ""), "lines": lines,
            "amount": int(report.total_may_come_off), "cards": kinds[:3], "sheets": sheet_urls[:5],
            "letter_to": letter.to if letter else "", "letter_subject": letter.subject if letter else "",
            "letter_body": body, "signer": mother, **story_proof(case, report)}
