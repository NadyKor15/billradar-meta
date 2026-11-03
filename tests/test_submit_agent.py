"""Muse Spark files the appeal on the demo copy of the portal (pack A, Я18). The model's turns are SYNTHETIC
`computer_call` items in the shape documented at dev.meta.ai/docs/computer-use.md; the browser is a fake
driver that keeps the form in memory and draws its screenshots."""

import io
import json
import re
from html.parser import HTMLParser

import pytest
from PIL import Image, ImageDraw

from billradar import appeal, plans, submit_agent
from billradar.meta_client import LiveTransport, MetaClient
from billradar.pipeline import RealDataGate
from tests import test_appeal

URL = submit_agent.portal_url()


class FakeDriver:
    """Fields stacked top to bottom, 40 px each, Submit button below them."""

    def __init__(self, url: str = URL):
        self._url = url
        self.fields = {k: "" for k in submit_agent.PORTAL_FIELDS}
        self.focus = None
        self.submitted = 0
        self.clicks = []

    def _at(self, x, y):
        i = (y - 20) // 40
        if 0 <= i < len(submit_agent.PORTAL_FIELDS):
            return submit_agent.PORTAL_FIELDS[i]
        if i == len(submit_agent.PORTAL_FIELDS):
            return "submit"
        return None

    def center(self, key):
        i = len(submit_agent.PORTAL_FIELDS) if key == "submit" else submit_agent.PORTAL_FIELDS.index(key)
        return 200, 20 + i * 40 + 20

    def url(self):
        return self._url

    def screenshot(self):
        img = Image.new("RGB", (640, 520), "white")
        d = ImageDraw.Draw(img)
        for k, v in self.fields.items():
            _, y = self.center(k)
            d.text((10, y - 6), f"{k}: {v}", fill="black")
        d.text((10, self.center("submit")[1] - 6), "[Submit appeal]", fill="blue")
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

    def element_at(self, x, y):
        k = self._at(x, y)
        if k == "submit":
            return {"id": "submit", "tag": "button", "type": "submit", "text": "Submit appeal"}
        return {"id": k, "tag": "input", "type": "text", "text": ""} if k else None

    def click(self, x, y, button="left"):
        self.clicks.append((x, y))
        k = self._at(x, y)
        if k == "submit":
            self.submitted += 1
        else:
            self.focus = k

    def double_click(self, x, y):
        self.click(x, y)

    def type(self, text):
        if self.focus:
            self.fields[self.focus] += text

    def keypress(self, keys):
        if {"enter", "return"} & {k.lower() for k in keys}:
            self.submitted += 1

    def scroll(self, x, y, dx, dy):
        pass

    def values(self):
        return dict(self.fields)

    def confirmation(self):
        return "Appeal received (SAMPLE). Confirmation number SHP-APL-01234." if self.submitted else ""


class ScriptedWonder:
    """Returns one turn per request: a list of actions (a computer_call) or a final sentence."""

    def __init__(self, turns, safety=None):
        self.turns, self.safety, self.bodies = list(turns), safety, []

    def events(self, body):
        self.bodies.append(json.loads(json.dumps(body)))
        n = len(self.bodies)
        turn = self.turns.pop(0) if self.turns else "Done."
        if isinstance(turn, str):
            out = [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": turn}]}]
            evs = [{"type": "response.output_text.delta", "delta": turn}]
        else:
            out = [{"type": "computer_call", "id": f"cc_{n}", "call_id": f"call_{n}", "actions": turn,
                    "pending_safety_checks": self.safety or [], "status": "completed",
                    "meta_safety_replay_receipt": f"receipt-SYNTHETIC-{n}"}]
            evs = []
        return evs + [{"type": "response.completed", "response": {"id": f"resp_SYNTHETIC_{n}", "usage": {},
                                                                  "output": out}}]


def values():
    c = test_appeal.case()
    return c, appeal.form_values(c, plans.load("sample-health-plan-2026"), appeal.denials(c)[0])


def fill_turns(driver, vals):
    turns = []
    for k in submit_agent.PORTAL_FIELDS:
        if vals.get(k):
            x, y = driver.center(k)
            turns.append([{"type": "click", "button": "left", "x": x, "y": y}, {"type": "type", "text": vals[k]}])
    return turns + ["Every field is filled. I did not submit."]


def run(turns, phase="fill", confirmed=False, driver=None, **kw):
    c, vals = values()
    driver = driver or FakeDriver()
    model = ScriptedWonder(turns(driver, vals) if callable(turns) else turns, kw.pop("safety", None))
    client = MetaClient(transport=model, record_to=None, journal=None)
    return submit_agent.run(client, driver, c, vals, phase, confirmed, **kw), driver, model, vals


# --- the demo page -------------------------------------------------------------------------------

def test_demo_portal_has_every_field_a_submit_button_and_the_sample_banner():
    ids = []

    class P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if "id" in a:
                ids.append(a["id"])

    html = submit_agent.PORTAL.read_text()
    P().feed(html)
    assert set(submit_agent.PORTAL_FIELDS) <= set(ids) and "submit" in ids and "confirmation" in ids
    assert "SAMPLE - FICTIONAL INSURER" in html and "Not a real portal" in html
    assert not re.search(r"https?://", html.split("<script>")[0].split("<style>")[0])  # nothing external


# --- fill, then stop ------------------------------------------------------------------------------

def test_fill_phase_fills_every_field_and_never_submits():
    r, d, model, vals = run(fill_turns)
    assert not r.mismatches and r.filled["claim_number"] == "CLM-7765301" and r.filled["member_id"] == "SHP-000-4417"
    assert r.stopped_before_submit and not r.submitted and d.submitted == 0 and r.confirmation == ""
    assert r.answer == "Every field is filled. I did not submit." and r.stopped == ""
    first, second = model.bodies[0], model.bodies[1]
    assert first["model"] == "muse-spark-1.3" and first["store"] is False and first["tools"] == [{"type": "computer"}]
    assert "Never press Submit" in first["instructions"]
    out = second["input"][-1]
    assert out["type"] == "computer_call_output" and out["call_id"] == "call_1"
    assert out["output"]["image_url"].startswith("data:image/png;base64,")
    assert second["input"][1]["meta_safety_replay_receipt"] == "receipt-SYNTHETIC-1"  # copied unchanged


def test_click_on_submit_in_the_fill_phase_is_blocked():
    def turns(d, vals):
        x, y = d.center("submit")
        return fill_turns(d, vals)[:2] + [[{"type": "click", "button": "left", "x": x, "y": y}]]
    r, d, *_ = run(turns)
    assert d.submitted == 0 and r.stopped == "stopped before Submit" and r.stopped_before_submit
    assert (d.center("submit")) not in d.clicks


def test_enter_in_a_field_is_blocked_in_the_fill_phase():
    def turns(d, vals):
        x, y = d.center("patient_name")
        return [[{"type": "click", "button": "left", "x": x, "y": y}, {"type": "type", "text": "x"},
                 {"type": "keypress", "keys": ["Enter"]}]]
    r, d, *_ = run(turns)
    assert d.submitted == 0 and "Enter" in r.stopped and r.steps[0].done == 2


def test_wrong_value_is_reported_after_reading_the_page_back():
    def turns(d, vals):
        t = fill_turns(d, vals)
        t[0] = [t[0][0], {"type": "type", "text": "Maria Smaple"}]
        return t
    r, *_ = run(turns)
    assert r.mismatches == ["patient_name: asked 'Maria Sample', page has 'Maria Smaple'"]


CONFIRM = [{"id": "cu_sc_1", "code": "computer_action_requires_confirmation", "message": "Review and confirm before executing this computer action."}]


def test_the_plain_confirmation_is_given_by_the_guards_and_named_back():
    """Every action comes with this check on Spark. The harness has already read what is under the pointer, on the
    allowed page, so it answers for the action, and echoes the check as the API asks."""
    r, d, model, vals = run(fill_turns, safety=CONFIRM)
    assert not r.stopped and d.fields["patient_name"] == vals["patient_name"]
    output = next(i for i in model.bodies[1]["input"] if i.get("type") == "computer_call_output")
    assert output["acknowledged_safety_checks"] == CONFIRM


def test_the_confirmation_does_not_open_the_submit_button():
    def press(driver, vals):
        x, y = driver.center("submit")
        return [[{"type": "click", "x": x, "y": y}]]

    r, d, *_ = run(press, safety=CONFIRM)
    assert not d.submitted and r.stopped


def test_any_other_check_with_it_still_stops_for_a_person():
    other = CONFIRM + [{"id": "csc_2", "code": "malicious_instructions", "message": "?"}]
    r, d, model, _ = run(fill_turns, safety=other)
    assert "safety review" in r.stopped and d.fields["patient_name"] == "" and len(model.bodies) == 1


def test_safety_check_stops_for_a_person():
    r, d, model, _ = run(fill_turns, safety=[{"id": "csc_1", "code": "malicious_instructions", "message": "?"}])
    assert "safety review" in r.stopped and d.fields["patient_name"] == "" and len(model.bodies) == 1


def test_only_the_demo_copy_is_allowed():
    with pytest.raises(submit_agent.NotAllowed):
        run(fill_turns, allow=["https://portal.example-insurer.com/appeal"])
    r, d, model, _ = run(fill_turns, driver=FakeDriver("file:///tmp/other/appeal.html"))
    assert r.stopped.startswith("not on the demo portal") and model.bodies == []


# --- submit, only after the family's Send -----------------------------------------------------------

def test_submit_needs_the_familys_confirmation():
    with pytest.raises(submit_agent.NotAllowed):
        run(lambda d, v: [], phase="submit")


def test_confirmed_submit_presses_once_and_reads_the_confirmation():
    def turns(d, vals):
        x, y = d.center("submit")
        click = {"type": "click", "button": "left", "x": x, "y": y}
        return [[click], [click], "Submitted."]
    d = FakeDriver()
    _, vals = values()
    d.fields.update({k: vals.get(k, "") for k in submit_agent.PORTAL_FIELDS})
    r, d, model, _ = run(turns, phase="submit", confirmed=True, driver=d)
    assert r.submitted and d.submitted == 1 and r.stopped == "Submit was already pressed once"
    assert r.confirmation.endswith("SHP-APL-01234.") and "Press the Submit appeal button once" in model.bodies[0]["instructions"]


def test_live_agent_only_for_a_fictional_case():
    c, vals = values()
    c.demo = False
    live = MetaClient(transport=LiveTransport("not-a-key"), record_to=None, journal=None)
    with pytest.raises(RealDataGate):
        submit_agent.run(live, FakeDriver(), c, vals)


def test_journal_line_keeps_no_values():
    r, *_ = run(fill_turns)
    line = submit_agent.journal_line(r)
    assert "Maria" not in line and "SHP-000" not in line and json.loads(line)["stopped_before_submit"] is True


def test_keys_the_model_names_its_own_way_reach_the_browser_by_their_names():
    """The first live press of Send died on "Unknown key: ctrl"."""
    pressed = []
    driver = submit_agent.PlaywrightDriver.__new__(submit_agent.PlaywrightDriver)
    driver.page = type("P", (), {"keyboard": type("K", (), {"press": staticmethod(pressed.append)})()})()
    for keys in (["ctrl", "a"], ["Tab"], ["shift", "tab"], ["ESC"], ["a"]):
        driver.keypress(keys)
    assert pressed == ["ControlOrMeta+a", "Tab", "Shift+Tab", "Escape", "a"]

