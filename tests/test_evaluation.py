import base64
import dataclasses
import importlib.util
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from billradar import checks, pipeline, redact
from billradar import evaluation as ev
from billradar.meta_client import MetaClient, check_body
from billradar.policies import source
from tests.synth import FakeSAM, table_photo
from tests.test_pipeline import FIX, spark_payload_from_fixture
from tests.test_sam import QUADS, SIZE
from tests.test_writer import case

needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES),
                                reason="run scripts/fetch_policies.py first")

# What the demo case of the Anna family has to give: the sums and the date the product finds for it.
KEY = ev.Key(pack_id="anna-birth", split="work", items=[
    ev.KeyItem(cls="E1", sheets=["S1", "S4"], amount=Decimal("46.86")),
    ev.KeyItem(cls="F3", sheets=["S1", "S2"], amount=Decimal("1054.00")),
    ev.KeyItem(cls="F2", sheets=["S3"], deadline=date(2026, 9, 2)),
])


def _load_eval_run():
    """scripts/eval_run.py is not a package: load it by path."""
    path = Path(__file__).resolve().parents[1] / "scripts" / "eval_run.py"
    spec = importlib.util.spec_from_file_location("eval_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeModels:
    """SAM draws the table; every other model answers by the name of its answer format. All answers are SYNTHETIC."""

    def __init__(self, answers: dict, usage: dict):
        self.sam = FakeSAM(QUADS, SIZE)
        self.answers = answers  # format name (None: the free-text question) -> answer text
        self.usage = usage
        self.simple_images: list[str] = []  # the pictures of the plain question, as sent

    def events(self, body):
        if body["model"] == "sam-3.1":
            return self.sam.events(body)
        name = body.get("text", {}).get("format", {}).get("name")
        if name is None:
            self.simple_images += [part["image_url"] for part in body["input"][0]["content"] if part["type"] == "input_image"]
        return [{"type": "response.output_text.delta", "delta": self.answers[name]},
                {"type": "response.completed", "response": {"id": "r", "usage": self.usage}}]


def _anna_reading() -> str:
    return json.dumps(spark_payload_from_fixture({"S6": "S5"}))


def _anna_pack(tmp_path: Path) -> Path:
    """A pack folder: the drawn table photo, the family and the answer key."""
    pack = tmp_path / "anna"
    pack.mkdir()
    (pack / "table.jpg").write_bytes(table_photo(QUADS, SIZE))
    meta = {"policy_id": "memorial-2026-05", "today": "2026-06-15", "fictional": True,
            "profile": json.loads(FIX.read_text())["profile"]}
    (pack / "profile.json").write_text(json.dumps(meta))
    (pack / "key.json").write_text(KEY.model_dump_json())
    return pack


def _counts(score: ev.Score) -> dict[str, tuple]:
    return {cls: (c.found, c.n, c.false, c.wrong_amount, c.wrong_deadline) for cls, c in score.by_class.items()}


@needs_text
def test_billradar_on_its_own_case_finds_everything():
    c = case()
    score = ev.score(KEY, ev.from_report(checks.run(c)))
    assert _counts(score) == {"E1": (1, 1, 0, 0, 0), "F3": (1, 1, 0, 0, 0), "F2": (1, 1, 0, 0, 0)}


def test_scoring_counts_misses_falses_and_wrong_numbers():
    preds = [ev.Prediction(cls="F3", sheets=["S2"], amount=Decimal("900.00")),
             ev.Prediction(cls="F2", deadline=date(2027, 1, 14)),  # no sheets: still the key's F2
             ev.Prediction(cls="E2", sheets=["S1"], amount=Decimal("10.00"))]  # no E2 in the key
    score = ev.score(KEY, preds)

    assert _counts(score) == {"E1": (0, 1, 0, 0, 0), "F3": (1, 1, 0, 1, 0), "F2": (1, 1, 0, 0, 1), "E2": (0, 0, 1, 0, 0)}
    table = ev.table({"X": score})
    for cell in ("| E1 | 0 of 1 |", "1 wrong $", "| E2 | 0 of 0 (1 false) |"):
        assert cell in table


def test_a_prediction_matches_only_one_key_item():
    twice = ev.Key(pack_id="p", split="work", items=[ev.KeyItem(cls="E2", sheets=["S1"]), ev.KeyItem(cls="E2", sheets=["S1"])])
    score = ev.score(twice, [ev.Prediction(cls="E2", sheets=["S1"])])
    assert (score.by_class["E2"].found, score.by_class["E2"].n) == (1, 2)


def test_seal_refuses_a_changed_key(tmp_path):
    key_file = tmp_path / "pack1" / "key.json"
    key_file.parent.mkdir()
    key_file.write_text(KEY.model_dump_json())
    ledger = tmp_path / "SEALED.txt"

    ev.seal([key_file], ledger)
    assert ev.check_seal(key_file, ledger)

    data = json.loads(key_file.read_text())
    key_file.write_text(json.dumps(data, indent=4))  # the same content, laid out differently
    assert ev.check_seal(key_file, ledger)

    data["items"][0]["amount"] = "50.00"
    key_file.write_text(json.dumps(data))
    assert not ev.check_seal(key_file, ledger)


@needs_text
def test_bodies_are_valid_requests():
    sheets = [("S1", b"\xff\xd8fake"), ("S2", b"\xff\xd8fake")]
    simple = ev.simple_body(sheets, [])
    strong = ev.strong_body(sheets, [], "memorial-2026-05", {"size": 4})
    judge = ev.judge_body("You may qualify for a discount.", KEY)

    for body in (simple, strong, judge):
        check_body(body)
    assert "text" not in simple  # a free answer
    assert simple["input"][0]["content"][0]["text"] == ev.SIMPLE_QUESTION
    assert strong["input"][0]["role"] == "developer"
    assert strong["text"]["format"]["strict"] is True
    files = [part for part in strong["input"][1]["content"] if part["type"] == "input_file"]
    assert files[0]["filename"] == "memorial-2026-05.pdf"  # the policy is attached


def test_judge_and_strong_answers_parse():
    verdict = {"items": [{"index": 1, "found": True, "amount": "$1,054.00", "deadline": ""},
                         {"index": 0, "found": False, "amount": "", "deadline": ""}],
               "other_money_claims": 2}
    preds, extra = ev.from_judge(json.dumps(verdict), KEY)
    assert [(p.cls, p.amount) for p in preds] == [("F3", Decimal("1054.00"))]  # key item 1, the sum without "$" and ","
    assert extra == 2

    strong = {"findings": [{"cls": "F2", "sheets": ["S3"], "amount": "", "deadline": "2026-09-02", "explanation": "..."}]}
    [pred] = ev.from_strong(json.dumps(strong))
    assert (pred.cls, pred.sheets, pred.amount, pred.deadline) == ("F2", ["S3"], None, date(2026, 9, 2))


@needs_text
def test_run_pack_end_to_end_on_synthetic_answers(tmp_path):
    answers = {
        "billradar_case": _anna_reading(),
        "judge": json.dumps({"items": [{"index": 1, "found": True, "amount": "", "deadline": ""}], "other_money_claims": 1}),
        "strong_baseline": json.dumps({"findings": [{"cls": "F3", "sheets": ["S2"], "amount": "1054.00", "deadline": "",
                                                     "explanation": ""}]}),
        None: "You may be able to ask the hospital for help with the baby's bill.",
    }
    client = MetaClient(FakeModels(answers, {}), record_to=None, journal=None)

    results = _load_eval_run().run_pack(client, _anna_pack(tmp_path), tmp_path / "out")

    assert set(results) == {"BillRadar", "Simple prompt", "Strong prompt"}
    table = ev.table(results)
    for row in ("| F3 | 1 of 1 (1 no $) | 1 of 1 | 1 of 1 |", "| E1 | 0 of 1 | 0 of 1 | 1 of 1 |",
                "| other money claims not in the key | 1 | 0 | 0 |"):
        assert row in table
    assert results["BillRadar"].by_class["E1"].found == 1 and results["BillRadar"].by_class["F2"].found == 1
    assert results["Simple prompt"].by_class["F3"].found == 1 and results["Simple prompt"].extra_false == 1
    assert results["Strong prompt"].by_class["E1"].found == 0
    assert (tmp_path / "out" / "simple.txt").read_text().startswith("You may")


def test_billradar_runs_private_and_the_prompts_get_the_sheets_as_photographed(tmp_path, monkeypatch):
    answers = {"billradar_case": _anna_reading(), "judge": json.dumps({"items": [], "other_money_claims": 0}),
               "strong_baseline": json.dumps({"findings": []}), None: "ok"}
    fake = FakeModels(answers, {"input_tokens": 1000, "output_tokens": 100})
    real_redact, real_run = redact.redact, pipeline.run
    runs = []

    def marked(img, vault, *args, **kwargs):
        """The covered copy of a sheet gets a black square in its corner: that is what tells it from the sheet itself."""
        closed = real_redact(img, vault, *args, **kwargs)
        picture = closed.image.copy()
        picture.paste((0, 0, 0), (0, 0, 60, 60))
        return dataclasses.replace(closed, image=picture)

    def spy(*args, **kwargs):
        runs.append(kwargs)
        runs.append(real_run(*args, **kwargs))
        return runs[-1]

    monkeypatch.setattr(redact, "redact", marked)
    monkeypatch.setattr(pipeline, "run", spy)
    eval_run = _load_eval_run()

    eval_run.run_pack(MetaClient(fake, record_to=None, journal=None), _anna_pack(tmp_path), tmp_path / "out")

    kwargs, run = runs
    assert kwargs["private"] is True
    assert run.originals  # private mode keeps the sheets as photographed
    asked = base64.b64decode(fake.simple_images[0].split(",", 1)[1])
    first = run.sheets[0]
    assert asked == eval_run.jpeg(run.originals[first.doc_id])
    assert asked != eval_run.jpeg(first.image)  # must differ: the covered copy carries the square

    summary = json.loads((tmp_path / "out" / "summary.json").read_text())
    assert set(summary["usd"]) == {"Simple prompt", "Strong prompt", "BillRadar"}
    assert summary["usd"]["Strong prompt"] > 0  # priced from the tokens the answer reported
    assert summary["seconds"]["BillRadar"] >= 0
    assert summary["unproven_amounts"] == 0


def test_totals_give_found_of_n_and_a_percent():
    s = ev.score(KEY, [ev.Prediction(cls="F3", sheets=["S2"], amount=Decimal("1054.00"))])
    results = {"Simple prompt": s}
    assert "| All classes | 1 of " in ev.table(results)
    numbers = ev.numbers(results)
    assert numbers["Simple prompt"]["found"] == 1 and numbers["Simple prompt"]["n"] == sum(c.n for c in s.by_class.values())
    assert numbers["Simple prompt"]["percent"] == round(100 / numbers["Simple prompt"]["n"])
