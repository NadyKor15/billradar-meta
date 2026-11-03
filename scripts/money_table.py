"""The acceptance table of a run: every confirmed sum, the printed values it stands on, and what went without a sum.

    python scripts/money_table.py runs/<case>/report.json
"""

from __future__ import annotations

import sys
from pathlib import Path

from billradar.checks import Report


def table(report: Report) -> str:
    rows = ["| Finding | Sum | Printed values |", "|---|---|---|"]
    for f in report.findings:
        if f.amount is None:
            continue
        steps = "; ".join(f"{s.doc_id}{f' line {s.line_no}' if s.line_no else ''} {s.field} {s.printed}: {s.role}" for s in f.trace)
        rows.append(f"| {f.kind.value} | ${f.amount:,.2f} | {steps} |")
    rows.append(f"| Total | ${report.total_may_come_off:,.2f} | |")
    for f in report.worth_asking:
        if "amount_if_confirmed" in f.math:
            rows.append(f"| {f.kind.value} without a sum | was ${f.math['amount_if_confirmed']} | {f.math.get('why_unsure', '')} |")
    return "\n".join(rows) + "\n"


if __name__ == "__main__":
    print(table(Report.model_validate_json(Path(sys.argv[1]).read_text())))
