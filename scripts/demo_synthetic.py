"""Build the demo case from drawn sample sheets and canned answers, then save it under runs/ for the case screen."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from billradar import example, pipeline  # noqa: E402


def main() -> None:
    run = example.run_demo_synthetic()
    out = ROOT / "runs" / "demo-synthetic"
    pipeline.save(run, out)
    print(f"saved {out}: {len(run.sheets)} sheets, total ${run.report.total_may_come_off}, problems: {run.problems}")


if __name__ == "__main__":
    main()
