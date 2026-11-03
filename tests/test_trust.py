"""Trust screens: the example case, "Is it safe?", deleting a case, the case history, who did what.

SYNTHETIC data only: the example is a fictional sample pack answered from its generator's files.
"""

import html as htmllib
import json
import re
import socket
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from billradar import app as app_module
from billradar import evaluation as ev
from billradar import example, history, view
from billradar.checks import Evidence, Finding, Kind
from billradar.policies import source
from tests.synth import table_photo
from tests.test_app import fake_client
from tests.test_sam import QUADS, SIZE

ROOT = Path(__file__).parents[1]
needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), reason="run scripts/fetch_policies.py first")


@pytest.fixture(scope="session")
def example_runs(tmp_path_factory):
    """The example cases, built once per test session (the private one runs local OCR: slow)."""
    d = tmp_path_factory.mktemp("examples")
    if all(source.is_cached(p) for p in source.SOURCES):
        example.ensure(d)
    return d


@pytest.fixture
def client(tmp_path, monkeypatch, example_runs):
    import shutil
    shutil.copytree(example_runs, tmp_path, dirs_exist_ok=True)
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    monkeypatch.delenv("BILLRADAR_PUBLIC", raising=False)
    return TestClient(app_module.app)


def _no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("the example must not touch the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)


def _key():
    return ev.Key.model_validate_json((example.PACK / "key.json").read_text())


@needs_text
def test_example_is_replayed_offline_fast_and_matches_its_key(monkeypatch):
    _no_network(monkeypatch)
    t = time.monotonic()
    run = example.run_pack(example.PACK, example.EXAMPLE_ID)
    assert time.monotonic() - t < 90  # Я21: findings, letters and the screen offline; 18–24 s on default OCR threads, 32–34 s on 2 (a judge's slower machine)
    assert run.replayed and run.case.demo
    s = ev.score(_key(), ev.from_report(run.report))
    assert all(c.found == c.n and not c.false and not c.wrong_amount and not c.wrong_deadline
               for c in s.by_class.values()), ev.table({"example": s})
    assert s.by_class and not s.extra_false


@needs_text
def test_replay_script_still_gives_the_same_result():
    """scripts/replay_pack.py is now a wrapper around billradar.example; its table must still equal the key."""
    out = subprocess.run([sys.executable, "scripts/replay_pack.py", str(example.PACK), "--private"], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr
    key = _key()
    for cls in {i.cls for i in key.items}:
        n = sum(1 for i in key.items if i.cls == cls)
        assert re.search(rf"\| {cls} \| {n} of {n}( \(.*\))? \|", out.stdout), out.stdout
    assert "false" not in out.stdout.lower() or "0 false" in out.stdout.lower()


@needs_text
def test_example_page_is_labelled_and_never_claims_covering_on_this_pack(client):
    page = htmllib.unescape(client.get("/example").text)
    assert "Example case — all data is made up" in page
    assert "Try with my bills" in page
    assert "Delete this case" not in page  # the example cannot be deleted
    # the models-saw view is the same pack in private mode, and the page says the PDFs are not sent there
    assert "/cases/example-private/sent-sheet/S1.jpg" in page  # each covered sheet as the model got it
    assert "photos and PDF pages leave your computer like this" in page
    rows = page.count('class="frow ')
    report = json.loads((app_module.RUNS / "example" / "report.json").read_text())
    assert rows == len(report["findings"]) + len(report["worth_asking"]) + len(report["no_money"])
    # every finding row says which model found and read its sheets, and that it was a replay
    for block in page.split('class="frow ')[1:]:
        block = block.split("</article>")[0]
        assert 'class="model ' in block and ">recorded<" in block


@needs_text
def test_safe_page_shows_what_left_the_device(client):
    page = htmllib.unescape(client.get("/safe").text)
    assert "What Meta's models saw" in page and "sent-sheet/S1.jpg" in page  # the sheet as photographed and as sent
    assert client.get("/cases/example-private/overlay/sent-1.jpg").headers["content-type"] == "image/jpeg"
    assert "Open a case to delete it." in page


def test_how_page_names_every_model_and_its_status(client):
    page = htmllib.unescape(client.get("/how").text)
    for m in view.MODEL_STATUS:
        assert m.model in page and m.status in page
    assert "You review and sign every letter." in page


def _make_case(client, monkeypatch):
    """Upload a fictional case through the real form and send all its sheets; returns (case id, the upload's response)."""
    monkeypatch.setattr(app_module.providers, "make_client", fake_client)
    form = {"policy_id": "memorial-2026-05", "letterhead": "Lakeview Demo Hospital", "household_size": "4",
            "annual_income": "85000", "liquid_assets": "6000", "insured": "true", "mother_name": "Anna",
            "baby_name": "Baby", "fictional": "true"}
    photo = ("table.jpg", table_photo(QUADS, SIZE), "image/jpeg")
    created = client.post("/cases", data=form, files={"photos": photo}, follow_redirects=False)
    assert created.status_code == 303
    review = created.headers["location"]
    case_id = re.fullmatch(r"/cases/(c[0-9a-f]{10})/review", review).group(1)

    sheets = re.findall(r'<input type="radio" name="(S\d+)" value="send" checked>', client.get(review).text)
    sent = client.post(f"/cases/{case_id}/send", data={name: "send" for name in sheets}, follow_redirects=False)
    assert sent.status_code == 303
    return case_id, created


@needs_text
def test_delete_needs_the_cookie_on_a_public_deploy(client, monkeypatch, tmp_path):
    case_id, r = _make_case(client, monkeypatch)  # a public copy takes no uploads: the case comes first
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    cookie = r.cookies.get(history.cookie_name(case_id))
    assert cookie and "token_sha256" in (tmp_path / case_id / "owner.json").read_text()
    assert cookie not in (tmp_path / case_id / "owner.json").read_text()  # only a hash is kept

    stranger = TestClient(app_module.app)
    assert stranger.post(f"/cases/{case_id}/delete", follow_redirects=False).status_code == 403
    stranger.cookies.set(history.cookie_name(case_id), "not-the-token", path=f"/cases/{case_id}")
    assert stranger.post(f"/cases/{case_id}/delete", follow_redirects=False).status_code == 403
    assert (tmp_path / case_id).exists()

    owner = TestClient(app_module.app)
    owner.cookies.set(history.cookie_name(case_id), cookie, path=f"/cases/{case_id}")
    page = owner.get(f"/cases/{case_id}").text
    assert "Delete this case" in page
    d = owner.post(f"/cases/{case_id}/delete", follow_redirects=False)
    assert d.status_code == 303 and d.headers["location"] == f"/cases?deleted={case_id}"
    assert not (tmp_path / case_id).exists()
    assert owner.get(f"/cases/{case_id}").status_code == 404


def test_examples_can_never_be_deleted_and_odd_ids_are_404(client, tmp_path):
    runs = tmp_path / "other"
    for case_id in example.READ_ONLY:
        (runs / case_id).mkdir(parents=True)
        (runs / case_id / "case.json").write_text("{}")
        assert not history.delete(runs, case_id, None)
        assert (runs / case_id).exists()
    assert client.post("/cases/..%2F..%2Fetc/delete").status_code == 404
    assert client.post("/cases/nope/delete").status_code == 404
    assert not history.delete(runs, "../x", None)


@needs_text
def test_history_lists_runs_on_this_device_but_not_on_a_public_deploy(client, monkeypatch):
    case_id, _ = _make_case(client, monkeypatch)
    page = client.get("/cases").text
    assert f'data-id="{case_id}"' in page and "Anna&#39;s birth case" in page
    summary = client.get(f"/cases/{case_id}/summary.json").json()
    assert summary["case_id"] == case_id and summary["demo"] and summary["sheets"] == 5
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    assert f'data-id="{case_id}"' not in client.get("/cases").text  # strangers do not see other people's cases
    assert client.get("/cases/nope/summary.json").status_code == 404


def _finding(docs):
    return Finding(kind=Kind.E2, title="t", detail="d", evidence=[Evidence(doc_id=d) for d in docs])


def test_model_labels_come_from_the_run_not_hard_wired():
    ran = {"sam": 1.0, "spark": 2.0}
    f = _finding(["S1", "D1"])
    assert [t.label for t in view.models_for(f, {"replayed": True, "timings": ran})] == ["SAM 3.1", "Muse Spark"]
    assert all(t.replayed for t in view.models_for(f, {"replayed": True, "timings": ran}))
    assert [t.label for t in view.models_for(_finding(["D1"]), {"timings": ran})] == ["Muse Spark"]  # a PDF: no photo
    other = {"provider": "other", "models": {"find": "Finder X", "read": "Reader Y"}, "replayed": False, "timings": ran}
    assert [t.label for t in view.models_for(f, other)] == ["Finder X", "Reader Y"]
    # a case whose papers were typed in (no photo, no model reading): no model is credited
    assert view.models_for(f, {"timings": {}}) == []
    # the reviewer appears only when it really answered
    assert "Muse Wonder" not in [t.label for t in view.models_for(f, {"checker": {"issues": []}, "timings": ran})]
    reviewed = {"checker": {"issues": [{"what": "Muse Wonder: wording"}]}, "timings": ran}
    assert "Muse Wonder" in [t.label for t in view.models_for(f, reviewed)]


def test_a_card_flagged_by_wonder_says_who_flagged_it_and_not_its_words():
    shown = view._unsure("Muse Wonder: the sheet gives 2025-12-01 for this line; the sum is off by S4")
    assert shown == "Muse Wonder flagged this on its second look; its notes are in the case data."
    assert view._unsure("the bill has no payment date") == "the bill has no payment date."  # must light: other reasons keep their words
    assert view._unsure("") == ""


def test_an_unconfirmed_card_never_prints_the_second_reads_own_words(client):
    """The second read's reason can hold "; " itself (the F2 card once printed "...the policy window ... gives 2026-02-11
    or an unknown date" after the cut): the card says who doubted it, the words stay in the case data."""
    why = ("Muse Wonder: the quoted rule gives 2025-12-01; the policy window gives 2026-02-11 or an "
           "unknown date; Muse Wonder: could not check it from the papers")
    shown = view._unsure(why)
    assert "policy window" not in shown and "unknown date" not in shown and "2025-12-01" not in shown
    assert shown.startswith("Muse Wonder flagged this on its second look; its notes are in the case data")
    assert re.sub(r"Muse Wonder:[^;]*", "X", why).count("policy window") == 1  # must light: the old cut kept it
    page = client.get("/example").text
    assert "policy window" not in page and "unknown date" not in page


def test_the_policy_finder_page_is_linked_from_how_and_the_example(client):
    for path in ("/how", "/example"):
        assert 'href="/policy-finder"' in client.get(path).text, path
    assert client.get("/policy-finder").status_code == 200


def test_the_doctors_bills_card_names_each_office_once_on_hover_too(client):
    """The NM card's hover text once read "300_Women First OB/GYN Care, LLC, ..., Women First OB/GYN Care, LLC":
    the raw words of the check, kept as they are in the case data. The hover now says what the card says."""
    page = client.get("/example").text
    assert "300_" not in page
    m = re.search(r'<p title="([^"]*)">([^<]*)</p>', page[page.index("outside the hospital"):])
    assert m and m.group(1) == m.group(2)


def test_illustrations_are_said_once_on_the_home_page_not_as_badges(client):
    home = client.get("/").text
    assert home.count("Pictures on this page are illustrations; numbers and screens come from the app.") == 1
    for path in ("/", "/how", "/safe", "/example"):
        assert re.findall(r"(?i)illustration(?!s; numbers)", client.get(path).text) == [], path


def test_borderline_findings_show_no_amount():
    from decimal import Decimal

    from billradar.case import Case, Profile
    case = Case(case_id="x", policy_id="memorial-2026-05", today=date(2026, 7, 20),
                profile=Profile(household_size=2, annual_income=Decimal(1)), documents=[])
    f = _finding(["S1"]).model_copy(update={"amount": Decimal("312.00"), "severity": "borderline"})
    r = view.row(f, case, "memorial-2026-05", {})
    assert r.level == "worth checking" and "312" not in r.value and r.value == "No amount yet"
    r2 = view.row(f.model_copy(update={"severity": None}), case, "memorial-2026-05", {})
    assert r2.level == "serious" and r2.value == "$312.00"


def test_upload_without_live_calls_or_a_recording_says_so(client, monkeypatch):
    """A public deploy has no keys yet: a new upload must not fake a result."""
    from billradar.meta_client import MetaClient
    from tests.synth import table_photo
    from tests.test_sam import QUADS, SIZE
    monkeypatch.setattr(app_module.providers, "make_client", lambda: MetaClient(record_to=None, journal=None))
    r = client.post("/cases", data={"policy_id": "memorial-2026-05", "household_size": "3", "annual_income": "50000",
                                    "fictional": "true"},
                    files=[("photos", ("t.jpg", table_photo(QUADS, SIZE), "image/jpeg"))], follow_redirects=False)
    assert r.status_code == 503
    assert "starts when the model calls are switched on" in r.text and 'href="/example"' in r.text


@needs_text
def test_letter_page_lists_letters_and_marks_quotes(client):
    page = htmllib.unescape(client.get("/example").text)
    kind = re.search(r'href="/cases/example/letters/([a-z-]+)"', page).group(1)
    letter = htmllib.unescape(client.get(f"/cases/example/letters/{kind}").text)
    assert "Letters and appeal" in letter and 'id="copy"' in letter and 'id="save"' in letter
    assert "SAMPLE — FICTIONAL DATA" in letter
    kinds = set(re.findall(r'href="/cases/example/letters/([a-z0-9-]+)[?"]', page))
    calls = letter.count('class="lthumb call"')
    assert letter.count('class="lcard') - calls == len(kinds) and calls >= 1



def test_agents_entry_is_mounted_after_the_screens(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    with TestClient(app_module.app) as c:  # runs the lifespan once, as in production
        assert c.get("/agents/healthz").json()["mcp"] == "/mcp"
        card = c.get("/.well-known/agent-card.json")
        assert card.status_code == 200 and "skills" in card.text
        page = c.get("/agents").text
        assert "For AI agents" in page and "/mcp" in page and "list_sample_packs" in page
        assert c.get("/how").status_code == 200  # the screens still win over the mount


def test_pdf_files_show_their_first_page(client):
    page = client.get("/cases/example").text
    assert "/cases/example/file/D1.jpg" in page
    r = client.get("/cases/example/file/D1.jpg")
    assert r.status_code == 200 and r.content[:2] == b"\xff\xd8"
    assert client.get("/cases/example/file/..%2Fcase.json").status_code == 404


def test_example_second_read_replays(client, tmp_path):
    """Changing a letter or a finding changes the review request; then its recording must be made again
    (one live review call per example run), or the example silently loses the second read."""
    import json as _json
    client.get("/cases/example")
    for case_id in ("example", "example-private"):
        checker = _json.loads((app_module.RUNS / case_id / "problems.json").read_text())["checker"]
        assert not [i for i in checker["issues"] if "review did not run" in i["what"]], case_id


def test_one_chip_when_one_model_finds_and_reads():
    ran = {"sam": 1.0, "spark": 2.0}
    meta = {"replayed": True, "timings": ran, "models": {"find": "Muse Spark", "read": "Muse Spark"}}
    labels = [t.label for t in view.models_for(_finding(["S1"]), meta)]
    assert labels == ["Muse Spark · found & read"]


def test_the_example_shows_the_double_charge_on_its_sheet(client):
    """The card links its marked sheet, and the mark stands on the row of the sum, confirmed by SAM 3.1."""
    from billradar import highlight
    page = client.get("/cases/example").text
    assert "See this line on the sheet" in page
    marks = highlight.load(app_module.RUNS / "example")
    assert {m.kind for m in marks} == {"E2", "E3"} and all(m.by == "SAM 3.1" for m in marks)
    href = f"/cases/example/marked/{marks[0].index}.jpg"
    assert href in page
    r = client.get(href)
    assert r.status_code == 200 and r.content[:2] == b"\xff\xd8"
    assert client.get("/cases/example/marked/..%2Fcase.json").status_code == 404


def test_with_no_seed_the_example_is_the_recording_or_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(example, "DEMO_CASES", tmp_path / "no-seeds")
    monkeypatch.setattr(source, "CACHE", tmp_path)
    with pytest.raises(source.PolicyMissing):
        example.ensure(tmp_path / "runs", tmp_path / "no-image-seeds")
    assert not (tmp_path / "runs" / example.EXAMPLE_ID).exists()


def test_a_replay_that_lost_its_review_is_not_the_recording(monkeypatch):
    from types import SimpleNamespace

    from billradar.meta_client import ReplayMissing
    issue = SimpleNamespace(subject="model review", what="review did not run: no recording")
    monkeypatch.setattr(example, "_run", lambda *a, **k: SimpleNamespace(verdict=SimpleNamespace(issues=[issue])))
    with pytest.raises(ReplayMissing):
        example.run_recorded(example.PACK, example.EXAMPLE_ID)
