import json

import numpy as np
import pytest

from billradar import sam
from billradar.meta_client import MetaAPIError, MetaClient, ReplayMissing, ReplayTransport, check_body
from tests.synth import FakeSAM, record, sent_size, sheet_quad, table_photo

SIZE = (2400, 1800)  # a real phone photo of a kitchen table
# Five sheets, 520 by 670 (8.5 by 11), a little turned: three on the top row, two below. Listed in reading order.
QUADS = [
    sheet_quad(500, 470, 520, 670, -6),
    sheet_quad(1180, 450, 520, 670, 4),
    sheet_quad(1880, 480, 520, 670, -3),
    sheet_quad(700, 1330, 520, 670, 5),
    sheet_quad(1500, 1310, 520, 670, -4),
]


def client(fake, tmp_path) -> MetaClient:
    """A client over the fake SAM: nothing recorded, the journal inside tmp_path."""
    return MetaClient(fake, record_to=None, journal=tmp_path / "requests.jsonl")


def find(tmp_path, quads=QUADS, **fake_args):
    """Run the sheet finder on a drawn table; returns the fake (to read its requests), the photo and the result."""
    fake = FakeSAM(quads, SIZE, **fake_args)
    photo = table_photo(quads, SIZE)
    return fake, photo, sam.find_sheets(client(fake, tmp_path), photo)


def test_finds_every_sheet_in_reading_order(tmp_path):
    fake, _, res = find(tmp_path)
    assert [s.doc_id for s in res.sheets] == ["S1", "S2", "S3", "S4", "S5"]
    for sheet, quad in zip(res.sheets, QUADS):
        left, top, right, bottom = sheet.box
        cx, cy = quad.mean(axis=0)  # the sheet's centre in the pixels of the real photo
        assert abs((left + right) / 2 - cx) <= 25 and abs((top + bottom) / 2 - cy) <= 25
    sent = sent_size(fake.bodies[0])
    assert sent[0] <= sam.SAM_MAX_SIDE and res.sent_size == sent
    assert res.original_size == SIZE


def test_sheets_are_straightened_to_paper_shape(tmp_path):
    _, _, res = find(tmp_path)
    assert len(res.sheets) == 5
    for sheet in res.sheets:
        width, height = sheet.image.size
        assert sheet.straightened
        assert abs(width - 520) <= 0.06 * 520 and abs(height - 670) <= 0.06 * 670


def test_noise_is_dropped_with_a_reason(tmp_path):
    frame = (1600, 1200)  # what SAM got: two thirds of the photo
    k = frame[0] / SIZE[0]
    noise = [
        record(90, sheet_quad(2300, 1700, 40, 40, 0) * k, frame),  # a speck
        record(91, sheet_quad(505, 472, 515, 668, -6) * k, frame),  # the first sheet again
        record(92, sheet_quad(1200, 1750, 1800, 60, 0) * k, frame),  # a long strip of table edge
    ]
    _, _, res = find(tmp_path, extra=noise)
    assert [s.doc_id for s in res.sheets] == ["S1", "S2", "S3", "S4", "S5"]
    why = " | ".join(res.dropped)
    assert "too small" in why and "duplicate" in why and "not sheet-shaped" in why


def test_no_sheets_is_a_normal_answer(tmp_path):
    _, _, res = find(tmp_path, quads=[])
    assert res.sheets == []
    assert res.dropped == []


def test_cut_stream_is_an_error_not_a_short_answer(tmp_path):
    fake = FakeSAM(QUADS[:3], SIZE, completed=False)
    with pytest.raises(MetaAPIError, match="without a final event"):
        sam.find_sheets(client(fake, tmp_path), table_photo(QUADS, SIZE))


def test_request_asks_for_one_bit_masks_and_confidence(tmp_path):
    fake, _, _ = find(tmp_path)
    [body] = fake.bodies
    assert body["model"] == "sam-3.1"
    assert body["input"][0]["content"][0] == {"type": "input_text", "text": "sheet of paper"}
    assert body["metadata"] == {"mask_encoding": "one_bit", "include_confidence": "true"}


def test_journal_logs_the_request_but_never_the_image(tmp_path):
    find(tmp_path)
    [line] = (tmp_path / "requests.jsonl").read_text().splitlines()
    row = json.loads(line)
    assert row["model"] == "sam-3.1" and row["images"] == 1 and row["live"] is False
    assert "base64" not in line and len(line) < 1000


def test_overlay_draws_numbers(tmp_path):
    _, photo, res = find(tmp_path)
    drawn = sam.overlay(photo, res)
    assert max(drawn.size) == 1400
    bare = sam.overlay(photo, sam.SheetsResult([]))
    assert bare.size == drawn.size and not np.array_equal(np.asarray(drawn), np.asarray(bare))  # the outlines and numbers are on it


# --- client guards ------------------------------------------------------------------------------


def test_contributor_models_are_refused():
    with pytest.raises(MetaAPIError, match="not allowed"):
        check_body({"model": "muse-spark-1.3-contributor", "store": False, "input": []})


def test_spark_must_not_store():
    with pytest.raises(MetaAPIError, match="store must be false"):
        check_body({"model": "muse-spark-1.3", "input": []})
    check_body({"model": "muse-spark-1.3", "store": False, "input": []})  # the same request with store off passes


def test_default_is_replay_without_key_and_flag(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "not-a-real-key")
    monkeypatch.delenv("BILLRADAR_LIVE", raising=False)
    assert not MetaClient().live  # a key alone is not enough
    monkeypatch.delenv("MODEL_API_KEY")
    monkeypatch.setenv("BILLRADAR_LIVE", "1")
    assert not MetaClient().live  # the flag alone is not enough
    monkeypatch.setenv("MODEL_API_KEY", "not-a-real-key")
    assert MetaClient().live  # both together switch it on (nothing is sent: the client only exists)


def test_missing_recording_is_an_error(tmp_path):
    replay = MetaClient(ReplayTransport(tmp_path), record_to=None, journal=None)
    with pytest.raises(ReplayMissing):
        replay.respond({"model": "sam-3.1", "input": []})
