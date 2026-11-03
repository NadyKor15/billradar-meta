"""Muse Spark files the appeal on a copy of the insurer's portal: it fills the form, and stops.
Only after the family presses "Send" in BillRadar does it press the portal's Submit.

The `computer` tool is a protocol, not an environment (dev.meta.ai/docs/computer-use.md). The API refuses it on Muse
Wonder for this account ("Unsupported tool type", 01.11) and takes it on Muse Spark, which the page names for the same loop:
the model looks at a screenshot and returns mouse and keyboard actions; our driver runs them and sends
the next screenshot back. With `store: false` the whole history is sent each turn (up to 29 pairs).

What the model cannot override, because it is enforced here, in code:
  - the page must be the demo copy (an exact file:// address on the allow list); anything else stops the run;
  - before every click we ask the page what is under the pointer; a click on Submit, or Enter in a field
    (which would submit the form), is blocked in the fill phase. Submit is pressed only in the submit
    phase, only with `confirmed=True`, and only once;
  - a safety check from the API is never acknowledged automatically: the run stops for a person;
  - after the run, the fields are read back from the page and compared with what we asked for.
Screenshots carry the family's details, so a live run is allowed only for a fictional case.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from billradar.case import Case
from billradar.meta_client import MetaClient, data_url
from billradar.pipeline import RealDataGate

MODEL = "muse-spark-1.3"
PORTAL = Path(__file__).parent / "demo_portal" / "appeal.html"
PORTAL_FIELDS = ["patient_name", "member_id", "claim_number", "service_dates", "provider", "denial_date",
                 "denial_codes", "amount", "reason", "phone"]
MAX_TURNS = 25  # stateless replay holds up to 29 call/output pairs
# The API attaches this plain check to every action. It asks the developer to stand behind the action, and the guards in
# this file do: the page is the demo copy, the case is fictional, and what is under the pointer is read before each click.
# Any other check, malicious_instructions above all, stops the run for a person.
GUARDS_ANSWER_FOR = {"computer_action_requires_confirmation"}


class NotAllowed(RuntimeError):
    pass


class Driver(Protocol):
    def url(self) -> str: ...
    def screenshot(self) -> bytes: ...  # PNG of the viewport the coordinates refer to
    def element_at(self, x: int, y: int) -> dict | None: ...  # {"id", "tag", "type", "text"}
    def click(self, x: int, y: int, button: str = "left") -> None: ...
    def double_click(self, x: int, y: int) -> None: ...
    def type(self, text: str) -> None: ...
    def keypress(self, keys: list[str]) -> None: ...
    def scroll(self, x: int, y: int, dx: int, dy: int) -> None: ...
    def values(self) -> dict[str, str]: ...
    def confirmation(self) -> str: ...


def portal_url(path: Path = PORTAL) -> str:
    return path.resolve().as_uri()


def check_allow(allow: list[str]) -> list[str]:
    for a in allow:
        if not (a.startswith("file://") and a.endswith("/demo_portal/appeal.html")):
            raise NotAllowed(f"{a!r}: only the demo copy of the portal, opened as a file, is allowed")
    return allow


def is_allowed(url: str, allow: list[str]) -> bool:
    return url.split("#", 1)[0].split("?", 1)[0] in allow


def _is_submit(el: dict | None) -> bool:
    if not el:
        return False
    return (el.get("id") == "submit" or el.get("type") == "submit"
            or bool(re.search(r"\b(submit|send)\b", el.get("text") or "", re.I)))


SYSTEM = """You are a computer-use agent filling one web form for BillRadar, a helper for hospital bills and insurance. You see screenshots of a browser and return mouse and keyboard actions.

Coordinates are pixels in the screenshot you were last shown; click the center of the target. Batch only actions that do not depend on new visual feedback (click a field, type into it). After typing, look at the next screenshot before moving on.

Type each value exactly as given, nothing else. Do not change, shorten or complete a value. Leave a field empty when no value is given for it.
{phase_rule}
When you are done, stop and answer in one short sentence. If the page is not the Sample Health Plan appeal form or something blocks you, stop and say what."""

FILL_RULE = "Never press Submit, Send or Enter. A person reviews the form and decides whether to submit."
SUBMIT_RULE = ("The person has reviewed the form and asked to submit. Press the Submit appeal button once. "
               "Then stop and report the confirmation number shown on the page.")


def task(values: dict[str, str], phase: str) -> str:
    if phase == "submit":
        return "Submit the appeal form that is already filled in. Press Submit appeal once."
    lines = [f"- {k}: {values[k]}" for k in PORTAL_FIELDS if values.get(k)]
    return "Fill the Sample Health Plan appeal form with these values (field id: value):\n" + "\n".join(lines)


def body(history: list[dict], phase: str) -> dict:
    return {"model": MODEL, "store": False, "stream": True, "reasoning": {"effort": "low"},
            "max_output_tokens": 4000, "tools": [{"type": "computer"}],
            "instructions": SYSTEM.format(phase_rule=FILL_RULE if phase == "fill" else SUBMIT_RULE),
            "input": history}


def _output(events: list[dict]) -> list[dict]:
    final = next((e for e in reversed(events) if e.get("type") == "response.completed"), {})
    return (final.get("response") or {}).get("output") or []


@dataclass
class Step:
    n: int
    actions: list[dict]
    done: int  # how many actions of the batch ran
    stopped: str = ""


@dataclass
class AgentRun:
    phase: str
    steps: list[Step] = field(default_factory=list)
    submitted: bool = False
    stopped_before_submit: bool = False
    stopped: str = ""  # why the loop ended early, if it did
    answer: str = ""
    filled: dict[str, str] = field(default_factory=dict)
    mismatches: list[str] = field(default_factory=list)
    confirmation: str = ""
    screenshots: list[bytes] = field(default_factory=list)
    replayed: bool = True


def _run_batch(driver: Driver, actions: list[dict], phase: str, confirmed: bool, allow: list[str],
               run: AgentRun) -> tuple[int, str]:
    for i, a in enumerate(actions):
        if not is_allowed(driver.url(), allow):
            return i, f"left the demo portal ({driver.url()})"
        t = a.get("type")
        if t in ("click", "double_click"):
            x, y = int(a["x"]), int(a["y"])
            if _is_submit(driver.element_at(x, y)):
                if run.submitted:
                    return i, "Submit was already pressed once"
                if phase != "submit" or not confirmed:
                    run.stopped_before_submit = True
                    return i, "stopped before Submit"
                run.submitted = True
            if t == "click":
                driver.click(x, y, a.get("button", "left"))
            else:
                driver.double_click(x, y)
        elif t == "keypress":
            keys = [k.lower() for k in a.get("keys", [])]
            if phase == "fill" and ({"enter", "return"} & set(keys)):
                run.stopped_before_submit = True
                return i, "stopped before Enter (it would submit the form)"
            driver.keypress(a.get("keys", []))
        elif t == "type":
            driver.type(a.get("text", ""))
        elif t == "scroll":
            driver.scroll(int(a["x"]), int(a["y"]), int(a.get("scroll_x", 0)), int(a.get("scroll_y", 0)))
        elif t in ("screenshot", "wait", "move"):
            continue
        else:
            return i, f"action {t!r} is not used on this form"
    return len(actions), ""


def run(client: MetaClient, driver: Driver, case: Case, values: dict[str, str], phase: str = "fill",
        confirmed: bool = False, allow: list[str] | None = None, max_turns: int = MAX_TURNS) -> AgentRun:
    if phase not in ("fill", "submit"):
        raise ValueError(phase)
    if phase == "submit" and not confirmed:
        raise NotAllowed("submit needs the family's own press of Send (confirmed=True)")
    if client.live and not case.demo:
        raise RealDataGate("live computer use is allowed only for a fictional case")
    allow = check_allow(allow or [portal_url()])
    out = AgentRun(phase)
    if not is_allowed(driver.url(), allow):
        out.stopped = f"not on the demo portal ({driver.url()})"
        return out
    shot = driver.screenshot()
    out.screenshots.append(shot)
    history: list[dict] = [{"role": "user", "content": [
        {"type": "input_text", "text": task(values, phase)},
        {"type": "input_image", "image_url": data_url(shot, "image/png")}]}]
    for n in range(1, max_turns + 1):
        res = client.respond(body(history, phase), label=f"spark:portal-{phase}")
        out.replayed = res.replayed
        items = _output(res.events)
        calls = [i for i in items if i.get("type") == "computer_call"]
        if not calls:
            out.answer = res.text.strip()
            break
        call = calls[0]
        checks = call.get("pending_safety_checks") or []
        if any(c.get("code") not in GUARDS_ANSWER_FOR for c in checks):
            out.stopped = "the API asked for a safety review; a person has to look"
            out.steps.append(Step(n, call.get("actions", []), 0, out.stopped))
            break
        done, why = _run_batch(driver, call.get("actions", []), phase, confirmed, allow, out)
        out.steps.append(Step(n, call.get("actions", []), done, why))
        shot = driver.screenshot()
        out.screenshots.append(shot)
        if why:
            out.stopped = why
            break
        history += [i for i in items if i.get("type") != "message"]  # receipts copied unchanged
        history.append({"type": "computer_call_output", "call_id": call.get("call_id"),
                        "acknowledged_safety_checks": checks,  # every action of the batch passed the guards above
                        "output": {"type": "computer_screenshot", "image_url": data_url(shot, "image/png")}})
    else:
        out.stopped = "step budget reached"
    if phase == "fill":
        out.stopped_before_submit = not out.submitted
    out.filled = driver.values()
    for k in PORTAL_FIELDS:
        want = re.sub(r"\s+", " ", values.get(k, "")).strip()
        got = re.sub(r"\s+", " ", out.filled.get(k, "")).strip()
        if want != got:
            out.mismatches.append(f"{k}: asked {want!r}, page has {got!r}")
    if phase == "submit":
        out.confirmation = driver.confirmation()
    return out


def journal_line(r: AgentRun) -> str:
    """What the screen and the build log keep about a run: no screenshots, no field values."""
    return json.dumps({"phase": r.phase, "steps": len(r.steps), "submitted": r.submitted,
                       "stopped_before_submit": r.stopped_before_submit, "stopped": r.stopped,
                       "mismatches": len(r.mismatches), "confirmation": bool(r.confirmation),
                       "replayed": r.replayed})


# The model names keys its own way ("ctrl", "esc"); the browser wants its own names. ControlOrMeta selects all on any machine.
KEY_NAMES = {"ctrl": "ControlOrMeta", "control": "ControlOrMeta", "cmd": "ControlOrMeta", "command": "ControlOrMeta",
             "meta": "ControlOrMeta", "super": "ControlOrMeta", "alt": "Alt", "option": "Alt", "shift": "Shift",
             "enter": "Enter", "return": "Enter", "esc": "Escape", "escape": "Escape", "tab": "Tab", "space": "Space",
             "backspace": "Backspace", "delete": "Delete", "del": "Delete", "home": "Home", "end": "End",
             "pageup": "PageUp", "pagedown": "PageDown", "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft",
             "right": "ArrowRight", "arrowup": "ArrowUp", "arrowdown": "ArrowDown", "arrowleft": "ArrowLeft",
             "arrowright": "ArrowRight"}


class PlaywrightDriver:
    """A real browser for the live run on the test machine (headless Chromium, file:// page).
    Not used by the tests; needs `pip install playwright` and its Chromium there."""

    def __init__(self, url: str, width: int = 1280, height: int = 900):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self.page = self._browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        self.page.goto(url)

    def close(self) -> None:
        self._browser.close()
        self._pw.stop()

    def url(self) -> str:
        return self.page.url

    def screenshot(self) -> bytes:
        return self.page.screenshot(type="png")

    def element_at(self, x: int, y: int) -> dict | None:
        return self.page.evaluate("""([x, y]) => { const e = document.elementFromPoint(x, y);
            if (!e) return null; const b = e.closest('button') || e;
            return {id: b.id || '', tag: b.tagName.toLowerCase(), type: b.type || '', text: (b.innerText || '').slice(0, 80)}; }""",
                                  [x, y])

    def click(self, x: int, y: int, button: str = "left") -> None:
        self.page.mouse.click(x, y, button=button if button in ("left", "right", "middle") else "left")

    def double_click(self, x: int, y: int) -> None:
        self.page.mouse.dblclick(x, y)

    def type(self, text: str) -> None:
        self.page.keyboard.type(text)

    def keypress(self, keys: list[str]) -> None:
        self.page.keyboard.press("+".join(KEY_NAMES.get(k.lower(), k) for k in keys))

    def scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        self.page.mouse.move(x, y)
        self.page.mouse.wheel(dx, dy)

    def values(self) -> dict[str, str]:
        return self.page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('input, textarea')]
            .map(e => [e.id, e.value]))""")

    def confirmation(self) -> str:
        return self.page.inner_text("#confirmation").strip()
