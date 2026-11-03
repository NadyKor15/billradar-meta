"""A video of the table: the clip stays here, a soft copy goes out, sheets are cut from the clip. All SYNTHETIC."""

import base64
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from billradar import meta_client, redact, sam, video
from billradar.meta_client import MetaClient, check_body, video_cost, worst_case
from tests.synth import WOOD, record, sam_events, sheet_quad

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="no ffmpeg")
SIZE = (720, 1280)
WORDS = ["INVOICE", "STATEMENT", "BALANCE", "PAYMENT", "HOSPITAL", "INSURANCE", "SERVICE", "ACCOUNT", "CHARGES",
         "DISCOUNT", "COVERAGE", "PROVIDER", "PATIENT", "ADJUSTED", "ALLOWED", "BENEFITS"]


def paper(seed: int, w=400, h=520) -> np.ndarray:
    img = np.full((h, w, 3), 245, dtype=np.uint8)
    for k in range(12):
        text = f"{WORDS[(seed + k) % 16]} {WORDS[(seed * 3 + k * 5) % 16]} {1000 + seed * 37 + k}"
        cv2.putText(img, text, (14, 34 + k * 40), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (20, 20, 20), 2, cv2.LINE_AA)
    return img


NUMBERS = {"1037", "1038", "1039", "1040", "1041", "1042", "1043"}


def one_paper(img) -> set[str]:
    """What the local model reads when every cut is the same paper: its numbers on a sharp cut, nothing on a smeared one."""
    return NUMBERS if cv2.Laplacian(np.asarray(img.convert("L")), cv2.CV_64F).var() >= 60 else set()


@pytest.fixture(autouse=True)
def no_numbers_by_default(monkeypatch):
    monkeypatch.setattr(video, "_numbers", lambda img: set())


def stage(papers: dict[int, np.ndarray], places: dict[int, tuple[int, int]]) -> np.ndarray:
    W, H = SIZE
    img = np.full((H, W, 3), WOOD, dtype=np.uint8)
    for i, (x, y) in places.items():
        p = papers[i]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(W, x + p.shape[1]), min(H, y + p.shape[0])
        if x1 > x0 and y1 > y0:
            img[y0:y1, x0:x1] = p[y0 - y:y1 - y, x0 - x:x1 - x]
    return img


def place(i: int, t: float) -> tuple[int, int]:
    """Sheets slide past the camera one after another: each is whole in the middle of its pass."""
    return 160, int(380 + (t - (0.9 + i * 1.2)) * 620)


def encode(path: Path, seconds: float = 3.6, count: int = 2, extra: tuple = (), fps: int = 30, fix=None) -> Path:
    papers = {i: paper(i) for i in range(count)}
    W, H = SIZE
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           *extra, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv420p", str(path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(int(seconds * fps)):
        t = n / fps
        places = {i: (fix(i, t) if fix else place(i, t)) for i in range(count)}
        p.stdin.write(stage(papers, places).tobytes())
    p.stdin.close()
    assert p.wait() == 0
    return path


class FakeVideoSAM:
    """Answers like SAM on the copy it was sent: a stable id per sheet, one line per frame, boxes in the copy's pixels."""

    def __init__(self, count=2, ids=None, fix=None):
        self.count, self.ids, self.fix = count, ids or (lambda i, t: i), fix
        self.bodies = []
        self.copy = None

    def events(self, body):
        self.bodies.append(body)
        url = body["input"][0]["content"][1]["video_url"]
        self.copy = base64.b64decode(url.split(",", 1)[1])
        out = Path(self.tmp) / "got.mp4"
        out.write_bytes(self.copy)
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                                          "stream=width,height,nb_read_frames", "-of", "json", str(out)],
                                         capture_output=True, text=True).stdout)["streams"][0]
        w, h, frames = info["width"], info["height"], int(info["nb_read_frames"])
        k = np.array([w / SIZE[0], h / SIZE[1]])
        lines = []
        for n in range(frames):
            t = n / 10
            recs = []
            for i in range(self.count):
                x, y = (self.fix or place)(i, t)
                if y >= SIZE[1] or y + 520 <= 0:
                    continue
                top, bottom = max(0, y), min(SIZE[1] - 1, y + 519)
                q = sheet_quad(x + 200, (top + bottom) / 2, 400, bottom - top, 0) * k
                recs.append(record(self.ids(i, t), np.clip(q, 0, [w - 1, h - 1]).astype(np.float32), (w, h)))
            if recs:
                lines.append(f"<{n}f>" + ",".join(recs))
        return sam_events("\n".join(lines) + "\n")


def client_for(fake, tmp_path) -> MetaClient:
    fake.tmp = tmp_path
    return MetaClient(transport=fake, record_to=None, journal=tmp_path / "requests.jsonl")


@pytest.fixture
def clip(tmp_path) -> bytes:
    return encode(tmp_path / "clip.mp4").read_bytes()


def streams(path: Path) -> dict:
    return json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,"
                                      "r_frame_rate:stream_tags:format_tags", "-of", "json", str(path)],
                                     capture_output=True, text=True).stdout)


# --- what leaves the device ---------------------------------------------------------------------

def test_the_copy_has_no_sound_no_metadata_and_is_small(tmp_path):
    src = encode(tmp_path / "with-all.mp4", extra=("-f", "lavfi", "-i", "sine=frequency=440:duration=3.6", "-metadata",
                                                   "title=SECRET-TITLE", "-metadata", "location=+27.9-082.4/",
                                                   "-c:a", "aac", "-shortest"))
    have = streams(src)
    assert {s["codec_type"] for s in have["streams"]} == {"video", "audio"}  # must light
    assert "SECRET-TITLE" in json.dumps(have)  # must light
    c = video.probe(src)
    raw, _ = video.soft_copy(c, [], tmp_path)
    out = tmp_path / "out.mp4"
    out.write_bytes(raw)
    got = streams(out)
    assert [s["codec_type"] for s in got["streams"]] == ["video"]
    v = got["streams"][0]
    assert v["codec_name"] == "h264" and max(v["width"], v["height"]) <= video.SOFT_SIDE and v["r_frame_rate"] == "10/1"
    text = json.dumps(got)
    assert "SECRET-TITLE" not in text and "27.9" not in text and "location" not in text and "creation_time" not in text


def test_nothing_on_the_papers_can_be_read_on_the_copy(tmp_path):
    c = video.probe(encode(tmp_path / "clip.mp4"))
    raw, sigma = video.soft_copy(c, [], tmp_path)
    copy = tmp_path / "copy.mp4"
    copy.write_bytes(raw)
    sharp, soft = video.frames_at(c.path, [10])[10], video.frames_at(copy, [10])[10]
    def edges(img):
        return cv2.Laplacian(np.asarray(img.convert("L")), cv2.CV_64F).var()

    assert edges(sharp) > 5 * edges(soft) and sigma >= video.SOFT_SIDE / 150  # must differ: the clip itself is sharp


def test_a_family_value_still_readable_blurs_the_copy_more(tmp_path, monkeypatch):
    c = video.probe(encode(tmp_path / "clip.mp4"))
    seen = []
    monkeypatch.setattr(video, "still_readable", lambda *a: seen.append(a[0]) or len(seen) < 2)
    _, sigma = video.soft_copy(c, [], tmp_path)
    assert len(seen) == 2 and sigma == pytest.approx(video.SOFT_SIDE / 150 * 1.6)


def test_a_copy_that_stays_readable_is_never_sent(tmp_path, monkeypatch):
    monkeypatch.setattr(video, "still_readable", lambda *a: True)
    fake = FakeVideoSAM()
    raw = encode(tmp_path / "clip.mp4").read_bytes()
    with pytest.raises(video.VideoError, match="not sent"):
        video.find_sheets(client_for(fake, tmp_path), raw)
    assert fake.bodies == []


def test_only_the_soft_copy_reaches_the_model(tmp_path, clip):
    fake = FakeVideoSAM()
    video.find_sheets(client_for(fake, tmp_path), clip)
    body = fake.bodies[0]
    assert hashlib.sha256(fake.copy).digest() != hashlib.sha256(clip).digest() and clip not in fake.copy
    assert len(fake.copy) < len(clip)
    part = body["input"][0]["content"][1]
    assert part["type"] == "input_video" and part["video_url"].startswith("data:video/mp4;base64,")
    assert body["model"] == "sam-3.1" and "file_id" not in part  # no file left in Meta's storage
    check_body(body)


# --- what comes back ----------------------------------------------------------------------------

def test_every_sheet_is_cut_from_the_clip_in_the_order_it_appears(tmp_path, clip):
    found = video.find_sheets(client_for(FakeVideoSAM(), tmp_path), clip)
    r = found.result
    assert [s.doc_id for s in r.sheets] == ["S1", "S2"] and r.original_size == SIZE
    assert all(s.straightened for s in r.sheets)
    for s in r.sheets:  # cut from the sharp clip, not from the soft copy
        assert one_paper(s.image), s.doc_id
    a, b = [np.asarray(s.image.convert("L")) for s in r.sheets]
    assert a.shape != b.shape or (a != b).any()
    assert found.frames_sent == 36 and found.soft.size == video._soft_size(SIZE) and found.strip.width > 0


def test_a_sheet_never_whole_in_the_frame_is_named_not_cut(tmp_path):
    fix = lambda i, t: (160, -200 if i == 0 else int(380 + (t - 1.8) * 300))  # noqa: E731 - sheet 0 stays cut by the top edge
    raw = encode(tmp_path / "cut.mp4", fix=fix).read_bytes()
    r = video.find_sheets(client_for(FakeVideoSAM(fix=fix), tmp_path), raw).result
    assert len(r.sheets) == 1 and any("never whole" in d for d in r.dropped)


def test_a_flicker_is_not_a_sheet():
    box = (10.0, 10.0, 200.0, 260.0)
    kept, dropped = video.choose({"7": [video.Seen(n, box) for n in range(video.MIN_SEEN - 1)]}, (720, 1280))
    assert kept == [] and "seen for" in dropped[0]


def test_a_strip_of_table_is_not_sheet_shaped():
    kept, dropped = video.choose({"7": [video.Seen(n, (10.0, 10.0, 700.0, 40.0)) for n in range(6)]}, (720, 1280))
    assert kept == [] and "not sheet-shaped" in dropped[0]


def test_the_sharpest_of_a_sheets_frames_is_kept():
    frames = {1: Image.fromarray(stage({0: paper(0)}, {0: (160, 380)})).filter(_blur()), 2: Image.fromarray(stage({0: paper(0)}, {0: (160, 380)}))}
    seen = [video.Seen(1, (160.0, 380.0, 560.0, 900.0)), video.Seen(2, (160.0, 380.0, 560.0, 900.0))]
    assert video.cut_best("0", seen, frames).seen.frame == 2


def _blur():
    from PIL import ImageFilter
    return ImageFilter.GaussianBlur(3)


def test_a_sheet_that_left_and_came_back_is_one_sheet(tmp_path, monkeypatch):
    """SAM gives it a new id on return; the words on the cut say it is the same paper."""
    monkeypatch.setattr(video, "_numbers", one_paper)
    fix = lambda i, t: (160, int(380 + (((t + 0.6) % 1.8) - 0.9) * 700))  # noqa: E731
    raw = encode(tmp_path / "back.mp4", count=1, fix=fix).read_bytes()
    fake = FakeVideoSAM(count=1, fix=fix, ids=lambda i, t: 0 if t < 1.8 else 5)
    r = video.find_sheets(client_for(fake, tmp_path), raw).result
    assert len(r.sheets) == 1 and any("same sheet" in d for d in r.dropped)


def test_two_pages_of_one_form_stay_two_sheets(tmp_path, clip):
    """They share their words, not their numbers: taking them for one paper would lose a sheet with no word said."""
    r = video.find_sheets(client_for(FakeVideoSAM(), tmp_path), clip).result
    assert len(r.sheets) == 2


def test_a_turned_phone_video_uses_its_displayed_size(tmp_path):
    src = encode(tmp_path / "flat.mp4")
    turned = tmp_path / "turned.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-display_rotation", "90", "-i", str(src), "-c", "copy", str(turned)], check=True)
    assert video.probe(turned).size == (SIZE[1], SIZE[0])


def test_not_a_video_says_so(tmp_path):
    with pytest.raises(video.VideoError, match="could not be opened"):
        video.find_sheets(client_for(FakeVideoSAM(), tmp_path), b"this is not a video")


def test_too_long_a_video_is_refused_before_anything_is_sent(tmp_path, monkeypatch):
    monkeypatch.setattr(video, "MAX_SECONDS", 2)
    fake = FakeVideoSAM()
    with pytest.raises(video.VideoError, match="keep it under"):
        video.find_sheets(client_for(fake, tmp_path), encode(tmp_path / "clip.mp4").read_bytes())
    assert fake.bodies == []


# --- what it costs ------------------------------------------------------------------------------

def test_a_video_is_billed_per_frame_with_a_floor():
    assert video_cost(200) == pytest.approx(0.04) and video_cost(10) == pytest.approx(0.01)  # 50 frames at least


def test_a_video_reserves_the_longest_clip_and_a_photo_keeps_its_price():
    v = {"model": "sam-3.1", "input": [{"content": [{"type": "input_video", "video_url": "data:video/mp4;base64,AA"}]}]}
    p = {"model": "sam-3.1", "input": [{"content": [{"type": "input_image", "image_url": "data:image/jpeg;base64,AA"}]}]}
    assert worst_case(v) == pytest.approx(video_cost(meta_client.MAX_VIDEO_FRAMES)) and worst_case(p) == pytest.approx(0.0025)


def test_the_journal_settles_a_video_at_the_frames_it_got(tmp_path, monkeypatch):
    ledger = meta_client.SpendLedger(tmp_path / "spend.jsonl", cap=9.8)
    t = meta_client.LiveTransport("k", ledger=ledger)
    lines = "".join(f"<{n}f>0<|box;x1=1;y1=1;x2=9;y2=9;w=20;h=20|>\n" for n in range(120))

    class R:
        status_code, headers, text = 200, {}, ""

        def iter_lines(self):
            yield ("data: " + json.dumps({"type": "response.output_text.delta", "delta": lines})).encode()
            yield ("data: " + json.dumps({"type": "response.completed", "response": {"id": "r", "usage": {}}})).encode()

    monkeypatch.setattr(meta_client.requests, "post", lambda *a, **k: R())
    t.events({"model": "sam-3.1", "input": [{"content": [{"type": "input_video", "video_url": "data:video/mp4;base64,AA"}]}]})
    spent = sum(json.loads(x)["usd"] for x in (tmp_path / "spend.jsonl").read_text().splitlines())
    assert spent == pytest.approx(0.024)


# --- the photo path and the recordings stay as they were ----------------------------------------

def test_a_photo_still_costs_one_image_and_sends_an_image(tmp_path):
    assert sam.request_body(b"x")["input"][0]["content"][1]["type"] == "input_image"


def test_sam_copy_of_a_photo_is_not_changed_by_the_video_path():
    assert redact.sam_copy.__defaults__ == (900, None, 4)


# --- through the same gate as a photo -----------------------------------------------------------

def _profile():
    from decimal import Decimal

    from billradar.case import Person, Profile, Role
    return Profile(household_size=4, annual_income=Decimal("85000"), insured=True,
                   people=[Person(token="PATIENT_1", role=Role.MOTHER, name="Anna Sample")])


class Reader(FakeVideoSAM):
    """SAM for the video, an empty reading for everything else: this test is about what gets sent."""

    def __init__(self):
        super().__init__()
        self.images = []

    def events(self, body):
        if body["model"] == "sam-3.1":
            return super().events(body)
        self.images += [p["image_url"] for item in body["input"] if isinstance(item.get("content"), list)
                        for p in item["content"] if p.get("type") == "input_image"]
        return [{"type": "response.output_text.delta", "delta": json.dumps({"documents": []})},
                {"type": "response.completed", "response": {"id": "r", "usage": {}}}]


def test_a_video_outside_private_mode_is_refused(tmp_path, clip):
    from datetime import date

    from billradar import pipeline
    with pytest.raises(pipeline.RealDataGate, match="private mode"):
        pipeline.run(client_for(FakeVideoSAM(), tmp_path), [], [], _profile(), "memorial-2026-05", today=date(2026, 3, 2), video=clip)


def test_every_sheet_from_a_video_passes_the_leak_gate_before_it_is_sent(tmp_path, clip, monkeypatch):
    from datetime import date

    from billradar import pipeline
    gated = []
    real = pipeline._no_leaks
    monkeypatch.setattr(pipeline, "_no_leaks", lambda img, vault, doc_id: gated.append(doc_id) or real(img, vault, doc_id))
    run = pipeline.run(client_for(Reader(), tmp_path), [], [], _profile(), "memorial-2026-05", today=date(2026, 3, 2),
                       private=True, video=clip)
    assert gated == ["S1", "S2"] and [s.doc_id for s in run.sheets] == ["S1", "S2"]
    assert set(run.originals) == {"S1", "S2"} and run.redacted and len(run.overlays) == 1


def test_photos_and_a_video_number_their_sheets_as_one_pile(tmp_path, clip):
    from datetime import date

    from billradar import pipeline
    from tests.synth import FakeSAM, table_photo
    quads = [sheet_quad(500, 470, 520, 670, -6), sheet_quad(1180, 450, 520, 670, 4)]

    class Both(Reader):
        def __init__(self):
            super().__init__()
            self.photo = FakeSAM(quads, (2400, 1800))

        def events(self, body):
            if body["model"] == "sam-3.1" and body["input"][0]["content"][1]["type"] == "input_image":
                return self.photo.events(body)
            return super().events(body)

    run = pipeline.run(client_for(Both(), tmp_path), [table_photo(quads)], [], _profile(), "memorial-2026-05",
                       today=date(2026, 3, 2), private=True, video=clip)
    assert [s.doc_id for s in run.sheets] == ["S1", "S2", "S3", "S4"]


def test_the_photo_path_in_the_pipeline_has_not_moved():
    """Everything the video added sits behind `if video is not None`."""
    import inspect

    from billradar import pipeline
    src = inspect.getsource(pipeline._prepare)
    assert inspect.signature(pipeline.run).parameters["video"].default is None
    head, rest = src.split("if video is not None:  # one more source", 1)
    assert "found = find_sheets(client, photo, send=to_sam, crop_from=as_taken)" in head
    assert "lost: dict[str, list[str]] = {}" in rest and "clips." not in head.replace("video is not None", "")


# --- what the first live clip taught ------------------------------------------------------------

def test_of_a_sheets_frames_the_one_where_the_camera_stood_still_wins_not_the_largest(tmp_path):
    """Sheet 0 is largest while it moves; it stands still, a little smaller, for one second."""
    pause = lambda t: 1.4 <= t <= 2.4  # noqa: E731

    def fix(i, t):
        return (160 + (0 if pause(t) else int(t * 400) % 60), 380)

    def blur_moves(frame_t):
        return not pause(frame_t)

    raw_path = tmp_path / "pause.mp4"
    papers = {0: paper(0)}
    W, H = SIZE
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "30", "-i", "-",
                          "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv420p", str(raw_path)], stdin=subprocess.PIPE)
    for n in range(108):
        t = n / 30
        img = stage(papers, {0: fix(0, t)})
        p.stdin.write((cv2.GaussianBlur(img, (0, 0), 3) if blur_moves(t) else img).tobytes())
    p.stdin.close()
    assert p.wait() == 0
    found = video.find_sheets(client_for(FakeVideoSAM(count=1, fix=fix), tmp_path), raw_path.read_bytes())
    assert len(found.result.sheets) == 1 and one_paper(found.result.sheets[0].image)  # the blurred frames read nothing


def test_masks_are_read_only_for_the_frames_in_use(tmp_path, monkeypatch):
    seen = []
    real = video.video_segmentation_format

    class Spy:
        def create_parser(self):
            inner = real().create_parser()

            class P:
                def push(self, text):
                    seen.append(text)
                    inner.push(text)

                def finish(self, outcome):
                    return inner.finish(outcome)
            return P()
    monkeypatch.setattr(video, "video_segmentation_format", Spy)
    raw = encode(tmp_path / "clip.mp4").read_bytes()
    video.find_sheets(client_for(FakeVideoSAM(), tmp_path), raw)
    frames = video.FRAME.findall(seen[0])
    assert len(seen) == 1 and 0 < len(frames) <= 2 * video.PICK < 36


# --- the 16 places of one request ---------------------------------------------------------------

def test_a_long_clip_goes_out_in_overlapping_pieces():
    got = video.pieces(575)
    assert got[0][0] == 0 and sum(c for _, c in got) < 2 * 575 and got[-1][0] + got[-1][1] == 575
    for (a, n), (b, _) in zip(got, got[1:]):
        assert n <= video.WINDOW and a + n - b >= video.OVERLAP  # the join is seen twice


def test_a_short_clip_is_one_request():
    assert video.pieces(36) == [(0, 36)] and video.pieces(video.WINDOW) == [(0, video.WINDOW)]


class FakeTracker(FakeVideoSAM):
    """Like the live model: 16 objects in one request, then nobody new."""

    def __init__(self, count, fix):
        super().__init__(count=count, fix=fix)
        self.requests = 0

    def events(self, body):
        self.requests += 1
        self.bodies.append(body)
        url = body["input"][0]["content"][1]["video_url"]
        out = Path(self.tmp) / f"got-{self.requests}.mp4"
        out.write_bytes(base64.b64decode(url.split(",", 1)[1]))
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                                          "stream=width,height,nb_read_frames", "-of", "json", str(out)],
                                         capture_output=True, text=True).stdout)["streams"][0]
        w, h, frames = info["width"], info["height"], int(info["nb_read_frames"])
        k = np.array([w / SIZE[0], h / SIZE[1]])
        start = self.starts[self.requests - 1]
        lines, known = [], {}
        for n in range(frames):
            t = (n + start) / 10
            recs = []
            for i in range(self.count):
                x, y = self.fix(i, t)
                if y >= SIZE[1] or y + 520 <= 0:
                    continue
                if i not in known:
                    if len(known) == self.cap:
                        continue
                    known[i] = len(known)
                top, bottom = max(0, y), min(SIZE[1] - 1, y + 519)
                q = sheet_quad(x + 200, (top + bottom) / 2, 400, bottom - top, 0) * k
                recs.append(record(known[i], np.clip(q, 0, [w - 1, h - 1]).astype(np.float32), (w, h)))
            if recs:
                lines.append(f"<{n}f>" + ",".join(recs))
        return sam_events("\n".join(lines) + "\n")


def test_sheets_past_the_sixteenth_object_are_still_found(tmp_path, monkeypatch):
    """Four sheets pass the camera; this tracker holds three places per request, as the live one holds 16."""
    monkeypatch.setattr(video, "WINDOW", 30)
    monkeypatch.setattr(video, "OVERLAP", 8)
    fix = lambda i, t: (160, int(380 + (t - (0.9 + i * 1.2)) * 620))  # noqa: E731
    raw = encode(tmp_path / "many.mp4", seconds=6.0, count=4, fix=fix).read_bytes()
    fake = FakeTracker(4, fix)
    fake.cap = 3  # the sheet leaving the frame still holds a place, as the next row's edges do in a live clip
    fake.starts = [s for s, _ in video.pieces(60)]

    papers = {s: np.asarray(Image.fromarray(paper(s)).convert("L"), dtype=np.float32) for s in range(4)}

    def which(img):
        g = np.asarray(img.convert("L").resize((400, 520)), dtype=np.float32)
        turned = [g, g[::-1, ::-1].copy(), g[::-1].copy(), g[:, ::-1].copy()]  # the corners of a cut may start anywhere
        return max(papers, key=lambda s: max(float(cv2.matchTemplate(x, papers[s][60:460, 10:390], cv2.TM_CCOEFF_NORMED).max()) for x in turned))

    monkeypatch.setattr(video, "_numbers", lambda img: {f"{which(img)}-{k}" for k in range(8)})
    r = video.find_sheets(client_for(fake, tmp_path), raw).result
    assert fake.requests == len(fake.starts) > 1 and len(r.sheets) == 4
    assert len({frozenset(video._numbers(s.image)) for s in r.sheets}) == 4


def test_with_one_request_the_same_clip_loses_sheets(tmp_path, monkeypatch):  # must light
    monkeypatch.setattr(video, "WINDOW", 1000)
    fix = lambda i, t: (160, int(380 + (t - (0.9 + i * 1.2)) * 620))  # noqa: E731
    raw = encode(tmp_path / "many.mp4", seconds=6.0, count=4, fix=fix).read_bytes()
    fake = FakeTracker(4, fix)
    fake.cap = 3
    fake.starts = [0]
    assert len(video.find_sheets(client_for(fake, tmp_path), raw).result.sheets) == 3


# --- the edge of the frame, and a smeared twin (a live clip lost sheet 4 and kept sheet 5 twice) ----

def test_a_sheet_against_one_edge_with_its_full_shape_is_whole():
    assert video._whole((30.0, 500.0, 2160.0, 3158.0), (2160, 3840))  # live: 2121 by 2658, its right side on the frame's edge


def test_a_sheet_cut_by_the_edge_is_not():  # must differ
    assert not video._whole((0.0, 500.0, 1835.0, 3038.0), (2160, 3840))  # live: 1835 by 2538, 7 % short


def test_a_strip_at_the_foot_of_the_frame_is_not_a_sheet():
    assert not video._whole((100.0, 3300.0, 2000.0, 3840.0), (2160, 3840))


def test_a_sheet_in_a_corner_is_not_whole():
    assert not video._whole((0.0, 0.0, 1800.0, 2300.0), (2160, 3840))


def test_the_clips_own_sheets_set_the_shape():
    tracks = {"1": [video.Seen(n, (100.0, 100.0, 1100.0, 1514.0)) for n in range(6)]}  # A4
    assert video.paper_shape(tracks, (2160, 3840)) == pytest.approx(1.414)
    assert video.paper_shape({}, (2160, 3840)) == video.PAPER


def _cut(img: Image.Image, sharp: float) -> video.Cut:
    return video.Cut("x", video.Seen(0, (0.0, 0.0, 1.0, 1.0)), None, img, sharp)


def test_a_smeared_copy_of_a_sharp_sheet_is_one_sheet_and_the_sharp_one_stays(monkeypatch):
    monkeypatch.setattr(video, "_numbers", one_paper)
    sheet = Image.fromarray(paper(3))
    smeared = sheet.filter(_blur())
    kept, dropped = video.one_paper_once([_cut(smeared, 10.0), _cut(sheet, 900.0)])
    assert len(kept) == 1 and kept[0].sharp == 900.0 and "same sheet" in dropped[0]


def test_two_sharp_pages_of_one_layout_stay_two_however_alike_they_look(monkeypatch):  # must differ
    def form(seed: int) -> Image.Image:
        img = np.full((520, 400, 3), 245, dtype=np.uint8)
        for k in range(12):
            cv2.putText(img, f"CHARGE FOR SERVICE {seed}{k:02d}1 {seed}{k:02d}2", (14, 34 + k * 40), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 2, cv2.LINE_AA)
        return Image.fromarray(img)
    a, b = form(3), form(7)
    assert float(video._look(a) @ video._look(b)) / video._look(a).size > video.SAME_LOOK  # must light: the look alone would merge them
    read = {id(a): {f"3{k:02d}1" for k in range(12)}, id(b): {f"7{k:02d}1" for k in range(12)}}
    monkeypatch.setattr(video, "_numbers", lambda img: read[id(img)])
    kept, _ = video.one_paper_once([_cut(a, 900.0), _cut(b, 880.0)])
    assert len(kept) == 2


def test_one_sheet_read_differently_on_two_frames_is_one_sheet(monkeypatch):
    sheet = Image.fromarray(paper(5))
    twin = sheet.filter(_blur())
    read = {id(sheet): {"11.11", "22.22", "33.33", "44.44", "55.55", "66.66", "77.77", "88.88"},
            id(twin): {"11.11", "22.22", "33.33", "99.91", "99.92", "99.93"}}
    monkeypatch.setattr(video, "_numbers", lambda img: read[id(img)])
    kept, _ = video.one_paper_once([_cut(twin, 200.0), _cut(sheet, 800.0)])
    assert len(kept) == 1 and kept[0].sharp == 800.0



def test_the_upload_says_when_a_file_is_not_a_video(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from billradar import app as app_module
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    r = TestClient(app_module.app).post("/cases", data={"policy_id": "memorial-2026-05", "household_size": 3, "annual_income": 50000, "fictional": "on"},
                                        files={"video": ("clip.mov", b"not a video", "video/quicktime")})
    assert r.status_code == 400 and "could not be opened as a video" in r.text
