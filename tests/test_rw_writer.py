"""Current behaviour of billradar/writer.py: the words, numbers, refs and shape of every letter the family signs.

Everything here is made up: a fictional family, a fictional hospital and the SAMPLE plan. Expected texts are written out
in full on purpose: letters go into recorded model requests, so one changed word means a recording no longer replays.
"""

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from billradar import fpl, plans, policy, writer
from billradar.case import Case, DocKind, Document, Line, LocalDetails, Person, Profile, Role, Source
from billradar.checks import Evidence, Finding, Kind, Report
from billradar.policies import source
from billradar.appeal import Denial
from billradar.plans import Fragment as PlanFragment
from billradar.plans import Ground
from billradar.writer import Letter, Paragraph

pytestmark = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES),
                                reason="policy text not downloaded: run scripts/fetch_policies.py")

MEMORIAL = "memorial-2026-05"
BAPTIST = "baptist-2026-09"
PLAN = "sample-health-plan-2026"
HOSPITAL = "Harbor Demo Hospital"
DOCTORS = "Women First OB/GYN"
OFFICE = f"Patient Financial Services, {HOSPITAL}"
TODAY = date(2030, 6, 1)
START = date(2030, 3, 4)
END = date(2030, 3, 6)

MOTHER = Person(token="PATIENT_1", role=Role.MOTHER, name="Rosa Example")
BABY = Person(token="PATIENT_2", role=Role.NEWBORN, name="Theo Example")
TWIN = Person(token="PATIENT_3", role=Role.NEWBORN, name="Mia Example")
TOKENS = {"ACCT_1": "HDH-1001", "ACCT_2": "HDH-1002", "ACCT_3": "HDH-1003", "MEMBER_1": "SHP-77"}

ITEMIZED_LAW = ("Florida law says the hospital must provide it after discharge upon request, within 7 days "
                "of my request (Florida Statutes 395.301(1)(e)).")
GRIEVANCE = (" Florida law requires the hospital to give a first response to a billing dispute within 7 business days "
             "(Florida Statutes 395.301(6)).")


def family(*documents, letterhead=HOSPITAL, policy_id=MEMORIAL, today=TODAY, people=(MOTHER, BABY), tokens=TOKENS,
           household=4, income="52000.00", context=(), demo=False, **local) -> Case:
    profile = Profile(household_size=household, annual_income=Decimal(income), people=list(people),
                      local=LocalDetails(tokens=dict(tokens), **local), context=list(context))
    return Case(case_id="rw", letterhead=letterhead, policy_id=policy_id, today=today, demo=demo, profile=profile,
                documents=list(documents))


def bill(doc_id="S1", account="[ACCT_1]", patient="PATIENT_1", provider=HOSPITAL, balance="300.00", start=START, end=END,
         kind=DocKind.HOSPITAL_STATEMENT, lines=()) -> Document:
    return Document(doc_id=doc_id, source=Source.PAPER, kind=kind, patient=patient, provider=provider, account_ref=account,
                    patient_balance=None if balance is None else Decimal(balance), service_from=start, service_to=end,
                    lines=list(lines))


def finding(kind, *evidence, **fields) -> Finding:
    return Finding(kind=kind, title="title", detail="detail", evidence=list(evidence), **fields)


def report(*findings, fpl_pct="230.5", worth_asking=()) -> Report:
    return Report(case_id="rw", policy_id=MEMORIAL, fpl_pct=Decimal(fpl_pct), findings=list(findings), no_money=[],
                  held_back=[], total_may_come_off=Decimal(0), apply_by=None, worth_asking=list(worth_asking))


def facts(letter: Letter) -> dict:
    return {"kind": letter.kind, "button": letter.button, "to": letter.to, "subject": letter.subject,
            "paragraphs": [(p.text, p.refs) for p in letter.paragraphs], "attachments": letter.attachments,
            "dropped": letter.dropped, "office": letter.office, "rows": letter.rows}


def texts(letter: Letter) -> list[str]:
    return [p.text for p in letter.paragraphs]


def only_refused(monkeypatch, *refs: str) -> None:
    real = writer.verified
    monkeypatch.setattr(writer, "verified", lambda ref: ref not in refs and real(ref))


# --- _money ----------------------------------------------------------------------------------

@pytest.mark.parametrize("value, printed", [
    (Decimal("0"), "$0.00"),
    (Decimal("0.50"), "$0.50"),
    (Decimal("1234.5"), "$1,234.50"),
    (Decimal("999.99"), "$999.99"),
    (Decimal("1000"), "$1,000.00"),
    (Decimal("999999.99"), "$999,999.99"),
    (Decimal("1000000.00"), "$1,000,000.00"),
    (Decimal("1E+3"), "$1,000.00"),
    (7, "$7.00"),
])
def test_money_is_dollars_with_thousands_commas_and_two_places(value, printed):
    assert writer._money(value) == printed


@pytest.mark.parametrize("value, printed", [
    (Decimal("-1234.50"), "$-1,234.50"),
    (Decimal("-0.01"), "$-0.01"),
    (Decimal("-0.001"), "$-0.00"),
])
def test_money_prints_a_minus_after_the_dollar_sign(value, printed):
    assert writer._money(value) == printed


@pytest.mark.parametrize("value, printed", [
    (Decimal("2.345"), "$2.34"),
    (Decimal("2.355"), "$2.36"),
    (Decimal("0.005"), "$0.00"),
    (Decimal("0.015"), "$0.02"),
])
def test_money_rounds_a_third_decimal_half_to_even(value, printed):
    assert writer._money(value) == printed


def test_money_of_a_float_rounds_its_binary_value():
    assert writer._money(2.675) == "$2.67"


@pytest.mark.parametrize("value, error", [(None, TypeError), ("12.00", ValueError)])
def test_money_refuses_what_is_not_a_number(value, error):
    with pytest.raises(error):
        writer._money(value)


# --- _a --------------------------------------------------------------------------------------

@pytest.mark.parametrize("number", [8, 11, 18, 80, 81, 83, 85, 89, 800, 8000, 85.5, 11.0])
def test_article_is_an_for_numbers_said_with_a_vowel(number):
    assert writer._a(number) == "an"


@pytest.mark.parametrize("number", [0, 1, 7, 9, 10, 12, 17, 19, 20, 50, 79, 90, 100, 110, 118, 180, 1100, -8])
def test_article_is_a_for_every_other_number(number):
    assert writer._a(number) == "a"


# --- _date -----------------------------------------------------------------------------------

@pytest.mark.parametrize("day, printed", [
    (date(2030, 3, 4), "March 4, 2030"),
    (date(2030, 1, 1), "January 1, 2030"),
    (date(2030, 12, 31), "December 31, 2030"),
    (date(2028, 2, 29), "February 29, 2028"),
    (date(2025, 9, 10), "September 10, 2025"),
    (datetime(2030, 3, 4, 23, 59), "March 4, 2030"),
])
def test_date_is_the_month_in_words_and_a_day_without_a_leading_zero(day, printed):
    assert writer._date(day) == printed


@pytest.mark.parametrize("day, printed", [
    (date(225, 3, 4), "March 4, 0225"),
    (date(25, 3, 4), "March 4, 0025"),
    (date(1, 3, 4), "March 4, 0001"),
    (date(999, 12, 31), "December 31, 0999"),
    (date(9999, 1, 2), "January 2, 9999"),
])
def test_date_prints_the_year_as_four_digits_with_zeros_in_front(day, printed):
    assert writer._date(day) == printed


@pytest.mark.parametrize("nothing", [None, ""])
def test_date_of_nothing_is_empty_text(nothing):
    assert writer._date(nothing) == ""


@pytest.mark.parametrize("value", ["2030-03-04", 20300304])
def test_date_refuses_what_is_not_a_date(value):
    with pytest.raises(ValueError):
        writer._date(value)


# --- _account --------------------------------------------------------------------------------

@pytest.mark.parametrize("printed, shown", [
    ("[ACCT_1]", "HDH-1001"),
    ("  [ACCT_2]\t", "HDH-1002"),
    ("[ACCT_404]", "[account number]"),
    ("[]", "[account number]"),
    ("[ ACCT_1 ]", "[account number]"),
    ("LDH-77", "LDH-77"),
    ("  LDH-77  ", "LDH-77"),
    ("", "[account number]"),
    ("   ", "[account number]"),
    ("[ACCT_1", "[ACCT_1"),
    ("ACCT_1]", "ACCT_1]"),
    ("[ACCT_1] page 2", "[ACCT_1] page 2"),
])
def test_account_turns_a_token_into_its_value_on_this_device(printed, shown):
    c = family()
    assert writer._account(c, bill(account=printed)) == shown


def test_account_with_an_empty_value_on_this_device_stays_empty():
    assert writer._account(family(tokens={"ACCT_1": ""}), bill()) == ""


# --- _mother ---------------------------------------------------------------------------------

def test_mother_is_the_name_of_the_person_with_that_role_wherever_she_is_listed():
    assert writer._mother(family(people=(BABY, MOTHER))) == "Rosa Example"


@pytest.mark.parametrize("people", [
    (),
    (BABY,),
    (Person(token="PATIENT_1", role=Role.PATIENT, name="Rosa Example"),),
    (Person(token="PATIENT_1", role=Role.MOTHER),),
])
def test_mother_without_a_name_is_a_blank_to_fill(people):
    assert writer._mother(family(people=people)) == "[your name]"


def test_only_the_first_mother_counts_even_with_no_name():
    nameless = Person(token="PATIENT_1", role=Role.MOTHER)
    assert writer._mother(family(people=(nameless, MOTHER))) == "[your name]"


# --- _billing_office -------------------------------------------------------------------------

def test_billing_office_names_the_hospital_on_the_letterhead():
    assert writer._billing_office(family()) == OFFICE


def test_billing_office_without_a_letterhead_has_no_comma():
    assert writer._billing_office(family(letterhead="")) == "Patient Financial Services"


# --- _finalize -------------------------------------------------------------------------------

GOOD = "fl-395-301#itemized-7-days"
PLAN_GOOD = f"plan:{PLAN}#copies-free"


def letter_of(*paragraphs, **fields) -> Letter:
    return Letter(kind="k", button="b", to="t", subject="s", paragraphs=list(paragraphs), **fields)


def test_finalize_keeps_a_paragraph_whose_quotes_all_verify_and_one_with_no_quotes():
    first, second, third = Paragraph("One.", [GOOD]), Paragraph("Two."), Paragraph("Three.", [GOOD, PLAN_GOOD])
    letter = letter_of(first, second, third)
    assert writer._finalize(letter) is letter
    assert letter.paragraphs[0] is first and letter.paragraphs[1] is second and letter.paragraphs[2] is third
    assert letter.dropped == []


def test_finalize_drops_a_paragraph_with_any_unverified_quote_and_keeps_the_order_of_the_rest():
    letter = letter_of(Paragraph("One."), Paragraph("Two.", [GOOD, "nope#a"]), Paragraph("Three.", [GOOD]))
    writer._finalize(letter)
    assert texts(letter) == ["One.", "Three."]
    assert letter.dropped == ["Two.... (unverified nope#a)"]


def test_finalize_reports_the_first_sixty_characters_and_only_the_bad_quotes_in_their_order():
    text = "x" * 61
    letter = letter_of(Paragraph(text, ["nope#b", GOOD, "nope#a", "nope#b"]))
    writer._finalize(letter)
    assert letter.paragraphs == []
    assert letter.dropped == ["x" * 60 + "... (unverified nope#b, nope#a, nope#b)"]


def test_finalize_adds_to_what_was_already_dropped():
    letter = letter_of(Paragraph("One.", ["nope#a"]), Paragraph("Two.", ["nope#b"]), dropped=["earlier"])
    writer._finalize(letter)
    assert letter.dropped == ["earlier", "One.... (unverified nope#a)", "Two.... (unverified nope#b)"]


@pytest.mark.parametrize("ref", [f"{MEMORIAL}#no-such-part", f"plan:{PLAN}#no-such-part", f"plan:no-such-plan#x", "no-hash"])
def test_finalize_treats_an_unknown_quote_as_unverified(ref):
    letter = letter_of(Paragraph("One.", [ref]))
    writer._finalize(letter)
    assert letter.paragraphs == [] and letter.dropped == [f"One.... (unverified {ref})"]


def test_finalize_of_a_letter_with_no_paragraphs_changes_nothing():
    letter = letter_of()
    assert writer._finalize(letter).paragraphs == [] and letter.dropped == []


def test_finalize_asks_the_modules_own_quote_check(monkeypatch):
    monkeypatch.setattr(writer, "verified", lambda ref: ref == "yes#1")
    letter = letter_of(Paragraph("One.", ["yes#1"]), Paragraph("Two.", [GOOD]))
    writer._finalize(letter)
    assert texts(letter) == ["One."]


# --- signature -------------------------------------------------------------------------------

@pytest.mark.parametrize("local, lines", [
    ({"street": "12 Bay Road", "city": "Hollywood", "state": "FL", "zip": "33021", "phone": "(555) 010-0100"},
     ["Rosa Example", "12 Bay Road", "Hollywood, FL 33021", "(555) 010-0100"]),
    ({}, ["Rosa Example"]),
    ({"city": "Hollywood"}, ["Rosa Example", "Hollywood"]),
    ({"state": "FL"}, ["Rosa Example", "FL"]),
    ({"zip": "33021"}, ["Rosa Example", "33021"]),
    ({"state": "FL", "zip": "33021"}, ["Rosa Example", "FL 33021"]),
    ({"city": "Hollywood", "state": "FL"}, ["Rosa Example", "Hollywood, FL"]),
    ({"city": "Hollywood", "zip": "33021"}, ["Rosa Example", "Hollywood, 33021"]),
    ({"street": "12 Bay Road", "phone": "(555) 010-0100"}, ["Rosa Example", "12 Bay Road", "(555) 010-0100"]),
])
def test_signature_is_the_mother_and_the_address_lines_that_are_known(local, lines):
    assert writer.signature(family(**local)) == lines


def test_signature_without_a_mother_starts_with_a_blank_to_fill():
    assert writer.signature(family(people=(BABY,), phone="(555) 010-0100")) == ["[your name]", "(555) 010-0100"]


# --- itemized_bill ---------------------------------------------------------------------------

def test_itemized_letter_lists_each_person_and_account_with_their_dates():
    c = family(bill("S1"), bill("S2", account="[ACCT_2]", patient="PATIENT_2", start=date(2030, 3, 5), end=date(2030, 3, 5)))
    assert facts(writer.itemized_bill(c)) == {
        "kind": "itemized", "button": "Letter: request itemized bill", "to": OFFICE,
        "subject": "Request for an itemized statement",
        "paragraphs": [
            ("I am asking for an itemized statement for each of these accounts: Rosa Example, account HDH-1001, services "
             "from March 4, 2030 to March 6, 2030; Theo Example, account HDH-1002, services on March 5, 2030.", []),
            (ITEMIZED_LAW, ["fl-395-301#itemized-on-request", "fl-395-301#itemized-7-days"]),
            ("Please send it to the address below. Thank you.", []),
        ],
        "attachments": [], "dropped": [], "office": "", "rows": {}}


def test_itemized_pages_of_one_account_share_a_line_with_the_widest_dates():
    c = family(bill("S1", start=date(2030, 3, 4), end=date(2030, 3, 6)),
               bill("S2", start=date(2030, 2, 27), end=date(2030, 3, 1)),
               bill("S3", start=None, end=date(2030, 3, 9)))
    assert texts(writer.itemized_bill(c))[0] == ("I am asking for an itemized statement for each of these accounts: "
                                                 "Rosa Example, account HDH-1001, services from February 27, 2030 to March 9, 2030.")


def test_itemized_leaves_out_a_bill_that_asks_for_nothing():
    c = family(bill("S1"), bill("S2", account="[ACCT_2]", balance="0.00"), bill("S3", account="[ACCT_3]", balance=None))
    assert "HDH-1002" not in texts(writer.itemized_bill(c))[0] and "HDH-1003" not in texts(writer.itemized_bill(c))[0]


def test_itemized_counts_a_credit_balance_as_a_bill_to_ask_about():
    assert "HDH-1001" in texts(writer.itemized_bill(family(bill(balance="-40.00"))))[0]


def test_itemized_leaves_out_a_doctors_bill_when_the_hospital_has_one():
    c = family(bill("S1"), bill("S2", account="[ACCT_2]", provider=DOCTORS))
    assert "HDH-1002" not in texts(writer.itemized_bill(c))[0]


def test_itemized_with_no_hospital_bill_writes_about_the_bills_there_are():
    c = family(bill("S1", provider=DOCTORS))
    assert "HDH-1001" in texts(writer.itemized_bill(c))[0]


def test_itemized_does_not_fall_back_to_a_doctor_when_the_hospitals_bill_asks_for_nothing():
    c = family(bill("S1", balance="0.00"), bill("S2", account="[ACCT_2]", provider=DOCTORS))
    assert texts(writer.itemized_bill(c))[0] == "I am asking for an itemized statement for each of these accounts: ."


def test_itemized_with_no_date_gives_the_account_alone():
    c = family(bill(start=None, end=None))
    assert texts(writer.itemized_bill(c))[0].endswith("accounts: Rosa Example, account HDH-1001.")


def test_itemized_with_no_account_gives_the_dates_alone():
    c = family(bill(account="  ", end=None))
    assert texts(writer.itemized_bill(c))[0].endswith("accounts: Rosa Example, services on March 4, 2030.")


def test_itemized_says_nothing_about_a_bill_with_neither_account_nor_dates():
    c = family(bill("S1"), bill("S2", account="", patient="PATIENT_2", start=None, end=None))
    assert "Theo Example" not in texts(writer.itemized_bill(c))[0]


def test_itemized_with_a_token_that_has_no_value_leaves_a_blank_to_fill():
    c = family(bill(account="[ACCT_404]"))
    assert "Rosa Example, account [account number], services from" in texts(writer.itemized_bill(c))[0]


def test_itemized_merges_two_accounts_it_can_only_print_as_the_same_blank():
    c = family(bill("S1", account="[ACCT_404]"), bill("S2", account="[ACCT_405]", start=date(2030, 3, 2), end=date(2030, 3, 2)))
    assert texts(writer.itemized_bill(c))[0].endswith(
        "accounts: Rosa Example, account [account number], services from March 2, 2030 to March 6, 2030.")


def test_itemized_finds_a_person_however_the_token_was_read_and_says_the_patient_otherwise():
    c = family(bill("S1", patient="patient 1"), bill("S2", account="[ACCT_2]", patient="PATIENT_9"))
    assert texts(writer.itemized_bill(c))[0] == (
        "I am asking for an itemized statement for each of these accounts: Rosa Example, account HDH-1001, services from "
        "March 4, 2030 to March 6, 2030; the patient, account HDH-1002, services from March 4, 2030 to March 6, 2030.")


def test_itemized_keeps_the_order_the_accounts_first_appear_in():
    c = family(bill("S1", account="[ACCT_2]", patient="PATIENT_2"), bill("S2"), bill("S3", account="[ACCT_2]", patient="PATIENT_2"))
    text = texts(writer.itemized_bill(c))[0]
    assert text.index("HDH-1002") < text.index("HDH-1001") and text.count("HDH-1002") == 1


def test_itemized_without_a_letterhead_goes_to_the_office_with_no_name():
    letter = writer.itemized_bill(family(bill(provider=""), letterhead=""))
    assert letter.to == "Patient Financial Services"


def test_itemized_drops_the_law_when_one_of_its_two_quotes_does_not_verify(monkeypatch):
    only_refused(monkeypatch, "fl-395-301#itemized-7-days")
    letter = writer.itemized_bill(family(bill()))
    assert ITEMIZED_LAW not in texts(letter) and len(letter.paragraphs) == 2
    assert letter.dropped == [f"{ITEMIZED_LAW[:60]}... (unverified fl-395-301#itemized-7-days)"]


# --- apply_discount --------------------------------------------------------------------------

MOM = bill("S1")
SON = bill("S2", account="[ACCT_2]", patient="PATIENT_2", balance="1240.00")
SIS = bill("S3", account="[ACCT_3]", patient="PATIENT_3", balance="88.10")
F3 = finding(Kind.F3, Evidence(doc_id="S1"), Evidence(doc_id="S2"))
F3_SIS = finding(Kind.F3, Evidence(doc_id="S1"), Evidence(doc_id="S3"))


def test_discount_letter_asks_for_the_same_assistance_on_the_bill_that_lacks_it():
    assert facts(writer.apply_discount(family(MOM, SON), report(F3))) == {
        "kind": "apply-discount", "button": "Letter: apply discount to Theo Example's bill", "to": OFFICE,
        "subject": "Apply financial assistance to account HDH-1002",
        "paragraphs": [
            ("Financial assistance was applied to account HDH-1001 for my hospital stay (March 4, 2030 to March 6, 2030). "
             "The account for Theo Example, HDH-1002, is from the same stay and still shows the full balance of $1,240.00.", []),
            ("Please apply the same financial assistance to that account. Your Financial Assistance Policy covers balances "
             "left after insurance payment and says the hospital will also consider accounts from the prior twelve months.",
             [f"{MEMORIAL}#insured-balances", f"{MEMORIAL}#prior-accounts"]),
            ("Please send me a corrected statement. Thank you.", []),
        ],
        "attachments": [], "dropped": [], "office": "", "rows": {}}


def test_discount_letter_for_two_accounts_names_both_and_says_those():
    letter = writer.apply_discount(family(MOM, SON, SIS, people=(MOTHER, BABY, TWIN)), report(F3, F3_SIS))
    assert letter.subject == "Apply financial assistance to account HDH-1002 and HDH-1003"
    assert letter.button == "Letter: apply discount to Theo Example's bill"
    assert texts(letter)[0] == (
        "Financial assistance was applied to account HDH-1001 for my hospital stay (March 4, 2030 to March 6, 2030). "
        "The account for Theo Example, HDH-1002, is from the same stay and still shows the full balance of $1,240.00. "
        "The account for Mia Example, HDH-1003, is from the same stay and still shows the full balance of $88.10.")
    assert texts(letter)[1].startswith("Please apply the same financial assistance to those accounts. Your Financial")


def test_discount_letter_takes_the_bill_with_the_discount_from_the_first_finding():
    other = bill("S4", account="[ACCT_3]", start=date(2030, 1, 2), end=date(2030, 1, 3))
    second = finding(Kind.F3, Evidence(doc_id="S4"), Evidence(doc_id="S2"))
    letter = writer.apply_discount(family(MOM, SON, other), report(F3, second))
    assert "account HDH-1001 for my hospital stay (March 4, 2030" in texts(letter)[0]


def test_discount_letter_calls_an_unnamed_child_my_child():
    letter = writer.apply_discount(family(MOM, SON, people=(MOTHER,)), report(F3))
    assert letter.button == "Letter: apply discount to my child's bill"
    assert "The account for my child, HDH-1002, is from" in texts(letter)[0]


def test_discount_letter_prints_empty_dates_rather_than_guessing_them():
    has = bill("S1", start=None, end=None)
    assert "for my hospital stay ( to )." in texts(writer.apply_discount(family(has, SON), report(F3)))[0]


def test_discount_letter_keeps_its_ask_with_no_quote_when_the_policy_has_neither_part():
    letter = writer.apply_discount(family(MOM, SON, policy_id=BAPTIST), report(F3))
    assert letter.paragraphs[1].refs == [] and "those" not in texts(letter)[1]
    assert texts(letter)[1].startswith("Please apply the same financial assistance to that account.")
    assert letter.dropped == []


def test_discount_letter_drops_the_ask_when_a_quote_does_not_verify(monkeypatch):
    only_refused(monkeypatch, f"{MEMORIAL}#prior-accounts")
    letter = writer.apply_discount(family(MOM, SON), report(F3))
    assert [t[:30] for t in texts(letter)] == ["Financial assistance was appli", "Please send me a corrected sta"]
    assert letter.dropped == ["Please apply the same financial assistance to that account. ... "
                              f"(unverified {MEMORIAL}#prior-accounts)"]


def test_no_discount_letter_without_that_finding_and_no_policy_is_read():
    f1 = finding(Kind.F1, Evidence(doc_id="S1"))
    assert writer.apply_discount(family(MOM, policy_id="no-such-policy"), report(f1)) is None


def test_discount_letter_needs_a_policy_that_exists():
    with pytest.raises(FileNotFoundError):
        writer.apply_discount(family(MOM, SON, policy_id="no-such-policy"), report(F3))


def test_discount_letter_needs_the_sheets_its_finding_names():
    with pytest.raises(Exception) as caught:
        writer.apply_discount(family(MOM), report(F3))
    assert type(caught.value) in (StopIteration, RuntimeError)  # a missing sheet, however it surfaces; not "not written"


# --- application -----------------------------------------------------------------------------

F1 = finding(Kind.F1, Evidence(doc_id="S1"))
OPEN = finding(Kind.F2, Evidence(doc_id="S1"), deadline=date(2030, 9, 2), policy_refs=[f"{MEMORIAL}#window", "federal-501r#application-period"])
FORM_NOTE = "The completed Financial Evaluation Form and the documents it lists are attached."


def test_application_states_the_household_the_discount_and_the_open_window():
    assert facts(writer.application(family(MOM), report(F1, OPEN))) == {
        "kind": "application", "button": "Financial assistance form · ready to sign", "to": OFFICE,
        "subject": "Application for financial assistance",
        "paragraphs": [
            ("I am applying for financial assistance. My household has 4 people and our yearly income is $52,000.00, which is "
             "230.5% of the 2026 federal poverty guidelines.", []),
            ("Your Financial Assistance Policy lists a 90% discount at this income level.", [f"{MEMORIAL}#scale-mrh"]),
            ("I am applying before September 2, 2030, within the application period.",
             [f"{MEMORIAL}#window", "federal-501r#application-period"]),
            (FORM_NOTE, []),
        ],
        "attachments": ["Financial Evaluation Form", "Documents listed in Table C of the form"], "dropped": [], "office": "",
        "rows": {f"{MEMORIAL}#scale-mrh": "201% - 250% of FPG 90% Discount"}}


def test_application_after_the_window_asks_to_accept_it_late():
    c = family(MOM, today=date(2030, 9, 3))
    assert texts(writer.application(c, report(F1, OPEN)))[2] == (
        "The application period ended on September 2, 2030. I am asking you to accept this late application.")


def test_application_on_the_last_day_is_still_in_time():
    c = family(MOM, today=date(2030, 9, 2))
    assert texts(writer.application(c, report(F1, OPEN)))[2] == (
        "I am applying before September 2, 2030, within the application period.")


def test_application_without_a_window_goes_straight_to_the_form():
    assert texts(writer.application(family(MOM), report(F1)))[2:] == [FORM_NOTE]


def test_application_looks_for_the_window_among_the_confirmed_findings_only():
    assert texts(writer.application(family(MOM), report(F1, worth_asking=[OPEN])))[2:] == [FORM_NOTE]


def test_application_takes_the_first_window_even_if_it_has_no_date():
    blank = finding(Kind.F2, Evidence(doc_id="S1"))
    assert texts(writer.application(family(MOM), report(F1, blank, OPEN)))[2:] == [FORM_NOTE]


def test_application_with_a_window_without_quotes_keeps_the_sentence():
    bare = finding(Kind.F2, Evidence(doc_id="S1"), deadline=date(2030, 9, 2))
    letter = writer.application(family(MOM), report(F1, bare))
    assert letter.paragraphs[2].refs == [] and texts(letter)[2].startswith("I am applying before")


def test_application_drops_a_window_whose_quote_does_not_verify(monkeypatch):
    only_refused(monkeypatch, "federal-501r#application-period")
    letter = writer.application(family(MOM), report(F1, OPEN))
    assert texts(letter)[2:] == [FORM_NOTE]
    assert letter.dropped == ["I am applying before September 2, 2030, within the applicati... "
                              "(unverified federal-501r#application-period)"]


def test_application_keeps_the_table_row_when_the_discount_paragraph_is_dropped(monkeypatch):
    only_refused(monkeypatch, f"{MEMORIAL}#scale-mrh")
    letter = writer.application(family(MOM), report(F1))
    assert "discount" not in " ".join(texts(letter))
    assert letter.rows == {f"{MEMORIAL}#scale-mrh": "201% - 250% of FPG 90% Discount"}
    assert letter.dropped == ["Your Financial Assistance Policy lists a 90% discount at thi... "
                              f"(unverified {MEMORIAL}#scale-mrh)"]


def test_application_also_follows_a_discount_missing_on_one_bill():
    assert writer.application(family(MOM, SON), report(F3)).kind == "application"


@pytest.mark.parametrize("kind", [Kind.E1, Kind.F2, Kind.NM])
def test_no_application_without_a_finding_about_assistance(kind):
    other = finding(kind, Evidence(doc_id="S1"), deadline=date(2030, 9, 2))
    assert writer.application(family(MOM, policy_id="no-such-policy"), report(other)) is None


def test_no_application_above_the_top_tier():
    assert writer.application(family(MOM), report(F1, fpl_pct="401.0")) is None


@pytest.mark.parametrize("pct, article, discount, row", [
    ("100.0", "a", 100, None),
    ("200.9", "a", 100, None),
    ("201.0", "a", 90, "201% - 250% of FPG 90% Discount"),
    ("250.9", "a", 90, "201% - 250% of FPG 90% Discount"),
    ("251.0", "an", 85, "251% - 300% of FPG 85% Discount"),
    ("300.4", "an", 85, "251% - 300% of FPG 85% Discount"),
    ("301.0", "an", 83, "301% - 350% of FPG 83% Discount"),
    ("400.9", "an", 83, "351% - 400% of FPG 83% Discount"),
])
def test_application_quotes_the_tier_of_the_familys_income(pct, article, discount, row):
    letter = writer.application(family(MOM), report(F1, fpl_pct=pct))
    assert texts(letter)[1] == f"Your Financial Assistance Policy lists {article} {discount}% discount at this income level."
    assert list(letter.rows.values()) == ([row] if row else [])


def test_application_prints_the_percent_exactly_as_the_report_holds_it():
    assert "which is 250.40% of the 2026 federal" in texts(writer.application(family(MOM), report(F1, fpl_pct="250.40")))[0]


def test_application_says_people_for_a_household_of_one():
    c = family(MOM, household=1, income="9.5")
    assert "My household has 1 people and our yearly income is $9.50, which is" in texts(writer.application(c, report(F1)))[0]


def test_application_names_a_policy_without_its_revision_and_without_a_table_row():
    letter = writer.application(family(MOM, policy_id=BAPTIST), report(F1, fpl_pct="250.0"))
    assert letter.paragraphs[1].text == "Your Financial Assistance Policy BHSF-355.14 lists a 100% discount at this income level."
    assert letter.paragraphs[1].refs == [f"{BAPTIST}#levels"] and letter.rows == {}


def test_application_says_the_policys_own_guideline_year(monkeypatch):
    monkeypatch.setattr(policy.load(MEMORIAL), "fpg_year", 2029)
    monkeypatch.setattr(fpl, "latest_year", lambda: 2031)
    assert "of the 2029 federal poverty guidelines." in texts(writer.application(family(MOM), report(F1)))[0]


def test_application_says_the_latest_guideline_year_when_the_policy_names_none(monkeypatch):
    monkeypatch.setattr(policy.load(MEMORIAL), "fpg_year", None)
    monkeypatch.setattr(fpl, "latest_year", lambda: 2031)
    assert "of the 2031 federal poverty guidelines." in texts(writer.application(family(MOM), report(F1)))[0]


def test_application_needs_a_policy_that_exists():
    with pytest.raises(FileNotFoundError):
        writer.application(family(MOM, policy_id="no-such-policy"), report(F1))


# --- _dispute --------------------------------------------------------------------------------

def double(amount=None, amount_from=None, doc_id="S1", first=3, second=7) -> Finding:
    math = {"code": "99231", "service_date": "2030-03-05", "charges": "480"}
    if amount_from is not None:
        math["amount_from"] = amount_from
    return finding(Kind.E2, Evidence(doc_id=doc_id, line_no=first), Evidence(doc_id=doc_id, line_no=second),
                   amount=None if amount is None else Decimal(amount), math=math)


def line(no=2, **fields) -> Line:
    base = {"code": "59409", "description": "Delivery", "service_date": START, "patient_responsibility": Decimal("500"),
            "claim_ref": "C-1002"}
    return Line(line_no=no, **(base | fields))


def too_much(doc_id="S1", line_no=2) -> Finding:
    return finding(Kind.E1, Evidence(doc_id=doc_id, line_no=line_no), Evidence(doc_id="S9", line_no=1),
                   math={"eob_patient_responsibility": "410.1", "difference": "89.9"})


BILLED_TWICE = "My statement for account HDH-1001 lists the same service twice: lines 3 and 7, code 99231, on March 5, 2030, $480.00 each. "
ASKS_TOO_MUCH = ("Line 2 of my statement for account HDH-1001 asks $500.00 for Delivery (code 59409) on March 4, 2030. "
                 "My insurance Explanation of Benefits for claim C-1002 shows my patient responsibility for it as $410.10, "
                 "a difference of $89.90.")
ASK_DOUBLE = "Please correct the balance, or explain it in writing."
ASK_MATCH = "Please correct the balance to match my insurance, or explain the difference in writing."


def test_dispute_of_a_double_asks_to_remove_it_and_cites_the_grievance_law():
    assert facts(writer._dispute(family(bill()), [], [double()], "dispute")) == {
        "kind": "dispute", "button": "Letter: fix the amount from your insurance statement", "to": OFFICE,
        "subject": "Billing dispute: the same service billed twice",
        "paragraphs": [(BILLED_TWICE + "Please remove the duplicate and the charge to me for it.", []),
                       (ASK_DOUBLE + GRIEVANCE, ["fl-395-301#grievance-7-days"])],
        "attachments": ["Copy of the Explanation of Benefits"], "dropped": [], "office": "", "rows": {}}


@pytest.mark.parametrize("amount, amount_from, tail", [
    ("120.5", "S9", "Please remove the duplicate and my $120.50 share of it, as my insurance statement shows."),
    ("120.5", None, "Please remove the duplicate and my $120.50 share of it."),
    ("120.5", "", "Please remove the duplicate and my $120.50 share of it."),
    (None, None, "Please remove the duplicate and the charge to me for it."),
    (None, "S9", "Please remove the duplicate and the charge to me for it."),
    ("0.00", "S9", "Please remove the duplicate and the charge to me for it."),
])
def test_dispute_of_a_double_names_my_share_only_when_there_is_one(amount, amount_from, tail):
    letter = writer._dispute(family(bill()), [], [double(amount, amount_from)], "dispute")
    assert texts(letter)[0] == BILLED_TWICE + tail


def test_dispute_of_a_double_reads_the_bill_of_its_first_evidence():
    f = double()
    f.evidence += [Evidence(doc_id="S2", line_no=1, note="also twice here"), Evidence(doc_id="S2", line_no=2)]
    c = family(bill(), bill("S2", account="[ACCT_2]"))
    assert texts(writer._dispute(c, [], [f], "dispute"))[0].startswith("My statement for account HDH-1001 lists")


def test_dispute_of_an_overcharge_compares_the_bill_line_with_the_insurance_statement():
    c = family(bill(lines=[line(1, patient_responsibility=Decimal("1")), line()]))
    assert facts(writer._dispute(c, [too_much()], [], "dispute")) == {
        "kind": "dispute", "button": "Letter: fix the amount from your insurance statement", "to": OFFICE,
        "subject": "Billing dispute: amount does not match my insurance",
        "paragraphs": [(ASKS_TOO_MUCH, []), (ASK_MATCH + GRIEVANCE, ["fl-395-301#grievance-7-days"])],
        "attachments": ["Copy of the Explanation of Benefits"], "dropped": [], "office": "", "rows": {}}


def test_dispute_of_an_overcharge_leaves_out_what_the_line_does_not_print():
    c = family(bill(lines=[line(code="", description="", claim_ref="", service_date=None)]))
    assert texts(writer._dispute(c, [too_much()], [], "dispute"))[0] == (
        "Line 2 of my statement for account HDH-1001 asks $500.00 for a service on . My insurance Explanation of Benefits "
        "shows my patient responsibility for it as $410.10, a difference of $89.90.")


def test_dispute_of_an_overcharge_takes_the_first_line_with_that_number():
    c = family(bill(lines=[line(description="First"), line(description="Second")]))
    assert "for First (code" in texts(writer._dispute(c, [too_much()], [], "dispute"))[0]


def test_dispute_with_both_kinds_lists_doubles_first_and_asks_to_match_the_insurance():
    c = family(bill(lines=[line()]))
    letter = writer._dispute(c, [too_much()], [double("120.5"), double(first=4, second=8)], "dispute-s1")
    assert letter.kind == "dispute-s1"
    assert letter.subject == "Billing dispute: amount does not match my insurance"
    assert texts(letter) == [BILLED_TWICE + "Please remove the duplicate and my $120.50 share of it.",
                             BILLED_TWICE.replace("lines 3 and 7", "lines 4 and 8") + "Please remove the duplicate and the charge to me for it.",
                             ASKS_TOO_MUCH, ASK_MATCH + GRIEVANCE]


def test_dispute_goes_to_the_office_that_sent_the_bill_and_gives_it_thirty_days():
    letter = writer._dispute(family(bill(provider=DOCTORS)), [], [double()], "dispute")
    assert letter.to == f"Billing office, {DOCTORS}"
    assert letter.paragraphs[-1].text == f"{ASK_DOUBLE} Please answer in writing within 30 days."
    assert letter.paragraphs[-1].refs == []


def test_dispute_to_a_doctors_office_about_an_overcharge_also_gives_thirty_days():
    letter = writer._dispute(family(bill(provider=DOCTORS, lines=[line()])), [too_much()], [], "dispute")
    assert letter.paragraphs[-1].text == f"{ASK_MATCH} Please answer in writing within 30 days."


def test_dispute_says_an_offices_name_as_a_person_would():
    letter = writer._dispute(family(bill(provider="300_SUNRISE ANESTHESIA (IP) 300")), [], [double()], "dispute")
    assert letter.to == "Billing office, Sunrise Anesthesia"


def test_dispute_decides_the_office_by_the_first_double_when_there_are_both_kinds():
    c = family(bill(), bill("S2", provider=DOCTORS, lines=[line()]))
    letter = writer._dispute(c, [too_much("S2")], [double()], "dispute")
    assert letter.to == OFFICE and letter.paragraphs[-1].refs == ["fl-395-301#grievance-7-days"]


@pytest.mark.parametrize("sender", ["300_", "(IP) 300"])
def test_dispute_to_an_office_whose_name_comes_out_empty_is_still_not_the_hospitals(sender):
    letter = writer._dispute(family(bill(provider=sender)), [], [double()], "dispute")
    assert letter.to == "Billing office, "
    assert letter.paragraphs[-1].text == f"{ASK_DOUBLE} Please answer in writing within 30 days."
    assert letter.paragraphs[-1].refs == []


def test_dispute_treats_a_bill_with_no_sender_as_the_hospitals():
    letter = writer._dispute(family(bill(provider="")), [], [double()], "dispute")
    assert letter.to == OFFICE and letter.paragraphs[-1].refs == ["fl-395-301#grievance-7-days"]


def test_dispute_without_a_letterhead_goes_to_the_billing_office_with_no_name():
    letter = writer._dispute(family(bill(provider=DOCTORS), letterhead=""), [], [double()], "dispute")
    assert letter.to == "Patient Financial Services" and letter.paragraphs[-1].refs == ["fl-395-301#grievance-7-days"]


def test_dispute_drops_the_ask_with_the_law_when_its_quote_does_not_verify(monkeypatch):
    only_refused(monkeypatch, "fl-395-301#grievance-7-days")
    letter = writer._dispute(family(bill()), [], [double()], "dispute")
    assert len(letter.paragraphs) == 1
    assert letter.dropped == ["Please correct the balance, or explain it in writing. Florid... "
                              "(unverified fl-395-301#grievance-7-days)"]


def test_dispute_needs_a_finding():
    with pytest.raises(IndexError):
        writer._dispute(family(bill()), [], [], "dispute")


def test_dispute_needs_the_line_the_finding_names():
    with pytest.raises(StopIteration):
        writer._dispute(family(bill()), [too_much()], [], "dispute")


def test_dispute_needs_the_sheet_the_finding_names():
    with pytest.raises(StopIteration):
        writer._dispute(family(bill()), [], [double(doc_id="S404")], "dispute")


def test_dispute_needs_the_numbers_of_the_finding():
    f = double()
    del f.math["charges"]
    with pytest.raises(KeyError):
        writer._dispute(family(bill()), [], [f], "dispute")


def test_every_office_gets_its_own_dispute_named_after_its_sheet():
    c = family(bill(), bill("S2", provider=DOCTORS, account="[ACCT_2]"))
    letters = writer.disputes(c, report(double(), double(doc_id="S2")))
    assert [(x.kind, x.to) for x in letters] == [("dispute", OFFICE), ("dispute-s2", f"Billing office, {DOCTORS}")]


# --- appeal ----------------------------------------------------------------------------------

def denial(**fields) -> Denial:
    base = dict(plan_id=PLAN, eob_id="S9", claim_ref="CLM-1", patient="PATIENT_1", member_ref="[MEMBER_1]", codes=["P31"],
                line_nos=[1], description="Inpatient stay", code="0120", service_from=START, service_to=END,
                patient_responsibility=Decimal("6100"), denial_date=date(2030, 4, 1))
    return Denial(**(base | fields))


def the_plan(**changes) -> plans.Plan:
    return replace(plans.load(PLAN), **changes)


def ref(fragment: str) -> str:
    return f"plan:{PLAN}#{fragment}"


OPENING = ("I am appealing the denial of claim CLM-1 for Rosa Example (Inpatient stay, March 4, 2030 to March 6, 2030). Your "
           "Explanation of Benefits dated April 1, 2030 denies it with remark code ")
CHILDBIRTH = ("This claim is part of my hospital stay for the birth of my child. My plan document says (page 2): “Medically "
              "necessary inpatient care for childbirth and delivery is covered.”")
NO_AUTH = ("Please check my stay against this rule before asking for prior authorization. My plan document says (page 2): "
           "“Prior authorization is not required for a hospital stay for childbirth of up to 48 hours after a vaginal delivery "
           "or 96 hours after a cesarean section.”")
EMERGENCY = ("If prior authorization could not be obtained in time, the plan does not allow a denial for that reason alone. "
             "My plan document says (page 2): “In emergency situations or when prior authorization cannot be obtained, covered "
             "services will not be denied solely for lack of prior authorization.”")
LEAVES = ("Your Explanation of Benefits leaves $6,100.00 for me to pay on this claim. Please review the claim and process it "
          "as a covered service under my plan.")
COPIES = "Please also send me free copies of all documents, records and other information relevant to my claim."
IN_TIME = f"I am sending this appeal before September 28, 2030, within the time the plan allows after a denial. {COPIES}"
FEDERAL = ("Federal rules for employer health plans give at least 180 days to appeal a denied claim "
           "(29 CFR 2560.503-1(h)(3)(i)).")
CLOSING = "Please send your decision in writing to the address below. Thank you."
P31_OPENING = OPENING + "P31: “Prior authorization was not obtained for this service.”"


def test_appeal_quotes_the_plan_for_every_point():
    assert facts(writer.appeal(family(MOM), the_plan(), denial())) == {
        "kind": "appeal-s9-clm-1", "button": "Appeal to Sample Health Plan",
        "to": "Appeals Department, Sample Health Plan, PO Box 12345, Riverton, ST 12345",
        "subject": "Appeal of denied claim CLM-1, member ID SHP-77",
        "paragraphs": [
            (P31_OPENING, [ref("code-p31")]),
            (CHILDBIRTH, [ref("childbirth-covered")]),
            (NO_AUTH, [ref("no-auth-for-childbirth-stay")]),
            (EMERGENCY, [ref("emergency-auth")]),
            (LEAVES, []),
            (IN_TIME, [ref("appeal-180-days"), ref("copies-free")]),
            (FEDERAL, ["erisa-2560-503-1#appeal-180-days"]),
            (CLOSING, []),
        ],
        "attachments": ["Explanation of Benefits dated April 1, 2030", "Member appeal form"], "dropped": [],
        "office": "Sample Health Plan appeals", "rows": {}}


def test_appeal_past_the_plans_time_asks_for_a_late_review():
    c = family(MOM, today=date(2030, 9, 29))
    assert (f"The time the plan allows after a denial ended on September 28, 2030. I am asking you to review this late appeal. "
            f"{COPIES}") in texts(writer.appeal(c, the_plan(), denial()))


def test_appeal_on_the_last_day_is_still_in_time():
    assert IN_TIME in texts(writer.appeal(family(MOM, today=date(2030, 9, 28)), the_plan(), denial()))


def test_appeal_without_a_denial_date_has_no_deadline_and_no_date_on_the_statement():
    letter = writer.appeal(family(MOM), the_plan(), denial(denial_date=None))
    assert texts(letter)[0] == ("I am appealing the denial of claim CLM-1 for Rosa Example (Inpatient stay, March 4, 2030 to "
                                "March 6, 2030). Your Explanation of Benefits denies it with remark code P31: “Prior "
                                "authorization was not obtained for this service.”")
    assert IN_TIME not in texts(letter) and COPIES not in " ".join(texts(letter))
    assert letter.attachments == ["Explanation of Benefits", "Member appeal form"]


def test_appeal_to_a_plan_that_is_not_an_employers_has_no_federal_paragraph():
    assert FEDERAL not in texts(writer.appeal(family(MOM), the_plan(plan_type="individual"), denial()))


@pytest.mark.parametrize("people, context", [((MOTHER,), ()), ((MOTHER,), ("er_visit",))])
def test_appeal_uses_a_birth_ground_only_when_the_case_shows_a_birth(people, context):
    letter = writer.appeal(family(MOM, people=people, context=context), the_plan(), denial())
    assert CHILDBIRTH not in texts(letter) and NO_AUTH not in texts(letter) and EMERGENCY in texts(letter)


def test_appeal_counts_the_birth_chip_as_a_birth():
    letter = writer.appeal(family(MOM, people=(MOTHER,), context=("birth",)), the_plan(), denial())
    assert CHILDBIRTH in texts(letter)


def test_appeal_counts_a_newborn_in_the_household_as_a_birth():
    letter = writer.appeal(family(MOM, people=(BABY,)), the_plan(), denial(patient="PATIENT_2"))
    assert CHILDBIRTH in texts(letter)


def test_no_appeal_when_no_ground_is_left_for_this_case():
    assert writer.appeal(family(MOM, people=(MOTHER,)), the_plan(), denial(codes=["M12"])) is None


def test_no_appeal_when_the_plan_has_no_ground_for_the_code():
    assert writer.appeal(family(MOM), the_plan(), denial(codes=["CO2"])) is None


def test_no_appeal_for_a_denial_with_no_codes():
    assert writer.appeal(family(MOM), the_plan(), denial(codes=[])) is None


def test_appeal_opens_once_for_each_code_even_one_with_no_ground():
    letter = writer.appeal(family(MOM), the_plan(), denial(codes=["P31", "CO2"]))
    assert texts(letter)[:2] == [P31_OPENING, OPENING + "CO2: “Coinsurance amount.”"]
    assert letter.paragraphs[1].refs == [ref("code-co2")]


def test_appeal_quotes_a_ground_shared_by_two_codes_once():
    letter = writer.appeal(family(MOM), the_plan(), denial(codes=["P31", "M12"]))
    assert texts(letter).count(CHILDBIRTH) == 1 and letter.refs.count(ref("childbirth-covered")) == 1


def test_appeal_keeps_the_first_place_and_the_last_words_of_a_repeated_ground():
    plan = the_plan(grounds={"P31": [Ground("P31", "emergency-auth", "First words."), Ground("P31", "copies-free", "Middle.")],
                             "M12": [Ground("M12", "emergency-auth", "Last words.")]})
    letter = writer.appeal(family(MOM), plan, denial(codes=["P31", "M12"]))
    said = [t.split(" My plan document says")[0] for t in texts(letter) if "My plan document says" in t]
    assert said == ["Last words.", "Middle."]


def test_appeal_only_holds_back_a_ground_that_needs_a_birth():
    plan = the_plan(grounds={"P31": [Ground("P31", "emergency-auth", "Other need.", "something-else")]})
    letter = writer.appeal(family(MOM, people=(MOTHER,)), plan, denial())
    assert any(t.startswith("Other need. My plan document says (page 2): “In emergency") for t in texts(letter))


def test_appeal_prints_the_page_of_each_quote():
    plan = the_plan(grounds={"P31": [Ground("P31", "copies-free", "See this.")]})
    letter = writer.appeal(family(MOM), plan, denial())
    assert ("See this. My plan document says (page 4): “You may ask for free copies of all documents, records and other "
            "information relevant to your claim.”") in texts(letter)


@pytest.mark.parametrize("start, end, span", [
    (START, START, "March 4, 2030"),
    (START, None, "March 4, 2030"),
    (START, END, "March 4, 2030 to March 6, 2030"),
    (None, END, " to March 6, 2030"),
    (None, None, ""),
])
def test_appeal_gives_the_dates_of_care_it_has(start, end, span):
    letter = writer.appeal(family(MOM), the_plan(), denial(service_from=start, service_to=end))
    assert f"for Rosa Example (Inpatient stay, {span}). Your" in texts(letter)[0]


@pytest.mark.parametrize("claim, opens, subject", [
    ("CLM-1", "the denial of claim CLM-1 for", "Appeal of denied claim CLM-1, member ID SHP-77"),
    ("", "the denial of the claim for", "Appeal of denied the claim, member ID SHP-77"),
])
def test_appeal_names_the_claim_when_it_has_a_number(claim, opens, subject):
    letter = writer.appeal(family(MOM), the_plan(), denial(claim_ref=claim))
    assert opens in texts(letter)[0] and letter.subject == subject


def test_appeal_without_a_claim_number_is_keyed_by_its_line():
    assert writer.appeal(family(MOM), the_plan(), denial(claim_ref="", line_nos=[4, 5])).kind == "appeal-s9-4"


def test_appeal_calls_an_undescribed_service_hospital_care():
    assert "(hospital care, March 4, 2030" in texts(writer.appeal(family(MOM), the_plan(), denial(description="")))[0]


def test_appeal_for_someone_the_case_cannot_name_says_the_patient():
    assert " for the patient (Inpatient stay," in texts(writer.appeal(family(MOM), the_plan(), denial(patient="PATIENT_9")))[0]


def test_appeal_finds_the_person_however_the_token_was_read():
    assert " for Rosa Example (" in texts(writer.appeal(family(MOM), the_plan(), denial(patient="[patient 1]")))[0]


@pytest.mark.parametrize("owed", [None, Decimal("0.00")])
def test_appeal_leaves_out_the_sum_when_nothing_is_left_to_pay(owed):
    assert "for me to pay" not in " ".join(texts(writer.appeal(family(MOM), the_plan(), denial(patient_responsibility=owed))))


@pytest.mark.parametrize("member, subject", [
    ("[MEMBER_1]", "Appeal of denied claim CLM-1, member ID SHP-77"),
    ("  SHP-12 ", "Appeal of denied claim CLM-1, member ID SHP-12"),
    ("[MEMBER_404]", "Appeal of denied claim CLM-1"),
    ("", "Appeal of denied claim CLM-1"),
])
def test_appeal_shows_a_member_id_only_when_there_is_a_real_one(member, subject):
    assert writer.appeal(family(MOM), the_plan(), denial(member_ref=member)).subject == subject


def test_appeal_attaches_the_itemized_bill_when_the_case_holds_one():
    itemized = bill("S2", kind=DocKind.ITEMIZED_BILL)
    assert writer.appeal(family(MOM, itemized), the_plan(), denial()).attachments == [
        "Explanation of Benefits dated April 1, 2030", "Itemized hospital bill", "Member appeal form"]


def test_appeal_drops_what_does_not_verify_and_reports_it(monkeypatch):
    only_refused(monkeypatch, ref("emergency-auth"), ref("copies-free"))
    letter = writer.appeal(family(MOM), the_plan(), denial())
    assert EMERGENCY not in texts(letter) and IN_TIME not in texts(letter)
    assert letter.dropped == [
        f"{EMERGENCY[:60]}... (unverified {ref('emergency-auth')})",
        f"{IN_TIME[:60]}... (unverified {ref('copies-free')})"]


def test_appeal_without_the_copies_quote_is_an_error():
    plan = the_plan()
    plan.fragments = {k: v for k, v in plan.fragments.items() if k != "copies-free"}
    with pytest.raises(KeyError):
        writer.appeal(family(MOM), plan, denial())


def test_appeal_with_a_ground_for_a_code_outside_the_plans_legend_is_an_error():
    plan = the_plan(grounds={"ZZ9": [Ground("ZZ9", "emergency-auth", "Say.")]})
    with pytest.raises(AttributeError):
        writer.appeal(family(MOM), plan, denial(codes=["ZZ9"]))


def test_appeal_quotes_a_legend_line_that_does_not_start_with_its_code_whole(monkeypatch):
    monkeypatch.setattr(writer, "verified", lambda _: True)
    plan = the_plan()
    plan.fragments = plan.fragments | {"code-p31": PlanFragment(PLAN, "code-p31", 3, "  Denied for no reason.  ")}
    assert texts(writer.appeal(family(MOM), plan, denial()))[0] == OPENING + "P31: “Denied for no reason.”"


# --- the letters together --------------------------------------------------------------------

def test_a_letter_written_without_a_sheet_says_so_at_the_end():
    c = family(MOM, SON)
    r = report(F3, F1)
    r.not_sent = ["S7"]
    letters = writer.all_letters(c, r)
    assert [x.kind for x in letters] == ["itemized", "apply-discount", "application"]
    assert all(x.paragraphs[-1].text == writer.NOT_ALL_PAPERS for x in letters)


def test_plain_text_of_a_finished_letter():
    c = family(bill(), street="12 Bay Road", city="Hollywood", state="FL", zip="33021", phone="(555) 010-0100", demo=True)
    assert writer.plain_text(writer.itemized_bill(c), c) == "\n".join([
        "SAMPLE - FICTIONAL DATA", "", "June 1, 2030", "", OFFICE, "", "Subject: Request for an itemized statement", "",
        "Dear Patient Financial Services team,", "",
        "I am asking for an itemized statement for each of these accounts: Rosa Example, account HDH-1001, services from "
        "March 4, 2030 to March 6, 2030.\n", ITEMIZED_LAW + "\n", "Please send it to the address below. Thank you.\n",
        "Sincerely,", "", "Rosa Example", "12 Bay Road", "Hollywood, FL 33021", "(555) 010-0100"]) + "\n"
