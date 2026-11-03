"""Screens for letters in three languages, Copy/Save/PDF, the PDF report, the call cheat sheet and the voice note.

The example with a denied claim is SYNTHETIC (tests/fixtures/cases/sample-appeal.json). No live model calls:
a translation or a voice note without a recording must say so, never show something made up.
"""

import html as htmllib
import io
import re
import wave
from datetime import date

import pytest
from fastapi.testclient import TestClient

from billradar import app as app_module
from billradar.policies import source
from tests.test_trust import example_runs  # noqa: F401  (session fixture)

needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES),
                                reason="run scripts/fetch_policies.py first")


@pytest.fixture
def client(tmp_path, monkeypatch, example_runs):
    import shutil
    shutil.copytree(example_runs, tmp_path, dirs_exist_ok=True)
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    monkeypatch.delenv("BILLRADAR_PUBLIC", raising=False)
    monkeypatch.delenv("BILLRADAR_LIVE", raising=False)
    return TestClient(app_module.app)


def _appeal_kind(client) -> str:
    page = client.get("/cases/example-appeal").text
    return re.search(r'/cases/example-appeal/letters/(appeal-[a-z0-9-]+)"', page).group(1)


@needs_text
def test_case_shows_appeal_call_sheets_and_pdf_report(client):
    page = htmllib.unescape(client.get("/cases/example-appeal").text)
    assert "Insurance appeal" in page and "Before you call" not in page
    assert page.count("/cases/example-appeal/call/") == 2  # the hospital and the insurer
    for lang in ("en", "ru", "es"):
        assert f"/cases/example-appeal/report.pdf?lang={lang}" in page
    assert client.get("/cases/example-appeal/report.pdf?lang=ru").content.startswith(b"%PDF-")
    assert client.get("/cases/example-appeal/report.pdf?lang=xx").status_code == 400


@needs_text
def test_appeal_letter_shows_deadline_and_never_fakes_a_translation(client):
    kind = _appeal_kind(client)
    en = htmllib.unescape(client.get(f"/cases/example-appeal/letters/{kind}").text)
    assert "Deadline:" in en and "days from the denial notice" in en and "Stops before Send" in en
    assert "Plan document p." in en  # quotes from her plan, with the page
    assert '<span class="quoted">“' in en  # only the quoted words are marked
    ru = htmllib.unescape(client.get(f"/cases/example-appeal/letters/{kind}?lang=ru").text)
    # no recording of a translation exists: the page says so and shows the English letter only
    assert app_module.NOT_LIVE in ru and "letter translation" not in ru
    assert client.get(f"/cases/example-appeal/letters/{kind}?lang=de").status_code == 400


@needs_text
def test_copy_save_and_pdf_give_the_letter_to_send(client):
    kind = _appeal_kind(client)
    text = client.get(f"/cases/example-appeal/letters/{kind}/text").text
    assert text.startswith("SAMPLE - FICTIONAL DATA") and "Sincerely," in text
    page = client.get(f"/cases/example-appeal/letters/{kind}").text
    assert f'data-src="/cases/example-appeal/letters/{kind}/text?lang=en"' in page  # Copy fetches the same text
    assert client.get(f"/cases/example-appeal/letters/{kind}/pdf").content.startswith(b"%PDF-")


@needs_text
def test_call_cheat_sheets_and_the_voice_note_without_a_recording(client):
    for to, who in (("hospital", "Lakeview Demo Hospital"), ("insurer", "Sample Health Plan")):
        page = htmllib.unescape(client.get(f"/cases/example-appeal/call/{to}").text)
        assert f"Before you call {who}" in page and "Say this first" in page and "Ask for" in page
    assert client.get("/cases/example-appeal/call/dentist").status_code == 404
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(b"\0\0" * 16000)
    r = client.post("/cases/example-appeal/call/hospital/note?lang=en", content=buf.getvalue())
    assert r.status_code == 503 and "switched on" in r.json()["error"]
    assert client.post("/cases/example-appeal/call/hospital/note?lang=ru", content=buf.getvalue()).status_code == 400
    assert client.post("/cases/example-appeal/call/hospital/note?lang=en", content=b"not a wav").status_code in (400, 503)


@needs_text
def test_appeal_tracker_owner_marks_sent_examples_are_read_only(client, monkeypatch, tmp_path):
    page = htmllib.unescape(client.get("/cases/example-appeal/appeals").text)
    assert "Track your appeals and letters" in page and "last day to appeal" in page
    assert "Examples are read-only" in page
    key = re.search(r'href="/cases/[^"?]+/appeals\?key=(appeal-[a-z0-9-]+)"', page).group(1)  # absolute: the static copy crawls it
    assert client.post(f"/cases/example-appeal/appeals/{key}/sent", data={"on": "2026-10-28"},
                       follow_redirects=False).status_code == 403
    ics = client.get("/cases/example-appeal/appeals.ics").text
    assert "Last day to appeal" in ics and "TRIGGER:-P7D" in ics

    # her own case (made on this device): she marks it sent; the tracker counts the days
    import shutil
    shutil.copytree(tmp_path / "example-appeal", tmp_path / "mine")
    r = client.post(f"/cases/mine/appeals/{key}/sent", data={"on": "2026-10-20", "confirmation": "A-123"},
                    follow_redirects=False)
    assert r.status_code == 303
    after = htmllib.unescape(client.get(f"/cases/mine/appeals?key={key}").text)
    assert "A-123" in after and "Got a reply? Take a photo" in after
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")  # on a public deploy a stranger cannot change it
    assert client.post(f"/cases/mine/appeals/{key}/sent", data={"on": "2026-10-21"},
                       follow_redirects=False).status_code == 403


@needs_text
def test_findings_show_plain_lines_and_ask_never_fakes_an_answer(client):
    page = htmllib.unescape(client.get("/example").text)
    assert "% sure" not in page  # an unmeasured number is not shown: the level and its label say what is known
    assert "What these lines mean" in page and "Your share" in page
    assert 'id="ask"' in page
    r = client.post("/cases/example/ask", json={"question": "Why is the baby's bill on my insurance?"})
    assert r.status_code == 200
    j = r.json()
    if j["reason"] == "no_model":  # no live call and no recording: says so, no made-up answer, no citations
        assert j["refused"] and "not connected" in j["text"] and j["citations"] == []
    assert client.post("/cases/example/ask", json={"question": ""}).status_code == 400


def test_a_wrong_address_gets_a_page_with_a_way_back(client):
    html = {"accept": "text/html"}
    for url in ("/no-such-page", "/cases/no-such-case/letters/itemized"):
        r = client.get(url, headers=html)
        assert r.status_code == 404 and "Back to the start" in r.text and 'class="nav' in r.text
    assert client.get("/no-such-page").headers["content-type"].startswith("text/plain")  # not a browser: no page
    assert client.get("/.well-known/agent-card.json", headers=html).headers["content-type"].startswith("application/json")


def test_the_side_of_a_letter_speaks_about_that_letter(client):
    itemized = client.get("/cases/example/letters/itemized").text
    application = client.get("/cases/example/letters/application").text
    assert "Last day to apply" not in itemized and "Last day to apply" in application
    dispute = client.get("/cases/example/letters/dispute").text
    assert "This letter quotes no rule" in dispute and "the hospital's published policy" not in htmllib.unescape(dispute)
    kind = _appeal_kind(client)
    appeal = htmllib.unescape(client.get(f"/cases/example-appeal/letters/{kind}").text)
    assert "quoted from your plan's document or the law" in appeal and "must be received" not in appeal


def test_protections_are_numbered_in_the_order_shown(client):
    numbers = re.findall(r'class="ln">(\d+)<', client.get("/example").text)
    assert numbers and numbers == [str(i + 1) for i in range(len(numbers))]


def test_a_passed_deadline_reads_as_passed(client, monkeypatch):
    load = app_module._load

    def later(case_id, *a, **k):
        d, case, report = load(case_id, *a, **k)
        return d, case.model_copy(update={"today": date(2099, 1, 1)}), report

    monkeypatch.setattr(app_module, "_load", later)
    page = htmllib.unescape(client.get("/cases/example").text)
    assert "Deadline reminder" not in page and "reminder.ics" not in page
    letter = htmllib.unescape(client.get("/cases/example/letters/application").text)
    assert "The last day to apply was" in letter and "Add to my calendar" not in letter


def test_the_arrow_on_a_finding_opens_its_sheet(client):
    html = client.get("/example").text
    arrows = re.findall(r'<a class="chev" href="(/cases/example/(?:sheet|file)/[SD]\d+\.jpg)"', html)
    assert arrows and all(client.get(a).status_code == 200 for a in set(arrows))
    assert '<div class="chev"' not in html  # no arrow that goes nowhere


def test_a_question_goes_to_the_case_on_the_example_address(client):
    assert 'fetch("/cases/example/ask"' in client.get("/example").text.replace("\\u0022", '"')


def test_the_application_letter_says_to_check_the_date_and_the_tracker_reads_as_a_label(client):
    page = client.get("/cases/example/letters/application").text
    assert "Check the date with the hospital." in page and "before this day" not in page
    tracker = client.get("/cases/example-appeal/appeals").text
    assert "Last day to appeal:" in tracker and ">last day to appeal" not in tracker
    assert "fills, you press Send" in tracker


def test_a_case_without_a_recorded_picture_asks_for_none(client):
    assert "picture.png" not in client.get("/cases/example-appeal").text
    assert "picture.png" in client.get("/example").text  # must light: the example has its picture


def test_the_bill_picture_is_not_lazy_inside_its_hidden_card(client):
    html = client.get("/example").text
    if "picture-card" in html:
        assert 'loading="lazy" onload' not in html


def test_without_live_voice_the_call_page_offers_the_recorded_call(client):
    page = htmllib.unescape(client.get("/cases/example/call/hospital").text)
    assert "See a recorded call" in page and "Start a live call" not in page and 'data-live="0"' in page
    assert "The microphone is off on this copy." in page and 'id="mic" aria-label="Tap to record" disabled' in page
    script = client.get("/static/call-live.js").text
    assert 'sample }' in script and "d.sample" in script
