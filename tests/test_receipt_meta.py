"""The receipt of a case on Meta's models: every call from the client's own log, and the same tokens at two other
prices. Nothing here is an estimate of a step that did not run. Usage figures are SYNTHETIC."""

import pytest

from billradar import receipt, view

SPARK_USAGE = {"input_tokens": 30000, "input_tokens_details": {"cached_tokens": 10000}, "output_tokens": 10000,
               "output_tokens_details": {"reasoning_tokens": 8000}}
WONDER_USAGE = {"input_tokens": 8000, "output_tokens": 2000}
CALLS = [
    {"label": "sam:sheet of paper", "model": "sam-3.1", "seconds": 1.5, "usage": {}, "usd": 0.0025, "live": True,
     "response_id": "r1"},
    {"label": "spark:read", "model": "muse-spark-1.3", "seconds": 20.0, "usage": SPARK_USAGE, "usd": 0.0690,
     "live": True, "response_id": "r2"},
    {"label": "wonder:review", "model": "muse-wonder-1.0", "seconds": 9.0, "usage": WONDER_USAGE, "usd": 0.0720,
     "live": True, "response_id": "r3"},
    {"label": "voice:note", "model": "muse-voice-transcribe-1.0", "seconds": 2.0, "audio_ms": 60000, "usd": 0.00005,
     "live": True},
]


def test_our_price_is_the_sum_of_what_was_logged():
    r = receipt.build(CALLS)
    assert r["total_usd"] == pytest.approx(0.0025 + 0.0690 + 0.0720 + 0.00005, abs=1e-6)
    assert [x["step"] for x in r["rows"]] == ["Find sheets", "Read every sheet", "Second read of the case", "voice:note"]
    assert r["replayed"] is False


def test_the_same_tokens_at_the_other_prices():
    p = receipt.build(CALLS)["prices"]
    flat = 0.0025 + 0.00005  # sheets and speech have no token price: they stay what they cost
    spark = (20000 * 1.25 + 10000 * 0.15 + 10000 * 4.25 + 8000 * 1.25 + 2000 * 4.25) / 1e6
    wonder = (20000 * 4 + 10000 * 0.2 + 10000 * 20 + 8000 * 4 + 2000 * 20) / 1e6
    assert p["ours"] == pytest.approx(0.0025 + 0.0690 + 0.0720 + 0.00005, abs=1e-6)
    assert p["all_spark"] == pytest.approx(flat + spark, abs=1e-6)
    assert p["all_wonder"] == pytest.approx(flat + wonder, abs=1e-6)
    assert "same tokens" in p["note"].lower()


def test_a_recorded_run_says_so():
    r = receipt.build([c | {"live": False} for c in CALLS])
    assert r["replayed"] is True


def test_no_calls_no_receipt():
    assert receipt.build([]) is None


def test_the_screen_groups_a_voice_call_without_tokens():
    rows = view.receipt_rows(receipt.build(CALLS))
    assert [r.model for r in rows] == ["SAM 3.1", "Muse Spark", "Muse Wonder", "Muse Voice Transcribe"]
    assert rows[3].tokens == 0 and rows[3].usd == pytest.approx(0.00005)
