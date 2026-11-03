"""Private mode closes what a mail room and a scanner print on a bill, not only what follows a label: the postal
IMb under the address, DataMatrix, QR and 1D codes, the mailing line over the name, the apartment number (Apt,
Unit, #), the ZIP+4, a line up the margin, an account number in the cell under its header, a personal statement
code. A SYNTHETIC bill printed by reportlab carries all of them, with a text layer: each test checks both sides,
the values are on the page as printed (so the check is not blind) and nothing of them is on the closed copy."""

import io
import shutil

import numpy as np

import pytest
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from billradar import local_reader, pdf_lines, pdfpages, pipeline, redact, sheet_pieces
from billradar.redact import Vault, compact
from tests.reading import sheet

pytestmark = [pytest.mark.filterwarnings("ignore::DeprecationWarning"),
              pytest.mark.skipif(not shutil.which("pdftoppm"), reason="no poppler")]

HOME = "4089 Coral Reef Way Apt 400"  # what the family typed in; the bill prints "# 400"
SEEN = ["h2px375m007494", "4788416", "pxvevrdx", "292006143", "330674632", "oakstapt4b", "palmaveunit9",
        "409798605", "847673833", "418153782", "4106685", "237851g7", "77953", "480004440", "4744500976"]
KEEP = ["03212025", "99213", "123456", "67680", "179525"]  # date, service code, $1,234.56, $676.80, $1,795.25


def _code(c, kind, value, x, y, w, h, **kw):
    d = createBarcodeDrawing(kind, value=value, **kw)
    c.saveState()
    c.translate(x, y)
    c.scale(w / d.width, h / d.height)
    renderPDF.draw(d, c, 0, 0)
    c.restoreState()


def _bill() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _code(c, "ECC200DataMatrix", "H2PX375M007494001", 40, 720, 30, 30)
    c.setFont("Helvetica", 9)
    c.drawString(70, 680, "H2PX375M007494 HLNX")
    c.drawString(70, 664, "ANNA SAMPLE")
    c.drawString(70, 652, "4089 CORAL REEF WAY # 400")
    c.drawString(70, 640, "BAYSIDE FL 33067-4632")
    c.setFont("Helvetica", 6)
    c.drawString(20, 641, "4744 500976")  # the sort line printed small, left of the address, as on the Little Harbor coupon
    c.setFont("Helvetica", 9)
    _code(c, "USPS_4State", "01234567094987654321", 70, 622, 200, 12, routing="33067463240")
    c.drawString(330, 664, "Guarantor on file: 12 Oak St Apt 4B")
    c.drawString(330, 652, "Previous address: 77 Palm Ave Unit 9")
    c.drawString(330, 700, "Patient Account Num")
    c.drawString(330, 688, "4788416")
    c.drawString(70, 590, "Pay online with your personal statement code - PxvEVrdx")
    c.drawString(70, 520, "PATIENT NAME  Sample , Anna")
    c.drawString(70, 505, "Anna's visit on February 11, 2025 insurance applied")
    c.drawString(70, 490, "Guarantor # 409798605")
    c.drawString(70, 475, "Guarantor ID: 409798605")
    c.drawString(70, 440, "Statement Date      Due Date      Guarantor #      Amount Due")
    c.drawString(70, 426, "04/09/25            05/09/25      847673833        $1,795.25")
    c.drawString(70, 375, "Dear Mrs. Sample, thank you for your payment.")
    c.drawString(70, 360, "11/25/2024   Claim:4106685, Provider: Marit Halversen, MD")
    c.drawString(70, 345, "STMT 237851G7")
    c.drawString(40, 708, "77953")  # the mail piece number under the DataMatrix, as on the Cradleview letter
    c.drawString(276, 624, "480004 - 440")  # sort numbers right after the IMb, as on the Little Harbor coupon
    c.drawString(70, 400, "Account Number:")
    c.drawString(300, 400, "CVX 418153782")
    c.drawString(70, 560, "03/21/2025   99213   Office visit, established patient   $1,234.56")
    c.drawString(70, 545, "Balance due $676.80")
    c.rect(440, 455, 160, 95)  # the payment box around the QR, its label joined to the code
    _code(c, "QR", "https://pay.example/b/PxvEVrdx", 450, 480, 60, 60)
    c.rect(450, 468, 60, 11, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.drawString(456, 471, "SCAN TO PAY")
    c.setFillColorRGB(0, 0, 0)
    _code(c, "Code128", "292006-143-69524025", 70, 90, 120, 22)
    c.drawString(400, 95, "292006-143-69524025")
    c.saveState()
    c.translate(24, 300)
    c.rotate(90)
    c.setFont("Helvetica", 7)
    c.drawString(0, 0, "HLNX - H2PX375M - 007494 - 001 OF 001")
    c.restoreState()
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
def page():
    return pdfpages.render(_bill())[0]


def _vault() -> Vault:
    return Vault(known=[("ADDR", HOME), *[("ADDR", v) for v in redact.city_line("Bayside", "FL", "33067")]],
                 seed={("PATIENT", "Anna Sample"): "[PATIENT_1]"})


def _closed() -> tuple:
    v = _vault()
    pdfpages.learn(v, _bill())
    return pdfpages.cover(_bill(), "D1", v, lambda img, page_id, page: img)[0][1], v


def _text(img) -> str:
    return " ".join(compact(line.text) for line in redact.ocr(img))


def test_the_codes_and_the_values_are_on_the_page_as_printed(page):
    """Must light: before closing, the codes are found and the file's text holds every value."""
    boxes, _ = sheet_pieces.pieces(page)
    found = redact.codes(page, [redact.Line(redact._quad(b), "xxxx", .9) for b in boxes.values()])
    assert len(found) >= 3, found  # DataMatrix, QR, Code 128 at least
    text = " ".join(compact(t.text) for t in pdf_lines.lines_of(_bill(), pdfpages.DPI)[0])
    assert all(x in text for x in SEEN + KEEP), [x for x in SEEN + KEEP if x not in text]


def test_nothing_of_it_is_on_the_closed_copy():
    covered, v = _closed()
    learned = {compact(s.value) for s in v.secrets}
    assert {"4788416", "409798605", "847673833"} <= learned
    text = _text(covered)
    assert [x for x in SEEN if x in text] == []
    assert "annasample" not in text and "sample" not in text
    assert "400" not in text.replace("4089", "")  # the apartment number, wherever it was printed
    assert all(x in text for x in KEEP), [x for x in KEEP if x not in text]  # the checks still read these


def test_no_code_is_left_on_the_closed_copy():
    covered, _ = _closed()
    boxes, _ = sheet_pieces.pieces(covered)
    assert redact.codes(covered, [redact.Line(redact._quad(b), "xxxx", .9) for b in boxes.values()]) == []


def test_the_line_up_the_margin_leaves_no_ink():
    covered, _ = _closed()
    assert sheet_pieces.text_mask(covered)[800:1040, :70].sum() == 0


@pytest.mark.parametrize("printed,kind", [("H2PX375M007494 HLNX", "MAIL"), ("12 Oak St Apt 4B", "ADDR"), ("# 400", "ADDR"), ("Anna visit", "PATIENT"), ("Anna's visit", "PATIENT")])
def test_the_gate_refuses_what_it_can_still_read(page, monkeypatch, printed, kind):
    v = _vault()
    monkeypatch.setattr(local_reader, "transcribe", lambda img: "Total $10.00\n" + printed)
    assert kind in {s.kind for s in redact.leaks(page, v.secrets, v.units, v.name_words, edge=False)}


def test_the_gate_lets_a_clean_reading_through(page, monkeypatch):
    v = _vault()
    monkeypatch.setattr(local_reader, "transcribe", lambda img: "Total $10.00\n[PATIENT_1]\nOffice visit 99213")
    assert redact.leaks(page, v.secrets, v.units, v.name_words, edge=False) == []


def test_a_number_half_under_a_cover_still_counts_as_readable(page, monkeypatch):
    secret = redact.Secret("ACCT", "4788416", "[ACCT_1]")
    monkeypatch.setattr(local_reader, "transcribe", lambda img: "Account 478841")
    assert redact.leaks(page, [secret], edge=False) == [secret]


def test_a_sheet_with_a_leak_does_not_leave(page, monkeypatch):
    monkeypatch.setattr(local_reader, "transcribe", lambda img: "Anna visit")
    with pytest.raises(pipeline.RealDataGate):
        pipeline._no_leaks(page, _vault(), "S1")


def test_a_sum_that_closing_took_is_reported(monkeypatch):
    img = sheet(["Amount Due $719.03"])
    monkeypatch.setattr(local_reader, "transcribe", lambda i, again=False: "Amount Due")
    assert redact.amounts_gone(img, img) == ["719.03"]


def test_a_sum_printed_twice_counts_twice(monkeypatch):
    img = sheet(["Amount Due $27.00", "Pay this $27.00"])
    monkeypatch.setattr(local_reader, "transcribe", lambda i, again=False: "Amount Due $27.00")
    assert redact.amounts_gone(img, img) == ["27.00"]


def test_a_number_labelled_on_a_later_sheet_is_closed_on_an_earlier_one():
    first, second = sheet(["Your number 4788416 Hospital"]), sheet(["Account: 4788416", "Total $10.00"])
    v = Vault()
    redact.learn(first, v)
    redact.learn(second, v)
    assert "4788416" not in _text(redact.redact(first, v).image)


def test_a_table_rule_stays_on_the_copy_that_leaves():
    covered, _ = _closed()
    assert np.asarray(covered.convert("L")).min() < 128  # the page is not wiped blank
