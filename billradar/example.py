"""The example case ("See an example", "Try it yourself"): fictional papers, replayed answers, no keys.

"example" and "example-private" are both a replay of one real run: the pack below in private mode, sheets found by
SAM 3.1, read by Muse Spark and reviewed by Muse Wonder, recorded in tests/fixtures/recordings (scripts/record_example.py).
Until that recording is in the tree, the same pack is answered from its generator's own files: that shows the wiring,
not the models, and the screen says "replay".
  example-appeal   a claim the fictional Sample Health Plan denied (tests/fixtures/cases/sample-appeal.json):
                   the insurance appeal, the insurer's call cheat sheet and the appeal tracker.
  example-appeal   a claim the fictional Sample Health Plan denied (tests/fixtures/cases/sample-appeal.json):
                   the insurance appeal, the insurer's call cheat sheet and the appeal tracker.

The wire format of the replayed answers is written by tests/synth.py, which is why the repo root
must be importable (it is when the app runs from the repo).
"""

from __future__ import annotations

import io
import json
import re
import os
import shutil
import sys
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from billradar import highlight, pipeline
from billradar.case import Profile
from billradar.meta_client import MetaClient, ReplayMissing, ReplayTransport

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "runs-seed"  # the examples as baked into the image (Dockerfile)
DEMO_CASES = Path(__file__).parent / "demo_cases"
PACK = ROOT / "eval" / "packs" / "work" / "brs1-birth-all-errors"
EXAMPLE_ID = "example"
PRIVATE_ID = "example-private"
APPEAL_ID = "example-appeal"
VIDEO_ID = "example-video"  # the same pile filmed on a phone: a recorded run, kept as it came out (billradar/demo_cases)
READ_ONLY = {EXAMPLE_ID, PRIVATE_ID, APPEAL_ID, VIDEO_ID}


def _synth():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests import synth
    return synth


class PackAnswers:
    """Answers SAM from the generator's sheet corners and Spark from its perfect reading."""

    def __init__(self, pack: Path):
        self.reading = json.loads((pack / "answers" / "reading.json").read_text())
        self.corners = json.loads((pack / "answers" / "sam.json").read_text())
        self.photos = sorted(p for p in pack.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        self.sizes = {p.name: Image.open(p).size for p in self.photos}
        self.sam_calls = 0

    def events(self, body: dict) -> list[dict]:
        synth = _synth()
        if body["model"] == "sam-3.1":
            name = self.photos[self.sam_calls].name  # the pipeline sends photos in sorted order
            self.sam_calls += 1
            sw, sh = synth.sent_size(body)
            ow, oh = self.sizes[name]
            k = np.array([sw / ow, sh / oh])
            quads = [np.array(q, dtype=np.float32) * k for q in self.corners[name]]
            recs = [synth.record(10 + i, q, (sw, sh)) for i, q in enumerate(quads)]
            return synth.sam_events("<0f>" + ",".join(recs) + "\n" if recs else "")
        text = json.dumps(self.paged(body))
        return [{"type": "response.output_text.delta", "delta": text},
                {"type": "response.completed", "response": {"id": "resp_SYNTHETIC", "usage": {}}}]

    def paged(self, body: dict) -> dict:
        """Private mode sends a PDF as page images D1.1, D1.2, ...: answer each page, the file's whole reading on
        its first page and empty continuation pages, so the pipeline's merge_pages gives back the file's reading."""
        asked = re.findall(r"\b[SD]\d+(?:\.\d+)?\b", body["input"][1]["content"][0]["text"])  # "Documents in this case: ..."
        docs = []
        for d in self.reading["documents"]:
            pages = sorted((a for a in asked if a.startswith(d["doc_id"] + ".")), key=lambda a: int(a.split(".")[1]))
            if not pages:
                docs.append(d)
                continue
            docs.append(d | {"doc_id": pages[0]})
            blank = {k: ("" if isinstance(v, str) else v) for k, v in d.items()}
            docs += [blank | {"doc_id": pid, "kind": "other", "lines": [], "first_after_discharge": False,
                              "page_no": 0, "page_count": 0} for pid in pages[1:]]
        return self.reading | {"documents": docs}


def run_pack(pack: Path, case_id: str | None = None, private: bool = False) -> pipeline.CaseRun:
    meta = json.loads((pack / "profile.json").read_text())
    answers = PackAnswers(pack)
    client = MetaClient(transport=answers, record_to=None, journal=None)
    return _run(client, pack, meta, answers.photos, case_id, private)


def run_recorded(pack: Path, case_id: str) -> pipeline.CaseRun:
    """The recorded live run, replayed. A request with no recording is an error, never faked."""
    meta = json.loads((pack / "profile.json").read_text())
    photos = sorted(p for p in pack.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    client = _replay_client()
    flags = (pipeline.WONDER_REVIEW, pipeline.SECOND_READ)
    before = {f: os.environ.get(f) for f in flags}
    os.environ.update(dict.fromkeys(flags, "1"))  # the run was recorded with the second read and the review on
    try:
        run = _run(client, pack, meta, photos, case_id, private=True)
        if lost := [i.what for i in run.verdict.issues if i.subject == "model review"]:
            raise ReplayMissing(lost[0])
        return run
    finally:
        for f, value in before.items():
            if value is None:
                os.environ.pop(f, None)
            else:
                os.environ[f] = value


def _replay_client():
    return MetaClient(transport=ReplayTransport(), record_to=None, journal=None)


def _run(client, pack: Path, meta: dict, photo_paths: list[Path], case_id: str | None, private: bool) -> pipeline.CaseRun:
    photos = [p.read_bytes() for p in photo_paths]
    pdfs = [(p.name, p.read_bytes()) for p in sorted(pack.glob("*.pdf"))]
    run = pipeline.run(client, photos, pdfs, Profile.model_validate(meta["profile"]), meta["policy_id"],
                       meta.get("letterhead", ""), date.fromisoformat(meta["today"]), case_id or pack.name,
                       fictional=bool(meta.get("fictional")), private=private)
    run.case.demo = True
    return run


# ---- the drawn 5-sheet table (was scripts/demo_synthetic.py) ----

SIZE = (2400, 1700)
SHEETS = [  # (center x, center y, angle) for 5 letter-size sheets, plus what is printed on each
    ((480, 450, -6), "PATIENT STATEMENT", "Patient: Anna Sample", "Balance due $676.80"),
    ((1180, 430, 4), "PATIENT STATEMENT", "Patient: Baby Sample", "Balance due $1,240.00"),
    ((1880, 460, -3), "FIRST STATEMENT AFTER DISCHARGE", "Patient: Anna Sample", "Insurance pending"),
    ((760, 1250, 5), "EXPLANATION OF BENEFITS", "THIS IS NOT A BILL", "Member: Anna Sample"),
    ((1560, 1240, -4), "EXPLANATION OF BENEFITS", "THIS IS NOT A BILL", "Member: Baby Sample"),
]
W, H = 520, 672
DEMO_PEOPLE = [  # fictional family; stays local, the model only sees PATIENT_1 / PATIENT_2
    {"token": "PATIENT_1", "role": "mother", "name": "Anna", "birth_date": "03/14/1994", "relationship": "Self",
     "employer": "Sample Bakery LLC"},
    {"token": "PATIENT_2", "role": "newborn", "name": "Baby", "birth_date": "08/04/2025", "relationship": "Daughter"},
    {"token": "P3", "role": "other", "name": "Mark", "birth_date": "07/02/1990", "relationship": "Spouse",
     "employer": "Sample Auto Repair"},
    {"token": "P4", "role": "other", "name": "Leo", "birth_date": "09/30/2023", "relationship": "Son"},
]
DEMO_LOCAL = {"street": "100 Example Street", "city": "Hollywood", "state": "FL", "zip": "33021",
              "phone": "(555) 010-0000", "rent": "1850", "electricity": "140", "phone_bill": "60",
              "checking": "2400", "savings": "3600", "tokens": {"ACCT_1": "LDH-000123", "ACCT_2": "LDH-000124"}}


def font(size: int, bold: bool = False):
    """A system face for the drawn sheets; the built-in bitmap font when none is installed."""
    names = ("Arial Bold.ttf", "Helvetica-Bold.ttf") if bold else ("Arial.ttf", "Helvetica.ttc")
    folders = ("/System/Library/Fonts/Supplemental/", "/System/Library/Fonts/", "/Library/Fonts/")
    paths = (folder + name for name in names for folder in folders)  # a name is tried in every folder before the next name
    opened = None
    while opened is None and (path := next(paths, None)) is not None:
        try:
            opened = ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default() if opened is None else opened


def draw_sheet(title: str, who: str, last: str) -> Image.Image:
    """One made-up hospital sheet: a heading, a name, fourteen ruled lines with sums, a closing line and a SAMPLE stamp."""
    sheet = Image.new("RGBA", (W, H), (250, 249, 244, 255))
    pen = ImageDraw.Draw(sheet)
    head = [((28, 24), "LAKEVIEW DEMO HOSPITAL", 22, (30, 60, 70), True), ((28, 54), title, 17, (40, 40, 40), True),
            ((28, 84), who, 15, (60, 60, 60), False)]
    foot = [((28, H - 100), last, 18, (30, 30, 30), True),
            ((W // 2 - 120, H // 2 - 40), "SAMPLE", 64, (220, 60, 60, 90), True)]  # last, over everything, no blending

    def write(items: list) -> None:
        for at, text, size, ink, bold in items:
            pen.text(at, text, fill=ink, font=font(size, bold))

    write(head)
    for row in range(14):  # a ruled line with a made-up sum at its right end
        y = 130 + row * 30
        pen.line([(28, y), (W - 120, y)], fill=(150, 150, 150), width=2)
        write([((W - 105, y - 10), f"{row * 137 % 900 + 40}.00", 13, (90, 90, 90), False)])
    write(foot)
    return sheet


def _wood() -> Image.Image:
    """The empty table: grain along its length, a little noise, a soft edge. The seed keeps the picture the same every time."""
    across, down = SIZE
    noise = np.random.default_rng(3).normal(0, 6, (down, across))
    grain = np.sin(np.linspace(0, 60, down))[:, None] * 10 + noise
    channels = (132 + grain, 92 + grain * 0.8, 58 + grain * 0.6)
    return Image.fromarray(np.clip(np.stack(channels, axis=-1).astype(np.float32), 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(1.2))


def _lay(photo: Image.Image, sheet: Image.Image, cx: float, cy: float, angle: float) -> None:
    """Put a sheet on the table at its centre, turned, with a soft shadow down and to the right."""
    turned = sheet.rotate(-angle, expand=True, resample=Image.Resampling.BICUBIC)
    shade = Image.new("RGBA", turned.size, (0, 0, 0, 0))
    shade.paste((0, 0, 0, 70), mask=turned.getchannel("A"))
    shade = shade.filter(ImageFilter.GaussianBlur(10))
    x, y = int(cx - turned.width / 2), int(cy - turned.height / 2)
    photo.paste(shade, (x + 10, y + 14), shade)
    photo.paste(turned, (x, y), turned)


def table() -> tuple[bytes, list[np.ndarray]]:
    """A photo of a wooden table with the five sheets laid on it, and each sheet's four corners in the photo's pixels."""
    synth = _synth()
    photo = _wood()
    corners = []
    for (cx, cy, angle), *text in SHEETS:
        _lay(photo, draw_sheet(*text), cx, cy, angle)
        corners.append(synth.sheet_quad(cx, cy, W, H, angle))
    jpeg = io.BytesIO()
    photo.save(jpeg, format="JPEG", quality=90)
    return jpeg.getvalue(), corners


def _scripted_client(quads: list[np.ndarray]) -> MetaClient:
    """A client that answers from the drawn table's own corners and the fixture's reading: no network, no keys."""
    synth = _synth()  # puts the repo root on the path, which the test helpers need
    from tests.test_pipeline import FakeMeta, spark_payload_from_fixture
    return MetaClient(transport=FakeMeta(synth.FakeSAM(quads, SIZE), spark_payload_from_fixture({"S6": "S5"})),
                      record_to=None, journal=None)


def run_demo_synthetic(case_id: str = "demo-synthetic") -> pipeline.CaseRun:
    """The sample case end to end on the drawn table: made-up family, scripted answers, no keys. Always private, always fictional."""
    photo, quads = table()
    given = json.loads((ROOT / "tests" / "fixtures" / "cases" / "anna-birth.json").read_text())
    family = Profile.model_validate({**given["profile"], "people": DEMO_PEOPLE, "local": DEMO_LOCAL})
    demo = pipeline.run(_scripted_client(quads), [photo], [], family, given["policy_id"], given["letterhead"],
                        date.fromisoformat(given["today"]), case_id, fictional=True, private=True)
    demo.case.demo = True
    return demo


def run_appeal_example(case_id: str = APPEAL_ID) -> pipeline.CaseRun:
    """A case with no photos: the family's papers as already read (SYNTHETIC), checked like any other."""
    _synth()
    from billradar import checks
    from billradar.case import Case
    from tests.test_appeal import LOCAL, PEOPLE

    raw = json.loads((ROOT / "tests/fixtures/cases/sample-appeal.json").read_text())
    raw.pop("_note", None)
    raw["profile"]["people"], raw["profile"]["local"] = PEOPLE, LOCAL
    case = Case.model_validate(raw | {"case_id": case_id, "demo": True})
    report, verdict = pipeline.check_and_hold(case, checks.run(case))
    return pipeline.CaseRun(case, report, [], [], verdict=verdict)


def _save_once(runs: Path, case_id: str, build) -> None:
    out = runs / case_id
    if (out / "case.json").exists():
        return
    tmp = runs / f".build-{case_id}-{os.getpid()}"
    run = build()
    pipeline.save(run, tmp)
    highlight.attach(_replay_client(), run, tmp)
    try:
        tmp.rename(out)  # another request may have finished first; then ours is dropped
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)


def _from_seed(runs: Path, seed: Path) -> None:
    """The examples baked into the image, copied to the runs folder once: the first visitor waits for nothing."""
    for built in seed.iterdir() if seed.is_dir() else ():
        if not (runs / built.name).exists():
            shutil.copytree(built, runs / built.name)


def ensure(runs: Path, seed: Path = SEED) -> None:
    """Build the example runs once; later calls only check they are there."""
    runs.mkdir(parents=True, exist_ok=True)
    _from_seed(runs, seed)
    _from_seed(runs, DEMO_CASES)
    _save_once(runs, EXAMPLE_ID, lambda: run_recorded(PACK, EXAMPLE_ID))
    _save_once(runs, PRIVATE_ID, lambda: run_recorded(PACK, PRIVATE_ID))
    _save_once(runs, APPEAL_ID, lambda: run_appeal_example(APPEAL_ID))
