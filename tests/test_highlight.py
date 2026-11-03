"""A line marked on its sheet: only from a real finding, only where this device finds the row. All SYNTHETIC."""

import json
from datetime import date
from decimal import Decimal

import numpy as np
from PIL import Image, ImageDraw

from billradar import highlight, redact, sam
from billradar.case import Case, DocKind, Document, Line, Profile, Source
from billradar.checks import Finding, Kind, Report
from billradar.ledger import Step
from billradar.meta_client import MetaAPIError, MetaClient
from tests.synth import record, sam_events, sheet_quad

SIZE = (1200, 1560)
ROWS = [("99213", "$240.00", 300), ("85610", "$88.00", 380), ("85730", "$196.82", 460), ("99213", "$75.00", 540)]


def sheet() -> Image.Image:
    img = Image.new("RGB", SIZE, (248, 247, 243))
    d = ImageDraw.Draw(img)
    d.text((80, 120), "Statement of services", fill=(20, 20, 20), font=redact._font(40))
    for code, money, y in ROWS:
        d.text((80, y), f"02/11/2025   {code}   Office visit   {money}", fill=(20, 20, 20), font=redact._font(30))
    return img


def jpeg(img: Image.Image) -> bytes:
    return redact.as_sent(img)


def doc() -> Document:
    return Document(doc_id="S2", kind=DocKind.EOB, source=Source.PAPER, lines=[
        Line(line_no=1, code="99213", charges=Decimal("240.00")), Line(line_no=2, code="85610", charges=Decimal("88.00")),
        Line(line_no=3, code="85730", charges=Decimal("196.82")), Line(line_no=4, code="99213", charges=Decimal("75.00"))])


def finding(value="196.82", line=3) -> Finding:
    return Finding(kind=Kind.E2, title="t", detail="d", amount=Decimal(value),
                   trace=[Step(doc_id="S2", line_no=line, field="charges", printed=Decimal(value))])


class FakeSAM:
    """Answers a box prompt with a mask a little larger than the box, or the whole page."""

    def __init__(self, whole_page=False):
        self.whole_page, self.bodies = whole_page, []

    def events(self, body):
        self.bodies.append(body)
        text = body["input"][0]["content"][0]["text"]
        import re
        x1, y1, x2, y2, w, h = (int(v) for v in re.search(r"x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)", text).groups())
        if self.whole_page:
            x1, y1, x2, y2 = 2, 2, w - 3, h - 3
        q = sheet_quad((x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1, 0)
        return sam_events("<0f>" + record(1, q, (w, h), mask_scale=1.0) + "\n")


def client(fake, tmp_path) -> MetaClient:
    return MetaClient(transport=fake, record_to=None, journal=tmp_path / "r.jsonl")


def covered_row(body) -> tuple:
    return body["input"][0]["content"][1]["image_url"]


def test_the_mark_stands_on_the_row_that_prints_the_sum(tmp_path):
    s = sheet()
    m = highlight.mark_for(client(FakeSAM(), tmp_path), 0, finding(), doc(), s, jpeg(s))
    assert m.by == "SAM 3.1" and m.doc_id == "S2" and m.value == "196.82"
    assert m.box[1] - 12 <= 460 <= m.box[3] + 12 and m.outline


def test_of_two_lines_with_one_code_the_right_one_is_marked(tmp_path):
    s = sheet()
    m = highlight.mark_for(client(FakeSAM(), tmp_path), 0, finding("75.00", 4), doc(), s, jpeg(s))
    assert m.box[1] - 12 <= 540 <= m.box[3] + 12  # must differ: line 1 has the same code


def test_only_the_covered_sheet_goes_out(tmp_path):
    s = sheet()
    covered = s.copy()
    ImageDraw.Draw(covered).rectangle((80, 120, 500, 170), fill=(250, 250, 248))
    fake = FakeSAM()
    highlight.mark_for(client(fake, tmp_path), 0, finding(), doc(), s, jpeg(covered))
    url = covered_row(fake.bodies[0])
    assert url.endswith(__import__("base64").b64encode(jpeg(covered)).decode()[-40:])


def test_a_sum_the_sheet_does_not_print_gets_no_mark_and_no_call(tmp_path):
    s, fake = sheet(), FakeSAM()
    assert highlight.mark_for(client(fake, tmp_path), 0, finding("999.99"), doc(), s, jpeg(s)) is None
    assert fake.bodies == []


def test_a_finding_about_another_paper_gets_no_mark(tmp_path):
    f = Finding(kind=Kind.F1, title="t", detail="d", amount=Decimal("196.82"),
                trace=[Step(doc_id="D2", line_no=None, field="patient_balance", printed=Decimal("196.82"))])
    case = Case(case_id="c", policy_id="memorial-2026-05", today=date(2026, 3, 2), profile=Profile(household_size=1, annual_income=Decimal(1)),
                documents=[doc()])
    from billradar.checks import Report
    rep = Report(case_id="c", policy_id="p", fpl_pct=Decimal(100), findings=[f], no_money=[], held_back=[], total_may_come_off=Decimal(0), apply_by=None)
    assert highlight.marks(client(FakeSAM(), tmp_path), case, rep, tmp_path, tmp_path) == []


def test_a_mask_that_took_the_page_is_not_trusted(tmp_path):
    s = sheet()
    m = highlight.mark_for(client(FakeSAM(whole_page=True), tmp_path), 0, finding(), doc(), s, jpeg(s))
    assert m.by == "this device" and m.outline == [] and m.box[1] - 12 <= 460 <= m.box[3] + 12


def test_the_mark_keeps_the_print_readable_and_can_be_stored(tmp_path):
    s = sheet()
    m = highlight.mark_for(client(FakeSAM(), tmp_path), 0, finding(), doc(), s, jpeg(s))
    out = highlight.render(s, m)
    a, b = np.asarray(s, dtype=np.int16), np.asarray(out, dtype=np.int16)
    assert (a != b).any() and (a[:200] == b[:200]).all()  # must light: only the row changed
    x0, y0, x1, y1 = m.box
    assert (a[y0:y1, x1 - 3:x1] != b[y0:y1, x1 - 3:x1]).any()  # the band reaches the end of the row, where the sum stands
    highlight.save([m], tmp_path)
    assert highlight.load(tmp_path) == [m]


class Saved:
    def __init__(self, f, d):
        self.case = Case(case_id="t", policy_id="memorial-2026-05", today=date(2026, 6, 15), documents=[d],
                         profile=Profile(household_size=3, annual_income=Decimal(50000)))
        self.report = Report(case_id="t", policy_id="memorial-2026-05", fpl_pct=Decimal(200), findings=[f], no_money=[],
                             held_back=[], total_may_come_off=Decimal("196.82"), apply_by=None)


def saved(tmp_path, covered=True):
    s = sheet()
    (tmp_path / "sheets").mkdir()
    (tmp_path / "sent-sheets").mkdir()
    s.save(tmp_path / "sheets" / "S2.jpg", quality=95)
    (tmp_path / "sheets" / highlight.PRINTED).write_text(json.dumps({"S2": redact.stored_lines(s)}))
    if covered:
        (tmp_path / "sent-sheets" / "S2.jpg").write_bytes(jpeg(s))
    return Saved(finding(), doc())


def test_a_saved_case_keeps_its_marks_next_to_it(tmp_path):
    highlight.attach(client(FakeSAM(), tmp_path), saved(tmp_path), tmp_path)
    assert [m.doc_id for m in highlight.load(tmp_path)] == ["S2"] and (tmp_path / "marked" / "0.jpg").exists()


def test_a_sheet_that_never_went_out_gets_no_call(tmp_path):
    fake = FakeSAM()
    highlight.attach(client(fake, tmp_path), saved(tmp_path, covered=False), tmp_path)
    assert fake.bodies == [] and not (tmp_path / "highlights.json").exists()


def test_a_failed_call_leaves_the_case_as_it_is(tmp_path):
    class Down(FakeSAM):
        def events(self, body):
            raise MetaAPIError("HTTP 500")
    highlight.attach(client(Down(), tmp_path), saved(tmp_path), tmp_path)
    assert not (tmp_path / "highlights.json").exists() and highlight.load(tmp_path) == []


def test_the_filmed_example_opens_with_the_sum_of_the_photos(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from billradar import app as app_module, example
    runs = tmp_path / "runs"
    runs.mkdir()
    example._from_seed(runs, example.DEMO_CASES)
    monkeypatch.setattr(app_module, "RUNS", runs)
    monkeypatch.setattr(example, "ensure", lambda *_: None)
    c = TestClient(app_module.app)
    page = c.get(f"/cases/{example.VIDEO_ID}", headers={"accept": "text/html"})
    assert page.status_code == 200, page.text[:300]
    assert "1,596" in page.text
    import json
    unread = json.loads((app_module._load(example.VIDEO_ID)[0] / "problems.json").read_text())["unreadable"]
    assert page.text.count('class="retake"') == len(unread) and "could not be read" not in page.text
    assert "Check sheet 12." in page.text and "its readings do not all agree" in page.text  # read, but the reads disagree
    # the lighter look of frames from a video rides on the attribute: it must reach the browser unescaped (03.11)
    assert page.text.count('class="retake" role="alert" data-from="video"') == len(unread) and "&#34;video" not in page.text
    photo = c.get("/cases/example", headers={"accept": "text/html"})
    assert photo.status_code == 200 and 'data-from="video"' not in photo.text
    case = app_module._load(example.VIDEO_ID)[2]
    assert str(case.total_may_come_off) == "1596.53"
    assert c.get(f"/cases/{example.VIDEO_ID}/sheet/S14.jpg").status_code == 200
    assert example.VIDEO_ID in example.READ_ONLY


def test_examples_baked_into_the_image_are_copied_once_and_never_over_a_run(tmp_path):
    from billradar import example
    seed, runs = tmp_path / "seed", tmp_path / "runs"
    (seed / "example").mkdir(parents=True)
    (seed / "example" / "case.json").write_text("baked")
    runs.mkdir()
    example._from_seed(runs, seed)
    assert (runs / "example" / "case.json").read_text() == "baked"
    (runs / "example" / "case.json").write_text("in use")
    example._from_seed(runs, seed)
    assert (runs / "example" / "case.json").read_text() == "in use"
    example._from_seed(runs, tmp_path / "nowhere")  # no seed outside the image


def test_a_mask_is_measured_by_what_it_paints_not_by_its_box():
    row = (100, 500, 1100, 524)  # 1000 x 24
    thin = np.zeros((70, 1100), dtype=np.uint8)
    thin[20:50, :] = 1
    assert highlight._trusted(sam.Detection("o", (90, 480, 1190, 550), 0.3, thin), row)  # the live case: 3 rows tall, one painted
    full = np.ones((70, 1100), dtype=np.uint8)
    assert not highlight._trusted(sam.Detection("o", (90, 480, 1190, 550), 0.3, full), row)  # must differ: the same box, all painted

