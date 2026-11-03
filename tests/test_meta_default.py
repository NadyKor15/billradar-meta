"""This build answers on Meta's models, and papers uploaded through the app are covered on the device before
anything leaves it."""

import pytest
from fastapi.testclient import TestClient

from billradar import app as app_module
from billradar import links, pipeline, providers
from billradar.meta_client import MetaClient



@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    return tmp_path_factory.mktemp("runs")  # the example is built once: it takes minutes


@pytest.fixture
def client(runs, monkeypatch):
    monkeypatch.setattr(app_module, "RUNS", runs)
    return TestClient(app_module.app)


def test_meta_answers():
    assert isinstance(providers.make_client(), MetaClient)
    assert providers.labels()["read"] == "Muse Spark"


def test_the_agents_page_gives_the_public_address_behind_a_proxy(client, monkeypatch):
    monkeypatch.setenv("BILLRADAR_PUBLIC_URL", "https://bills.example.org/")
    page = client.get("/agents").text
    assert "https://bills.example.org/mcp" in page or "https://bills.example.org/agents" in page
    assert "testserver" not in page


def test_the_agents_page_uses_the_request_when_no_address_is_set(client, monkeypatch):
    monkeypatch.delenv("BILLRADAR_PUBLIC_URL", raising=False)
    assert "testserver" in client.get("/agents").text  # must light for the test above


def test_every_model_in_the_table_runs_in_the_app():
    from billradar import view
    rows = {m.model: m.status for m in view.MODEL_STATUS}
    assert set(rows) == {"SAM 3.1", "Muse Spark", "Muse Wonder", "Muse Voice Transcribe", "Muse Image"}
    assert set(rows.values()) == {view.READY}


def test_code_links_point_to_this_repo():
    assert links.REPO == "https://github.com/NadyKor15/billradar-meta"


def test_upload_goes_through_private_mode(client, monkeypatch):
    """What the description promises: private by default, on the path a person really uses."""
    seen = {}

    def fake_run(*args, **kwargs):
        seen.update(kwargs)
        raise pipeline.RealDataGate("stop here")

    monkeypatch.setattr(pipeline, "prepare", fake_run)
    r = client.post("/cases", data={"fictional": "true", "mother_name": "Anna", "household_size": "3",
                                    "annual_income": "50000", "insured": "true", "policy_id": "memorial-2026-05"},
                    files={"photos": ("t.jpg", b"not-a-photo", "image/jpeg")})
    assert r.status_code == 400, r.text
    assert seen.get("private") is True
