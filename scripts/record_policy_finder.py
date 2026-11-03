"""Record the live run of policy_finder behind /policy-finder: real hospitals, public policies, no bill.

    BILLRADAR_LIVE=1 TAVILY_CREDIT_CAP=60 META_SPEND_CAP_USD=... python scripts/record_policy_finder.py

Needs TAVILY_API_KEY and MODEL_API_KEY. A request recorded before is answered from its recording, so a second
run after a code change pays only for the requests that changed. Sends the searches only the hospital's name, city or
ZIP, state and site (billradar/policy_finder_run.json). Keeps what the run found in billradar/policy_finder_recorded.json
(short quotes, links, call ids), sets "recorded" in the run file, prints one line per hospital. Raw search answers and
page texts stay out of the repository.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from billradar import meta_client as mc
from billradar import policy_finder as pf
from billradar import tavily_client as tc
from billradar.meta_client import MetaClient
from billradar.tavily_client import TavilyClient

REUSED = {"tavily": 0, "model": 0}


class ReuseTavily(tc.LiveTransport):
    """A request already recorded is answered from its recording (no second charge); others go live."""

    def answer(self, endpoint, body):
        try:
            ans = tc.ReplayTransport().answer(endpoint, body)
            REUSED["tavily"] += 1
            return ans
        except tc.ReplayMissing:
            return super().answer(endpoint, body)


class ReuseModel(MetaClient):
    def respond(self, body, label=""):
        if (mc.RECORDINGS / mc.recording_name(body)).exists():
            replay = MetaClient(transport=mc.ReplayTransport(), record_to=None, journal=None)
            result = replay.respond(body, label)
            self.calls += replay.calls
            REUSED["model"] += 1
            return result
        return super().respond(body, label)


def main() -> int:
    tavily, client = TavilyClient(), ReuseModel()
    if tavily.live:
        tavily.transport = ReuseTavily(tavily.transport.api_key)
    if not (tavily.live and client.live):
        print("not live: set BILLRADAR_LIVE=1, TAVILY_API_KEY and MODEL_API_KEY", file=sys.stderr)
        return 2
    plan = pf.run_plan()
    rows, saved = [], []
    for item in plan["runs"]:
        hint = pf.Hint(**item["hint"])
        first = len(tavily.calls)
        found = pf.find(hint, tavily, client, confirmed=item.get("confirmed", False))
        saved.append(found.to_dict())
        credits = sum(int(c.get("credits") or 0) for c in tavily.calls[first:])
        rows.append({"hospital": hint.name, "state": hint.state, "status": found.status, "domain": found.domain,
                     "step": found.domain_step, "url": found.url, "doc_date": found.doc_date, "tiers": len(found.tiers),
                     "dropped": len(found.dropped), "credits": credits, "usd": found.model_usd,
                     "laws": (found.state_laws or {}).get("status"), "law_sections": len((found.state_laws or {}).get("sections") or []),
                     "law_url": (found.state_laws or {}).get("url"), "message": found.message, "date_note": found.date_note})
        print(json.dumps(rows[-1]))
    plan["recorded"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pf.RUN_FILE.write_text(json.dumps(plan, indent=1) + "\n")
    pf.RESULTS_FILE.write_text(json.dumps(saved, indent=1) + "\n")
    print(json.dumps({"hospitals": len({(r["hospital"], r["state"]) for r in rows}),
                      "states": len({r["state"] for r in rows}),
                      "credits": sum(r["credits"] for r in rows), "usd": round(sum(r["usd"] for r in rows), 6),
                      "tavily_request_ids": [c["request_id"] for c in tavily.calls], "reused": REUSED}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
