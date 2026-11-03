"""Two independent reads of every sheet, the device as witness, and a third read where they still disagree.
A sum on a sheet nobody can settle is not confirmed. All answers here are SYNTHETIC: no model is called."""

import json
from decimal import Decimal
from types import SimpleNamespace

from billradar import reader, reconcile_read
from billradar.case import Source
from billradar.table_rows import Row

EXPECTED = {"S1": Source.PAPER, "S2": Source.PAPER}


def raw_line(n=1, code="99213", charges="$500.00", paid="$300.00", adj="$150.00", share="$50.00") -> dict:
    return {"line_no": n, "code": code, "charges": charges, "insurance_paid": paid, "adjustment": adj,
            "patient_responsibility": share}


def raw_doc(doc_id="S1", lines=None, balance="$50.00") -> dict:
    return {"doc_id": doc_id, "kind": "eob", "patient_balance": balance, "lines": lines if lines is not None else [raw_line()]}


def docs(*raw) -> list:
    return reader.to_documents({"documents": list(raw)}, EXPECTED)[0]


class Script:
    """Answers each read from a list, and keeps what was asked."""

    live = False

    def __init__(self, *answers):
        self.answers, self.bodies, self.labels = list(answers), [], []

    def respond(self, body, label=""):
        self.bodies.append(body)
        self.labels.append(label)
        return SimpleNamespace(text=json.dumps({"documents": list(self.answers.pop(0))}), usage={}, seconds=0.1, replayed=True)


def sheets(*ids) -> list:
    return [(i, b"\xff\xd8sheet") for i in ids]


def row(*amounts, code="99213") -> Row:
    return Row("", {Decimal(a) for a in amounts}, {code})


def run(client, first, *ids, printed=None):
    problems = []
    out = reconcile_read.reconcile(client, first, sheets(*(ids or ("S1",))), printed or {}, problems)
    return out, problems


def test_two_reads_that_agree_change_nothing_and_cost_no_third_read():
    client = Script([raw_doc()])
    out, problems = run(client, docs(raw_doc()))
    assert client.labels == ["spark:read-2"] and out[0].doubts == [] and problems == []


def test_the_second_read_sees_the_sheets_in_the_other_order():
    client = Script([raw_doc("S2"), raw_doc("S1")])
    run(client, docs(raw_doc("S1"), raw_doc("S2")), "S1", "S2")
    asked = [c["text"] for c in client.bodies[0]["input"][1]["content"] if c.get("type") == "input_text"]
    assert [t for t in asked if t.startswith("Sheet")] == ["Sheet S2:", "Sheet S1:"]


def test_the_device_settles_a_difference_without_a_third_read():
    client = Script([raw_doc(lines=[raw_line(share="$60.00", adj="$140.00")])])
    out, _ = run(client, docs(raw_doc()), printed={"S1": [row("500.00", "300.00", "150.00", "50.00")]})
    assert client.labels == ["spark:read-2"]
    assert out[0].lines[0].patient_responsibility == Decimal("50.00") and out[0].doubts == []


def test_the_device_can_side_with_the_second_read():
    client = Script([raw_doc(lines=[raw_line(share="$60.00", adj="$140.00")])])
    out, _ = run(client, docs(raw_doc()), printed={"S1": [row("500.00", "300.00", "140.00", "60.00")]})
    assert out[0].lines[0].patient_responsibility == Decimal("60.00") and out[0].doubts == []


def test_a_third_read_settles_what_the_device_cannot():
    client = Script([raw_doc(lines=[raw_line(share="$60.00", adj="$140.00")])], [raw_doc()])
    out, problems = run(client, docs(raw_doc()))
    assert client.labels == ["spark:read-2", "spark:read-3"]
    assert out[0].lines[0].patient_responsibility == Decimal("50.00") and out[0].doubts == []
    assert any("third" in p for p in problems)


def test_three_reads_that_all_differ_leave_the_sheet_unconfirmed():
    client = Script([raw_doc(lines=[raw_line(share="$60.00", adj="$140.00")])],
                    [raw_doc(lines=[raw_line(share="$70.00", adj="$130.00")])])
    out, _ = run(client, docs(raw_doc()))
    assert out[0].doubts and "S1" in out[0].doubts[0]


def test_a_different_count_of_lines_goes_to_a_third_read():
    two = [raw_line(), raw_line(2, "85025", "$40.00", "$20.00", "$10.00", "$10.00")]
    client = Script([raw_doc(lines=two)], [raw_doc(lines=two)])
    out, _ = run(client, docs(raw_doc()))
    assert client.labels == ["spark:read-2", "spark:read-3"] and len(out[0].lines) == 2 and out[0].doubts == []


def test_a_line_that_does_not_add_up_in_both_reads_is_not_settled_by_their_agreement():
    wrong = [raw_line(share="$90.00")]  # 500 - 300 - 150 is 50, not 90
    client = Script([raw_doc(lines=wrong)], [raw_doc(lines=wrong)])
    out, _ = run(client, docs(raw_doc(lines=wrong)))
    assert out[0].doubts and "add up" in out[0].doubts[0]


def test_a_line_that_adds_up_with_a_discount_is_fine():
    assert reconcile_read.does_not_add_up(docs(raw_doc())[0]) == []
    line = dict(raw_line(share="$40.00"), fa_discount="$10.00")
    assert reconcile_read.does_not_add_up(docs(raw_doc(lines=[line]))[0]) == []


def test_a_balance_the_reads_differ_on_counts_too():
    client = Script([raw_doc(balance="$60.00")], [raw_doc(balance="$70.00")])
    out, _ = run(client, docs(raw_doc()))
    assert out[0].doubts


def test_a_balance_both_reads_left_out_is_taken_from_the_sheets_last_balance_row():
    client = Script([raw_doc(balance="")])
    moved = Row("Balance Transferred To Payment Plan ($712.31)", {Decimal("712.31")}, set())
    last = Row("Your Balance Due On These Services... $0.00", {Decimal("0.00")}, set())
    out, problems = run(client, docs(raw_doc(balance="")), printed={"S1": [moved, last]})
    assert out[0].patient_balance == Decimal("0.00") and any("read on this device" in p for p in problems)


def test_no_more_third_reads_than_the_limit():
    ids = [f"S{i}" for i in range(1, 12)]
    expected = {i: Source.PAPER for i in ids}
    first = reader.to_documents({"documents": [raw_doc(i) for i in ids]}, expected)[0]
    second = [raw_doc(i, lines=[raw_line(share="$60.00", adj="$140.00")]) for i in ids]
    client = Script(second, *[[raw_doc(i)] for i in ids])
    problems = []
    out = reconcile_read.reconcile(client, first, sheets(*ids), {}, problems)
    assert client.labels.count("spark:read-3") == reconcile_read.THIRD_READS
    assert sum(bool(d.doubts) for d in out) == len(ids) - reconcile_read.THIRD_READS


def test_a_live_case_is_read_twice_and_a_replay_only_when_it_was_recorded_so(monkeypatch):
    from billradar import pipeline
    monkeypatch.delenv(pipeline.SECOND_READ, raising=False)
    assert pipeline.second_read_on(SimpleNamespace(live=True)) and not pipeline.second_read_on(SimpleNamespace(live=False))
    monkeypatch.setenv(pipeline.SECOND_READ, "1")
    assert pipeline.second_read_on(SimpleNamespace(live=False))
    monkeypatch.setenv(pipeline.SECOND_READ, "0")
    assert not pipeline.second_read_on(SimpleNamespace(live=True))
