"""The device as a witness: a line the model read counts as seen when one printed row holds its code and its amounts.
Pages here are drawn: SYNTHETIC."""

from datetime import date
from decimal import Decimal

from PIL import Image, ImageDraw

from billradar import redact, table_rows
from billradar.case import DocKind, Document, Line, Source


ROWS = [(80, "02/11/2025"), (340, "01960"), (520, "Anesthesia"), (900, "$4,944.00"), (1200, "$196.82")]


def row_sheet() -> Image.Image:
    img = Image.new("RGB", (1500, 300), "white")
    d = ImageDraw.Draw(img)
    for x, text in ROWS:
        d.text((x, 100), text, fill="black", font=redact._font(30))
    d.text((80, 190), "Amount you owe (subtotal) $393.64", fill="black", font=redact._font(30))
    return img


def doc(*lines: Line) -> Document:
    return Document(doc_id="S1", source=Source.PAPER, kind=DocKind.HOSPITAL_STATEMENT, lines=list(lines))


def line(code="01960", charges="4944.00", share="196.82") -> Line:
    return Line(line_no=1, service_date=date(2025, 2, 11), code=code, charges=Decimal(charges),
                patient_responsibility=Decimal(share) if share else None)


def rows_of(img) -> list:
    return table_rows.rows(redact.ocr(img))


def test_a_row_keeps_its_code_and_its_amounts():
    first = next(r for r in rows_of(row_sheet()) if "01960" in r.codes)
    assert first.amounts == {Decimal("4944.00"), Decimal("196.82")}


def test_a_line_read_right_is_seen():
    assert table_rows.seen(line(), rows_of(row_sheet()))


def test_a_subtotal_read_into_a_line_is_not_seen():
    assert not table_rows.seen(line(share="393.64"), rows_of(row_sheet()))  # S10: printed two rows below


def test_a_misread_amount_is_not_seen():
    assert not table_rows.seen(line(charges="4994.00"), rows_of(row_sheet()))


def test_a_wrong_code_is_not_seen():
    assert not table_rows.seen(line(code="01961"), rows_of(row_sheet()))


def test_the_share_of_lines_seen():
    report = table_rows.witness(doc(line(), line(share="393.64")), rows_of(row_sheet()))
    assert (report.seen, report.total) == (1, 2) and report.unseen == [1]


def test_a_line_with_no_number_is_not_counted():
    empty = Line(line_no=3, code="01960")
    report = table_rows.witness(doc(empty), rows_of(row_sheet()))
    assert report.total == 0


def test_the_last_balance_on_a_sheet():
    img = Image.new("RGB", (1500, 500), "white")
    d = ImageDraw.Draw(img)
    for i, text in enumerate(["Your Balance Due On These Services... $26.72", "Balance Transferred To Payment Plan ($712.31)",
                              "Your Balance Due On These Services... $0.00"]):
        d.text((80, 80 + 90 * i), text, fill="black", font=redact._font(30))
    assert table_rows.last_balance(rows_of(img)) == Decimal("0.00")


def test_a_sheet_with_no_balance_row_says_so():
    img = Image.new("RGB", (1500, 300), "white")
    ImageDraw.Draw(img).text((80, 100), "Thank you for your payment of $50.00", fill="black", font=redact._font(30))
    assert table_rows.last_balance(rows_of(img)) is None


# --- what one printed line of a bill looks like across the papers ------------------------------

def row(text: str, *amounts: str, code: str = "") -> table_rows.Row:
    return table_rows.Row(text, {Decimal(a) for a in amounts}, {code} if code else set())


def test_a_share_printed_as_deductible_and_coinsurance_is_seen():
    printed = [row("0112 $4,364.00 $500.00 $315.22 $1,260.87", "4364.00", "500.00", "315.22", "1260.87", code="0112")]
    line = Line(line_no=1, code="0112", charges=Decimal("4364.00"), insurance_paid=Decimal("1260.87"),
                patient_responsibility=Decimal("815.22"))
    assert table_rows.seen(line, printed)


def test_a_share_nothing_on_the_row_adds_up_to_is_not_seen():  # must light
    printed = [row("0112 $4,364.00 $500.00 $315.22 $1,260.87", "4364.00", "500.00", "315.22", "1260.87", code="0112")]
    line = Line(line_no=1, code="0112", charges=Decimal("4364.00"), patient_responsibility=Decimal("999.99"))
    assert not table_rows.seen(line, printed)


def test_a_payment_printed_on_the_row_under_the_service_is_seen():
    printed = [row("Nov 25, 2024 99213 Office Visit $240.00", "240.00", code="99213"),
               row("Insurance Payment -$166.88", "166.88"), row("Adjustment -$53.12", "53.12"),
               row("Patient Responsibility $20.00", "20.00")]
    line = Line(line_no=1, code="99213", charges=Decimal("240.00"), insurance_paid=Decimal("166.88"),
                adjustment=Decimal("53.12"), patient_responsibility=Decimal("20.00"))
    assert table_rows.seen(line, printed)


def test_the_next_service_ends_a_line():
    printed = [row("99213 Office Visit $240.00", "240.00", code="99213"), row("Insurance Payment -$166.88", "166.88"),
               row("76815 OB US $332.00", "332.00", code="76815"), row("Adjustment -$85.57", "85.57")]
    line = Line(line_no=1, code="99213", charges=Decimal("240.00"), adjustment=Decimal("85.57"))
    assert not table_rows.seen(line, printed)


def test_a_subtotal_under_the_lines_is_not_part_of_the_last_line():
    printed = [row("01960 Anesthesia $4,944.00", "4944.00", code="01960"), row("Insurance adjusted total -$7,919.78", "7919.78")]
    line = Line(line_no=1, code="01960", charges=Decimal("4944.00"), adjustment=Decimal("7919.78"))
    assert not table_rows.seen(line, printed)


def test_a_code_printed_under_its_description_takes_the_amount_above():
    printed = [row("Anesthesia For Vaginal Delivery Only $4,944.00", "4944.00"), row("CPT/HCPCS code: 01960", code="01960")]
    assert table_rows.seen(Line(line_no=1, code="01960", charges=Decimal("4944.00")), printed)


def test_an_amount_broken_by_a_scan_is_read_whole():
    class Fake:
        def __init__(self, text):
            self.text, self.box = text, __import__("numpy").array([[0, 0], [100, 0], [100, 10], [0, 10]], dtype="float32")
            self.score = 1.0

    assert Decimal("467.86") in table_rows.rows([Fake("0251 $853.00 $467. .86 $385.14")])[0].amounts


def test_the_balance_of_one_service_is_part_of_its_line():
    printed = [row("Nov 25, 2024 99213 Office Visit $240.00", "240.00", code="99213"),
               row("Dec 16, 2024 Primary Insurance Payment $53.12", "53.12"),
               row("Dec 16, 2024 Primary Insurance Adjustment $166.88", "166.88"),
               row("Mar 18, 2025 Your Balance Due On These Services"), row("Mar 18, 2025"),
               row("Your Balance Due On These Services... $20.00", "20.00"),
               row("Dec 22, 2024 76815 OB US $332.00", "332.00", code="76815"),
               row("Your Balance Due On These Services... ($40.00)", "40.00")]
    first = Line(line_no=1, code="99213", charges=Decimal("240.00"), insurance_paid=Decimal("53.12"),
                 adjustment=Decimal("166.88"), patient_responsibility=Decimal("20.00"))
    assert table_rows.seen(first, printed)
    assert not table_rows.seen(first.model_copy(update={"patient_responsibility": Decimal("40.00")}), printed)


def test_the_balance_of_the_last_service_is_not_the_balance_of_the_sheet():
    printed = [row("Your Balance Due On These Services... $25.00", "25.00"), row("Your Balance Due On These Services... $0.00", "0.00")]
    assert table_rows.last_balance(printed) is None


def test_a_balance_moved_to_a_plan_leaves_a_zero_the_sheet_means():
    printed = [row("Your Balance Due On These Services... $712.31", "712.31"),
               row("Mar 18, 2025 Balance Transferred To Payment Plan ($712.31)", "712.31"),
               row("Your Balance Due On These Services... $0.00", "0.00")]
    assert table_rows.last_balance(printed) == Decimal("0.00")


def test_a_credit_on_a_service_stays_a_credit():
    assert table_rows.last_balance([row("Your Balance Due On These Services... ($40.00)", "40.00")]) == Decimal("-40.00")


def step(line_no: int, field: str, printed: str):
    from billradar.ledger import Step
    return Step(doc_id="S1", line_no=line_no, field=field, printed=Decimal(printed))


def drug_rows() -> list:
    return [row("02/11/2025 0251 BACITRACIN 1 $6.00", "6.00", code="0251"), row("02/11/2025 0251 SUCROSE 1 $7.00", "7.00", code="0251")]


def test_a_sum_copied_from_the_other_line_of_a_code_stands_on_nothing():
    paper = doc(Line(line_no=1, code="0251", charges=Decimal("7.00")), Line(line_no=2, code="0251", charges=Decimal("7.00")))
    assert not table_rows.confirms(paper, step(1, "charges", "7.00"), drug_rows())
    assert table_rows.confirms(paper, step(2, "charges", "7.00"), drug_rows())  # must light


def test_with_as_many_lines_as_rows_each_line_stands_on_its_own_row():
    paper = doc(Line(line_no=1, code="0251", charges=Decimal("6.00")), Line(line_no=2, code="0251", charges=Decimal("7.00")))
    assert table_rows.confirms(paper, step(1, "charges", "6.00"), drug_rows())
    assert table_rows.confirms(paper, step(2, "charges", "7.00"), drug_rows())


def test_a_line_that_cannot_be_placed_stands_only_on_what_all_its_rows_print():
    paper = doc(Line(line_no=1, code="0251", charges=Decimal("6.00")))
    assert not table_rows.confirms(paper, step(1, "charges", "6.00"), drug_rows())
    same = [row("0251 BACITRACIN $6.00", "6.00", code="0251"), row("0251 BACITRACIN $6.00", "6.00", code="0251")]
    assert table_rows.confirms(paper, step(1, "charges", "6.00"), same)


def test_a_share_of_two_columns_needs_a_line_that_adds_up():
    printed = [row("83735 $58.00 $48.04 $1.00 $8.96", "58.00", "48.04", "1.00", "8.96", code="83735")]
    wrong = Line(line_no=1, code="83735", charges=Decimal("58.00"), insurance_paid=Decimal("48.04"), adjustment=Decimal("1.00"),
                 patient_responsibility=Decimal("9.96"))
    assert not table_rows.confirms(doc(wrong), step(1, "patient_responsibility", "9.96"), printed)
    right = [row("0112 $4,364.00 $2,287.91 $500.00 $315.22 $1,260.87", "4364.00", "2287.91", "500.00", "315.22", "1260.87", code="0112")]
    good = Line(line_no=1, code="0112", charges=Decimal("4364.00"), insurance_paid=Decimal("1260.87"), adjustment=Decimal("2287.91"),
                patient_responsibility=Decimal("815.22"))
    assert table_rows.confirms(doc(good), step(1, "patient_responsibility", "815.22"), right)  # must light


def _word(text: str, x: float, y: float, w: float = 70, h: float = 18):
    import numpy as np
    return redact.Line(box=np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=float), text=text, score=1.0, turn=0)


def _crooked_table(slope: float = 0.013) -> list:
    """Two lines of an EOB on a sheet lying 0.75 degrees crooked, as on a frame of the table video: the far end of a row
    stands lower than its start by more than half a row, and each date cell prints two dates, one under the other."""
    lines = [("01960", ["$4,944.00", "$3,959.89", "$984.11", "$0.00", "$196.82", "$787.29", "CDA"]),
             ("85610", ["$88.00", "$70.40", "$17.60", "$0.00", "$1.10", "$16.50", "CDA"])]
    words = [_word(h, 160 + 130 * i, 20 + slope * (160 + 130 * i)) for i, h in enumerate(
        ["Dates", "Code", "Charge", "Discount", "Allowed", "Other", "Plan", "Covered", "Share", "Paid", "Reason"])]
    for row, (code, cells) in enumerate(lines):
        y = 120 + 58 * row
        words += [_word("02/11/2025-", 150, y + slope * 150, 104), _word("02/11/2025", 150, y + 20 + slope * 150, 104),
                  _word(code, 314, y + slope * 314, 54)]
        words += [_word(c, 400 + 210 * i, y + slope * (400 + 210 * i)) for i, c in enumerate(cells)]
    return words


def _crooked_doc() -> Document:
    return doc(Line(line_no=5, service_date=date(2025, 2, 11), code="01960", charges=Decimal("4944.00"),
                    patient_responsibility=Decimal("196.82")),
               Line(line_no=6, service_date=date(2025, 2, 11), code="85610", charges=Decimal("88.00"),
                    patient_responsibility=Decimal("1.10")))


def _step(line_no: int, value: str):
    from types import SimpleNamespace
    return SimpleNamespace(printed=Decimal(value), line_no=line_no, field="patient_responsibility", doc_id="S1")


def test_on_a_crooked_sheet_a_line_keeps_the_amounts_at_its_far_end():
    printed = table_rows.rows(_crooked_table())
    assert table_rows.confirms(_crooked_doc(), _step(5, "196.82"), printed)  # the video's S1: read right, then cut in two


def test_on_a_crooked_sheet_the_next_line_s_amount_does_not_stick_to_this_code():
    printed = table_rows.rows(_crooked_table())
    assert not table_rows.confirms(_crooked_doc(), _step(5, "1.10"), printed)
    assert not table_rows.confirms(_crooked_doc(), _step(6, "196.82"), printed)
    assert table_rows.confirms(_crooked_doc(), _step(6, "1.10"), printed)


def test_a_straight_sheet_is_grouped_as_before():
    assert table_rows._tilt(_crooked_table(0.0)) == 0.0


def test_a_sheet_crooked_past_two_degrees_is_not_levelled_here():
    assert table_rows._tilt(_crooked_table(0.06)) == 0.0  # past that the sheet is straightened from its corners, or retaken
