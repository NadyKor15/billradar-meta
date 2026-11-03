"""The letters a family reads and signs itself: itemized statement, discount on a second bill, billing dispute,
financial assistance application, insurance appeal.

Code writes them from the case and the findings; no model takes part. Amounts come from the case or from a finding's
math, and a rule stands only on a quote that verifies: a paragraph with any unverified quote leaves the letter and is
listed in `dropped`. What the case does not hold stays a blank to fill, never a token or a guess.

The text also travels in recorded model requests, so changing a word here means a recording no longer replays.
"""

from __future__ import annotations

import re

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from billradar import appeal as appeals
from billradar import days, fpl, plans, policy
from billradar.case import Case, DocKind, Document, Role
from billradar.checks import Kind, Report, hospital_bills, is_hospital_bill


@dataclass
class Paragraph:
    text: str
    refs: list[str] = field(default_factory=list)


@dataclass
class Letter:
    kind: str
    button: str
    to: str
    subject: str
    paragraphs: list[Paragraph]
    attachments: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)  # paragraphs removed because a quote did not verify
    office: str = ""  # who the letter greets, when `to` is a full address
    rows: dict[str, str] = field(default_factory=dict)  # ref -> the row of a table that its quote prints flat

    @property
    def refs(self) -> list[str]:
        return [r for p in self.paragraphs for r in p.refs]


def _money(x) -> str:
    return f"${x:,.2f}"


def _a(number: int) -> str:
    """The article before a percent, by how it is said: "an 85%", "a 90%"."""
    return "an" if number in (11, 18) or str(number).startswith("8") else "a"


def _date(d: date | None) -> str:
    return f"{d:%B} {d.day}, {d.year:04d}" if d else ""


def _account(case: Case, doc: Document) -> str:
    return appeals.token_value(case, doc.account_ref, "[account number]")


def _name(case: Case, token: str, fallback: str) -> str:
    return appeals.person_name(case, token, fallback)


def _mother(case: Case) -> str:
    return next((p.name for p in case.profile.people if p.role == Role.MOTHER), "") or "[your name]"


def _billing_office(case: Case) -> str:
    return ", ".join(filter(None, ("Patient Financial Services", case.letterhead)))


def policy_name(pol, version: bool = True) -> str:
    """The policy as a letter names it: no revision month ("Revised May 2026") that a dated letter could contradict.
    `version`: say it is the current public version (under a quote); the letter's own sentence just names it."""
    name = re.sub(r",?\s*\b[Rr]evised\b.*$", "", pol.title).strip()
    return f"{name} (current public version)" if name != pol.title and version else name


def demo_rules(case: Case, letter: "Letter | None" = None) -> str:
    """Whose rules a sample case uses, under anything built on them. An appeal to the plan rests on the plan's document."""
    if not (case.demo and case.policy_id.startswith("memorial")) or (letter and letter.kind.startswith("appeal")):
        return ""
    return ("Rules: the public Financial Assistance Policy and form of Memorial Regional Hospital (FL; MHS = Memorial "
            f"Healthcare System), applied to the fictional {case.letterhead or 'sample'} case.")


def verified(ref: str) -> bool:
    """A quote from a hospital policy, a law, or the family's insurance plan document."""
    if plans.is_ref(ref):
        return plans.verified(ref)
    try:
        return policy.verified(ref)
    except (FileNotFoundError, KeyError, ValueError):  # a law id not in the base yet
        return False


def _finalize(letter: Letter) -> Letter:
    """The last gate of a letter. All quotes are judged first, so a failing check leaves the letter as it was."""
    judged = [(p, [ref for ref in p.refs if not verified(ref)]) for p in letter.paragraphs]
    letter.dropped += [f"{p.text[:60]}... (unverified {', '.join(bad)})" for p, bad in judged if bad]
    letter.paragraphs = [p for p, bad in judged if not bad]
    return letter


def _services(start: date | None, end: date | None) -> str:
    """'services from March 4, 2030 to March 6, 2030', 'services on March 4, 2030', or nothing when no date was read."""
    if start and end and start != end:
        return f"services from {_date(start)} to {_date(end)}"
    return f"services on {_date(start or end)}" if (start or end) else ""


def _accounts_to_itemize(case: Case) -> list[str]:
    """One entry per person and account as printed: two accounts that are both a blank are one entry, there is nothing
    to tell them apart with. The doctors' bills count only when the hospital has no bill at all."""
    span: dict[tuple[str, str], list[date | None]] = {}  # (person, account) -> [earliest, latest]
    for bill in hospital_bills(case) or case.bills():
        if not bill.patient_balance:
            continue
        who = _name(case, bill.patient, "the patient")
        account = _account(case, bill) if bill.account_ref.strip() else ""
        ends = span.setdefault((who, account), [None, None])
        for day in filter(None, (bill.service_from, bill.service_to)):
            if ends[0] is None or day < ends[0]:
                ends[0] = day
            if ends[1] is None or day > ends[1]:
                ends[1] = day
    entries = []
    for (who, account), (first, last) in span.items():
        if account or first:
            entries.append(", ".join(filter(None, (who, account and f"account {account}", _services(first, last)))))
    return entries


def itemized_bill(case: Case) -> Letter:
    accounts = "; ".join(_accounts_to_itemize(case))
    return _finalize(Letter(
        kind="itemized", button="Letter: request itemized bill", to=_billing_office(case),
        subject="Request for an itemized statement",
        paragraphs=[
            Paragraph(f"I am asking for an itemized statement for each of these accounts: {accounts}."),
            Paragraph("Florida law says the hospital must provide it after discharge upon request, within 7 days of my "
                      "request (Florida Statutes 395.301(1)(e)).",
                      ["fl-395-301#itemized-on-request", "fl-395-301#itemized-7-days"]),
            Paragraph("Please send it to the address below. Thank you."),
        ]))


def _child(case: Case, bill: Document) -> str:
    return _name(case, bill.patient, "my child")


def apply_discount(case: Case, report: Report) -> Letter | None:
    missed = [f for f in report.findings if f.kind == Kind.F3]
    if not missed:
        return None
    pol = policy.load(case.policy_id)
    discounted = case.doc(missed[0].evidence[0].doc_id)
    full_price = [case.doc(f.evidence[1].doc_id) for f in missed]

    story = [f"Financial assistance was applied to account {_account(case, discounted)} for my hospital stay "
             f"({_date(discounted.service_from)} to {_date(discounted.service_to)})."]
    story += [f"The account for {_child(case, b)}, {_account(case, b)}, is from the same stay and still shows the full "
              f"balance of {_money(b.patient_balance)}." for b in full_price]
    those = "those accounts" if len(full_price) > 1 else "that account"
    quotes = [pol.fragments[part].ref for part in ("insured-balances", "prior-accounts") if part in pol.fragments]
    return _finalize(Letter(
        kind="apply-discount", button=f"Letter: apply discount to {_child(case, full_price[0])}'s bill",
        to=_billing_office(case),
        subject="Apply financial assistance to account " + " and ".join(_account(case, b) for b in full_price),
        paragraphs=[
            Paragraph(" ".join(story)),
            Paragraph(f"Please apply the same financial assistance to {those}. Your Financial Assistance Policy covers "
                      "balances left after insurance payment and says the hospital will also consider accounts from the "
                      "prior twelve months.", quotes),
            Paragraph("Please send me a corrected statement. Thank you."),
        ]))


def _window_paragraphs(case: Case, report: Report) -> list[Paragraph]:
    """The application period. Only the first window finding counts: without a date there is nothing to say."""
    window = next((f for f in report.findings if f.kind == Kind.F2), None)
    if window is None or not window.deadline:
        return []
    last_day = _date(window.deadline)
    if days.passed(window.deadline, case.today):
        text = f"The application period ended on {last_day}. I am asking you to accept this late application."
    else:
        text = f"I am applying before {last_day}, within the application period."
    return [Paragraph(text, list(window.policy_refs))]


def application(case: Case, report: Report) -> Letter | None:
    if not any(f.kind in (Kind.F1, Kind.F3) for f in report.findings):
        return None
    pol = policy.load(case.policy_id)
    tier = pol.tier_for(report.fpl_pct)
    if tier is None:
        return None
    scale = f"{pol.policy_id}#{tier.fragment}"
    row = _table_row(source_of(scale)["quote"], tier)
    household, income = case.profile.household_size, _money(case.profile.annual_income)
    return _finalize(Letter(
        kind="application", button="Financial assistance form · ready to sign", to=_billing_office(case),
        subject="Application for financial assistance",
        paragraphs=[
            Paragraph(f"I am applying for financial assistance. My household has {household} people and our yearly income "
                      f"is {income}, which is {report.fpl_pct}% of the {pol.fpg_year or fpl.latest_year()} federal poverty "
                      "guidelines."),
            Paragraph(f"Your {policy_name(pol, version=False)} lists {_a(tier.discount_pct)} {tier.discount_pct}% discount "
                      "at this income level.", [scale]),
            *_window_paragraphs(case, report),
            Paragraph("The completed Financial Evaluation Form and the documents it lists are attached."),
        ],
        attachments=["Financial Evaluation Form", "Documents listed in Table C of the form"],
        rows={scale: row} if row else {}))


def _sender_of(case: Case, f) -> str | None:
    """Whose bill a finding is about: None for the hospital, the office's name for a doctors' group (which can come out
    as an empty text when the sender's name is only a file prefix or a ward code)."""
    from billradar.callprep import provider_name
    bill = case.doc(f.evidence[0].doc_id)
    return None if is_hospital_bill(case, bill) or not bill.provider else provider_name(bill.provider)


def _office_of(case: Case, f) -> str:
    """Whose bill a finding is about: "" for the hospital, the office's name for a doctors' group."""
    return _sender_of(case, f) or ""


def disputes(case: Case, report: Report) -> list[Letter]:
    """One letter for each office: a hospital cannot correct a doctors' group's bill, and its grievance law binds only it."""
    found = [f for f in report.findings if f.kind in (Kind.E2, Kind.E1)]
    offices = list(dict.fromkeys(_office_of(case, f) for f in found))
    letters = []
    for i, office in enumerate(offices):
        mine = [f for f in found if _office_of(case, f) == office]
        kind = "dispute" if i == 0 else f"dispute-{mine[0].evidence[0].doc_id.lower()}"
        letters.append(_dispute(case, [f for f in mine if f.kind == Kind.E1], [f for f in mine if f.kind == Kind.E2], kind))
    return letters


def dispute(case: Case, report: Report) -> Letter | None:
    return next(iter(disputes(case, report)), None)


def _double_paragraph(case: Case, found) -> Paragraph:
    """One service billed twice. Both lines are on the sheet of the first evidence."""
    first, second = found.evidence[:2]
    math = found.math
    if not found.amount:
        ending = "Please remove the duplicate and the charge to me for it."
    elif math.get("amount_from"):
        ending = f"Please remove the duplicate and my {_money(found.amount)} share of it, as my insurance statement shows."
    else:
        ending = f"Please remove the duplicate and my {_money(found.amount)} share of it."
    return Paragraph(
        f"My statement for account {_account(case, case.doc(first.doc_id))} lists the same service twice: "
        f"lines {first.line_no} and {second.line_no}, code {math['code']}, "
        f"on {_date(date.fromisoformat(math['service_date']))}, {_money(Decimal(math['charges']))} each. {ending}")


def _overcharge_paragraph(case: Case, found) -> Paragraph:
    """A bill line that asks for more than the insurance statement leaves. What it asks is read from the line itself."""
    where = found.evidence[0]
    sheet = case.doc(where.doc_id)
    line = next(ln for ln in sheet.lines if ln.line_no == where.line_no)
    code = f" (code {line.code})" if line.code else ""
    claim = f" for claim {line.claim_ref}" if line.claim_ref else ""
    return Paragraph(
        f"Line {where.line_no} of my statement for account {_account(case, sheet)} asks "
        f"{_money(line.patient_responsibility)} for {line.description or 'a service'}{code} on {_date(line.service_date)}. "
        f"My insurance Explanation of Benefits{claim} shows my patient responsibility for it as "
        f"{_money(Decimal(found.math['eob_patient_responsibility']))}, "
        f"a difference of {_money(Decimal(found.math['difference']))}.")


def _dispute(case: Case, e1: list, e2: list, kind: str) -> Letter:
    sender = _sender_of(case, (e2 or e1)[0])
    if e1:
        ask = "Please correct the balance to match my insurance, or explain the difference in writing."
    else:
        ask = "Please correct the balance, or explain it in writing."
    if sender is None:
        to = _billing_office(case)
        closing = Paragraph(f"{ask} Florida law requires the hospital to give a first response to a billing dispute within "
                            "7 business days (Florida Statutes 395.301(6)).", ["fl-395-301#grievance-7-days"])
    else:  # the grievance law binds the hospital, not a doctors' group
        to = f"Billing office, {sender}"
        closing = Paragraph(f"{ask} Please answer in writing within 30 days.")
    wrong = "amount does not match my insurance" if e1 else "the same service billed twice"
    return _finalize(Letter(
        kind=kind, button="Letter: fix the amount from your insurance statement", to=to,
        subject=f"Billing dispute: {wrong}",
        paragraphs=[*[_double_paragraph(case, f) for f in e2], *[_overcharge_paragraph(case, f) for f in e1], closing],
        attachments=["Copy of the Explanation of Benefits"]))


NOT_ALL_PAPERS = "I am still gathering one of my papers, so any amounts here may change once it is included."


def all_letters(case: Case, report: Report) -> list[Letter]:
    letters = [itemized_bill(case), apply_discount(case, report), *disputes(case, report), application(case, report)]
    letters = [x for x in letters if x is not None]
    if report.not_sent:  # an honest letter says what it was written without
        for x in letters:
            x.paragraphs.append(Paragraph(NOT_ALL_PAPERS))
    return letters


def signature(case: Case) -> list[str]:
    local = case.profile.local
    place = " ".join(filter(None, (local.state, local.zip)))
    return list(filter(None, (_mother(case), local.street, ", ".join(filter(None, (local.city, place))), local.phone)))


# --- insurance appeal ----------------------------------------------------------------------

def _plan_quote(plan: plans.Plan, fragment_id: str) -> tuple[str, int]:
    frag = plan.fragment(fragment_id)
    return frag.quote, frag.page


def _grounds_for(case: Case, plan: plans.Plan, denial: appeals.Denial) -> list[plans.Ground]:
    """What this case can argue, one ground per quote: a repeated quote keeps its first place and its last words."""
    people = case.profile.people
    birth = "birth" in case.profile.context or any(p.role == Role.NEWBORN for p in people)
    by_quote: dict[str, plans.Ground] = {}
    for code in denial.codes:
        for ground in plan.grounds.get(code, []):
            if birth or ground.needs != "birth":
                by_quote[ground.fragment] = ground
    return list(by_quote.values())


def _period(denial: appeals.Denial) -> str:
    """The dates of care. A missing start stays empty: the letter does not guess it."""
    start, end = denial.service_from, denial.service_to
    return f"{_date(start)} to {_date(end)}" if end and end != start else _date(start)


def _code_paragraph(plan: plans.Plan, code: str, opening: str) -> Paragraph:
    legend = plan.code_fragment(code)
    meaning = legend.quote.removeprefix(code).strip()
    return Paragraph(f"{opening} with remark code {code}: “{meaning}”", [legend.ref])


def _ground_paragraph(plan: plans.Plan, ground: plans.Ground) -> Paragraph:
    quote, page = _plan_quote(plan, ground.fragment)
    return Paragraph(f"{ground.say} My plan document says (page {page}): “{quote}”", [plan.ref(ground.fragment)])


def _deadline_paragraphs(case: Case, plan: plans.Plan, denial: appeals.Denial) -> list[Paragraph]:
    due = appeals.deadline(plan, denial)
    if due is None:
        return []
    if days.passed(due.day, case.today):
        timing = (f"The time the plan allows after a denial ended on {_date(due.day)}. "
                  "I am asking you to review this late appeal.")
    else:
        timing = f"I am sending this appeal before {_date(due.day)}, within the time the plan allows after a denial."
    copies = "Please also send me free copies of all documents, records and other information relevant to my claim."
    return [Paragraph(f"{timing} {copies}", [*due.refs, plan.ref("copies-free")])]


def appeal(case: Case, plan: plans.Plan, denial: appeals.Denial) -> Letter | None:
    grounds = _grounds_for(case, plan, denial)
    if not grounds:
        return None
    claim = f"claim {denial.claim_ref}" if denial.claim_ref else "the claim"
    statement = "Explanation of Benefits" + (f" dated {_date(denial.denial_date)}" if denial.denial_date else "")
    opening = (f"I am appealing the denial of {claim} for {_name(case, denial.patient, 'the patient')} "
               f"({denial.description or 'hospital care'}, {_period(denial)}). Your {statement} denies it")

    paragraphs = [_code_paragraph(plan, code, opening) for code in denial.codes]
    paragraphs += [_ground_paragraph(plan, ground) for ground in grounds]
    if denial.patient_responsibility:
        paragraphs.append(Paragraph(f"Your Explanation of Benefits leaves {_money(denial.patient_responsibility)} for me to "
                                    "pay on this claim. Please review the claim and process it as a covered service under "
                                    "my plan."))
    paragraphs += _deadline_paragraphs(case, plan, denial)
    if plan.plan_type == "employer":
        paragraphs.append(Paragraph("Federal rules for employer health plans give at least 180 days to appeal a denied "
                                    "claim (29 CFR 2560.503-1(h)(3)(i)).", [appeals.FEDERAL_APPEAL_REF]))
    paragraphs.append(Paragraph("Please send your decision in writing to the address below. Thank you."))

    member = appeals.token_value(case, denial.member_ref, "")
    has_itemized = any(d.kind == DocKind.ITEMIZED_BILL for d in case.documents)
    return _finalize(Letter(
        kind=appeals.letter_kind(denial), button=f"Appeal to {plan.insurer}", to=", ".join(plan.appeals_to),
        subject=f"Appeal of denied {claim}" + (f", member ID {member}" if member else ""),
        paragraphs=paragraphs, office=f"{plan.insurer} appeals",
        attachments=[statement, *(["Itemized hospital bill"] if has_itemized else []), "Member appeal form"]))


def appeal_letters(case: Case) -> list[Letter]:
    out = []
    for d in appeals.denials(case):
        letter = appeal(case, plans.load(d.plan_id), d)
        if letter:
            out.append(letter)
    return out


# --- for the screens: where each quote comes from, and the letter as plain text ------------

def paged(ref: str) -> bool:
    """Statutes and regulations read from a web page have no page numbers worth printing."""
    from billradar.policies import source
    pid = ref.split("#", 1)[0]
    return plans.is_ref(ref) or pid not in source.SOURCES or source.SOURCES[pid].kind == "pdf"


def source_of(ref: str) -> dict:
    """Title, page, quote and link of one source: a hospital policy, a law, or the family's plan document."""
    if plans.is_ref(ref):
        frag = plans.resolve(ref)
        return {"ref": ref, "title": plans.load(frag.plan_id).title, "page": frag.page, "quote": frag.quote, "url": ""}
    pid, fid = ref.split("#", 1)
    pol = policy.load(pid)
    frag = pol.fragment(fid)
    return {"ref": ref, "title": policy_name(pol), "page": frag.page, "quote": frag.quote, "url": pol.url}


def sources(letter: Letter) -> list[dict]:
    """Every source a letter leans on, in order, each once."""
    found = [source_of(ref) for ref in dict.fromkeys(letter.refs)]
    return [s | {"quote": letter.rows[s["ref"]]} if s["ref"] in letter.rows else s for s in found]


def _table_row(quote: str, tier) -> str | None:
    """The family's row of a table the policy's quote prints flat, word for word: "251% - 300% of FPG 85% Discount"."""
    m = re.search(rf"(?:\d+%\s*-\s*|Up to\s+){tier.max_fpl_pct}% of FPG\s+{tier.discount_pct}% Discount", quote)
    return m.group() if m else None


def greeting(letter: Letter) -> str:
    """Dear <the office the letter is addressed to>, not always the hospital's."""
    if letter.office:
        return f"Dear {letter.office} team,"
    office = letter.to.split(",")[0].strip() or "Billing office"
    return f"Dear {office} team," if office.startswith("Patient Financial") else f"Dear {letter.to.split(', ', 1)[-1]} billing team,"


def plain_text(letter: Letter, case: Case) -> str:
    """What "Copy" puts on the clipboard and "Save" writes to a .txt file."""
    parts = [_date(case.today), "", letter.to, "", f"Subject: {letter.subject}", "", greeting(letter), ""]
    parts += [p.text + "\n" for p in letter.paragraphs]
    if letter.attachments:
        parts += ["Attached: " + "; ".join(letter.attachments), ""]
    parts += ["Sincerely,", ""] + signature(case)
    if case.demo:
        parts = ["SAMPLE - FICTIONAL DATA", ""] + parts
    return "\n".join(parts).rstrip() + "\n"
