"""What the visitor is told about their data and about what BillRadar is. Every line on /privacy stands on the code."""

from pathlib import Path

from fastapi.testclient import TestClient

from billradar import app as app_module, voice

WEB = Path(app_module.__file__).parent / "web"


def test_the_privacy_page_says_what_leaves_and_where():
    page = TestClient(app_module.app).get("/privacy", headers={"accept": "text/html"})
    assert page.status_code == 200
    for fact in ("request log", "api.meta.ai", "Tavily", "Google Fonts", "until you delete it", "not its content"):
        assert fact in page.text


def test_each_fact_on_the_page_stands_on_the_code():
    body = (Path(app_module.__file__).parent / "ask.py").read_text()
    assert '"store": False' in body
    base = (WEB / "templates" / "base.html").read_text()
    assert "fonts.googleapis.com" in base
    assert "uvicorn" in (Path(app_module.__file__).parents[1] / "Dockerfile").read_text()
    assert "no-access-log" not in (Path(app_module.__file__).parents[1] / "Dockerfile").read_text()
    assert voice.LANGUAGES  # voice exists on this build, so the page may speak of it


def test_every_page_carries_the_line_and_the_link():
    for address in ("/how", "/upload", "/agents"):
        page = TestClient(app_module.app).get(address, headers={"accept": "text/html"}).text
        assert "Not legal or medical advice" in page and 'href="/privacy"' in page
