"""Muse Spark files the appeal from the app: the family presses "fill it", looks at what it filled, and
only their own press of "Send" lets it press the portal's Submit.

A job lives in this process and on the case's folder (agent.json, agent/<n>.png). The browser stays open between
the two presses, so what the family checked is what goes. A live run is only for a fictional case (submit_agent
refuses anything else) on the demo copy of the portal. Where no model is connected, the recorded run is shown and
says so; nothing is ever sent from a recording.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from billradar import appeal, plans, submit_agent
from billradar.case import Case
from billradar.meta_client import MetaClient

RECORDED = Path(__file__).parent / "demo_portal" / "recorded"
STATES = ("none", "filling", "ready", "sending", "sent", "failed")


def make_driver():
    return submit_agent.PlaywrightDriver(submit_agent.portal_url())


@dataclass
class Job:
    state: str = "none"
    steps: int = 0
    filled: dict = field(default_factory=dict)
    mismatches: list = field(default_factory=list)
    stopped: str = ""
    confirmation: str = ""
    shots: int = 0
    replayed: bool = False
    driver: object = None

    def view(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "driver"}


_jobs: dict[tuple[str, str], Job] = {}
_lock = threading.Lock()


def _denial(case: Case, key: str):
    return next((d for d in appeal.denials(case) if appeal.letter_kind(d) == key), None)


def _save(d: Path, job: Job, shots: list[bytes]) -> None:
    folder = d / "agent"
    folder.mkdir(exist_ok=True)
    for png in shots:
        (folder / f"{job.shots}.png").write_bytes(png)
        job.shots += 1
    (d / "agent.json").write_text(json.dumps(job.view(), indent=1))


def status(d: Path, key: str) -> dict:
    job = _jobs.get((str(d), key))
    if job:
        return job.view()
    p = d / "agent.json"
    return json.loads(p.read_text()) if p.exists() else Job().view()


def _recorded(d: Path, key: str) -> bool:
    """Where no model is connected: the run recorded on the demo copy, marked as such."""
    if not (RECORDED / "run.json").exists():
        return False
    job = Job(**json.loads((RECORDED / "run.json").read_text()) | {"state": "ready", "replayed": True})
    shots = [p.read_bytes() for p in sorted(RECORDED.glob("*.png"), key=lambda p: int(p.stem))]
    job.shots = 0
    _jobs[(str(d), key)] = job
    _save(d, job, shots)
    return True


def fill(client: MetaClient, d: Path, case: Case, key: str) -> dict:
    denial = _denial(case, key)
    if denial is None:
        raise KeyError(key)
    with _lock:
        running = _jobs.get((str(d), key))
        if running and running.state in ("filling", "sending"):
            return running.view()
        if not client.live and _recorded(d, key):
            return _jobs[(str(d), key)].view()
        job = _jobs[(str(d), key)] = Job(state="filling", replayed=not client.live)
    values = appeal.form_values(case, plans.load(denial.plan_id), denial)

    def work() -> None:
        try:
            job.driver = make_driver()
            r = submit_agent.run(client, job.driver, case, values, "fill")
            job.steps, job.filled, job.mismatches, job.stopped = len(r.steps), r.filled, r.mismatches, r.stopped
            ok = r.stopped_before_submit and not r.mismatches and (not r.stopped or "before" in r.stopped)
            job.state = "ready" if ok else "failed"
            _save(d, job, r.screenshots)
        except Exception as exc:  # noqa: BLE001 — shown to the family as "failed", with the reason
            job.state, job.stopped = "failed", f"{type(exc).__name__}: {exc}"
            _save(d, job, [])
        if job.state == "failed":
            _close(job)

    threading.Thread(target=work, daemon=True).start()
    return job.view()


def send(client: MetaClient, d: Path, case: Case, key: str, today: date, tracker: appeal.Tracker) -> dict:
    """The family pressed Send. A recorded run has nothing to send: it says so."""
    job = _jobs.get((str(d), key))
    if job is None or job.state != "ready":
        raise ValueError("nothing is ready to send: let the agent fill the form first")
    if job.replayed:
        return job.view() | {"note": "This is a recorded run on a copy of the portal: nothing was sent."}
    denial = _denial(case, key)
    job.state = "sending"
    values = appeal.form_values(case, plans.load(denial.plan_id), denial)
    try:
        r = submit_agent.run(client, job.driver, case, values, "submit", confirmed=True)
        job.stopped, job.confirmation = r.stopped, r.confirmation
        job.state = "sent" if r.submitted else "failed"
        _save(d, job, r.screenshots)
        if r.submitted:
            tracker.mark_sent(case, key, today, r.confirmation, note="filed by Muse Spark on the demo portal")
            tracker.save(d)
    finally:
        _close(job)
    return job.view()


def _close(job: Job) -> None:
    if job.driver is not None:
        job.driver.close()
        job.driver = None
