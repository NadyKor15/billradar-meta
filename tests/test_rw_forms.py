"""Current behaviour of the two filled forms, past what test_writer and test_appeal pin.

Tests read the finished PDF the way a printer would: what is drawn, where, in which font and colour, in any drawing
order. All people, accounts and amounts here are fictional.
"""
import io
import json
import math
from dataclasses import replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest
from pypdf import PdfReader
from pypdf.generic import ContentStream
from reportlab.pdfgen import canvas

from billradar import appeal, forms, plans
from billradar.case import Case
from billradar.policies import source

HOSPITAL = "Lakeview Demo Hospital"
needs_form = pytest.mark.skipif(not source.form_path("memorial-fef").exists(),
                                reason="run scripts/fetch_policies.py first")

INK = (0.05, 0.2, 0.45)
STAMP = (0.85, 0.15, 0.15)
BLACK = (0.0, 0.0, 0.0)
LABEL = (0.35, 0.38, 0.42)
EDGE = (0.55, 0.6, 0.65)


# --- reading a PDF page ---------------------------------------------------------------------

def _times(a, b):
    return (a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5])


def _point(m, x, y):
    return round(m[0] * x + m[2] * y + m[4], 2), round(m[1] * x + m[3] * y + m[5], 2)


def page_marks(page, reader):
    """Every text, box and line drawn on a page, with its final position and colour."""
    res = page["/Resources"]
    fonts = {k: v.get_object()["/BaseFont"][1:] for k, v in (res.get("/Font") or {}).items()}
    states = res.get("/ExtGState") or {}
    out, stack, boxes, segments = [], [], [], []
    ctm, fill, stroke, alpha = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), BLACK, BLACK, 1.0
    font, size, tm, here = "", 0.0, ctm, (0.0, 0.0)
    for args, op in ContentStream(page.get_contents(), reader).operations:
        if op == b"q":
            stack.append((ctm, fill, stroke, alpha))
        elif op == b"Q":
            ctm, fill, stroke, alpha = stack.pop()
        elif op == b"cm":
            ctm = _times(tuple(float(v) for v in args), ctm)
        elif op in (b"rg", b"g"):
            fill = tuple(round(float(v), 3) for v in args) * (3 if op == b"g" else 1)
        elif op in (b"RG", b"G"):
            stroke = tuple(round(float(v), 3) for v in args) * (3 if op == b"G" else 1)
        elif op == b"gs":
            alpha = round(float(states[args[0]].get_object().get("/ca", alpha)), 3)
        elif op == b"Tf":
            font, size = fonts.get(args[0], str(args[0])), round(float(args[1]), 2)
        elif op == b"Tm":
            tm = tuple(float(v) for v in args)
        elif op == b"Td":
            tm = _times((1, 0, 0, 1, float(args[0]), float(args[1])), tm)
        elif op == b"Tj" and str(args[0]):
            full = _times(tm, ctm)
            turn = round(math.degrees(math.atan2(full[1], full[0])), 1)
            out.append(("text", str(args[0]), *_point(full, 0, 0), font, size, fill, alpha, turn))
        elif op == b"re":
            x, y, w, h = (float(v) for v in args)
            boxes.append((*_point(ctm, x, y), round(w, 2), round(h, 2)))
        elif op == b"m":
            here = _point(ctm, float(args[0]), float(args[1]))
        elif op == b"l":
            to = _point(ctm, float(args[0]), float(args[1]))
            segments.append((*here, *to))
            here = to
        elif op == b"S":
            out += [("box", *b, stroke) for b in boxes] + [("line", *s, stroke) for s in segments]
            boxes, segments = [], []
        elif op == b"n":
            boxes, segments = [], []
    return out


def marks(pdf: bytes, page: int = 0):
    reader = PdfReader(io.BytesIO(pdf))
    return page_marks(reader.pages[page], reader)


def written(pdf: bytes, page: int = 0):
    """(text, x, y) of everything written on a page."""
    return sorted((m[1], m[2], m[3]) for m in marks(pdf, page) if m[0] == "text")


def one(pdf: bytes, text: str):
    found = [m for m in marks(pdf) if m[0] == "text" and m[1] == text]
    assert len(found) == 1, (text, found)
    return found[0]


def page_contents(pdf: bytes, page: int) -> bytes:
    return PdfReader(io.BytesIO(pdf)).pages[page].get_contents().get_data()


# --- a case to fill in ----------------------------------------------------------------------

MOM = {"token": "PATIENT_1", "role": "mother", "name": "Anna Sample", "birth_date": "03/14/1994",
       "relationship": "Self", "employer": "Sample Bakery LLC"}
BABY = {"token": "PATIENT_2", "role": "newborn", "name": "Baby Sample", "birth_date": "08/04/2025",
        "relationship": "Daughter"}
LOCAL = {"street": "100 Example Street", "city": "Hollywood", "state": "FL", "zip": "33021", "phone": "(555) 010-0000",
         "spouse_monthly_gross": "3100.5", "other_monthly_income": "0", "rent": "1800", "electricity": "142.255",
         "phone_bill": "65.1", "checking": "2400", "savings": "950.75", "residence_value": "0.004",
         "tokens": {"ACCT_1": "LDH-000123", "ACCT_2": "LDH-000124", "GUAR_1": "G-555"}}


def bill(doc_id="S1", account="[ACCT_1]", patient="PATIENT_1", provider=HOSPITAL, kind="hospital_statement",
         start="2025-08-04", end="2025-08-06"):
    return {"doc_id": doc_id, "source": "paper", "kind": kind, "patient": patient, "provider": provider,
            "account_ref": account, "service_from": start, "service_to": end}


def make_case(docs=None, people=(MOM, BABY), local=LOCAL, income="85000", size=4, letterhead=HOSPITAL,
              policy="memorial-2026-05", demo=False) -> Case:
    return Case.model_validate({
        "case_id": "rw-forms", "letterhead": letterhead, "policy_id": policy, "today": "2026-06-15", "demo": demo,
        "profile": {"household_size": size, "annual_income": income, "people": list(people), "local": local},
        "documents": [bill()] if docs is None else docs})


def values_of(**changes):
    return forms.memorial_values(make_case(**changes))


# --- _amount --------------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("0", "0.00"), ("7", "7.00"), ("1234.5", "1,234.50"), ("7083.333333", "7,083.33"), ("0.005", "0.01"),
    ("0.004", "0.00"), ("2.675", "2.68"), ("1.0049999999", "1.00"), ("999.995", "1,000.00"),
    ("999999.995", "1,000,000.00"), ("1000000", "1,000,000.00"), ("1E+3", "1,000.00"),
])
def test_amount_prints_cents_and_commas_with_halves_rounded_up(value, expected):
    assert forms._amount(Decimal(value)) == expected


@pytest.mark.parametrize("value,expected", [("-1234.565", "-1,234.57"), ("-0.005", "-0.01"), ("-0.001", "-0.00"),
                                            ("-0", "-0.00")])
def test_amount_keeps_the_sign_and_rounds_a_negative_half_away_from_zero(value, expected):
    assert forms._amount(Decimal(value)) == expected


def test_amount_of_none_is_an_empty_field():
    assert forms._amount(None) == ""


def test_amount_of_a_quiet_nan_prints_nan():
    assert forms._amount(Decimal("NaN")) == "NaN"


def test_amount_at_the_edge_of_decimal_precision():
    assert forms._amount(Decimal("1E+25")) == "10,000,000,000,000,000,000,000,000.00"
    with pytest.raises(InvalidOperation):
        forms._amount(Decimal("1E+26"))


@pytest.mark.parametrize("value", ["Infinity", "-Infinity", "sNaN"])
def test_amount_refuses_what_has_no_cents(value):
    with pytest.raises(InvalidOperation):
        forms._amount(Decimal(value))


@pytest.mark.parametrize("value", [5, 0, 1.5, "3", True])
def test_amount_takes_only_a_decimal(value):
    with pytest.raises(AttributeError):
        forms._amount(value)


# --- memorial_values ------------------------------------------------------------------------

def test_memorial_values_of_a_full_case():
    assert values_of() == {
        "account": "LDH-000123", "mr": "", "patient": "Anna Sample", "street": "100 Example Street",
        "phone": "(555) 010-0000", "city": "Hollywood", "state": "FL", "zip": "33021", "salary": "7,083.33",
        "spouse": "3,100.50", "other": "0.00", "rent": "1,800.00", "electricity": "142.26", "phone_bill": "65.10",
        "checking": "2,400.00", "savings": "950.75", "residence": "0.00",
        "member0": "Anna Sample|03/14/1994|Self|Sample Bakery LLC", "member1": "Baby Sample|08/04/2025|Daughter|",
        "member2": "", "member3": ""}


def test_memorial_values_of_a_case_with_nothing_local():
    assert values_of(docs=[], people=(), local={}, size=1, income="0") == {
        "account": "", "mr": "", "patient": "", "street": "", "phone": "", "city": "", "state": "", "zip": "",
        "salary": "0.00", "spouse": "", "other": "", "rent": "", "electricity": "", "phone_bill": "", "checking": "",
        "savings": "", "residence": "", "member0": ""}


@pytest.mark.parametrize("income,expected", [("12.06", "1.01"), ("6.06", "0.51"), ("0.06", "0.01"), ("0.05", "0.00"),
                                             ("1000000.00", "83,333.33"), ("120000", "10,000.00"),
                                             ("-1200", "-100.00")])
def test_salary_is_a_twelfth_of_the_yearly_income_with_exact_half_cents(income, expected):
    assert values_of(income=income)["salary"] == expected


@pytest.mark.parametrize("docs,expected", [
    ([bill("S1", "[ACCT_2]", "PATIENT_2"), bill("S2", "[ACCT_1]")], "LDH-000123"),
    ([bill("S1", "G-771"), bill("S2", "[ACCT_1]")], "LDH-000123"),
    ([bill("S1", "G-771"), bill("S2", "G-772")], "G-771"),
    ([bill("S1", "[ACCT_2]", "PATIENT_2")], "LDH-000124"),
    ([bill("S1", "G-771"), bill("S2", "[ACCT_2]", "PATIENT_2")], "G-771"),
    ([bill("S1", "[ACCT_9]")], ""),
    ([bill("S1", "[GUAR_1]")], "G-555"),
    ([bill("S1", "[GUAR_9]"), bill("S2", "G-771")], ""),
    ([bill("S1", "ACCT_1")], "LDH-000123"),
    ([bill("S1", "[ACCT_1")], "LDH-000123"),
    ([bill("S1", "G-771"), bill("S2", "[acct_1]")], "G-771"),
    ([bill("S1", " [ACCT_1]"), bill("S2", "G-771")], " [ACCT_1]"),
], ids=["mother-over-baby", "covered-over-printed", "first-printed", "only-the-baby", "printed-mother-over-baby",
        "token-not-on-device", "other-token", "first-token-unknown", "printed-token-name", "half-bracket",
        "lower-case-is-no-account-token", "space-keeps-it-printed"])
def test_account_is_the_mothers_covered_account_first(docs, expected):
    assert values_of(docs=docs)["account"] == expected


def test_account_comes_from_the_hospitals_bills_not_a_doctors_office():
    docs = [bill("S1", "[ACCT_1]", provider="Women First OB/GYN"), bill("S2", "[ACCT_2]")]
    assert values_of(docs=docs)["account"] == "LDH-000124"


def test_account_falls_back_to_any_bill_when_the_hospitals_bills_carry_none():
    docs = [bill("S1", ""), bill("S2", "[ACCT_1]", provider="Women First OB/GYN")]
    assert values_of(docs=docs)["account"] == "LDH-000123"


def test_account_skips_a_bill_for_care_before_the_latest_stay():
    docs = [bill("S1", "[ACCT_1]", start="2025-03-01", end="2025-03-02"), bill("S2", "[ACCT_2]", "PATIENT_2")]
    assert values_of(docs=docs)["account"] == "LDH-000124"


def test_account_falls_back_to_an_earlier_bill_when_the_stay_has_no_account():
    docs = [bill("S1", "[ACCT_1]", start="2025-03-01", end="2025-03-02"), bill("S2", "")]
    assert values_of(docs=docs)["account"] == "LDH-000123"


def test_itemized_bills_count_and_other_papers_do_not():
    assert values_of(docs=[bill("S1", "[ACCT_2]", kind="itemized_bill")])["account"] == "LDH-000124"
    assert values_of(docs=[bill("S1", "[ACCT_1]", kind="eob"), bill("S2", "[ACCT_2]", kind="other")])["account"] == ""


def test_account_without_a_mother_is_the_first_covered_account_of_any_patient():
    people = ({**MOM, "role": "patient"}, BABY)
    docs = [bill("S1", "G-771", "PATIENT_2"), bill("S2", "[ACCT_2]", "PATIENT_2"), bill("S3", "[ACCT_1]")]
    assert values_of(docs=docs, people=people)["account"] == "LDH-000124"


def test_a_bill_counts_as_the_mothers_only_by_the_exact_token():
    docs = [bill("S1", "[ACCT_2]", "PATIENT_2"), bill("S2", "[ACCT_1]", "[PATIENT_1]")]
    assert values_of(docs=docs)["account"] == "LDH-000124"


def test_patient_is_the_first_mother_and_nobody_else():
    assert values_of(people=({**MOM, "role": "patient"}, BABY))["patient"] == ""
    assert values_of(people=(BABY, MOM, {**MOM, "token": "PATIENT_3", "name": "Other Sample"}))["patient"] == "Anna Sample"


def test_a_member_row_holds_four_cells_in_the_order_of_the_people():
    v = values_of(people=(BABY, {"token": "X", "role": "other"}, MOM), size=3)
    assert (v["member0"], v["member1"], v["member2"]) == ("Baby Sample|08/04/2025|Daughter|", "|||",
                                                          "Anna Sample|03/14/1994|Self|Sample Bakery LLC")
    assert "member3" not in v


def people(n):
    return [{"token": f"P{i}", "role": "other", "name": f"Person {i}"} for i in range(n)]


def rows(values):
    return {k: v for k, v in values.items() if k.startswith("member")}


def test_the_household_counts_more_people_than_the_case_names():
    assert rows(values_of(people=people(1), size=3)) == {"member0": "Person 0|||", "member1": "", "member2": ""}


def test_the_case_names_more_people_than_the_household_counts():
    assert rows(values_of(people=people(3), size=1)) == {f"member{i}": f"Person {i}|||" for i in range(3)}


@pytest.mark.parametrize("named,size", [(7, 2), (8, 9), (2, 20), (0, 6), (0, 7), (6, 6)])
def test_the_form_has_six_rows_at_most(named, size):
    got = rows(values_of(people=people(named), size=size))
    assert sorted(got) == [f"member{i}" for i in range(6)]
    assert sum(1 for v in got.values() if v) == min(named, 6)


def test_household_size_unset_after_loading_adds_no_blank_rows():
    c = make_case(people=people(1))
    c.profile.household_size = None
    assert rows(forms.memorial_values(c)) == {"member0": "Person 0|||"}


def test_memorial_values_change_nothing_in_the_case():
    c = make_case()
    before = c.model_dump_json()
    forms.memorial_values(c)
    assert c.model_dump_json() == before


# --- fill_memorial --------------------------------------------------------------------------

FULL = [("LDH-000123", 36.0, 670.0), ("Anna Sample", 112.0, 645.5), ("100 Example Street", 112.0, 635.5),
        ("(555) 010-0000", 406.0, 635.5), ("Hollywood", 52.0, 625.5), ("FL", 274.0, 625.5), ("33021", 418.0, 625.5),
        ("7,083.33", 212.0, 380.0), ("3,100.50", 212.0, 366.5), ("0.00", 212.0, 353.0), ("1,800.00", 464.0, 380.0),
        ("142.26", 464.0, 366.5), ("65.10", 464.0, 353.0), ("2,400.00", 257.0, 315.0), ("950.75", 257.0, 303.0),
        ("0.00", 257.0, 291.0),
        ("Anna Sample", 36.0, 512.0), ("03/14/1994", 228.0, 512.0), ("Self", 334.0, 512.0),
        ("Sample Bakery LLC", 434.0, 512.0),
        ("Baby Sample", 36.0, 495.8), ("08/04/2025", 228.0, 495.8), ("Daughter", 334.0, 495.8)]


@needs_form
def test_memorial_form_draws_each_value_at_its_place():
    assert written(forms.fill_memorial(make_case()).pdf) == sorted(FULL)


@needs_form
def test_memorial_values_are_in_blue_helvetica():
    drawn = marks(forms.fill_memorial(make_case()).pdf)
    assert {(m[4], m[5], m[6], m[7], m[8]) for m in drawn} == {("Helvetica", 9.5, INK, 1.0, 0.0)}


@needs_form
def test_memorial_form_lists_what_was_filled_and_what_is_left():
    f = forms.fill_memorial(make_case())
    assert f.filled == ["account", "patient", "street", "phone", "city", "state", "zip", "salary", "spouse", "other",
                        "rent", "electricity", "phone_bill", "checking", "savings", "residence", "member0", "member1"]
    assert f.left_for_you == ["member2", "member3", "signature", "date", "witness"]


@needs_form
def test_memorial_form_with_nothing_local_leaves_every_field_to_the_family():
    f = forms.fill_memorial(make_case(docs=[], people=(), local={}, size=1, income="0"))
    assert f.filled == ["salary"]
    assert f.left_for_you == ["account", "patient", "street", "phone", "city", "state", "zip", "spouse", "other", "rent",
                              "electricity", "phone_bill", "checking", "savings", "residence", "member0", "signature",
                              "date", "witness"]
    assert written(f.pdf) == [("0.00", 212.0, 380.0)]


@needs_form
def test_memorial_form_has_six_rows_one_row_height_apart():
    f = forms.fill_memorial(make_case(people=people(7), size=9))
    got = [m for m in written(f.pdf) if m[0].startswith("Person")]
    assert got == [(f"Person {i}", 36.0, y) for i, y in enumerate((512.0, 495.8, 479.6, 463.4, 447.2, 431.0))]
    assert f.filled[-6:] == [f"member{i}" for i in range(6)]
    assert "member6" not in f.filled + f.left_for_you


@needs_form
def test_memorial_form_row_with_no_cells_counts_as_filled_and_draws_nothing():
    f = forms.fill_memorial(make_case(people=({"token": "X", "role": "other"},), size=1, local={}, docs=[]))
    assert f.filled == ["salary", "member0"]
    assert "member0" not in f.left_for_you
    assert written(f.pdf) == [("7,083.33", 212.0, 380.0)]


@needs_form
def test_memorial_form_skips_the_empty_cells_of_a_row():
    person = {"token": "X", "role": "other", "relationship": "Son"}
    f = forms.fill_memorial(make_case(people=(person,), size=1, local={}, docs=[]))
    assert ("Son", 334.0, 512.0) in written(f.pdf)
    assert len(written(f.pdf)) == 2


@needs_form
def test_memorial_form_row_never_runs_past_its_four_columns():
    person = {"token": "X", "role": "other", "name": "One|Two", "birth_date": "Three", "relationship": "Four",
              "employer": "Five"}
    f = forms.fill_memorial(make_case(people=(person,), size=1, local={}, docs=[]))
    assert written(f.pdf) == sorted([("7,083.33", 212.0, 380.0), ("One", 36.0, 512.0), ("Two", 228.0, 512.0),
                                     ("Three", 334.0, 512.0), ("Four", 434.0, 512.0)])


@needs_form
def test_memorial_form_writes_spanish_names_as_they_are():
    person = {**MOM, "name": "José Núñez"}
    pdf = forms.fill_memorial(make_case(people=(person,), size=1)).pdf
    assert {("José Núñez", 112.0, 645.5), ("José Núñez", 36.0, 512.0)} <= set(written(pdf))


@needs_form
def test_memorial_form_without_the_demo_flag_has_no_stamp():
    drawn = marks(forms.fill_memorial(make_case()).pdf)
    assert not [m for m in drawn if m[6] == STAMP]


@needs_form
def test_demo_memorial_form_carries_both_stamps_in_the_margins():
    pdf = forms.fill_memorial(make_case(demo=True)).pdf
    top = one(pdf, "SAMPLE - FICTIONAL DATA · Filled by BillRadar for a demo. Not a real application.")
    assert top[2:] == (89.62, 776.0, "Helvetica-Bold", 11.0, STAMP, 0.55, 0.0)
    bottom = one(pdf, "Rules: the public Financial Assistance Policy and form of Memorial Regional Hospital (FL; MHS = "
                      "Memorial Healthcare System), applied to the fictional Lakeview Demo Hospital case.")
    assert bottom[2:] == (23.86, 14.0, "Helvetica", 7.0, STAMP, 0.55, 0.0)
    assert len(written(pdf)) == len(FULL) + 2


@needs_form
def test_demo_stamp_does_not_change_the_ink_of_the_values():
    drawn = [m for m in marks(forms.fill_memorial(make_case(demo=True)).pdf) if m[1] == "LDH-000123"]
    assert drawn == [("text", "LDH-000123", 36.0, 670.0, "Helvetica", 9.5, INK, 1.0, 0.0)]


@needs_form
def test_demo_form_of_a_case_with_no_letterhead_says_sample():
    pdf = forms.fill_memorial(make_case(demo=True, letterhead="")).pdf
    assert one(pdf, "Rules: the public Financial Assistance Policy and form of Memorial Regional Hospital (FL; MHS = "
                    "Memorial Healthcare System), applied to the fictional sample case.")[3] == 14.0


@needs_form
def test_demo_form_under_another_policy_has_only_the_top_stamp():
    drawn = marks(forms.fill_memorial(make_case(demo=True, policy="baptist-2026-09")).pdf)
    assert [m[1] for m in drawn if m[6] == STAMP] == [
        "SAMPLE - FICTIONAL DATA · Filled by BillRadar for a demo. Not a real application."]


@needs_form
def test_memorial_form_keeps_the_blank_form_under_the_values():
    blank = source.form_path("memorial-fef")
    original = PdfReader(blank).pages[0].extract_text()
    page1 = PdfReader(io.BytesIO(forms.fill_memorial(make_case()).pdf)).pages[0].extract_text()
    for line in (ln.strip() for ln in original.splitlines()):
        assert line in page1


@needs_form
def test_memorial_form_leaves_the_other_pages_as_they_are():
    blank = source.form_path("memorial-fef").read_bytes()
    pdf = forms.fill_memorial(make_case(demo=True)).pdf
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 4
    for i in (1, 2, 3):
        assert page_contents(pdf, i) == page_contents(blank, i)


def two_page_blank(path: Path) -> Path:
    c = canvas.Canvas(str(path), pagesize=(612, 792))
    c.drawString(72, 720, "first page of the form")
    c.showPage()
    c.drawString(72, 720, "second page of the form")
    c.save()
    return path


def test_memorial_form_fills_the_first_page_of_whatever_blank_the_cache_holds(tmp_path, monkeypatch):
    asked = []
    blank = two_page_blank(tmp_path / "blank.pdf")
    monkeypatch.setattr(source, "form_path", lambda form_id: asked.append(form_id) or blank)
    f = forms.fill_memorial(make_case())
    assert asked == ["memorial-fef"]
    pages = PdfReader(io.BytesIO(f.pdf)).pages
    assert len(pages) == 2
    assert "first page of the form" in pages[0].extract_text() and "Anna Sample" in pages[0].extract_text()
    assert "second page of the form" in pages[1].extract_text() and "Anna Sample" not in pages[1].extract_text()


def test_memorial_form_without_the_blank_says_how_to_get_it(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "form_path", lambda form_id: tmp_path / "missing.pdf")
    with pytest.raises(FileNotFoundError) as e:
        forms.fill_memorial(make_case())
    assert str(e.value) == "run scripts/fetch_policies.py to download the blank form"


def test_missing_blank_is_reported_before_anything_about_the_case(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "form_path", lambda form_id: tmp_path / "missing.pdf")
    with pytest.raises(FileNotFoundError):
        forms.fill_memorial(make_case(income="1E+40"))


# --- fill_insurer_appeal --------------------------------------------------------------------

APPEAL_CASE = Path(__file__).parent / "fixtures" / "cases" / "sample-appeal.json"
PLAN = "sample-health-plan-2026"
FAMILY = [{"token": "PATIENT_1", "role": "mother", "name": "Maria Sample"},
          {"token": "PATIENT_2", "role": "newborn", "name": "Leo Sample"}]
ADDRESS = {"street": "12 Example Lane", "city": "Riverton", "state": "ST", "zip": "12345", "phone": "(555) 010-0199",
           "tokens": {"ACCT_1": "LDH-45821", "MEMBER_1": "SHP-000-4417"}}


def appeal_case(local: dict = ADDRESS, demo: bool = True) -> Case:
    raw = json.loads(APPEAL_CASE.read_text())
    raw["profile"]["people"], raw["profile"]["local"], raw["demo"] = FAMILY, local, demo
    return Case.model_validate(raw)


def fill(c: Case, plan=None, **denial):
    d = appeal.denials(c)[0]
    return forms.fill_insurer_appeal(c, plan or plans.load(PLAN), replace(d, **denial))


# (label, label y, what the form shows, value y, box bottom, box height), top to bottom
APPEAL_ROWS = [
    ("Patient name", 681.0, "Maria Sample", 671.0, 668.0, 22.0),
    ("Member ID", 653.0, "SHP-000-4417", 643.0, 640.0, 22.0),
    ("Claim number", 625.0, "CLM-7765301", 615.0, 612.0, 22.0),
    ("Date(s) of service", 597.0, "07/14/2026", 587.0, 584.0, 22.0),
    ("Provider or hospital", 569.0, "Lakeview Demo Hospital", 559.0, 556.0, 22.0),
    ("Date on the denial notice", 541.0, "10/15/2026", 531.0, 528.0, 22.0),
    ("Remark code(s) on the notice", 513.0, "P31", 503.0, 500.0, 22.0),
    ("Amount in dispute ($)", 485.0, "6,840.00", 475.0, 472.0, 22.0),
    ("Street address", 457.0, "12 Example Lane", 447.0, 444.0, 22.0),
    ("City", 429.0, "Riverton", 419.0, 416.0, 22.0),
    ("State", 401.0, "ST", 391.0, 388.0, 22.0),
    ("ZIP", 373.0, "12345", 363.0, 360.0, 22.0),
    ("Phone", 345.0, "(555) 010-0199", 335.0, 332.0, 22.0),
    ("Why you disagree", 317.0, "Please see the attached appeal letter. It quotes the plan document for each point.",
     307.0, 292.0, 34.0),
    ("Documents attached", 277.0, "Appeal letter; Explanation of Benefits (S2); hospital bill", 267.0, 264.0, 22.0),
]
APPEAL_HEAD = [
    ("text", "Sample Health Plan", 46.0, 744.0, "Helvetica-Bold", 15.0, BLACK, 1.0, 0.0),
    ("text", "Member Appeal Form", 46.0, 726.0, "Helvetica", 11.0, BLACK, 1.0, 0.0),
    ("text", "Appeals Department", 488.52, 748.0, "Helvetica", 8.5, BLACK, 1.0, 0.0),
    ("text", "Sample Health Plan", 490.89, 737.0, "Helvetica", 8.5, BLACK, 1.0, 0.0),
    ("text", "PO Box 12345", 510.72, 726.0, "Helvetica", 8.5, BLACK, 1.0, 0.0),
    ("text", "Riverton, ST 12345", 492.77, 715.0, "Helvetica", 8.5, BLACK, 1.0, 0.0),
]
APPEAL_FOOT = [
    ("text", "By signing, I ask the plan to review its decision on the claim above.", 46.0, 254.0, "Helvetica", 8.0,
     BLACK, 1.0, 0.0),
    ("text", "Signature of member or authorized representative", 46.0, 208.0, "Helvetica", 8.0, BLACK, 1.0, 0.0),
    ("text", "Date", 380.0, 208.0, "Helvetica", 8.0, BLACK, 1.0, 0.0),
    ("line", 46.0, 218.0, 346.0, 218.0, EDGE),
    ("line", 380.0, 218.0, 566.0, 218.0, EDGE),
]
DEMO_STAMP = [
    ("text", "SAMPLE - FICTIONAL DATA", 114.21, 367.68, "Helvetica-Bold", 30.0, STAMP, 0.55, 18.0),
    ("text", "Demo form of a made-up insurer. Not a real appeal.", 174.23, 364.05, "Helvetica-Bold", 12.0, STAMP, 0.55,
     18.0),
]
FIELD_KEYS = ["patient_name", "member_id", "claim_number", "service_dates", "provider", "denial_date", "denial_codes",
              "amount", "street", "city", "state", "zip", "phone", "reason", "attachments"]


def appeal_marks(rows_=APPEAL_ROWS, head=APPEAL_HEAD, stamp=DEMO_STAMP):
    out = list(head) + APPEAL_FOOT + list(stamp)
    for label, label_y, value, value_y, bottom, height in rows_:
        out.append(("text", label, 50.0, label_y, "Helvetica", 7.5, LABEL, 1.0, 0.0))
        out.append(("box", 46.0, bottom, 520.0, height, EDGE))
        if value:
            out.append(("text", value, 52.0, value_y, "Helvetica", 9.5, INK, 1.0, 0.0))
    return sorted(out, key=str)


def test_insurer_form_draws_the_whole_page():
    assert sorted(marks(fill(appeal_case()).pdf), key=str) == appeal_marks()


def test_insurer_form_lets_an_error_of_its_data_through():
    with pytest.raises(StopIteration):
        fill(appeal_case(), eob_id="S99")


def test_insurer_form_is_one_letter_page():
    page, = PdfReader(io.BytesIO(fill(appeal_case()).pdf)).pages
    assert [float(v) for v in page.mediabox] == [0, 0, 612, 792]


def test_insurer_form_lists_filled_fields_in_form_order():
    f = fill(appeal_case())
    assert f.filled == FIELD_KEYS
    assert f.left_for_you == ["signature", "date"]


def test_insurer_form_leaves_the_address_to_the_family_when_the_device_has_none():
    f = fill(appeal_case(local={}))
    missing = ["member_id", "street", "city", "state", "zip", "phone"]
    assert f.left_for_you == missing + ["signature", "date"]
    assert f.filled == [k for k in FIELD_KEYS if k not in missing]


def test_insurer_form_keeps_the_box_of_an_empty_field():
    pdf = fill(appeal_case(), patient="NOBODY", patient_responsibility=None, denial_date=None).pdf
    rows_ = [(*r[:2], "" if r[0] in ("Patient name", "Amount in dispute ($)", "Date on the denial notice") else r[2], *r[3:])
             for r in APPEAL_ROWS]
    assert sorted(marks(pdf), key=str) == appeal_marks(rows_)


def test_insurer_form_order_of_left_fields_follows_the_form():
    f = fill(appeal_case(), patient="NOBODY", patient_responsibility=None, denial_date=None, claim_ref="", codes=[])
    assert f.left_for_you == ["patient_name", "claim_number", "denial_date", "denial_codes", "amount", "signature", "date"]


def test_insurer_form_shows_a_range_of_service_dates():
    pdf = fill(appeal_case(), service_to=date(2026, 7, 16)).pdf
    assert one(pdf, "07/14/2026 - 07/16/2026")[2:4] == (52.0, 587.0)


@pytest.mark.parametrize("n,shown", [(110, 110), (111, 110), (130, 110), (109, 109)])
def test_insurer_form_cuts_a_long_value_at_110_characters(n, shown):
    c = appeal_case()
    c.letterhead = "x" * n
    f = fill(c)
    assert one(f.pdf, "x" * shown)[2:4] == (52.0, 559.0)
    assert "provider" in f.filled


def test_insurer_form_cut_keeps_a_trailing_space():
    c = appeal_case()
    c.letterhead = "x" * 109 + " " + "y" * 20
    assert one(fill(c).pdf, "x" * 109 + " ")


def test_insurer_form_does_not_print_the_last_day_to_appeal():
    c = appeal_case()
    last_day = appeal.form_values(c, plans.load(PLAN), appeal.denials(c)[0])["appeal_by"]
    assert last_day and last_day not in [t for t, _, _ in written(fill(c).pdf)]


def test_insurer_form_outside_a_demo_says_the_insurer_is_fictional():
    stamp = [("text", "SAMPLE - FICTIONAL INSURER", 89.63, 359.7, "Helvetica-Bold", 30.0, STAMP, 0.55, 18.0),
             DEMO_STAMP[1]]
    assert sorted(marks(fill(appeal_case(demo=False)).pdf), key=str) == appeal_marks(stamp=stamp)


def test_insurer_form_head_comes_from_the_plan():
    plan = replace(plans.load(PLAN), insurer="Other Fictional Plan", appeals_to=["Line one", "Line two"])
    head = [("text", "Other Fictional Plan", 46.0, 744.0, "Helvetica-Bold", 15.0, BLACK, 1.0, 0.0), APPEAL_HEAD[1],
            ("text", "Line one", 533.39, 748.0, "Helvetica", 8.5, BLACK, 1.0, 0.0),
            ("text", "Line two", 534.35, 737.0, "Helvetica", 8.5, BLACK, 1.0, 0.0)]
    assert sorted(marks(fill(appeal_case(), plan).pdf), key=str) == appeal_marks(head=head)


def test_insurer_form_with_no_appeal_address_has_an_empty_corner():
    plan = replace(plans.load(PLAN), appeals_to=[])
    assert sorted(marks(fill(appeal_case(), plan).pdf), key=str) == appeal_marks(head=APPEAL_HEAD[:2])


def test_insurer_form_is_the_same_bytes_each_time():
    pdf = fill(appeal_case()).pdf
    assert pdf == fill(appeal_case()).pdf
    assert PdfReader(io.BytesIO(pdf)).metadata["/CreationDate"] == "D:20000101000000+00'00'"  # no clock in the file


def test_insurer_form_changes_nothing_in_the_case():
    c = appeal_case()
    before = c.model_dump_json()
    fill(c)
    assert c.model_dump_json() == before


def test_the_filled_form_carries_none_of_the_blanks_properties():
    reader = PdfReader(io.BytesIO(forms.fill_memorial(make_case()).pdf))
    assert reader.metadata.title is None and reader.metadata.author is None
    assert "/AcroForm" not in reader.trailer["/Root"]
    assert "/Metadata" not in reader.trailer["/Root"]
