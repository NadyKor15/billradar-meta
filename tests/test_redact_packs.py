"""Private mode on the sample packs (all SYNTHETIC, made by the pack generator).

For every pack: each private value from the pack's profile is readable on what would leave the
device WITHOUT private mode (must light, so the check is not blind), and on nothing that leaves
WITH private mode. Amounts, dates and service codes stay readable: the checks need them.
"""

import base64
import importlib.util
import io
import json
import re
import shutil
from datetime import date
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from billradar import pdfpages, pipeline
from billradar.case import Profile
from billradar.meta_client import MetaClient
from billradar.redact import Secret, city_line, codes, compact, leaks, name_variants, ocr, read_back

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

ROOT = Path(__file__).resolve().parents[1]
PACKS = sorted((ROOT / "eval" / "packs" / "work").glob("brs1-*"))


def _replay_module():
    """scripts/replay_pack.py loaded as a module named replay_pack; PackAnswers is taken from it."""
    spec = importlib.util.spec_from_file_location("replay_pack", ROOT / "scripts" / "replay_pack.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Spy:
    """The pack's synthetic answers, and a copy of every image that was sent."""

    def __init__(self, answers):
        self.answers = answers
        self.sent: list[Image.Image] = []

    def events(self, body: dict) -> list[dict]:
        for item in body["input"]:
            for part in item.get("content", []) if isinstance(item.get("content"), list) else []:
                self.files_sent = getattr(self, "files_sent", 0) + (part.get("type") == "input_file")
                if part.get("type") == "input_image":
                    raw = base64.b64decode(part["image_url"].split(",", 1)[1])
                    self.sent.append(Image.open(io.BytesIO(raw)).convert("RGB"))
        return self.answers.events(body)


def _run(pack: Path, private: bool, pdfs: bool = False) -> list[Image.Image]:
    meta = json.loads((pack / "profile.json").read_text())
    spy = Spy(_replay_module().PackAnswers(pack))
    photos = [p.read_bytes() for p in spy.answers.photos]
    files = [(p.name, p.read_bytes()) for p in sorted(pack.glob("*.pdf"))] if pdfs else []
    spy.files_sent = 0
    pipeline.run(MetaClient(transport=spy, record_to=None, journal=None), photos, files,
                 Profile.model_validate(meta["profile"]), meta["policy_id"], meta.get("letterhead", ""),
                 date.fromisoformat(meta["today"]), pack.name, fictional=True, private=private)
    assert not (private and spy.files_sent), "no PDF may leave in private mode"
    return spy.sent  # every image SAM and Spark got


def _private_values(pack: Path) -> list[Secret]:
    prof = json.loads((pack / "profile.json").read_text())["profile"]
    out = [Secret("PATIENT", v, "") for p in prof["people"] if p.get("name")
           for v in [p["name"], *name_variants(p["name"])]]
    # A newborn's birth date is also the date of service on every bill of the birth: the checks need
    # it readable. Such a date is covered only next to its label ("DOB:"); any other birth date, everywhere.
    service = _service_dates(pack)
    out += [Secret("DOB", p["birth_date"], "") for p in prof["people"]
            if p.get("birth_date") and p["birth_date"] not in service]
    out += [Secret("EMPLOYER", p["employer"], "") for p in prof["people"] if p.get("employer")]
    loc = prof.get("local", {})
    out += [Secret("ADDR", loc["street"], "")] if loc.get("street") else []
    out += [Secret("PHONE", loc["phone"], "")] if loc.get("phone") else []
    out += [Secret("CITY", v, "") for v in city_line(loc.get("city", ""), loc.get("state", ""), loc.get("zip", ""))]
    out += [Secret(t.split("_")[0], v, "") for t, v in loc.get("tokens", {}).items()]
    return out


def _service_dates(pack: Path) -> set[str]:
    """Service dates as printed on US papers (MM/DD/YYYY), from the generator's reading."""
    reading = json.loads((pack / "answers" / "reading.json").read_text())
    iso = {v for d in reading["documents"] for v in [d.get("service_from"), d.get("service_to")]
           + [ln.get("service_date") for ln in d["lines"]] if v}
    return {f"{v[5:7]}/{v[8:10]}/{v[:4]}" for v in iso}


def _kept_values(pack: Path) -> set[str]:
    """Amounts, service dates and codes as printed, from the generator's reading of the sheets."""
    reading = json.loads((pack / "answers" / "reading.json").read_text())
    keep = set()
    for d in reading["documents"]:
        for ln in d["lines"]:
            for v in (ln.get("charges"), ln.get("patient_responsibility"), ln.get("code")):
                if v and len(compact(v)) >= 4:
                    keep.add(compact(v))
    return keep


def _kept_raw(pack: Path) -> set[str]:
    """Amounts and codes as printed ("4944.00", "01960"), to be found whole: a covered claim number "731384882100"
    holds "2100" but not the amount "21.00"."""
    reading = json.loads((pack / "answers" / "reading.json").read_text())
    keep = set()
    for d in reading["documents"]:
        for ln in d["lines"]:
            for v in (ln.get("charges"), ln.get("patient_responsibility"), ln.get("code")):
                if v and len(compact(v)) >= 4:
                    keep.add(str(v).strip().lstrip("$"))
    return keep


def _seen_whole(keep: set[str], images: list[Image.Image]) -> set[str]:
    """Values read whole on the images. Numbers compare by their digits: OCR reads "$6,402.00" as "$6.402.00" now
    and then, and that is the reading, not the covering."""
    numbers = {re.sub(r"\D", "", t) for img in images for line in ocr(img) for t in re.findall(r"\d[\d.,]*\d|\d", line.text)}
    return {v for v in keep if re.sub(r"\D", "", v) in numbers}


def _texts(images: list[Image.Image]) -> list[str]:
    """OCR once per image, as leaks() reads it: letters and digits only."""
    return [" ".join(compact(line.text) for line in ocr(img)) for img in images]


def _readable_on(text: str, s: Secret) -> bool:  # the same rule as redact.leaks
    v = compact(s.value)
    digits = re.sub(r"\D", "", v)
    return bool(v) and (v in text or (len(digits) >= 6 and digits in re.sub(r"\D", "", text)))


class SamSpy(Spy):
    """Only what the sheet finder gets."""

    def __init__(self, answers):
        super().__init__(answers)
        self.sam: list[Image.Image] = []

    def events(self, body: dict) -> list[dict]:
        before = len(self.sent)
        out = super().events(body)
        if body["model"] == "sam-3.1":
            self.sam += self.sent[before:]
        return out


def _edges(img: Image.Image) -> float:
    return float(cv2.Laplacian(np.asarray(img.convert("L")), cv2.CV_64F).var())


@pytest.mark.skipif(not PACKS, reason="no sample packs")
def test_the_sheet_finder_gets_only_a_small_blurred_copy():
    pack = PACKS[0]
    meta = json.loads((pack / "profile.json").read_text())
    spy = SamSpy(_replay_module().PackAnswers(pack))
    photo = spy.answers.photos[0]
    pipeline.run(MetaClient(transport=spy, record_to=None, journal=None), [photo.read_bytes()], [],
                 Profile.model_validate(meta["profile"]), meta["policy_id"], meta.get("letterhead", ""),
                 date.fromisoformat(meta["today"]), pack.name, fictional=True, private=True)
    assert len(spy.sam) == 1  # must light: the finder was called
    sent = spy.sam[0]
    plain = Image.open(photo).convert("RGB").resize(sent.size, Image.Resampling.LANCZOS)
    assert max(sent.size) <= 900
    assert _edges(sent) < 0.1 * _edges(plain)  # the same size without the blur has ten times the edges at least


def _closed(pack: Path) -> pipeline.Prepared:
    """The pile closed as the recorded run closed it: its photos and PDFs, Muse Glimmer's answers from tests/fixtures/recordings/glimmer."""
    meta = json.loads((pack / "profile.json").read_text())
    spy = Spy(_replay_module().PackAnswers(pack))
    prep = pipeline.prepare(MetaClient(transport=spy, record_to=None, journal=None), [p.read_bytes() for p in spy.answers.photos],
                            [(p.name, p.read_bytes()) for p in sorted(pack.glob("*.pdf"))], Profile.model_validate(meta["profile"]),
                            fictional=True, private=True)  # raises nothing: a leak holds a sheet back and says so
    assert not spy.files_sent
    return prep


def _read(images: list[Image.Image]) -> list[str]:
    """What the model read on each image as a whole, the same reading the gate gets."""
    return [compact(read_back(img)) for img in images]


@pytest.mark.skipif(not PACKS, reason="no sample packs")
@pytest.mark.parametrize("pack", PACKS, ids=[p.name for p in PACKS])
def test_private_mode_on_sample_pack(pack):
    prep = _closed(pack)
    secrets = _private_values(pack)
    plain_images = list(prep.originals.values())
    covered_images = [s.image for s in prep.sheets]
    assert len(covered_images) == len(plain_images) and not prep.withheld and not prep.problems
    plain = _read(plain_images)
    before = [s for s in secrets if any(_readable_on(t, s) for t in plain)]
    # must light: the names, the street and the insurance IDs are printed on these papers
    assert {s.kind for s in before} >= {"PATIENT", "ADDR", "MEMBER", "CITY"}, [s.value for s in before]

    covered = _read(covered_images)
    # machine codes (IMb, DataMatrix, QR, 1D): printed on these papers, none on what leaves in private mode
    assert sum(len(codes(img)) for img in plain_images) >= 3
    assert [i for i, img in enumerate(covered_images) if any(x.kind == "CODE" for x in leaks(img, []))] == []
    assert [(s.kind, s.value) for s in secrets if any(_readable_on(t, s) for t in covered)] == []

    keep = _kept_raw(pack)
    lost, seen = [], 0
    for sid, after in zip(prep.originals, covered_images):  # sheet by sheet
        here = _seen_whole(keep, [prep.originals[sid]])
        seen += len(here)
        lost += [(sid, v) for v in sorted(here - _seen_whole(here, [after]))]
    assert seen >= 10
    assert [x for x in lost if "." in x[1]] == [], lost  # covering touches no amount; a code alone may close, and the line stays


@pytest.mark.skipif(not PACKS or not shutil.which("pdftoppm"), reason="no sample packs or no poppler")
@pytest.mark.parametrize("pack", PACKS, ids=[p.name for p in PACKS])
def test_private_mode_sends_the_pdfs_as_covered_pages(pack):
    prep = _closed(pack)
    secrets = _private_values(pack)
    drawn = [img for f in sorted(pack.glob("*.pdf")) for img in pdfpages.render(f.read_bytes())]
    sent = [img for _, img in prep.pages]
    assert len(sent) == len(drawn)
    before = _read(drawn)
    lit = [s for s in secrets if any(_readable_on(t, s) for t in before)]
    # must light: the files print the names and the account numbers
    assert {s.kind for s in lit} >= {"PATIENT", "ACCT"}, [s.value for s in lit]
    after = _read(sent)
    assert [(s.kind, s.value) for s in secrets if any(_readable_on(t, s) for t in after)] == []

    keep = _kept_raw(pack)
    numbers = {re.sub(r"\D", "", t) for text in map(read_back, sent) for t in re.findall(r"\d[\d.,]*\d|\d", text)}
    seen_before = {v for v in keep if re.sub(r"\D", "", v) in {re.sub(r"\D", "", t) for text in map(read_back, drawn) for t in re.findall(r"\d[\d.,]*\d|\d", text)}}
    assert len(seen_before) >= 10
    assert {v for v in seen_before if re.sub(r"\D", "", v) not in numbers} == set()  # covering touches no code, no amount


@pytest.mark.skipif(not PACKS or not shutil.which("pdftoppm"), reason="no sample packs or no poppler")
def test_replay_answers_pdf_pages_and_the_file_comes_back_whole():
    from billradar.case import Profile
    from billradar.meta_client import MetaClient
    pack = next(p for p in PACKS if p.name == "brs1-birth-all-errors")
    meta = json.loads((pack / "profile.json").read_text())
    answers = _replay_module().PackAnswers(pack)
    files = [(p.name, p.read_bytes()) for p in sorted(pack.glob("*.pdf"))]
    run = pipeline.run(MetaClient(transport=answers, record_to=None, journal=None),
                       [p.read_bytes() for p in answers.photos], files, Profile.model_validate(meta["profile"]),
                       meta["policy_id"], meta.get("letterhead", ""), date.fromisoformat(meta["today"]), pack.name,
                       fictional=True, private=True)
    ids = [d.doc_id for d in run.case.documents]
    assert {"D1", "D2", "D3"} <= set(ids) and not any("." in i for i in ids)
    assert not [p for p in run.problems if "unknown document" in p or "did not return" in p], run.problems
    assert "F1" in {f.kind.value for f in run.report.findings}
    assert "F2" in {f.kind.value for f in run.report.worth_asking}  # no paper prints the payment date
