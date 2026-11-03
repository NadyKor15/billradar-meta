"""Live run of the portal agent on the demo copy, on a test machine (headless Chromium, file:// page).

python scripts/portal_agent_demo.py fill            # fills the form, stops before Submit
python scripts/portal_agent_demo.py submit --yes    # presses Submit once (the family's "Send")
python scripts/portal_agent_demo.py fill --record   # keeps the run for the app's recorded view (billradar/demo_portal/recorded)
python scripts/portal_agent_demo.py send --yes      # the form filled by code, then the agent's Send alone: the same page, a few calls

Needs MODEL_API_KEY and BILLRADAR_LIVE=1, and runs only on the SYNTHETIC sample-appeal case.
Screenshots go to runs/portal-agent/; the journal keeps no field values.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from billradar import appeal, plans, portal_job, submit_agent
from billradar.case import Case
from billradar.meta_client import MetaClient

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "cases" / "sample-appeal.json"
PEOPLE = [{"token": "PATIENT_1", "role": "mother", "name": "Maria Sample"},
          {"token": "PATIENT_2", "role": "newborn", "name": "Leo Sample"}]
LOCAL = {"phone": "(555) 010-0199", "tokens": {"ACCT_1": "LDH-45821", "MEMBER_1": "SHP-000-4417"}}


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else "fill"
    raw = json.loads(FIX.read_text())
    raw["profile"]["people"], raw["profile"]["local"] = PEOPLE, LOCAL
    case = Case.model_validate(raw)
    assert case.demo, "the demo case must be marked fictional"
    d = appeal.denials(case)[0]
    values = appeal.form_values(case, plans.load(d.plan_id), d)
    driver = submit_agent.PlaywrightDriver(submit_agent.portal_url())
    out = ROOT / "runs" / "portal-agent"
    out.mkdir(parents=True, exist_ok=True)
    try:
        if phase == "send":
            for field in submit_agent.PORTAL_FIELDS:
                if values.get(field):
                    driver.page.fill(f"#{field}", values[field])
            r = submit_agent.run(MetaClient(), driver, case, values, "submit", confirmed="--yes" in sys.argv)
        elif phase == "submit":
            # the form is filled first in the same page, then submitted only with --yes
            filled = submit_agent.run(MetaClient(), driver, case, values, "fill")
            if filled.mismatches or filled.stopped:
                print("NOT SUBMITTING:", filled.stopped or "; ".join(filled.mismatches))
                return 1
            r = submit_agent.run(MetaClient(), driver, case, values, "submit", confirmed="--yes" in sys.argv)
        else:
            r = submit_agent.run(MetaClient(), driver, case, values, "fill")
        for i, png in enumerate(r.screenshots):
            (out / f"{phase}-{i:02d}.png").write_bytes(png)
        print(submit_agent.journal_line(r))
        if "--record" in sys.argv and not r.mismatches:
            kept = portal_job.RECORDED
            kept.mkdir(parents=True, exist_ok=True)
            for i, png in enumerate(r.screenshots):
                (kept / f"{i}.png").write_bytes(png)
            (kept / "run.json").write_text(json.dumps({"steps": len(r.steps), "filled": r.filled}, indent=1))
        for m in r.mismatches:
            print("MISMATCH", m)
        return 0 if not r.mismatches else 1
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
