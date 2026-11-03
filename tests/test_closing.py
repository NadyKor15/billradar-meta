"""What leaves a sheet: only the pixels of open pieces, on smooth background. Drawn sheets, no model."""
from collections import Counter

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from billradar import closing, redact, sheet_pieces
from billradar.open_lines import Tag, Verdict

FONT = "billradar/fonts/NotoSans-Bold.ttf"


def sheet():
    img = Image.new("RGB", (1000, 700), (250, 250, 248))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 22)
    d.text((80, 80), "GRACE HUNTER", fill=(20, 20, 20), font=font)
    d.text((80, 160), "Amount Due", fill=(20, 20, 20), font=font)
    d.text((500, 160), "$719.03", fill=(20, 20, 20), font=font)
    d.text((80, 300), "unread line", fill=(20, 20, 20), font=font)
    d.line((40, 260, 960, 260), fill=(0, 0, 0), width=2)
    side = Image.new("RGB", (300, 26), (250, 250, 248))
    ImageDraw.Draw(side).text((2, 2), "HLNX 007494 001 OF 001", fill=(120, 120, 120), font=ImageFont.truetype(FONT, 16))
    img.paste(side.rotate(90, expand=True), (8, 200))  # a pale line up the margin that nobody read
    return img


def ink_in(img, box):
    return int(sheet_pieces.text_mask(img)[box[1]:box[3], box[0]:box[2]].sum())


def tags_and_verdicts():
    boxes, h = sheet_pieces.pieces(sheet())
    tags, verdicts = [], {}
    for k, b in boxes.items():
        name = b[1] < 120
        tags.append(Tag(k, "GRACE HUNTER" if name else "x", b))
        verdicts[k] = Verdict("closed", "known") if name or b[1] > 280 or b[0] < 60 else Verdict("open", "money")
    return tags, verdicts, h


def closed_sheet():
    tags, verdicts, h = tags_and_verdicts()
    return closing.close(sheet(), tags, verdicts, redact.Vault(), h)


def test_a_closed_line_leaves_no_ink():
    assert ink_in(sheet(), (70, 70, 300, 115)) > 500  # control: it was there
    assert ink_in(closed_sheet(), (70, 70, 300, 115)) == 0


def test_an_open_piece_keeps_its_pixels():
    before, after = np.asarray(sheet()), np.asarray(closed_sheet())
    assert np.array_equal(before[155:190, 500:600], after[155:190, 500:600])


def test_ink_nobody_read_is_gone_too():
    boxes, h = sheet_pieces.pieces(sheet())
    img = closing.close(sheet(), [], {}, redact.Vault(), h)
    assert ink_in(img, (0, 0, 1000, 700)) < 1500  # only what is left of the rule at most
    assert ink_in(img, (0, 190, 38, 520)) == 0  # the margin line


def test_a_pale_line_up_the_margin_leaves_no_ghost():
    img = closed_sheet()
    strip = np.asarray(img.convert("L"))[200:500, 8:34].astype(int)
    assert strip.max() - strip.min() < 12


def test_table_rules_stay():
    assert np.asarray(closed_sheet().convert("L"))[258:263, 300:700].min() < 90


def test_a_token_stands_where_the_value_was():
    vault = redact.Vault(seed={("PATIENT", "Grace Hunter"): "[PATIENT_1]"})
    assert closing.token_of("GRACE HUNTER", "", vault) == "[PATIENT_1]"


def test_the_given_name_says_who_when_a_family_shares_a_surname():
    vault = redact.Vault(seed={("PATIENT", "Daniela Castillo"): "[PATIENT_1]", ("PATIENT", "Adrian James Castillo"): "[PATIENT_2]"})
    assert closing.token_of("CASTILLO, ADRIAN", "", vault) == "[PATIENT_2]"
    assert closing.token_of("Castillo , Daniela", "", vault) == "[PATIENT_1]"


def line_sheet():
    img = Image.new("RGB", (1000, 200), (250, 250, 248))
    d = ImageDraw.Draw(img)
    d.text((80, 80), "statement code - PXVEVrdx $719.03", fill=(20, 20, 20), font=ImageFont.truetype(FONT, 22))
    return img


def piece():
    img = line_sheet()
    boxes, h = sheet_pieces.pieces(img)
    return img, list(boxes.values())[0], h


def test_a_hidden_value_ends_in_a_gap_between_words():
    img, box, h = piece()
    text = "statement code - PXVEVrdx $719.03"
    start, end = text.index("PXV"), text.index(" $")
    out = closing.close(img, [Tag(1, text, box)], {1: Verdict("open", "money only", [(start, end, "")])}, redact.Vault(), h)
    runs = closing._word_runs(box, sheet_pieces.text_mask(img), h, 5)
    before, after = sheet_pieces.text_mask(img), sheet_pieces.text_mask(out)
    assert after[box[1]:box[3], runs[3][0]:runs[3][1]].sum() == 0  # not a stroke of the first letter stays
    assert np.array_equal(before[box[1]:box[3], runs[4][0]:runs[4][1]], after[box[1]:box[3], runs[4][0]:runs[4][1]])  # the sum whole


def test_when_the_ink_does_not_give_the_words_the_whole_piece_closes():
    img, box, h = piece()
    text = "statement code one two three four five six seven eight nine $719.03"  # more words than the ink shows
    out = closing.close(img, [Tag(1, text, box)], {1: Verdict("open", "money only", [(0, 10, "")])}, redact.Vault(), h)
    assert ink_in(out, box) == 0


def test_a_value_at_the_end_of_a_line_takes_the_stars_after_it():
    img = Image.new("RGB", (900, 120), (250, 250, 248))
    ImageDraw.Draw(img).text((20, 40), "statement code - PXVEVrdx ****", fill=(20, 20, 20), font=ImageFont.truetype(FONT, 22))
    box, h = (20, 40, 460, 70), 22
    text = "statement code - PXVEVrdx ****"
    start, end = text.index("PXV"), text.index(" ****")
    out = closing.close(img, [Tag(1, text, box)], {1: Verdict("open", "text", [(start, end, "")])}, redact.Vault(), h)
    runs = closing._word_runs(box, sheet_pieces.text_mask(img), h, 5)
    assert sheet_pieces.text_mask(out)[box[1]:box[3], runs[3][0]:runs[4][1] + 1].sum() == 0


def test_a_token_on_a_dark_bar_is_light():
    img = Image.new("RGB", (600, 120), (250, 250, 248))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 20, 600, 90), fill=(40, 80, 130))
    d.text((40, 40), "Member ID: 16791689883", fill=(250, 250, 250), font=ImageFont.truetype(FONT, 20))
    box, h = (40, 40, 330, 66), 20
    text = "Member ID: 16791689883"
    out = closing.close(img, [Tag(1, text, box)], {1: Verdict("open", "label", [(text.index("1679"), len(text), "MEMBER")])}, redact.Vault(), h)
    px = np.array(out.convert("L"))[40:66, 150:330]
    assert px.max() > 200


def test_the_sums_left_as_printed_are_counted_and_a_hidden_value_is_not():
    img, box, h = piece()
    text = "statement code - PXVEVrdx $719.03"
    start, end = text.index("PXV"), text.index(" $")
    kept = Counter()
    closing.close(img, [Tag(1, text, box)], {1: Verdict("open", "money only", [(start, end, "")])}, redact.Vault(), h, kept)
    assert kept == Counter({"719.03": 1})
    kept = Counter()
    closing.close(img, [Tag(1, text, box)], {1: Verdict("closed", "no class")}, redact.Vault(), h, kept)
    assert not kept


def test_a_cut_word_after_a_label_never_becomes_a_family_value():
    """"Patient sibility" is a misread of "Patient Responsibility": as a value it would close that label on every later sheet."""
    img, box, h = piece()
    vault = redact.Vault()
    text = "Patient sibility | $0.00"
    closing.close(img, [Tag(1, text, box)], {1: Verdict("open", "money only", [(text.index("sib"), text.index("$"), "PATIENT")])}, vault, h)
    assert "sibility" not in " ".join(s.value for s in vault.secrets)


def test_a_name_after_a_label_is_still_learned():
    assert closing.token_of("Rosa Hunter", "PATIENT", (v := redact.Vault())) and any(s.value == "Rosa Hunter" for s in v.secrets)
    assert closing.token_of("4788416", "ACCT", (v := redact.Vault())) and any(s.value == "4788416" for s in v.secrets)
