"""The bill in one picture. Muse Image draws a wordless scene and code writes the numbers on it, so nothing the family
reads on the picture comes from a model. Every image here is SYNTHETIC: no model was called."""

import base64
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image

from billradar import bill_picture, meta_client as mc
from billradar.checks import Finding, Kind, Report
from tests.test_writer import case


def report(total="2977.76") -> Report:
    return Report(case_id="t", policy_id="memorial-2026-05", fpl_pct=Decimal(200),
                  findings=[Finding(kind=Kind.F1, title="t", detail="d", amount=Decimal("1399.71")),
                            Finding(kind=Kind.E2, title="t", detail="d", amount=Decimal("196.82"))],
                  no_money=[], held_back=[], total_may_come_off=Decimal(total), apply_by=date(2026, 9, 2))


def png(color=(240, 236, 220), size=(1536, 1024)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


class FakeImages:
    """Answers the images endpoint as the API does."""

    def __init__(self):
        self.requests = []

    def image(self, request):
        self.requests.append(request)
        return {"data": [{"b64_json": base64.b64encode(png()).decode()}]}


def client(fake=None):
    return mc.MetaClient(transport=fake or FakeImages(), record_to=None, journal=None)


def test_the_prompt_holds_no_person_no_amount_and_no_date():
    c, r = case(), report()
    prompt = bill_picture.prompt(c, r)
    for person in c.profile.people:
        assert person.name and person.name.split()[0].lower() not in prompt.lower()
    assert "2977" not in prompt and "1399" not in prompt and "2026" not in prompt
    assert "no text" in prompt.lower() and "no numbers" in prompt.lower()


def test_the_scene_follows_the_findings():
    errors_only = report()
    errors_only.findings = [Finding(kind=Kind.E2, title="t", detail="d", amount=Decimal("196.82"))]
    assert bill_picture.prompt(case(), report()) != bill_picture.prompt(case(), errors_only)


def test_the_numbers_on_the_picture_come_from_the_report():
    labels = bill_picture.labels(case(), report(), "en")
    assert "$2,977" in labels[0] and "Sep 2, 2026" in " ".join(labels)
    assert any("Русский" not in x for x in labels)
    ru = bill_picture.labels(case(), report(), "ru")
    assert "$2,977" in ru[0] and ru[0] != labels[0]


def test_render_draws_the_labels_on_the_models_scene():
    fake = FakeImages()
    out = bill_picture.render(client(fake), case(), report(), "en")
    img = Image.open(io.BytesIO(out))
    assert img.format == "PNG" and img.width == 1536 and img.height > 1024  # the band of labels is added below
    assert fake.requests[0]["model"] == "muse-image-1.0" and fake.requests[0]["n"] == 1
    assert fake.requests[0]["response_format"] == "b64_json"


def test_a_live_picture_needs_a_fictional_case():
    from billradar.pipeline import RealDataGate

    class Live(mc.MetaClient):
        live = True

    c = case()
    c.demo = False
    with pytest.raises(RealDataGate):
        bill_picture.render(Live(transport=FakeImages(), record_to=None, journal=None), c, report(), "en")


def test_a_picture_is_paid_for_once_in_the_ledger(tmp_path, monkeypatch):
    class HTTP:
        status_code, text, headers = 200, "", {}

        @staticmethod
        def json():
            return {"data": [{"b64_json": base64.b64encode(png()).decode()}]}

    posted = []
    monkeypatch.setattr(mc.requests, "post", lambda url, **k: posted.append((url, k["json"])) or HTTP())
    ledger = mc.SpendLedger(tmp_path / "s.jsonl", cap=1.0)
    c = mc.MetaClient(transport=mc.LiveTransport("k-synthetic", ledger=ledger), record_to=tmp_path, journal=None)
    raw, replayed = c.image({"model": "muse-image-1.0", "prompt": "a scene", "n": 1, "response_format": "b64_json"}, label="image:bill")
    assert raw.startswith(b"\x89PNG") and replayed is False
    assert posted[0][0].endswith("/images/generations")
    assert ledger.spent() == pytest.approx(0.01) and c.calls[-1]["usd"] == 0.01
    assert len(list(tmp_path.glob("muse-image-1.0-*.json"))) == 1  # recorded for replay
    json.loads(next(tmp_path.glob("muse-image-1.0-*.json")).read_text())


def test_an_image_request_is_checked():
    with pytest.raises(mc.MetaAPIError):
        client().image({"model": "muse-spark-1.3", "prompt": "x", "n": 1, "response_format": "b64_json"})
    with pytest.raises(mc.MetaAPIError):
        client().image({"model": "muse-image-1.0", "prompt": "x", "n": 2, "response_format": "b64_json"})


def label_of(png_bytes: bytes) -> bytes:
    i, found = 8, b""
    while i < len(png_bytes):
        size, kind = int.from_bytes(png_bytes[i:i + 4], "big"), png_bytes[i + 4:i + 8]
        if kind == b"iTXt":
            found += png_bytes[i + 8:i + 8 + size]
        i += size + 12
    return found


def test_metas_label_stays_on_the_picture_we_build():
    """Muse Image marks its picture as AI made in the file. The recorded answer is Meta's own, no new call."""
    recorded = sorted((Path(__file__).parent / "fixtures" / "recordings").glob("muse-image-*.json"))[0]
    raw = base64.b64decode(json.loads(recorded.read_text())["data"][0]["b64_json"])
    assert b"trainedAlgorithmicMedia" in label_of(raw)  # must light: the mark is there to keep
    out = bill_picture._with_labels(raw, ["May come off your bills: $1.00", "Letters are ready."])
    assert b"trainedAlgorithmicMedia" in label_of(out)
    buf = io.BytesIO()
    Image.open(io.BytesIO(raw)).convert("RGB").save(buf, format="PNG")
    assert label_of(buf.getvalue()) == b""  # must differ: a plain save drops it
