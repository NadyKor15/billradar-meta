import io
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from billradar import app as app_module
from billradar import callprep, checks, forms, policy, writer
from billradar.case import Case
from billradar.policies import source

FIX = Path(__file__).parent / "fixtures" / "cases" / "anna-birth.json"
needs_text = pytest.mark.skipif(
    not all(source.is_cached(p) for p in source.SOURCES) or not source.form_path("memorial-fef").exists(),
    reason="run scripts/fetch_policies.py first")

PEOPLE = [
    {"token": "PATIENT_1", "role": "mother", "name": "Anna Sample", "birth_date": "03/14/1994",
     "relationship": "Self", "employer": "Sample Bakery LLC"},
    {"token": "PATIENT_2", "role": "newborn", "name": "Baby Sample", "birth_date": "08/04/2025",
     "relationship": "Daughter"},
]
LOCAL = {
    "street": "100 Example Street", "city": "Hollywood", "state": "FL", "zip": "33021", "phone": "(555) 010-0000",
    "checking": "2400", "tokens": {"ACCT_1": "LDH-000123", "ACCT_2": "LDH-000124"},
}


def case(**changes) -> Case:
    """The Anna birth fixture with this device's names and private values; `changes` replace top-level keys."""
    raw = json.loads(FIX.read_text())
    raw["profile"].update(people=PEOPLE, local=LOCAL)
    raw.update(changes)
    return Case.model_validate(raw)


def text_of(letter: writer.Letter) -> str:
    return " ".join(p.text for p in letter.paragraphs)


# --- letters -------------------------------------------------------------------------------------

@needs_text
def test_letters_for_the_demo_case():
    c = case()
    letters = writer.all_letters(c, checks.run(c))
    by_kind = {x.kind: x for x in letters}
    assert len(letters) == 4 and set(by_kind) == {"itemized", "apply-discount", "dispute", "application"}
    assert all(not x.dropped for x in letters)

    expected = {
        "apply-discount": ["$1,240.00", "LDH-000124"],  # the newborn's balance and the account number from this device
        "dispute": ["$2,887.50", "$2,575.10", "$312.40", "claim C-1002"],
        "application": ["257.6%", "an 85% discount", "September 2, 2026"],
    }
    for kind, needles in expected.items():
        for needle in needles:
            assert needle in text_of(by_kind[kind]), f"{kind} letter lacks {needle}"


@needs_text
def test_every_number_in_a_letter_comes_from_the_case():
    c = case()
    report = checks.run(c)
    quoted = re.findall(r'"(-?\d+(?:\.\d+)?)"', c.model_dump_json() + report.model_dump_json())
    known = {Decimal(q).quantize(Decimal("0.01")) for q in quoted}
    seen = []
    for letter in writer.all_letters(c, report):
        for printed in re.findall(r"\$(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})(?!\d)", text_of(letter)):
            amount = Decimal(printed.replace(",", ""))
            seen.append(amount)
            assert amount in known, f"{letter.kind} letter prints ${printed}, which nobody counted"
    assert Decimal("1240.00") in seen and Decimal("312.40") in seen  # the check really read amounts


@needs_text
def test_letters_cite_only_verified_quotes():
    c = case()
    letters = writer.all_letters(c, checks.run(c))
    refs = [(x.kind, ref) for x in letters for ref in x.refs]
    assert refs  # the letters lean on quotes at all
    for kind, ref in refs:
        assert policy.verified(ref), f"{kind} letter cites {ref}, which is not on its page"


def test_paragraph_with_unverified_quote_is_dropped(monkeypatch):
    real = policy.verified
    monkeypatch.setattr(policy, "verified", lambda ref: not ref.startswith("fl-395-301") and real(ref))
    letter = writer.itemized_bill(case())
    text = text_of(letter)
    assert "Florida law" not in text and "itemized statement" in text  # the claim left, the request stayed
    assert letter.dropped and "fl-395-301" in letter.dropped[0] and "Florida law" in letter.dropped[0]


@needs_text
def test_account_numbers_stay_tokens_without_local_values():
    with_values = text_of(writer.itemized_bill(case()))
    assert "LDH-000123" in with_values and "LDH-000124" in with_values and "[account number]" not in with_values

    c = case()
    c.profile.local.tokens = {}
    text = text_of(writer.itemized_bill(c))
    assert "[account number]" in text and "ACCT_" not in text


@needs_text
def test_no_discount_or_dispute_letter_when_nothing_found():
    c = case()
    for bill in c.bills():  # the insurer's statements keep their shares, the bills do not repeat them
        for line in bill.lines:
            if line.claim_ref == "C-1002":
                line.patient_responsibility = None
    s2 = c.doc("S2")
    s2.fa_discount = s2.patient_balance  # the newborn's bill carries the discount too
    kinds = [x.kind for x in writer.all_letters(c, checks.run(c))]
    assert "itemized" in kinds
    assert "apply-discount" not in kinds and "dispute" not in kinds


# --- the hospital form ---------------------------------------------------------------------------

@needs_text
def test_memorial_form_is_filled_on_page_one_and_keeps_all_pages():
    filled = forms.fill_memorial(case(demo=True))
    pages = PdfReader(io.BytesIO(filled.pdf)).pages
    assert len(pages) == 4
    page1 = pages[0].extract_text()
    for needle in ("LDH-000123", "Anna Sample", "100 Example Street", "7,083.33", "2,400.00", "Sample Bakery LLC",
                   "Baby Sample", "SAMPLE - FICTIONAL DATA"):
        assert needle in page1, f"page 1 lacks {needle}"
    assert {"signature", "date", "witness", "spouse"} <= set(filled.left_for_you)


@needs_text
def test_form_without_demo_flag_has_no_stamp():
    page1 = PdfReader(io.BytesIO(forms.fill_memorial(case()).pdf)).pages[0].extract_text()
    assert "FICTIONAL" not in page1 and "Anna Sample" in page1


@needs_text
def test_a_household_member_the_case_does_not_name_is_a_blank_row_left_for_you():
    c = case(demo=True)
    c.profile.household_size = len(c.profile.people) + 1
    filled = forms.fill_memorial(c)
    page1 = PdfReader(io.BytesIO(filled.pdf)).pages[0].extract_text()
    assert "name to add" not in page1 and "Household member" not in page1  # no placeholder printed on the form
    assert f"member{len(c.profile.people)}" in filled.left_for_you  # the row is listed for the family to write


# --- routes --------------------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "RUNS", tmp_path)  # cases land in tmp_path, never in the real runs folder
    return TestClient(app_module.app), tmp_path


def save(tmp_path, c: Case, case_id: str = "w1"):
    """Leave a run on disk the way the app finds a saved case."""
    run = tmp_path / case_id
    run.mkdir()
    (run / "case.json").write_text(c.model_dump_json())
    (run / "report.json").write_text(checks.run(c).model_dump_json())


@needs_text
def test_letter_and_form_routes(client, monkeypatch):
    web, tmp_path = client
    monkeypatch.setattr(app_module, "_today", lambda case_id, c: c.today)  # not the real clock
    save(tmp_path, case(demo=True))

    page = web.get("/cases/w1")
    assert page.status_code == 200
    assert "/cases/w1/letters/apply-discount" in page.text and "/cases/w1/form.pdf" in page.text

    dispute = web.get("/cases/w1/letters/dispute")
    assert dispute.status_code == 200
    for needle in ("Where this comes from", "SAMPLE", "Anna Sample"):
        assert needle in dispute.text
    assert web.get("/cases/w1/letters/nope").status_code == 404

    form = web.get("/cases/w1/form.pdf")
    assert form.status_code == 200
    assert form.headers["content-type"] == "application/pdf" and form.content.startswith(b"%PDF")


@needs_text
def test_no_form_for_a_policy_without_one(client):
    web, tmp_path = client
    save(tmp_path, case())
    assert web.get("/cases/w1/form.pdf").status_code == 200  # control: Memorial has a form
    save(tmp_path, case(policy_id="baptist-2026-09"), "w2")
    assert web.get("/cases/w2/form.pdf").status_code == 404


def test_itemized_request_leaves_out_what_was_not_read_and_lists_an_account_once():
    c = case()
    bills = [b for b in c.bills() if b.patient_balance]
    first = bills[0]
    twin = first.model_copy(update={"doc_id": "S99"})                      # another page of the same bill
    blank = first.model_copy(update={"doc_id": "S98", "account_ref": "", "service_from": None, "service_to": None})
    c.documents += [twin, blank]
    text = text_of(writer.itemized_bill(c))
    assert "to ;" not in text and "services to" not in text and "[account number]" not in text
    assert text.count(f"account {writer._account(c, first)}") == 1


def test_call_sheet_shows_names_and_numbers_not_covering_tokens():
    c = case()
    c.profile.local.tokens.update({"CLAIM_1": "CLM-555001"})
    eob = next(iter(c.eobs()), None)
    bill = next(b for b in c.bills() if b.patient_balance)
    c.documents.append(bill.model_copy(update={"doc_id": "S97", "patient": "PATIENT 1"}))  # read with a space
    if eob is not None and eob.lines:
        eob.lines[0].claim_ref = "[CLAIM_1]"
        eob.lines[-1].claim_ref = "[CLAIM_404]"                                            # no value on this device
    sheet = callprep.hospital(c, checks.run(c))
    shown = sheet.say_first + " ".join(f"{n.label} {n.value}" for n in sheet.numbers)
    assert "PATIENT" not in shown and "[CLAIM" not in shown and "CLAIM_404" not in shown
    assert "Anna Sample" in sheet.say_first
    if eob is not None and eob.lines:
        assert any(n.value == "CLM-555001" for n in sheet.numbers)
        eob.lines[0].claim_ref = "ICIAIM 81"                                              # a token copied badly
        assert all(n.value != "ICIAIM 81" for n in callprep.hospital(c, checks.run(c)).numbers)


def test_private_values_order_does_not_depend_on_set_order():
    import subprocess
    import sys
    code = ("import json; from tests.test_writer import case; from billradar import i18n; "
            "print(json.dumps(i18n.private_values(case())))")
    runs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env={**__import__("os").environ, "PYTHONHASHSEED": seed}).stdout for seed in ("1", "2", "3")}
    assert len(runs) == 1 and runs.pop().strip()
