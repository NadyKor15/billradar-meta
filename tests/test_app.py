import html as htmllib
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from billradar import app as app_module
from billradar import pipeline
from billradar.meta_client import MetaClient
from billradar.policies import source
from tests.synth import FakeSAM, table_photo
from tests.test_pipeline import FakeMeta, profile, spark_payload_from_fixture
from tests.test_sam import QUADS, SIZE

needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), reason="run scripts/fetch_policies.py first")


def fake_client():
    """A Meta client over made-up answers: SAM finds the five drawn sheets, Spark reads the Anna birth case. Records nothing."""
    meta = FakeMeta(FakeSAM(QUADS, SIZE), spark_payload_from_fixture({"S6": "S5"}))  # the fixture has S6, the photo five sheets
    return MetaClient(meta, record_to=None, journal=None)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "RUNS", tmp_path)  # cases land in tmp_path, never in the real runs folder
    return TestClient(app_module.app)


@needs_text
def test_case_screen_shows_findings_with_their_evidence(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "_today", lambda case_id, case: date(2026, 10, 1))  # the deadline is already past
    anna = profile()
    named = anna.model_copy(update={"people": [anna.people[0].model_copy(update={"name": "Anna"}),
                                               anna.people[1].model_copy(update={"name": "Baby"})]})
    run = pipeline.run(fake_client(), [table_photo(QUADS, SIZE)], [], named, "memorial-2026-05", "Lakeview Demo Hospital",
                       date(2026, 6, 15), "t1")
    pipeline.save(run, tmp_path / "t1")

    page = client.get("/cases/t1")
    assert page.status_code == 200
    text = htmllib.unescape(page.text)
    assert '<span class="gold">$1,100</span><br>may come off your bills.' in text  # 1100.86, rounded down
    assert "The last day to apply was Sep 2, 2026" in text
    assert "<title>Anna's birth case · BillRadar</title>" in text and "Lakeview Demo Hospital" in text
    assert len(re.findall(r'class="frow serious"', text)) == 3  # E1, F3, F2
    f3 = re.search(r'<article class="frow[^"]*" data-kind="F3">.*?</article>', text, re.S).group(0)
    assert "$1,054.00" in f3 and "Not applied yet" in f3
    assert "Policy p.11" in text and "Federal rule" in text
    assert "Checked — no money here" in text
    assert ">recorded run<" in text
    overlay = client.get("/cases/t1/overlay/overlay-1.jpg")
    assert overlay.status_code == 200 and overlay.headers["content-type"] == "image/jpeg"

    # On the case's own day the same date is still ahead of the family.
    monkeypatch.setattr(app_module, "_today", lambda case_id, case: date(2026, 6, 15))
    early = htmllib.unescape(client.get("/cases/t1").text)
    assert "Apply by Sep 2, 2026" in early and "The last day to apply was" not in early


def test_unknown_or_odd_case_ids_are_404(client):
    assert client.get("/cases/nope").status_code == 404
    assert client.get("/cases/..%2F..%2Fetc").status_code == 404
    assert client.get("/cases/t1/overlay/..%2Fcase.json").status_code == 404  # there is no case t1 either


def test_upload_form_lists_hospital_policies_only(client):
    page = client.get("/upload")
    assert page.status_code == 200
    assert "memorial-2026-05" in page.text and "baptist-2026-09" in page.text
    assert "federal-501r" not in page.text  # the federal rule is not a hospital's policy


@needs_text
def test_upload_runs_the_pipeline(client, monkeypatch):
    monkeypatch.setattr(app_module.providers, "make_client", fake_client)
    form = {"policy_id": "memorial-2026-05", "letterhead": "Lakeview Demo Hospital", "household_size": "4", "annual_income": "85000",
            "liquid_assets": "6000", "insured": "true", "mother_name": "Anna", "baby_name": "Baby"}
    table = ("table.jpg", table_photo(QUADS, SIZE), "image/jpeg")
    created = client.post("/cases", data=form, files={"photos": table}, follow_redirects=False)
    assert created.status_code == 303
    assert re.fullmatch(r"/cases/c[0-9a-f]{10}/review", created.headers["location"])  # the sheets are shown before anything is sent
    review = client.get(created.headers["location"])
    sheets = re.findall(r'<input type="radio" name="(S\d+)" value="send" checked>', review.text)
    assert sheets == ["S1", "S2", "S3", "S4", "S5"]  # every sheet is offered, "send" chosen by default
    sent = client.post(created.headers["location"].replace("/review", "/send"), data={name: "send" for name in sheets},
                       follow_redirects=False)
    assert sent.status_code == 303
    done = client.get(sent.headers["location"])
    assert "may come off your bills" in htmllib.unescape(done.text)
