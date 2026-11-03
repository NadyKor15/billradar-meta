"""The local model's side of closing, with its answers scripted: what is asked, what is believed, what stops the case."""
import re
from collections import Counter

import pytest
from PIL import Image, ImageDraw, ImageFont

from billradar import local_reader, pipeline, redact
from billradar.local_reader import parse_rows, read_pieces
from billradar.open_lines import Tag
from tests.reading import sheet

FONT = "billradar/fonts/NotoSans-Bold.ttf"


def drawn():
    img = Image.new("RGB", (900, 300), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 22)
    d.text((60, 60), "Amount Due", fill="black", font=font)
    d.text((500, 60), "$719.03", fill="black", font=font)
    d.text((60, 160), "Your Responsibility", fill="black", font=font)
    return img


def test_a_row_is_a_number_a_bar_and_the_text():
    assert parse_rows("1|Amount Due\n 2 | $719.03\nnoise\n3|") == {1: "Amount Due", 2: "$719.03", 3: ""}


def test_a_piece_left_empty_is_read_again_larger(monkeypatch):
    asked = []

    def ask(prompt, page):
        asked.append(page.size)
        return "1|Amount Due\n2|\n3|Your Responsibility" if len(asked) == 1 else "2|$719.03"

    monkeypatch.setattr(local_reader, "_ask", ask)
    pairs, _ = read_pieces(drawn())
    assert [p[0] for p in pairs] == ["Amount Due", "$719.03", "Your Responsibility"]
    assert len(asked) == 2 and asked[1][1] / 1 > (local_reader.AGAIN_ROW_H - 1)  # the second list holds the piece larger


def test_a_piece_read_as_marks_only_counts_as_empty(monkeypatch):
    seen = []

    def ask(prompt, page):
        seen.append(page.size)
        return "1|Amount Due\n2|||\n3|Your Responsibility" if len(seen) == 1 else "2|—"

    monkeypatch.setattr(local_reader, "_ask", ask)
    pairs, _ = read_pieces(drawn())
    assert len(seen) == 2 and not re.search(r"\w", pairs[1][0])


def test_nothing_is_read_again_when_every_piece_was_read(monkeypatch):
    seen = []

    def ask(prompt, page):
        seen.append(1)
        return "1|Amount Due\n2|$719.03\n3|Your Responsibility"

    monkeypatch.setattr(local_reader, "_ask", ask)
    read_pieces(drawn())
    assert len(seen) == 1


def test_a_missing_model_stops_the_case_and_nothing_goes_out(monkeypatch, tmp_path):
    monkeypatch.setenv("BILLRADAR_GLIMMER_DIR", str(tmp_path))
    assert not local_reader.available()
    server = local_reader._Server()
    with pytest.raises(local_reader.NotAvailable):
        server.ask("x", b"y")


def test_a_case_without_the_model_is_refused_as_a_gate(monkeypatch):
    def gone(*a):
        raise local_reader.NotAvailable("no weights")

    monkeypatch.setattr(pipeline, "_prepare", gone)
    with pytest.raises(pipeline.RealDataGate):
        pipeline.run(None, [], [], None, "memorial-2026-05")


def test_a_sheet_that_reads_as_noise_is_turned_and_read_again(monkeypatch):
    img = sheet(["Patient responsibility $2,575.10", "Balance due $676.80"]).rotate(90, expand=True)
    monkeypatch.setattr(local_reader, "turn_of", lambda i: 270)
    assert redact._reading(img).turn == 270


def test_a_sheet_that_reads_well_is_not_asked_about_its_turn(monkeypatch):
    def never(i):
        raise AssertionError("no need to ask")

    monkeypatch.setattr(local_reader, "turn_of", never)
    redact._reading(sheet(["Patient responsibility $2,575.10", "Balance due $676.80"]))


def test_the_sum_check_reads_the_clean_sheet_whole(monkeypatch):
    """A sum in a piece the model left empty is invisible to a count of pieces; the whole reading sees it."""
    img = sheet(["Amount Due"])
    monkeypatch.setattr(local_reader, "transcribe", lambda i, again=False: "Amount Due $15.72" if i is img else "Amount Due")
    redact._read_backs.clear()
    assert redact.amounts_gone(img, Image.new("RGB", img.size, "white")) == ["15.72"]



def test_a_recorded_answer_needs_no_model(tmp_path, monkeypatch):
    img = Image.new("RGB", (40, 20), (250, 250, 248))
    monkeypatch.setattr(local_reader, "RECORDINGS", tmp_path)
    (tmp_path / local_reader.recording_name("q", img)).write_text("the answer")
    assert local_reader._ask("q", img) == "the answer"


def test_another_picture_is_another_question(tmp_path, monkeypatch):
    img = Image.new("RGB", (40, 20), (250, 250, 248))
    other = img.copy()
    other.putpixel((3, 3), (0, 0, 0))
    monkeypatch.setattr(local_reader, "RECORDINGS", tmp_path)
    (tmp_path / local_reader.recording_name("q", img)).write_text("the answer")
    with pytest.raises(local_reader.NotAvailable):
        local_reader._ask("q", other)


def test_an_answer_is_written_only_when_asked(tmp_path, monkeypatch):
    img = Image.new("RGB", (40, 20), (250, 250, 248))
    monkeypatch.setattr(local_reader, "RECORDINGS", tmp_path / "none")
    monkeypatch.setattr(local_reader._server, "ask", lambda prompt, jpeg: "said")
    monkeypatch.delenv(local_reader.RECORD_TO, raising=False)
    assert local_reader._ask("q", img) == "said" and not list(tmp_path.iterdir())
    monkeypatch.setenv(local_reader.RECORD_TO, str(tmp_path))
    local_reader._ask("q", img)
    assert (tmp_path / local_reader.recording_name("q", img)).read_text() == "said"


def counted(monkeypatch, first_clean, first_covered, second_clean, second_covered, pieces=""):
    original, covered = Image.new("RGB", (40, 20), (250, 250, 248)), Image.new("RGB", (40, 20), (240, 240, 240))
    redact.remember(original, [Tag(1, pieces, (0, 0, 40, 20))], 10)
    monkeypatch.setattr(redact, "read_back", lambda img: first_clean if img is original else first_covered)
    monkeypatch.setattr(local_reader, "transcribe", lambda img, again=False: second_clean if img is original else second_covered)
    return redact.amounts_gone(original, covered)


def test_a_column_repeated_by_one_read_holds_nothing(monkeypatch):
    assert counted(monkeypatch, "0.00 " * 12, "0.00 " * 10, "0.00 " * 10, "0.00 " * 10) == []


def test_a_row_skipped_by_one_read_of_the_covered_sheet_holds_nothing(monkeypatch):
    assert counted(monkeypatch, "5.00 5.00", "5.00", "5.00 5.00", "5.00 5.00") == []


def test_a_copy_of_a_sum_gone_on_both_reads_holds_the_sheet(monkeypatch):
    assert counted(monkeypatch, "5.00 5.00", "5.00", "5.00 5.00", "5.00") == ["5.00"]


def test_a_sum_no_read_finds_on_the_covered_sheet_holds_it_at_once(monkeypatch):
    assert counted(monkeypatch, "719.03", "", "", "") == ["719.03"]


def test_a_sum_in_a_piece_counts_even_if_both_whole_reads_missed_it(monkeypatch):
    assert counted(monkeypatch, "", "", "", "", pieces="719.03") == ["719.03"]


def read_as(monkeypatch, text):
    img = Image.new("RGB", (400, 60), (250, 250, 248))
    monkeypatch.setattr(redact, "read_back", lambda i: text)
    return img


def test_a_cut_word_taken_for_a_name_is_no_leak_inside_a_longer_word(monkeypatch):
    img = read_as(monkeypatch, "Patient Responsibility: $0.00")
    assert redact.leaks(img, [redact.Secret("PATIENT", "sibility |", "[PATIENT_3]")], edge=False) == []


def test_a_name_of_one_word_still_lights_as_a_word(monkeypatch):
    s = redact.Secret("PATIENT", "Moreno", "[PATIENT_3]")
    assert redact.leaks(read_as(monkeypatch, "Bill for MORENO, paid"), [s], edge=False) == [s]


def test_a_full_name_run_together_still_lights(monkeypatch):
    s = redact.Secret("PATIENT", "Daniela Moreno", "[PATIENT_1]")
    assert redact.leaks(read_as(monkeypatch, "DANIELAMORENO"), [s], edge=False) == [s]


def test_a_sum_in_an_open_piece_is_not_lost_when_the_whole_read_skips_it(monkeypatch):
    """White on a dark bar, a whole read often skips it; the piece's pixels went back untouched."""
    original, covered = Image.new("RGB", (40, 20), (250, 250, 248)), Image.new("RGB", (40, 20), (240, 240, 240))
    redact.remember(original, [Tag(1, "Your Responsibility: $739.03", (0, 0, 40, 20)), Tag(2, "$739.03", (0, 0, 40, 20))], 10)
    redact._kept(redact._untouched, redact._key(covered), Counter({"739.03": 2}))
    monkeypatch.setattr(redact, "read_back", lambda img: "$739.03" if img is original else "$739.03")
    monkeypatch.setattr(local_reader, "transcribe", lambda img, again=False: "$739.03")
    assert redact.amounts_gone(original, covered) == []


def test_a_sum_outside_the_untouched_pieces_still_counts_as_gone(monkeypatch):
    original, covered = Image.new("RGB", (40, 20), (250, 250, 248)), Image.new("RGB", (40, 20), (240, 240, 240))
    redact.remember(original, [Tag(1, "$739.03", (0, 0, 40, 20))], 10)
    redact._kept(redact._untouched, redact._key(covered), Counter({"5.00": 1}))
    monkeypatch.setattr(redact, "read_back", lambda img: "")
    monkeypatch.setattr(local_reader, "transcribe", lambda img, again=False: "")
    assert redact.amounts_gone(original, covered) == ["739.03"]
