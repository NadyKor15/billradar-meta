"""Lines of a PDF from its text layer: exact text, exact place, no model."""
import io
import shutil

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from billradar import pdf_lines, pdfpages

pytestmark = pytest.mark.skipif(not shutil.which("pdftotext"), reason="no poppler")


def bill() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica", 10)
    c.drawString(70, 700, "Patient: Grace Hunter")
    c.drawString(70, 660, "02/11/2025 0251 025594594 CEFAZOLIN")
    c.drawString(400, 660, "204.00")
    c.showPage()
    c.drawString(70, 700, "Total Charges 204.00")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_each_page_gives_its_lines_at_the_scale_of_the_drawn_page():
    pages = pdf_lines.lines_of(bill(), pdfpages.DPI)
    assert len(pages) == 2 and pages[0][0].text == "Patient: Grace Hunter"
    x0, y0, _, _ = pages[0][0].box
    assert abs(x0 - 70 * pdfpages.DPI / 72) < 3 and abs(y0 - (792 - 710) * pdfpages.DPI / 72) < 8


def test_a_wide_gap_on_a_line_makes_two_cells():
    texts = [t.text for t in pdf_lines.lines_of(bill(), pdfpages.DPI)[0]]
    assert "204.00" in texts and "02/11/2025 0251 025594594 CEFAZOLIN" in texts


def test_not_a_pdf_gives_nothing_and_does_not_crash():
    assert pdf_lines.lines_of(b"%PDF-1.4 fake", pdfpages.DPI) == []
