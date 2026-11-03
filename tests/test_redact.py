"""Closing private values on this computer. Every test checks both sides: the value is readable
before (so the check is not blind) and unreadable after. All text here is SYNTHETIC."""

import base64
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageFilter

from billradar import app as app_module
from billradar import pipeline, redact
from billradar.case import Profile
from billradar.meta_client import MetaClient
from billradar.redact import Secret, Vault, compact, leaks, ocr
from tests.reading import sheet
from tests.synth import FakeSAM
from tests.test_pipeline import FakeMeta, profile, spark_payload_from_fixture

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


PRIVATE = [  # (the line printed on the sheet, the kind of secret in it, its value)
    ("Patient: Anna Sample", "PATIENT", "Anna Sample"),
    ("Account: LDH-000123", "ACCT", "LDH-000123"),
    ("Member ID: XQZ123456789", "MEMBER", "XQZ123456789"),
    ("SSN: 123-45-6789", "SSN", "123-45-6789"),
    ("DOB 03/14/1994", "DOB", "03/14/1994"),
    ("Address: 100 Example Street, Hollywood FL 33021", "ADDR", "100 Example Street, Hollywood FL 33021"),
]
KEEP = ["08/04/2025 59409 Delivery $2,887.50", "Patient responsibility $2,575.10", "Balance due $676.80"]


def text_of(img) -> str:
    """What the local reader finds on the image, in the compact form the checks compare."""
    return " ".join(compact(line.text) for line in ocr(img))


def lit_name_controls() -> list[Secret]:
    """Anna's and the baby's names as secrets. A sheet that prints them proves the probe finds both (it must light)."""
    controls = [Secret("PATIENT", "Anna Sample", ""), Secret("PATIENT", "Baby Sample", "")]
    assert leaks(sheet(["Patient: Anna Sample", "Patient: Baby Sample"]), controls) == controls
    return controls


def drawn_family() -> Profile:
    """The Anna family with the demo people and the demo address, the way the example case makes it."""
    example = _demo_module()
    return Profile.model_validate({**profile().model_dump(mode="json"), "people": example.DEMO_PEOPLE, "local": example.DEMO_LOCAL})


def _sparse_page(lines: int = 8) -> Image.Image:
    """A real kind of sheet: a few lines of print on a page that is otherwise empty, as big as a cut from a 4K frame."""
    from PIL import ImageDraw
    img = Image.new("RGB", (2000, 2600), (236, 236, 232))
    draw = ImageDraw.Draw(img)
    for i in range(lines):
        draw.text((180, 200 + i * 70), f"Insurance adjusted {i} -$7,919.78 Total due $393.64", fill=(30, 30, 30), font=redact._font(44))
    return img


def test_a_sharp_page_that_is_mostly_empty_is_not_soft():
    assert not redact.too_soft(_sparse_page().filter(ImageFilter.GaussianBlur(1.2)))  # measured on all the paper it scored 11-15


def test_print_blurred_past_reading_is_soft_on_an_empty_page_too():
    assert redact.too_soft(_sparse_page().filter(ImageFilter.GaussianBlur(4)))


def test_a_sharp_barcode_does_not_vouch_for_blurred_print():
    from PIL import ImageDraw
    img = _sparse_page(30).filter(ImageFilter.GaussianBlur(4))
    draw = ImageDraw.Draw(img)
    for x in range(60, 150, 6):  # printed strip at the sheet's edge, the sharpest thing on it
        draw.rectangle((x, 300, x + 2, 2300), fill=(0, 0, 0))
    assert redact.too_soft(img)


def test_a_blank_page_is_not_soft():
    assert not redact.too_soft(Image.new("RGB", (2000, 2600), (236, 236, 232)))


def _demo_module():
    from billradar import example  # the drawn table that used to live in scripts/demo_synthetic.py
    return example


def test_private_values_are_readable_before_and_covered_after():
    img = sheet([line for line, _, _ in PRIVATE] + KEEP)
    controls = [Secret(kind, value, "") for _, kind, value in PRIVATE]
    assert leaks(img, controls) == controls  # must light: all six are readable before

    r = redact.redact(img, Vault())

    assert leaks(r.image, controls) == []
    assert {s.kind for s in r.secrets} >= {"PATIENT", "ACCT", "MEMBER", "SSN", "DOB", "ADDR"}
    account = next(s for s in r.secrets if s.token == "[ACCT_1]")  # the token stands where the account number was
    assert compact(account.value) == "ldh000123"
    after = text_of(r.image)
    for kept in ("$2,887.50", "59409", "08/04/2025", "Patient responsibility $2,575.10", "$676.80"):
        assert compact(kept) in after  # the sums, the code and the date of service stay readable


def test_same_value_gets_the_same_token_on_every_sheet():
    vault = Vault()
    first = redact.redact(sheet(["Account: LDH-000123", "Total $10.00"]), vault)
    second = redact.redact(sheet(["Account #: LDH-000123", "Claim #: CL-55120"]), vault)

    def token_of(r: redact.Redaction, kind: str) -> str | None:
        return next((s.token for s in r.secrets if s.kind == kind), None)

    assert token_of(first, "ACCT") == token_of(second, "ACCT") == "[ACCT_1]"
    assert token_of(second, "CLAIM") == "[CLAIM_1]"


def test_names_the_family_gave_us_are_covered_anywhere():
    img = sheet(["Dear Anna Sample,", "Your baby Mia Sample was seen on 08/04/2025."])
    controls = [Secret("PATIENT", "Anna Sample", ""), Secret("PATIENT", "Mia Sample", "")]
    assert leaks(img, controls) == controls  # must light: neither name has a label

    vault = Vault(known=[("PATIENT", "Anna Sample"), ("PATIENT", "Mia Sample")])
    r = redact.redact(img, vault)

    assert leaks(r.image, controls) == []
    assert "08042025" in text_of(r.image)  # the date of service stays


def test_headers_without_numbers_are_left_alone():
    img = sheet(["Account Summary", "Claim Totals", "Patient responsibility $40.00"])
    assert redact.redact(img, Vault()).secrets == []


def test_what_sam_gets_is_small_and_soft():
    big = sheet([line for line, _, _ in PRIVATE] + KEEP)
    big = big.resize((big.width * 2, big.height * 2))

    small = redact.sam_copy(big, max_side=900)

    assert max(small.size) == 900
    assert redact.too_soft(small)
    sharp = big.copy()
    sharp.thumbnail((900, 900), Image.Resampling.LANCZOS)
    assert not redact.too_soft(sharp)  # must differ: the same size without the blur is still readable


def test_private_pipeline_sends_nothing_readable():
    example = _demo_module()
    photo, quads = example.table()
    names = ["Anna Sample", "Baby Sample", "Mark Sample", "Leo Sample"]
    people = [{**person, "name": name} for person, name in zip(example.DEMO_PEOPLE, names)]
    family = Profile.model_validate({**profile().model_dump(mode="json"), "people": people, "local": example.DEMO_LOCAL})
    controls = lit_name_controls()
    fake = FakeMeta(FakeSAM(quads, example.SIZE), spark_payload_from_fixture({"S6": "S5"}))

    def images(body: dict):
        """Every picture in one request; a PDF in it fails the test."""
        for item in body["input"]:
            for part in item["content"] if isinstance(item["content"], list) else []:
                assert part["type"] != "input_file", "no PDF may leave in private mode"
                if part["type"] == "input_image":
                    yield Image.open(io.BytesIO(base64.b64decode(part["image_url"].split(",", 1)[1]))).convert("RGB")

    run = pipeline.run(MetaClient(fake, record_to=None, journal=None), [photo], [("portal.pdf", b"%PDF-1.4 fake")], family,
                       "memorial-2026-05", "Lakeview Demo Hospital", date(2026, 6, 15), "p1", fictional=True, private=True)

    to_sam = [img for body in fake.sam.bodies for img in images(body)]
    to_spark = [img for body in fake.spark_bodies for img in images(body)]
    assert (len(to_sam), len(to_spark)) == (1, 5)  # the blurred photo, and the five closed sheets
    assert [leaks(img, controls) for img in to_sam + to_spark] == [[]] * 6
    assert run.redacted
    assert any("not sent" in p for p in run.problems)  # the PDF stayed here, and the family is told
    assert run.case.profile.local.tokens["PATIENT_1"] == "Anna Sample"  # the name stays on this computer
    assert set(run.originals) == {s.doc_id for s in run.sheets} == {"S1", "S2", "S3", "S4", "S5"}


def test_a_labelled_name_keeps_the_persons_token():
    vault = Vault(seed={("PATIENT", "Anna"): "[PATIENT_1]", ("PATIENT", "Mia"): "[PATIENT_2]"})
    img = sheet(["Patient: Anna Sample", "Member: Mia Sample", "Guarantor: Mark Sample"])

    r = redact.redact(img, vault)

    tokens = {compact(s.value): s.token for s in r.secrets}  # compact: the reader may lose the space inside a name
    assert tokens == {"anna": "[PATIENT_1]", "mia": "[PATIENT_2]", "marksample": "[PATIENT_3]"}


def test_screen_can_show_what_the_models_saw(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    example = _demo_module()
    photo, quads = example.table()
    controls = lit_name_controls()
    fake = FakeMeta(FakeSAM(quads, example.SIZE), spark_payload_from_fixture({"S6": "S5"}))
    run = pipeline.run(MetaClient(fake, record_to=None, journal=None), [photo], [], drawn_family(), "memorial-2026-05",
                       "Lakeview Demo Hospital", date(2026, 6, 15), "v1", fictional=True, private=True)
    pipeline.save(run, tmp_path / "v1")

    page = TestClient(app_module.app).get("/cases/v1")

    assert page.status_code == 200
    for shown in ("What Meta&#39;s models saw", "/cases/v1/sent-sheet/S1.jpg", "hidden before anything leaves this computer"):
        assert shown in page.text
    with Image.open(tmp_path / "v1" / "sent-1.jpg") as opened:
        sent = opened.convert("RGB")
    assert leaks(sent, controls) == []
    assert sent.width > sent.height  # the blurred photo and a tile for each sheet, laid out in a wide strip


def test_a_name_printed_last_name_first_is_covered_too():
    vault = Vault(seed={("PATIENT", "Anna Mia Sample"): "[PATIENT_1]"})
    img = sheet(["Statement for SAMPLE, ANNA MIA", "Guarantor copy: Sample,Anna", "Anna Sample visit 08/04/2025"])
    controls = [Secret("PATIENT", v, "") for v in ["Sample Anna Mia", "Sample Anna", "Anna Sample"]]
    assert leaks(img, controls) == controls  # must light: all three forms are readable before
    r = redact.redact(img, vault)
    assert leaks(r.image, controls) == []
    assert {s.token for s in r.secrets} == {"[PATIENT_1]"}  # one person, one token
    assert "08042025" in text_of(r.image)  # the date stays readable
