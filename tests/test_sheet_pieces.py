"""Finding printed pieces with plain image processing. Drawn sheets, no model."""
from PIL import Image, ImageDraw, ImageFont

from billradar import sheet_pieces

FONT = "billradar/fonts/NotoSans-Bold.ttf"


def drawn():
    img = Image.new("RGB", (1000, 400), (255, 255, 255))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 20)
    d.rectangle((50, 40, 950, 80), fill=(40, 90, 130))
    d.text((70, 48), "Amount Due", fill=(255, 255, 255), font=font)
    d.text((70, 120), "$9,888.00", fill=(0, 0, 0), font=font)
    d.text((600, 120), "01960", fill=(0, 0, 0), font=font)
    d.line((50, 170, 950, 170), fill=(0, 0, 0), width=2)
    d.text((70, 200), "Office Visit", fill=(0, 0, 0), font=font)
    return img


def test_print_on_a_dark_bar_counts_and_the_bar_does_not():
    ink = sheet_pieces.ink_mask(drawn())
    assert ink[48:72, 70:190].sum() > 300
    assert ink[44:47, 400:900].sum() == 0


def test_a_table_rule_is_not_text():
    assert sheet_pieces.text_mask(drawn())[168:173, 300:900].sum() == 0


def test_each_cell_is_its_own_piece_in_reading_order():
    boxes, h = sheet_pieces.pieces(drawn())
    tops = [b[1] for b in boxes.values()]
    assert tops == sorted(tops) and len(boxes) == 4 and h >= 8


def test_dense_bold_print_is_not_thrown_away():
    img = Image.new("RGB", (600, 200), (255, 255, 255))
    ImageDraw.Draw(img).text((50, 80), "$9,888.00", fill=(0, 0, 0), font=ImageFont.truetype(FONT, 15), stroke_width=1, stroke_fill=(0, 0, 0))
    assert len(sheet_pieces.pieces(img)[0]) == 1


def test_the_list_gives_every_piece_a_row():
    img = drawn()
    boxes, _ = sheet_pieces.pieces(img)
    pages = sheet_pieces.lists(img, boxes, FONT)
    assert len(pages) == 1 and pages[0].height == len(boxes) * (sheet_pieces.ROW_H + sheet_pieces.GAP) + sheet_pieces.GAP


def test_a_long_sheet_goes_on_several_lists():
    img = drawn()
    boxes = {i: (70, 120, 180, 140) for i in range(1, sheet_pieces.PAGE_ROWS + 2)}
    assert len(sheet_pieces.lists(img, boxes, FONT)) == 2


def test_print_on_a_rounded_bar_is_a_piece_of_its_own():
    img = Image.new("RGB", (900, 300), (250, 250, 248))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((100, 100, 430, 148), radius=8, fill=(40, 90, 130))
    d.text((120, 113), "Your Responsibility: $8.55", fill=(255, 255, 255), font=ImageFont.truetype(FONT, 18))
    boxes, h = sheet_pieces.pieces(img)
    assert any(b[0] <= 140 and b[2] >= 330 and b[3] - b[1] < 40 for b in boxes.values()), boxes
