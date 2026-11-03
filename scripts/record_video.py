"""One live pass of a table video through the whole pipeline: the same case as the example, with the clip in place of photos.

  MODEL_API_KEY=... BILLRADAR_LIVE=1 python scripts/record_video.py clip.mov out_dir recordings_dir

SAM's answers already in recordings_dir are used again; what is missing goes out once, against META_SPEND_CAP_USD.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from billradar import example, highlight, meta_client as mc, pipeline  # noqa: E402
from billradar.case import Profile  # noqa: E402
from record_example import Fill  # noqa: E402


def main(argv: list[str]) -> int:
    clip, out, recordings = Path(argv[0]), Path(argv[1]), Path(argv[2])
    client = Fill()
    client.replay, client.record_to = mc.ReplayTransport(recordings), recordings
    pack = example.PACK
    meta = json.loads((pack / "profile.json").read_text())
    run = pipeline.run(client, [], [(p.name, p.read_bytes()) for p in sorted(pack.glob("*.pdf"))],
                       Profile.model_validate(meta["profile"]), meta["policy_id"], meta.get("letterhead", ""),
                       date.fromisoformat(meta["today"]), "example-video", fictional=True, private=True, video=clip.read_bytes())
    run.case.demo = True
    pipeline.save(run, out)
    highlight.attach(client, run, out)
    r = run.report
    print("sheets", len(run.sheets), "total", r.total_may_come_off, "apply_by", r.apply_by, "apply_by_sure", r.apply_by_sure)
    print("findings", [(f.kind.value, str(f.amount)) for f in r.findings], "ask", [f.kind.value for f in r.worth_asking])
    print("unreadable", run.unreadable, "calls", len(client.calls), "spent $%.4f" % mc.SpendLedger().spent())
    for p in run.problems:
        print(" ", p[:140])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
