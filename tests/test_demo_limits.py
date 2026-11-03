"""The public demo runs live: a question costs money and the card on the account pays after the free credits. So the
second read is on for every live run, a day has its own ceiling, and nobody's own papers can be uploaded there."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from billradar import app as app_module
from billradar import meta_client as mc, pipeline


class Fake(mc.MetaClient):
    def __init__(self, is_live):
        super().__init__(transport=object(), record_to=None, journal=None)
        self._is_live = is_live

    @property
    def live(self):
        return self._is_live


def test_the_second_read_is_on_for_every_live_run(monkeypatch):
    monkeypatch.delenv(pipeline.WONDER_REVIEW, raising=False)
    assert pipeline.review_on(Fake(True)) is True


def test_a_replay_has_no_second_read_unless_it_was_recorded(monkeypatch):
    monkeypatch.delenv(pipeline.WONDER_REVIEW, raising=False)
    assert pipeline.review_on(Fake(False)) is False
    monkeypatch.setenv(pipeline.WONDER_REVIEW, "1")
    assert pipeline.review_on(Fake(False)) is True


def test_it_can_be_switched_off_on_purpose(monkeypatch):
    monkeypatch.setenv(pipeline.WONDER_REVIEW, "0")
    assert pipeline.review_on(Fake(True)) is False


def ledger(tmp_path, day=1.0):
    return mc.SpendLedger(tmp_path / "s.jsonl", cap=100.0, daily=day)


def test_a_day_has_its_own_ceiling(tmp_path):
    led = ledger(tmp_path)
    led.reserve(0.9, "first")
    with pytest.raises(mc.SpendCapReached, match="today"):
        led.reserve(0.2, "second")


def test_yesterday_does_not_count_against_today(tmp_path):
    led = ledger(tmp_path)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
    (tmp_path / "s.jsonl").write_text(json.dumps({"at": yesterday, "usd": 0.95, "note": "yesterday"}) + "\n")
    led.reserve(0.5, "today")
    assert led.spent() == pytest.approx(1.45)


def test_no_daily_ceiling_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("BILLRADAR_DAILY_SPEND_USD", raising=False)
    led = mc.SpendLedger(tmp_path / "s.jsonl", cap=100.0)
    led.reserve(50.0, "big")
    assert led.spent() == 50.0


def test_the_daily_ceiling_is_read_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("BILLRADAR_DAILY_SPEND_USD", "3")
    assert mc.SpendLedger(tmp_path / "s.jsonl", cap=100.0).daily == 3.0


def test_the_public_copy_takes_no_papers(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    called = []
    monkeypatch.setattr(pipeline, "prepare", lambda *a, **k: called.append(1))
    r = TestClient(app_module.app).post("/cases", data={"fictional": "true", "household_size": "3", "annual_income": "50000",
                                                        "policy_id": "memorial-2026-05"},
                                        files={"photos": ("t.jpg", b"x", "image/jpeg")})
    assert r.status_code == 403 and called == []
