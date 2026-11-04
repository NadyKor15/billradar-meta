# Lines older than the hackathon start

Taken on 2026-11-03 at 18:27 UTC from commit 559c891 of the working repository. Method: `git blame -w -C -C`; a line counts as old when the commit that last brought it in, or its author date, is before 2026-10-26 16:24 UTC (12:24 PM ET), the start of hacking. 1457 files, 254 of them binary; blame errors 0, Python parse errors 0.

In Python: 2,020 of 44,972 lines are older (4.5%); 755 of them (1.7%) are logic, the rest are imports, function signatures, field names, brackets and docstrings. All files below, Python and not.

| Class | Lines |
|---|---|
| code | 755 |
| import | 476 |
| signature | 434 |
| field | 223 |
| data | 207 |
| text | 79 |
| template | 79 |
| punct | 71 |
| config | 52 |
| doc | 35 |
| string | 21 |
| comment | 5 |
| binary file | 2 |
| total | 2439 |

| Folder | Lines |
|---|---|
| billradar | 1544 |
| tests | 680 |
| scripts | 79 |
| (root) | 78 |
| docs | 52 |
| samples | 5 |
| eval | 1 |

| File | Line | Block | Class | Date | Text |
|---|---|---|---|---|---|
| .env.example | 1 | (file) | config | 2026-10-26 | # Meta Model API key (dev.meta.ai -> API keys). Never commit the real value. |
| .env.example | 2 | (file) | config | 2026-10-26 | MODEL_API_KEY= |
| .env.example | 3 | (file) | config | 2026-10-26 | # Set to 1 to call the live API. Anything else replays recorded responses. |
| .env.example | 4 | (file) | config | 2026-10-26 | BILLRADAR_LIVE=0 |
| .gitignore | 1 | (file) | config | 2026-10-26 | .env |
| .gitignore | 2 | (file) | config | 2026-10-26 | .env.* |
| .gitignore | 3 | (file) | config | 2026-10-26 | *.key |
| .gitignore | 4 | (file) | config | 2026-10-26 | __pycache__/ |
| .gitignore | 5 | (file) | config | 2026-10-26 | node_modules/ |
| .gitignore | 6 | (file) | config | 2026-10-26 | .DS_Store |
| .gitignore | 7 | (file) | config | 2026-10-26 | private/ |
| .gitignore | 8 | (file) | config | 2026-10-26 | .venv/ |
| .gitignore | 9 | (file) | config | 2026-10-26 | .cache/ |
| .gitignore | 10 | (file) | config | 2026-10-26 | .pytest_cache/ |
| .gitignore | 11 | (file) | config | 2026-10-26 | runs/ |
| .gitignore | 12 | (file) | config | 2026-10-26 | !.env.example |
| README.md | 9 | (file) | text | 2026-10-26 | ## How it works |
| README.md | 47 | (file) | text | 2026-10-26 | ## What it finds |
| README.md | 49 | (file) | text | 2026-10-26 | \| Class \| What \| |
| README.md | 50 | (file) | text | 2026-10-26 | \|---\|---\| |
| README.md | 51 | (file) | text | 2026-10-26 | \| F1 \| The household qualifies under the hospital's policy, but no discount is on the bill \| |
| README.md | 52 | (file) | text | 2026-10-26 | \| F2 \| The last day to apply, counted from the first bill after discharge (policy + federal rule) \| |
| README.md | 54 | (file) | text | 2026-10-26 | \| E1 \| A bill line asks more than the insurance statement says the patient owes \| |
| README.md | 55 | (file) | text | 2026-10-26 | \| E2 \| The same service billed twice \| |
| README.md | 56 | (file) | text | 2026-10-26 | \| E3 \| A credit or overpayment left on the account \| |
| README.md | 57 | (file) | text | 2026-10-26 | \| E4 \| One sheet asks two different amounts \| |
| README.md | 58 | (file) | text | 2026-10-26 | \| B1 \| Newborn care billed under the mother's insurance ID \| |
| README.md | 59 | (file) | text | 2026-10-26 | \| P1 \| Pages missing from a statement \| |
| README.md | 63 | (file) | text | 2026-10-26 | ## Run it |
| README.md | 65 | (file) | text | 2026-10-26 | ```sh |
| README.md | 66 | (file) | text | 2026-10-26 | uv venv --python 3.12 && uv pip install -e ".[dev]" |
| README.md | 67 | (file) | text | 2026-10-26 | python scripts/fetch_policies.py        # public policies and the blank form -> .cache/ (not committed) |
| README.md | 68 | (file) | text | 2026-10-26 | pytest |
| README.md | 80 | (file) | text | 2026-10-26 | ``` |
| README.md | 99 | (file) | text | 2026-10-26 | ## Sources in the repo |
| README.md | 101 | (file) | text | 2026-10-26 | \| Source \| From \| |
| README.md | 102 | (file) | text | 2026-10-26 | \|---\|---\| |
| README.md | 103 | (file) | text | 2026-10-26 | \| Memorial Healthcare System, Financial Assistance Policy, revised May 2026 \| mhs.net (public PDF) \| |
| README.md | 105 | (file) | text | 2026-10-26 | \| Baptist Health South Florida, BHSF-355.14, revised 09/29/2026 \| baptisthealth.net (public PDF) \| |
| README.md | 106 | (file) | text | 2026-10-26 | \| 26 CFR 1.501(r)-1, application period \| eCFR \| |
| README.md | 107 | (file) | text | 2026-10-26 | \| Florida Statutes 395.301 (itemized statement, billing disputes) \| leg.state.fl.us \| |
| README.md | 109 | (file) | text | 2026-10-26 | We store short quotes and page numbers, not the documents. Estimates follow the published policy; the hospital decides. |
| billradar/agent_api.py | 26 | (module) | import | 2026-10-26 | from datetime import date |
| billradar/agent_api.py | 27 | (module) | import | 2026-10-26 | from decimal import Decimal |
| billradar/agent_api.py | 28 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/agent_api.py | 86 | _load | code | 2026-10-26 |     case = Case.model_validate_json((d / "case.json").read_text()) |
| billradar/agent_api.py | 203 | _finding | code | 2026-10-26 |             "amount": str(f.amount) if f.amount is not None else None, |
| billradar/agent_api.py | 214 | get_findings | code | 2026-10-26 |     for f in report.findings: |
| billradar/agent_api.py | 215 | get_findings | code | 2026-10-26 |         counts[f.kind.value] = counts.get(f.kind.value, 0) + 1 |
| billradar/app.py | 3 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/app.py | 9 | (module) | import | 2026-10-26 | import json |
| billradar/app.py | 11 | (module) | import | 2026-10-26 | import re |
| billradar/app.py | 13 | (module) | import | 2026-10-26 | import secrets |
| billradar/app.py | 22 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/app.py | 28 | (module) | import | 2026-10-26 | from fastapi.staticfiles import StaticFiles |
| billradar/app.py | 29 | (module) | import | 2026-10-26 | from fastapi.templating import Jinja2Templates |
| billradar/app.py | 36 | (module) | import | 2026-10-26 | from billradar.case import Case, Person, Profile, Role |
| billradar/app.py | 42 | (module) | code | 2026-10-26 | WEB = Path(__file__).parent / "web" |
| billradar/app.py | 43 | (module) | code | 2026-10-26 | RUNS = Path(__file__).resolve().parents[1] / "runs" |
| billradar/app.py | 60 | (module) | code | 2026-10-26 | app.mount("/static", StaticFiles(directory=WEB / "static"), name="static") |
| billradar/app.py | 61 | (module) | code | 2026-10-26 | templates = Jinja2Templates(directory=WEB / "templates") |
| billradar/app.py | 102 | _sample_answers | code | 2026-10-26 |     _, case, report = _load(case_id) |
| billradar/app.py | 117 | _sample_note_ready | code | 2026-10-26 |     _, case, report = _load(case_id) |
| billradar/app.py | 136 | _run_dir | signature | 2026-10-26 | def _run_dir(case_id: str) -> Path: |
| billradar/app.py | 141 | _run_dir | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 142 | _run_dir | code | 2026-10-26 |     return d |
| billradar/app.py | 190 | home | signature | 2026-10-26 | @app.get("/", response_class=HTMLResponse) |
| billradar/app.py | 191 | home | signature | 2026-10-26 | def home(request: Request): |
| billradar/app.py | 238 | _calls | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 348 | create_case | signature | 2026-10-26 | @app.post("/cases") |
| billradar/app.py | 349 | create_case | signature | 2026-10-26 | async def create_case( |
| billradar/app.py | 351 | create_case | signature | 2026-10-26 |     photos: list[UploadFile] = File(default=[]), |
| billradar/app.py | 352 | create_case | signature | 2026-10-26 |     files: list[UploadFile] = File(default=[]), |
| billradar/app.py | 354 | create_case | signature | 2026-10-26 |     policy_id: str = Form(...), |
| billradar/app.py | 355 | create_case | signature | 2026-10-26 |     letterhead: str = Form(""), |
| billradar/app.py | 356 | create_case | signature | 2026-10-26 |     household_size: int = Form(...), |
| billradar/app.py | 357 | create_case | signature | 2026-10-26 |     annual_income: Decimal = Form(...), |
| billradar/app.py | 358 | create_case | signature | 2026-10-26 |     liquid_assets: Decimal \| None = Form(None), |
| billradar/app.py | 359 | create_case | signature | 2026-10-26 |     insured: bool = Form(False), |
| billradar/app.py | 360 | create_case | signature | 2026-10-26 |     fictional: bool = Form(False), |
| billradar/app.py | 361 | create_case | signature | 2026-10-26 |     mother_name: str = Form(""), |
| billradar/app.py | 362 | create_case | signature | 2026-10-26 |     baby_name: str = Form(""), |
| billradar/app.py | 364 | create_case | signature | 2026-10-26 | ): |
| billradar/app.py | 367 | create_case | code | 2026-10-26 |     if policy_id not in policy.available(): |
| billradar/app.py | 368 | create_case | code | 2026-10-26 |         raise HTTPException(400, "unknown policy") |
| billradar/app.py | 374 | create_case | code | 2026-10-26 |     case_id = "c" + secrets.token_hex(5) |
| billradar/app.py | 392 | _waiting | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 393 | _waiting | code | 2026-10-26 |     return d |
| billradar/app.py | 419 | review_image | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 425 | review_image | code | 2026-10-26 |     raise HTTPException(404) |
| billradar/app.py | 502 | _load | signature | 2026-10-26 | def _load(case_id: str) -> tuple[Path, Case, checks.Report]: |
| billradar/app.py | 503 | _load | code | 2026-10-26 |     d = _run_dir(case_id) |
| billradar/app.py | 504 | _load | code | 2026-10-26 |     case = Case.model_validate_json((d / "case.json").read_text()) |
| billradar/app.py | 505 | _load | code | 2026-10-26 |     report = checks.Report.model_validate_json((d / "report.json").read_text()) |
| billradar/app.py | 510 | (module) | code | 2026-10-26 | FORM_FOR_POLICY = {"memorial-2026-05": forms.fill_memorial} |
| billradar/app.py | 519 | _case_page | code | 2026-10-26 |     d, case, report = _load(case_id) |
| billradar/app.py | 521 | _case_page | code | 2026-10-26 |     overlays = [f"/cases/{case_id}/overlay/{p.name}" for p in sorted(d.glob("overlay-*.jpg"))] |
| billradar/app.py | 570 | find_policy_for_case | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 611 | case_screen | signature | 2026-10-26 | @app.get("/cases/{case_id}", response_class=HTMLResponse) |
| billradar/app.py | 612 | case_screen | signature | 2026-10-26 | def case_screen(request: Request, case_id: str): |
| billradar/app.py | 626 | sent_sheet | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 629 | sent_sheet | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 636 | file_preview | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 639 | file_preview | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 646 | sheet | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 649 | sheet | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 656 | marked_sheet | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 659 | marked_sheet | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 677 | deadlines | code | 2026-10-26 |     d, case, report = _load(case_id) |
| billradar/app.py | 688 | picture | code | 2026-10-26 |     d, case, report = _load(case_id) |
| billradar/app.py | 704 | reminder | signature | 2026-10-26 | @app.get("/cases/{case_id}/reminder.ics") |
| billradar/app.py | 705 | reminder | signature | 2026-10-26 | def reminder(case_id: str): |
| billradar/app.py | 707 | reminder | code | 2026-10-26 |     _, case, report = _load(case_id) |
| billradar/app.py | 727 | reminder | code | 2026-10-26 |                     headers={"Content-Disposition": f'attachment; filename="{case_id}-apply-by.ics"'}) |
| billradar/app.py | 749 | _letter | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 760 | letter | signature | 2026-10-26 | @app.get("/cases/{case_id}/letters/{kind}", response_class=HTMLResponse) |
| billradar/app.py | 791 | report_as_pdf | code | 2026-10-26 |     d, case, report = _load(case_id) |
| billradar/app.py | 799 | call_sheet | code | 2026-10-26 |     d, case, report = _load(case_id) |
| billradar/app.py | 801 | call_sheet | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 815 | call_note | code | 2026-10-26 |     d, case, report = _load(case_id) |
| billradar/app.py | 818 | call_note | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 891 | live_call | code | 2026-10-26 |         _, case, report = _load(case_id) |
| billradar/app.py | 1001 | ask_case | code | 2026-10-26 |     _, case, report = _load(case_id) |
| billradar/app.py | 1053 | voice_sample | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 1060 | ask_case_by_voice | code | 2026-10-26 |     _, case, report = _load(case_id) |
| billradar/app.py | 1110 | appeals | code | 2026-10-26 |     d, case, report = _load(case_id) |
| billradar/app.py | 1126 | appeal_sent | code | 2026-10-26 |     d, case, report = _load(case_id) |
| billradar/app.py | 1130 | appeal_sent | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 1164 | appeal_agent_shot | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 1171 | appeal_agent_send | code | 2026-10-26 |     d, case, report = _load(case_id) |
| billradar/app.py | 1182 | appeal_reply | code | 2026-10-26 |     d, case, report = _load(case_id) |
| billradar/app.py | 1186 | appeal_reply | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 1201 | appeals_ics | code | 2026-10-26 |     d, case, report = _load(case_id) |
| billradar/app.py | 1207 | form_pdf | signature | 2026-10-26 | @app.get("/cases/{case_id}/form.pdf") |
| billradar/app.py | 1208 | form_pdf | signature | 2026-10-26 | def form_pdf(case_id: str): |
| billradar/app.py | 1211 | form_pdf | code | 2026-10-26 |         raise HTTPException(404, "no form for this policy yet") |
| billradar/app.py | 1217 | overlay | signature | 2026-10-26 | @app.get("/cases/{case_id}/overlay/{name}") |
| billradar/app.py | 1218 | overlay | signature | 2026-10-26 | def overlay(case_id: str, name: str): |
| billradar/app.py | 1219 | overlay | code | 2026-10-26 |     if not re.fullmatch(r"(overlay\|sent)-\\d+\\.jpg", name): |
| billradar/app.py | 1220 | overlay | code | 2026-10-26 |         raise HTTPException(404) |
| billradar/app.py | 1221 | overlay | code | 2026-10-26 |     return FileResponse(_run_dir(case_id) / name) |
| billradar/app.py | 1224 | report_json | signature | 2026-10-26 | @app.get("/cases/{case_id}/report.json") |
| billradar/app.py | 1225 | report_json | signature | 2026-10-26 | def report_json(case_id: str): |
| billradar/app.py | 1226 | report_json | code | 2026-10-26 |     return FileResponse(_run_dir(case_id) / "report.json") |
| billradar/ask.py | 13 | (module) | doc | 2026-10-26 | """ |
| billradar/ask.py | 15 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/ask.py | 17 | (module) | import | 2026-10-26 | import json |
| billradar/ask.py | 18 | (module) | import | 2026-10-26 | import re |
| billradar/ask.py | 19 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/ask.py | 99 | request_body | code | 2026-10-26 |                       "amount": str(f.amount) if f.amount is not None else None, |
| billradar/ask.py | 100 | request_body | code | 2026-10-26 |                       "deadline": f.deadline.isoformat() if f.deadline else None, |
| billradar/ask.py | 109 | request_body | code | 2026-10-26 |         "input": [ |
| billradar/ask.py | 110 | request_body | code | 2026-10-26 |             {"role": "developer", "content": [{"type": "input_text", "text": INSTRUCTIONS}]}, |
| billradar/ask.py | 111 | request_body | code | 2026-10-26 |             {"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload, default=str)}]}, |
| billradar/ask.py | 112 | request_body | punct | 2026-10-26 |         ], |
| billradar/ask.py | 113 | request_body | punct | 2026-10-26 |     } |
| billradar/call_assist.py | 15 | (module) | doc | 2026-10-26 | """ |
| billradar/call_assist.py | 17 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/call_assist.py | 19 | (module) | import | 2026-10-26 | import hashlib |
| billradar/call_assist.py | 20 | (module) | import | 2026-10-26 | import json |
| billradar/call_assist.py | 25 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/call_assist.py | 26 | (module) | import | 2026-10-26 | from datetime import datetime, timezone |
| billradar/call_assist.py | 27 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/call_assist.py | 125 | ReplayRealtime.__init__ | signature | 2026-10-26 |     def __init__(self, directory: Path = RECORDINGS): |
| billradar/call_assist.py | 126 | ReplayRealtime.__init__ | code | 2026-10-26 |         self.directory = directory |
| billradar/call_assist.py | 353 | CallSession._log | code | 2026-10-26 |         self.journal.parent.mkdir(parents=True, exist_ok=True) |
| billradar/call_assist.py | 354 | CallSession._log | code | 2026-10-26 |         with self.journal.open("a") as f: |
| billradar/call_assist.py | 355 | CallSession._log | code | 2026-10-26 |             f.write(json.dumps(entry) + "\\n") |
| billradar/callprep.py | 13 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/callprep.py | 14 | (module) | import | 2026-10-26 | from datetime import date |
| billradar/callprep.py | 15 | (module) | import | 2026-10-26 | from decimal import Decimal |
| billradar/callprep.py | 33 | Objection (class) | field | 2026-10-26 |     refs: list[str] = field(default_factory=list) |
| billradar/callprep.py | 36 | CallSheet (class) | signature | 2026-10-26 | @dataclass |
| billradar/callprep.py | 106 | paper_name | code | 2026-10-26 |     return f"sheet {doc_id[1:]}" if doc_id.startswith("S") else f"file {doc_id[1:]}" |
| billradar/callprep.py | 113 | hospital | code | 2026-10-26 |     ends = [b.service_to or b.service_from for b in bills if b.service_to or b.service_from] |
| billradar/case.py | 5 | (module) | doc | 2026-10-26 | """ |
| billradar/case.py | 7 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/case.py | 9 | (module) | import | 2026-10-26 | import re |
| billradar/case.py | 10 | (module) | import | 2026-10-26 | from datetime import date |
| billradar/case.py | 12 | (module) | import | 2026-10-26 | from enum import StrEnum |
| billradar/case.py | 14 | (module) | import | 2026-10-26 | from pydantic import BaseModel, Field, field_validator |
| billradar/case.py | 24 | parse_money | signature | 2026-10-26 | def parse_money(text: str \| None) -> Decimal \| None: |
| billradar/case.py | 28 | parse_money | code | 2026-10-26 |     if text is None: |
| billradar/case.py | 29 | parse_money | punct | 2026-10-26 |         return None |
| billradar/case.py | 32 | parse_money | punct | 2026-10-26 |         return None |
| billradar/case.py | 44 | parse_date | signature | 2026-10-26 | def parse_date(text: str \| None) -> date \| None: |
| billradar/case.py | 50 | parse_date | code | 2026-10-26 |     if not text: |
| billradar/case.py | 51 | parse_date | punct | 2026-10-26 |         return None |
| billradar/case.py | 58 | parse_date | punct | 2026-10-26 |             try: |
| billradar/case.py | 60 | parse_date | code | 2026-10-26 |             except ValueError: |
| billradar/case.py | 61 | parse_date | punct | 2026-10-26 |                 return None |
| billradar/case.py | 65 | DocKind (class) | signature | 2026-10-26 | class DocKind(StrEnum): |
| billradar/case.py | 66 | DocKind (class) | code | 2026-10-26 |     HOSPITAL_STATEMENT = "hospital_statement" |
| billradar/case.py | 67 | DocKind (class) | code | 2026-10-26 |     ITEMIZED_BILL = "itemized_bill" |
| billradar/case.py | 68 | DocKind (class) | code | 2026-10-26 |     EOB = "eob" |
| billradar/case.py | 69 | DocKind (class) | code | 2026-10-26 |     FA_LETTER = "fa_letter" |
| billradar/case.py | 70 | DocKind (class) | code | 2026-10-26 |     PAYMENT_RECEIPT = "payment_receipt" |
| billradar/case.py | 71 | DocKind (class) | code | 2026-10-26 |     OTHER = "other" |
| billradar/case.py | 74 | Source (class) | signature | 2026-10-26 | class Source(StrEnum): |
| billradar/case.py | 75 | Source (class) | code | 2026-10-26 |     PAPER = "paper" |
| billradar/case.py | 76 | Source (class) | code | 2026-10-26 |     PDF = "pdf" |
| billradar/case.py | 77 | Source (class) | code | 2026-10-26 |     SCREENSHOT = "screenshot" |
| billradar/case.py | 80 | Line (class) | signature | 2026-10-26 | class Line(BaseModel): |
| billradar/case.py | 81 | Line (class) | doc | 2026-10-26 |     """One printed line: a charge on a bill, or a claim line on an EOB.""" |
| billradar/case.py | 83 | Line (class) | field | 2026-10-26 |     line_no: int |
| billradar/case.py | 84 | Line (class) | field | 2026-10-26 |     service_date: date \| None = None |
| billradar/case.py | 85 | Line (class) | field | 2026-10-26 |     code: str = "" |
| billradar/case.py | 86 | Line (class) | field | 2026-10-26 |     description: str = "" |
| billradar/case.py | 87 | Line (class) | field | 2026-10-26 |     charges: Decimal \| None = None |
| billradar/case.py | 88 | Line (class) | field | 2026-10-26 |     insurance_paid: Decimal \| None = None |
| billradar/case.py | 89 | Line (class) | field | 2026-10-26 |     adjustment: Decimal \| None = None |
| billradar/case.py | 90 | Line (class) | field | 2026-10-26 |     fa_discount: Decimal \| None = None |
| billradar/case.py | 91 | Line (class) | field | 2026-10-26 |     patient_responsibility: Decimal \| None = None |
| billradar/case.py | 92 | Line (class) | field | 2026-10-26 |     claim_ref: str = "" |
| billradar/case.py | 96 | Document (class) | signature | 2026-10-26 | class Document(BaseModel): |
| billradar/case.py | 97 | Document (class) | field | 2026-10-26 |     doc_id: str  # "S1".."Sn" for paper sheets (number shown on screen), "D1".. for digital files |
| billradar/case.py | 98 | Document (class) | field | 2026-10-26 |     source: Source |
| billradar/case.py | 99 | Document (class) | field | 2026-10-26 |     kind: DocKind |
| billradar/case.py | 100 | Document (class) | field | 2026-10-26 |     patient: str = ""  # a token from the local profile, e.g. "PATIENT_1"; never a real name |
| billradar/case.py | 101 | Document (class) | field | 2026-10-26 |     provider: str = "" |
| billradar/case.py | 102 | Document (class) | field | 2026-10-26 |     account_ref: str = "" |
| billradar/case.py | 103 | Document (class) | field | 2026-10-26 |     claim_ref: str = "" |
| billradar/case.py | 104 | Document (class) | field | 2026-10-26 |     statement_date: date \| None = None |
| billradar/case.py | 105 | Document (class) | field | 2026-10-26 |     service_from: date \| None = None |
| billradar/case.py | 106 | Document (class) | field | 2026-10-26 |     service_to: date \| None = None |
| billradar/case.py | 107 | Document (class) | field | 2026-10-26 |     first_after_discharge: bool = False |
| billradar/case.py | 108 | Document (class) | field | 2026-10-26 |     insurance_payment_date: date \| None = None |
| billradar/case.py | 109 | Document (class) | field | 2026-10-26 |     total_charges: Decimal \| None = None |
| billradar/case.py | 110 | Document (class) | field | 2026-10-26 |     insurance_paid: Decimal \| None = None |
| billradar/case.py | 111 | Document (class) | field | 2026-10-26 |     fa_discount: Decimal \| None = None |
| billradar/case.py | 112 | Document (class) | field | 2026-10-26 |     patient_balance: Decimal \| None = None |
| billradar/case.py | 114 | Document (class) | field | 2026-10-26 |     amount_due_coupon: Decimal \| None = None  # the "PAY THIS AMOUNT" box, when the sheet has one |
| billradar/case.py | 116 | Document (class) | field | 2026-10-26 |     member_ref: str = ""  # insurance member ID as printed (a token) |
| billradar/case.py | 117 | Document (class) | field | 2026-10-26 |     page_no: int \| None = None  # "Page 2 of 5" -> 2, 5 |
| billradar/case.py | 118 | Document (class) | field | 2026-10-26 |     page_count: int \| None = None |
| billradar/case.py | 121 | Document (class) | field | 2026-10-26 |     lines: list[Line] = Field(default_factory=list) |
| billradar/case.py | 131 | Role (class) | signature | 2026-10-26 | class Role(StrEnum): |
| billradar/case.py | 132 | Role (class) | code | 2026-10-26 |     MOTHER = "mother" |
| billradar/case.py | 133 | Role (class) | code | 2026-10-26 |     NEWBORN = "newborn" |
| billradar/case.py | 135 | Role (class) | code | 2026-10-26 |     OTHER = "other" |
| billradar/case.py | 138 | Person (class) | signature | 2026-10-26 | class Person(BaseModel): |
| billradar/case.py | 139 | Person (class) | field | 2026-10-26 |     token: str |
| billradar/case.py | 140 | Person (class) | field | 2026-10-26 |     role: Role |
| billradar/case.py | 141 | Person (class) | field | 2026-10-26 |     name: str = ""  # shown on this device only; the cloud sees the token |
| billradar/case.py | 142 | Person (class) | field | 2026-10-26 |     birth_date: str = ""  # local only, for the hospital form |
| billradar/case.py | 143 | Person (class) | field | 2026-10-26 |     relationship: str = ""  # "Self", "Daughter", ... as the form asks |
| billradar/case.py | 144 | Person (class) | field | 2026-10-26 |     employer: str = "" |
| billradar/case.py | 147 | LocalDetails (class) | signature | 2026-10-26 | class LocalDetails(BaseModel): |
| billradar/case.py | 148 | LocalDetails (class) | doc | 2026-10-26 |     """What only the family's letters and forms need. Never sent to any model.""" |
| billradar/case.py | 150 | LocalDetails (class) | field | 2026-10-26 |     street: str = "" |
| billradar/case.py | 151 | LocalDetails (class) | field | 2026-10-26 |     city: str = "" |
| billradar/case.py | 152 | LocalDetails (class) | field | 2026-10-26 |     state: str = "" |
| billradar/case.py | 153 | LocalDetails (class) | field | 2026-10-26 |     zip: str = "" |
| billradar/case.py | 154 | LocalDetails (class) | field | 2026-10-26 |     phone: str = "" |
| billradar/case.py | 155 | LocalDetails (class) | field | 2026-10-26 |     spouse_monthly_gross: Decimal \| None = None |
| billradar/case.py | 156 | LocalDetails (class) | field | 2026-10-26 |     other_monthly_income: Decimal \| None = None |
| billradar/case.py | 157 | LocalDetails (class) | field | 2026-10-26 |     rent: Decimal \| None = None |
| billradar/case.py | 158 | LocalDetails (class) | field | 2026-10-26 |     electricity: Decimal \| None = None |
| billradar/case.py | 159 | LocalDetails (class) | field | 2026-10-26 |     phone_bill: Decimal \| None = None |
| billradar/case.py | 160 | LocalDetails (class) | field | 2026-10-26 |     checking: Decimal \| None = None |
| billradar/case.py | 161 | LocalDetails (class) | field | 2026-10-26 |     savings: Decimal \| None = None |
| billradar/case.py | 162 | LocalDetails (class) | field | 2026-10-26 |     residence_value: Decimal \| None = None |
| billradar/case.py | 163 | LocalDetails (class) | field | 2026-10-26 |     tokens: dict[str, str] = Field(default_factory=dict)  # "ACCT_1" -> the real account number |
| billradar/case.py | 173 | Profile (class) | signature | 2026-10-26 | class Profile(BaseModel): |
| billradar/case.py | 174 | Profile (class) | doc | 2026-10-26 |     """Kept on the device. Only tokens and the numbers the checks need.""" |
| billradar/case.py | 176 | Profile (class) | field | 2026-10-26 |     household_size: int |
| billradar/case.py | 177 | Profile (class) | field | 2026-10-26 |     annual_income: Decimal |
| billradar/case.py | 178 | Profile (class) | field | 2026-10-26 |     liquid_assets: Decimal \| None = None |
| billradar/case.py | 179 | Profile (class) | field | 2026-10-26 |     insured: bool = True |
| billradar/case.py | 180 | Profile (class) | field | 2026-10-26 |     people: list[Person] = Field(default_factory=list) |
| billradar/case.py | 181 | Profile (class) | field | 2026-10-26 |     local: LocalDetails = Field(default_factory=LocalDetails) |
| billradar/case.py | 185 | Profile._size | signature | 2026-10-26 |     @field_validator("household_size") |
| billradar/case.py | 186 | Profile._size | signature | 2026-10-26 |     @classmethod |
| billradar/case.py | 187 | Profile._size | signature | 2026-10-26 |     def _size(cls, v: int) -> int: |
| billradar/case.py | 188 | Profile._size | code | 2026-10-26 |         if v < 1: |
| billradar/case.py | 189 | Profile._size | code | 2026-10-26 |             raise ValueError("household_size must be >= 1") |
| billradar/case.py | 190 | Profile._size | code | 2026-10-26 |         return v |
| billradar/case.py | 192 | Profile.role_of | signature | 2026-10-26 |     def role_of(self, token: str) -> Role: |
| billradar/case.py | 197 | Case (class) | signature | 2026-10-26 | class Case(BaseModel): |
| billradar/case.py | 198 | Case (class) | field | 2026-10-26 |     case_id: str |
| billradar/case.py | 199 | Case (class) | field | 2026-10-26 |     letterhead: str = ""  # name printed on the sheets (demo: a fictional hospital) |
| billradar/case.py | 200 | Case (class) | field | 2026-10-26 |     policy_id: str  # which real public policy the case is checked against |
| billradar/case.py | 201 | Case (class) | field | 2026-10-26 |     today: date |
| billradar/case.py | 202 | Case (class) | field | 2026-10-26 |     demo: bool = False  # sample data: every generated document carries a SAMPLE stamp |
| billradar/case.py | 203 | Case (class) | field | 2026-10-26 |     profile: Profile |
| billradar/case.py | 204 | Case (class) | field | 2026-10-26 |     documents: list[Document] |
| billradar/case.py | 206 | Case.doc | signature | 2026-10-26 |     def doc(self, doc_id: str) -> Document: |
| billradar/case.py | 213 | Case.bills | signature | 2026-10-26 |     def bills(self) -> list[Document]: |
| billradar/case.py | 215 | Case.bills | code | 2026-10-26 |         return [d for d in self.documents if d.kind in (DocKind.HOSPITAL_STATEMENT, DocKind.ITEMIZED_BILL)] |
| billradar/case.py | 217 | Case.eobs | signature | 2026-10-26 |     def eobs(self) -> list[Document]: |
| billradar/case.py | 219 | Case.eobs | code | 2026-10-26 |         return [d for d in self.documents if d.kind == DocKind.EOB] |
| billradar/checks.py | 7 | (module) | doc | 2026-10-26 | """ |
| billradar/checks.py | 9 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/checks.py | 14 | (module) | import | 2026-10-26 | from datetime import date, timedelta |
| billradar/checks.py | 15 | (module) | import | 2026-10-26 | from decimal import ROUND_HALF_UP, Decimal |
| billradar/checks.py | 16 | (module) | import | 2026-10-26 | from enum import StrEnum |
| billradar/checks.py | 19 | (module) | import | 2026-10-26 | from pydantic import BaseModel, Field |
| billradar/checks.py | 22 | (module) | import | 2026-10-26 | from billradar.case import Case, Document, DocKind, Line, Role |
| billradar/checks.py | 28 | (module) | code | 2026-10-26 | CENT = Decimal("0.01") |
| billradar/checks.py | 31 | _q | signature | 2026-10-26 | def _q(x: Decimal) -> Decimal: |
| billradar/checks.py | 33 | _q | code | 2026-10-26 |     return x.quantize(CENT, rounding=ROUND_HALF_UP) |
| billradar/checks.py | 36 | _add_months | signature | 2026-10-26 | def _add_months(d: date, months: int) -> date: |
| billradar/checks.py | 40 | _add_months | code | 2026-10-26 |         raise ValueError(d) |
| billradar/checks.py | 55 | Kind (class) | signature | 2026-10-26 | class Kind(StrEnum): |
| billradar/checks.py | 56 | Kind (class) | code | 2026-10-26 |     E1 = "E1" |
| billradar/checks.py | 57 | Kind (class) | code | 2026-10-26 |     E2 = "E2" |
| billradar/checks.py | 58 | Kind (class) | code | 2026-10-26 |     E3 = "E3" |
| billradar/checks.py | 59 | Kind (class) | code | 2026-10-26 |     E4 = "E4" |
| billradar/checks.py | 60 | Kind (class) | code | 2026-10-26 |     B1 = "B1" |
| billradar/checks.py | 62 | Kind (class) | code | 2026-10-26 |     P1 = "P1" |
| billradar/checks.py | 63 | Kind (class) | code | 2026-10-26 |     F1 = "F1" |
| billradar/checks.py | 64 | Kind (class) | code | 2026-10-26 |     F2 = "F2" |
| billradar/checks.py | 65 | Kind (class) | code | 2026-10-26 |     F3 = "F3" |
| billradar/checks.py | 71 | Kind (class) | code | 2026-10-26 |     NM = "NM" |
| billradar/checks.py | 74 | Evidence (class) | signature | 2026-10-26 | class Evidence(BaseModel): |
| billradar/checks.py | 75 | Evidence (class) | field | 2026-10-26 |     doc_id: str |
| billradar/checks.py | 76 | Evidence (class) | field | 2026-10-26 |     line_no: int \| None = None |
| billradar/checks.py | 77 | Evidence (class) | field | 2026-10-26 |     note: str = "" |
| billradar/checks.py | 80 | Finding (class) | signature | 2026-10-26 | class Finding(BaseModel): |
| billradar/checks.py | 81 | Finding (class) | field | 2026-10-26 |     kind: Kind |
| billradar/checks.py | 82 | Finding (class) | field | 2026-10-26 |     title: str |
| billradar/checks.py | 83 | Finding (class) | field | 2026-10-26 |     detail: str |
| billradar/checks.py | 84 | Finding (class) | field | 2026-10-26 |     amount: Decimal \| None = None  # what may come off; None for dates and no-money notes |
| billradar/checks.py | 85 | Finding (class) | field | 2026-10-26 |     deadline: date \| None = None |
| billradar/checks.py | 86 | Finding (class) | field | 2026-10-26 |     evidence: list[Evidence] = Field(default_factory=list) |
| billradar/checks.py | 87 | Finding (class) | field | 2026-10-26 |     policy_refs: list[str] = Field(default_factory=list) |
| billradar/checks.py | 88 | Finding (class) | field | 2026-10-26 |     math: dict[str, str] = Field(default_factory=dict)  # every number the result came from |
| billradar/checks.py | 96 | Report (class) | signature | 2026-10-26 | class Report(BaseModel): |
| billradar/checks.py | 97 | Report (class) | field | 2026-10-26 |     case_id: str |
| billradar/checks.py | 98 | Report (class) | field | 2026-10-26 |     policy_id: str |
| billradar/checks.py | 99 | Report (class) | field | 2026-10-26 |     fpl_pct: Decimal |
| billradar/checks.py | 100 | Report (class) | field | 2026-10-26 |     findings: list[Finding] |
| billradar/checks.py | 101 | Report (class) | field | 2026-10-26 |     no_money: list[Finding] |
| billradar/checks.py | 102 | Report (class) | field | 2026-10-26 |     held_back: list[Finding]  # cited quotes not verified -> not shown to the family |
| billradar/checks.py | 103 | Report (class) | field | 2026-10-26 |     total_may_come_off: Decimal |
| billradar/checks.py | 104 | Report (class) | field | 2026-10-26 |     apply_by: date \| None |
| billradar/checks.py | 110 | episodes | signature | 2026-10-26 | def episodes(bills: list[Document]) -> list[list[Document]]: |
| billradar/checks.py | 113 | episodes | code | 2026-10-26 |     dated = sorted((b for b in bills if b.service_from), key=lambda b: b.service_from) |
| billradar/checks.py | 115 | episodes | code | 2026-10-26 |     groups: list[list[Document]] = [] |
| billradar/checks.py | 123 | episodes | code | 2026-10-26 |     undated = [b for b in bills if not b.service_from] |
| billradar/checks.py | 124 | episodes | code | 2026-10-26 |     if undated: |
| billradar/checks.py | 125 | episodes | code | 2026-10-26 |         groups.append(undated) |
| billradar/checks.py | 126 | episodes | code | 2026-10-26 |     return groups |
| billradar/checks.py | 221 | has_discount | signature | 2026-10-26 | def has_discount(doc: Document) -> bool: |
| billradar/checks.py | 248 | _insurance_lines | code | 2026-10-26 |     for eob in case.eobs(): |
| billradar/checks.py | 249 | _insurance_lines | code | 2026-10-26 |         if eob.patient and bill.patient and eob.patient != bill.patient: |
| billradar/checks.py | 250 | _insurance_lines | punct | 2026-10-26 |             continue |
| billradar/checks.py | 261 | _insurance_lines | punct | 2026-10-26 |     return None |
| billradar/checks.py | 303 | check_e1 | code | 2026-10-26 |     for bill in case.bills(): |
| billradar/checks.py | 304 | check_e1 | code | 2026-10-26 |         for line in bill.lines: |
| billradar/checks.py | 307 | check_e1 | punct | 2026-10-26 |                 continue |
| billradar/checks.py | 310 | check_e1 | punct | 2026-10-26 |                 continue |
| billradar/checks.py | 321 | check_e1 | code | 2026-10-26 |             if diff > 0: |
| billradar/checks.py | 323 | check_e1 | punct | 2026-10-26 |             else: |
| billradar/checks.py | 402 | check_assistance | code | 2026-10-26 |     tier = pol.tier_for(fpl_pct) |
| billradar/checks.py | 424 | check_assistance | punct | 2026-10-26 |                 continue |
| billradar/checks.py | 440 | check_assistance | punct | 2026-10-26 |             else: |
| billradar/checks.py | 596 | check_window | signature | 2026-10-26 | def check_window(case: Case, pol: policy.Policy) -> Finding \| None: |
| billradar/checks.py | 603 | check_window | code | 2026-10-26 |     refs.append("federal-501r#application-period") |
| billradar/checks.py | 1028 | _finish | code | 2026-10-26 |     for f in candidates: |
| billradar/checks.py | 1040 | _finish | punct | 2026-10-26 |         else: |
| billradar/checks.py | 1041 | _finish | code | 2026-10-26 |             shown.append(f) |
| billradar/checks.py | 1045 | run | signature | 2026-10-26 | def run(case: Case) -> Report: |
| billradar/checks.py | 1050 | run | code | 2026-10-26 |     pol = policy.load(case.policy_id) |
| billradar/checks.py | 1109 | (module) | code | 2026-10-26 | __all__ = ["run", "Report", "Finding", "Kind", "Evidence", "episodes", "DocKind"] |
| billradar/cli.py | 3 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/cli.py | 5 | (module) | import | 2026-10-26 | import argparse |
| billradar/cli.py | 6 | (module) | import | 2026-10-26 | import json |
| billradar/cli.py | 7 | (module) | import | 2026-10-26 | import sys |
| billradar/cli.py | 8 | (module) | import | 2026-10-26 | from datetime import date |
| billradar/cli.py | 9 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/cli.py | 12 | (module) | import | 2026-10-26 | from billradar.case import Case, Profile |
| billradar/cli.py | 13 | (module) | import | 2026-10-26 | from billradar.meta_client import MetaClient |
| billradar/cli.py | 16 | _print_report | signature | 2026-10-26 | def _print_report(r: checks.Report) -> None: |
| billradar/cli.py | 18 | _print_report | code | 2026-10-26 |     for f in r.findings: |
| billradar/cli.py | 28 | _parser | code | 2026-10-26 |     ap = argparse.ArgumentParser(prog="billradar") |
| billradar/cli.py | 29 | _parser | code | 2026-10-26 |     sub = ap.add_subparsers(dest="cmd", required=True) |
| billradar/cli.py | 59 | _check_case | code | 2026-10-26 |     return 0 |
| billradar/cli.py | 63 | _run_pack | code | 2026-10-26 |     meta = json.loads((args.pack / "profile.json").read_text()) |
| billradar/cli.py | 77 | _run_pack | code | 2026-10-26 |     return 0 |
| billradar/cli.py | 80 | main | signature | 2026-10-26 | def main(argv: list[str] \| None = None) -> int: |
| billradar/cli.py | 106 | (module) | code | 2026-10-26 | if __name__ == "__main__": |
| billradar/cli.py | 107 | (module) | code | 2026-10-26 |     sys.exit(main()) |
| billradar/context.py | 8 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/context.py | 10 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/demo_cases/example-appeal/case.json | 3 | (file) | data | 2026-10-26 |   "letterhead": "Lakeview Demo Hospital", |
| billradar/demo_cases/example-appeal/case.json | 4 | (file) | data | 2026-10-26 |   "policy_id": "memorial-2026-05", |
| billradar/demo_portal/appeal.html | 1 | (file) | template | 2026-10-26 | <!doctype html> |
| billradar/demo_portal/appeal.html | 2 | (file) | template | 2026-10-26 | <html lang="en"> |
| billradar/demo_portal/appeal.html | 3 | (file) | template | 2026-10-26 | <head> |
| billradar/demo_portal/appeal.html | 4 | (file) | template | 2026-10-26 | <meta charset="utf-8"> |
| billradar/demo_portal/appeal.html | 5 | (file) | template | 2026-10-26 | <meta name="viewport" content="width=device-width, initial-scale=1"> |
| billradar/evaluation.py | 6 | (module) | doc | 2026-10-26 | """ |
| billradar/evaluation.py | 8 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/evaluation.py | 10 | (module) | import | 2026-10-26 | import hashlib |
| billradar/evaluation.py | 11 | (module) | import | 2026-10-26 | import json |
| billradar/evaluation.py | 13 | (module) | import | 2026-10-26 | from datetime import date |
| billradar/evaluation.py | 14 | (module) | import | 2026-10-26 | from decimal import Decimal |
| billradar/evaluation.py | 15 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/evaluation.py | 17 | (module) | import | 2026-10-26 | from pydantic import BaseModel, Field |
| billradar/evaluation.py | 19 | (module) | import | 2026-10-26 | from billradar import policy |
| billradar/evaluation.py | 20 | (module) | import | 2026-10-26 | from billradar.checks import Kind, Report |
| billradar/evaluation.py | 21 | (module) | import | 2026-10-26 | from billradar.meta_client import data_url |
| billradar/evaluation.py | 22 | (module) | import | 2026-10-26 | from billradar.policies import source |
| billradar/evaluation.py | 27 | (module) | code | 2026-10-26 | MODEL = "muse-spark-1.3" |
| billradar/evaluation.py | 31 | KeyItem (class) | signature | 2026-10-26 | class KeyItem(BaseModel): |
| billradar/evaluation.py | 32 | KeyItem (class) | field | 2026-10-26 |     cls: str |
| billradar/evaluation.py | 33 | KeyItem (class) | field | 2026-10-26 |     sheets: list[str] = Field(default_factory=list)  # e.g. ["S1", "S2"]; any overlap counts |
| billradar/evaluation.py | 34 | KeyItem (class) | field | 2026-10-26 |     amount: Decimal \| None = None |
| billradar/evaluation.py | 35 | KeyItem (class) | field | 2026-10-26 |     deadline: date \| None = None |
| billradar/evaluation.py | 36 | KeyItem (class) | field | 2026-10-26 |     note: str = "" |
| billradar/evaluation.py | 39 | Key (class) | signature | 2026-10-26 | class Key(BaseModel): |
| billradar/evaluation.py | 40 | Key (class) | field | 2026-10-26 |     pack_id: str |
| billradar/evaluation.py | 41 | Key (class) | field | 2026-10-26 |     split: str  # "work" or "holdout" |
| billradar/evaluation.py | 42 | Key (class) | field | 2026-10-26 |     items: list[KeyItem] |
| billradar/evaluation.py | 45 | Prediction (class) | signature | 2026-10-26 | class Prediction(BaseModel): |
| billradar/evaluation.py | 46 | Prediction (class) | field | 2026-10-26 |     cls: str |
| billradar/evaluation.py | 47 | Prediction (class) | field | 2026-10-26 |     sheets: list[str] = Field(default_factory=list) |
| billradar/evaluation.py | 48 | Prediction (class) | field | 2026-10-26 |     amount: Decimal \| None = None |
| billradar/evaluation.py | 49 | Prediction (class) | field | 2026-10-26 |     deadline: date \| None = None |
| billradar/evaluation.py | 53 | key_hash | signature | 2026-10-26 | def key_hash(path: Path) -> str: |
| billradar/evaluation.py | 63 | seal | signature | 2026-10-26 | def seal(paths: list[Path], ledger: Path) -> list[str]: |
| billradar/evaluation.py | 68 | seal | code | 2026-10-26 |     return lines |
| billradar/evaluation.py | 71 | check_seal | signature | 2026-10-26 | def check_seal(path: Path, ledger: Path) -> bool: |
| billradar/evaluation.py | 79 | from_report | signature | 2026-10-26 | def from_report(report: Report) -> list[Prediction]: |
| billradar/evaluation.py | 83 | from_report | code | 2026-10-26 |     return [Prediction(cls=f.kind.value, sheets=sorted({e.doc_id for e in f.evidence}), amount=f.amount, |
| billradar/evaluation.py | 87 | (module) | code | 2026-10-26 | STRONG_SCHEMA = { |
| billradar/evaluation.py | 91 | (module) | code | 2026-10-26 |     "properties": {"findings": {"type": "array", "items": { |
| billradar/evaluation.py | 94 | (module) | code | 2026-10-26 |         "required": ["cls", "sheets", "amount", "deadline", "explanation"], |
| billradar/evaluation.py | 95 | (module) | code | 2026-10-26 |         "properties": { |
| billradar/evaluation.py | 97 | (module) | code | 2026-10-26 |             "sheets": {"type": "array", "items": {"type": "string"}}, |
| billradar/evaluation.py | 98 | (module) | code | 2026-10-26 |             "amount": {"type": "string"}, |
| billradar/evaluation.py | 99 | (module) | code | 2026-10-26 |             "deadline": {"type": "string"}, |
| billradar/evaluation.py | 100 | (module) | code | 2026-10-26 |             "explanation": {"type": "string"}, |
| billradar/evaluation.py | 103 | (module) | punct | 2026-10-26 | } |
| billradar/evaluation.py | 137 | _media | signature | 2026-10-26 | def _media(sheets: list[tuple[str, bytes]], files: list[tuple[str, str, bytes]]) -> list[dict]: |
| billradar/evaluation.py | 158 | simple_body | signature | 2026-10-26 | def simple_body(sheets, files) -> dict: |
| billradar/evaluation.py | 164 | strong_body | signature | 2026-10-26 | def strong_body(sheets, files, policy_id: str, household: dict) -> dict: |
| billradar/evaluation.py | 183 | _predict | import | 2026-10-26 |     from billradar.case import parse_date, parse_money |
| billradar/evaluation.py | 187 | from_strong | signature | 2026-10-26 | def from_strong(text: str) -> list[Prediction]: |
| billradar/evaluation.py | 192 | (module) | code | 2026-10-26 | JUDGE_SCHEMA = { |
| billradar/evaluation.py | 196 | (module) | code | 2026-10-26 |     "properties": { |
| billradar/evaluation.py | 197 | (module) | code | 2026-10-26 |         "items": {"type": "array", "items": { |
| billradar/evaluation.py | 204 | (module) | code | 2026-10-26 |                 "amount": {"type": "string"}, |
| billradar/evaluation.py | 205 | (module) | code | 2026-10-26 |                 "deadline": {"type": "string"}, |
| billradar/evaluation.py | 208 | (module) | code | 2026-10-26 |         "other_money_claims": {"type": "integer"}, |
| billradar/evaluation.py | 209 | (module) | punct | 2026-10-26 |     }, |
| billradar/evaluation.py | 210 | (module) | punct | 2026-10-26 | } |
| billradar/evaluation.py | 223 | judge_body | signature | 2026-10-26 | def judge_body(answer: str, key: Key) -> dict: |
| billradar/evaluation.py | 233 | from_judge | signature | 2026-10-26 | def from_judge(text: str, key: Key) -> tuple[list[Prediction], int]: |
| billradar/evaluation.py | 235 | from_judge | code | 2026-10-26 |     preds = [] |
| billradar/evaluation.py | 248 | ClassScore (class) | signature | 2026-10-26 | @dataclass |
| billradar/evaluation.py | 249 | ClassScore (class) | signature | 2026-10-26 | class ClassScore: |
| billradar/evaluation.py | 250 | ClassScore (class) | field | 2026-10-26 |     n: int = 0 |
| billradar/evaluation.py | 251 | ClassScore (class) | field | 2026-10-26 |     found: int = 0 |
| billradar/evaluation.py | 252 | ClassScore (class) | field | 2026-10-26 |     false: int = 0 |
| billradar/evaluation.py | 253 | ClassScore (class) | field | 2026-10-26 |     wrong_amount: int = 0 |
| billradar/evaluation.py | 254 | ClassScore (class) | field | 2026-10-26 |     no_amount: int = 0  # found, but said no amount where the key has one |
| billradar/evaluation.py | 255 | ClassScore (class) | field | 2026-10-26 |     wrong_deadline: int = 0 |
| billradar/evaluation.py | 258 | Score (class) | signature | 2026-10-26 | @dataclass |
| billradar/evaluation.py | 259 | Score (class) | signature | 2026-10-26 | class Score: |
| billradar/evaluation.py | 260 | Score (class) | field | 2026-10-26 |     by_class: dict[str, ClassScore] = field(default_factory=dict) |
| billradar/evaluation.py | 261 | Score (class) | field | 2026-10-26 |     extra_false: int = 0  # unmatched money claims the judge counted (simple path) |
| billradar/evaluation.py | 263 | Score.add | signature | 2026-10-26 |     def add(self, other: "Score") -> None: |
| billradar/evaluation.py | 268 | Score.add | code | 2026-10-26 |         self.extra_false += other.extra_false |
| billradar/evaluation.py | 305 | score | signature | 2026-10-26 | def score(key: Key, preds: list[Prediction], extra_false: int = 0) -> Score: |
| billradar/evaluation.py | 320 | table | signature | 2026-10-26 | def table(results: dict[str, Score]) -> str: |
| billradar/evaluation.py | 321 | table | code | 2026-10-26 |     paths = list(results) |
| billradar/evaluation.py | 333 | table | code | 2026-10-26 |     rows = ["\| Class \| " + " \| ".join(paths) + " \|", "\|---\|" + "---\|" * len(paths)] |
| billradar/evaluation.py | 340 | table | code | 2026-10-26 |     return "\\n".join(rows) |
| billradar/evaluation.py | 355 | verified_policy | signature | 2026-10-26 | def verified_policy(policy_id: str) -> bool: |
| billradar/example.py | 14 | (module) | doc | 2026-10-26 | """ |
| billradar/example.py | 16 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/example.py | 18 | (module) | import | 2026-10-26 | import io |
| billradar/example.py | 19 | (module) | import | 2026-10-26 | import json |
| billradar/example.py | 23 | (module) | import | 2026-10-26 | import sys |
| billradar/example.py | 24 | (module) | import | 2026-10-26 | from datetime import date |
| billradar/example.py | 25 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/example.py | 27 | (module) | import | 2026-10-26 | import numpy as np |
| billradar/example.py | 28 | (module) | import | 2026-10-26 | from PIL import Image, ImageDraw, ImageFilter, ImageFont |
| billradar/example.py | 128 | _run | code | 2026-10-26 |     pdfs = [(p.name, p.read_bytes()) for p in sorted(pack.glob("*.pdf"))] |
| billradar/example.py | 138 | (module) | code | 2026-10-26 | SIZE = (2400, 1700) |
| billradar/example.py | 139 | (module) | code | 2026-10-26 | SHEETS = [  # (center x, center y, angle) for 5 letter-size sheets, plus what is printed on each |
| billradar/example.py | 141 | (module) | code | 2026-10-26 |     ((1180, 430, 4), "PATIENT STATEMENT", "Patient: Baby Sample", "Balance due $1,240.00"), |
| billradar/example.py | 142 | (module) | code | 2026-10-26 |     ((1880, 460, -3), "FIRST STATEMENT AFTER DISCHARGE", "Patient: Anna Sample", "Insurance pending"), |
| billradar/example.py | 143 | (module) | code | 2026-10-26 |     ((760, 1250, 5), "EXPLANATION OF BENEFITS", "THIS IS NOT A BILL", "Member: Anna Sample"), |
| billradar/example.py | 144 | (module) | code | 2026-10-26 |     ((1560, 1240, -4), "EXPLANATION OF BENEFITS", "THIS IS NOT A BILL", "Member: Baby Sample"), |
| billradar/example.py | 145 | (module) | punct | 2026-10-26 | ] |
| billradar/example.py | 146 | (module) | code | 2026-10-26 | W, H = 520, 672 |
| billradar/example.py | 147 | (module) | code | 2026-10-26 | DEMO_PEOPLE = [  # fictional family; stays local, the model only sees PATIENT_1 / PATIENT_2 |
| billradar/example.py | 148 | (module) | code | 2026-10-26 |     {"token": "PATIENT_1", "role": "mother", "name": "Anna", "birth_date": "03/14/1994", "relationship": "Self", |
| billradar/example.py | 149 | (module) | code | 2026-10-26 |      "employer": "Sample Bakery LLC"}, |
| billradar/example.py | 151 | (module) | code | 2026-10-26 |     {"token": "P3", "role": "other", "name": "Mark", "birth_date": "07/02/1990", "relationship": "Spouse", |
| billradar/example.py | 152 | (module) | code | 2026-10-26 |      "employer": "Sample Auto Repair"}, |
| billradar/example.py | 153 | (module) | code | 2026-10-26 |     {"token": "P4", "role": "other", "name": "Leo", "birth_date": "09/30/2023", "relationship": "Son"}, |
| billradar/example.py | 154 | (module) | punct | 2026-10-26 | ] |
| billradar/example.py | 155 | (module) | code | 2026-10-26 | DEMO_LOCAL = {"street": "100 Example Street", "city": "Hollywood", "state": "FL", "zip": "33021", |
| billradar/example.py | 156 | (module) | code | 2026-10-26 |               "phone": "(555) 010-0000", "rent": "1850", "electricity": "140", "phone_bill": "60", |
| billradar/example.py | 157 | (module) | code | 2026-10-26 |               "checking": "2400", "savings": "3600", "tokens": {"ACCT_1": "LDH-000123", "ACCT_2": "LDH-000124"}} |
| billradar/example.py | 160 | font | signature | 2026-10-26 | def font(size: int, bold: bool = False): |
| billradar/example.py | 174 | draw_sheet | signature | 2026-10-26 | def draw_sheet(title: str, who: str, last: str) -> Image.Image: |
| billradar/example.py | 233 | _scripted_client | import | 2026-10-26 |     from tests.test_pipeline import FakeMeta, spark_payload_from_fixture |
| billradar/explain.py | 11 | (module) | doc | 2026-10-26 | """ |
| billradar/explain.py | 13 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/explain.py | 15 | (module) | import | 2026-10-26 | import json |
| billradar/explain.py | 16 | (module) | import | 2026-10-26 | import re |
| billradar/explain.py | 183 | request_body | code | 2026-10-26 |         "input": [ |
| billradar/explain.py | 184 | request_body | code | 2026-10-26 |             {"role": "developer", "content": [{"type": "input_text", "text": INSTRUCTIONS}]}, |
| billradar/family_agent.py | 8 | (module) | doc | 2026-10-26 | """ |
| billradar/family_agent.py | 10 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/family_agent.py | 12 | (module) | import | 2026-10-26 | import json |
| billradar/family_agent.py | 13 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/finding_text.py | 6 | (module) | doc | 2026-10-26 | """ |
| billradar/finding_text.py | 8 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/finding_text.py | 10 | (module) | import | 2026-10-26 | import re |
| billradar/finding_text.py | 11 | (module) | import | 2026-10-26 | from datetime import date |
| billradar/forms.py | 7 | (module) | doc | 2026-10-26 | """ |
| billradar/forms.py | 9 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/forms.py | 11 | (module) | import | 2026-10-26 | import io |
| billradar/forms.py | 12 | (module) | import | 2026-10-26 | from dataclasses import dataclass |
| billradar/forms.py | 13 | (module) | import | 2026-10-26 | from decimal import ROUND_HALF_UP, Decimal |
| billradar/forms.py | 15 | (module) | import | 2026-10-26 | from pypdf import PdfReader, PdfWriter |
| billradar/forms.py | 16 | (module) | import | 2026-10-26 | from reportlab.lib.colors import Color |
| billradar/forms.py | 17 | (module) | import | 2026-10-26 | from reportlab.pdfgen import canvas |
| billradar/forms.py | 21 | (module) | import | 2026-10-26 | from billradar.policies import source |
| billradar/forms.py | 23 | (module) | code | 2026-10-26 | PAGE_H = 792.0  # Letter; pdftotext measures y from the top, reportlab from the bottom |
| billradar/forms.py | 24 | (module) | code | 2026-10-26 | INK = Color(0.05, 0.2, 0.45) |
| billradar/forms.py | 25 | (module) | code | 2026-10-26 | STAMP = Color(0.85, 0.15, 0.15, alpha=0.55) |
| billradar/forms.py | 27 | (module) | code | 2026-10-26 | MEMORIAL_FEF = { |
| billradar/forms.py | 28 | (module) | code | 2026-10-26 |     "account": (36, 122), "mr": (362, 122), |
| billradar/forms.py | 29 | (module) | code | 2026-10-26 |     "patient": (112, 146.5), "street": (112, 156.5), "phone": (406, 156.5), |
| billradar/forms.py | 30 | (module) | code | 2026-10-26 |     "city": (52, 166.5), "state": (274, 166.5), "zip": (418, 166.5), |
| billradar/forms.py | 31 | (module) | code | 2026-10-26 |     "row0": 280, "row_h": 16.2, "cols": (36, 228, 334, 434), |
| billradar/forms.py | 32 | (module) | code | 2026-10-26 |     "salary": (212, 412), "spouse": (212, 425.5), "other": (212, 439), |
| billradar/forms.py | 33 | (module) | code | 2026-10-26 |     "rent": (464, 412), "electricity": (464, 425.5), "phone_bill": (464, 439), |
| billradar/forms.py | 34 | (module) | code | 2026-10-26 |     "checking": (257, 477), "savings": (257, 489), "residence": (257, 501), |
| billradar/forms.py | 35 | (module) | punct | 2026-10-26 | } |
| billradar/forms.py | 38 | FilledForm (class) | signature | 2026-10-26 | @dataclass |
| billradar/forms.py | 39 | FilledForm (class) | signature | 2026-10-26 | class FilledForm: |
| billradar/forms.py | 40 | FilledForm (class) | field | 2026-10-26 |     pdf: bytes |
| billradar/forms.py | 41 | FilledForm (class) | field | 2026-10-26 |     filled: list[str]  # which fields got a value |
| billradar/forms.py | 42 | FilledForm (class) | field | 2026-10-26 |     left_for_you: list[str]  # which fields the family still has to write by hand |
| billradar/forms.py | 54 | _amount | signature | 2026-10-26 | def _amount(x: Decimal \| None) -> str: |
| billradar/forms.py | 81 | memorial_values | signature | 2026-10-26 | def memorial_values(case: Case) -> dict[str, str]: |
| billradar/forms.py | 92 | memorial_values | punct | 2026-10-26 |     } |
| billradar/forms.py | 99 | _memorial_layer | code | 2026-10-26 |     c.setFillColor(INK) |
| billradar/forms.py | 100 | _memorial_layer | code | 2026-10-26 |     c.setFont("Helvetica", 9.5) |
| billradar/forms.py | 108 | _memorial_layer | code | 2026-10-26 |             if cell: |
| billradar/forms.py | 110 | _memorial_layer | code | 2026-10-26 |     if case.demo: |
| billradar/forms.py | 120 | _memorial_layer | code | 2026-10-26 |     c.save() |
| billradar/forms.py | 124 | fill_memorial | signature | 2026-10-26 | def fill_memorial(case: Case) -> FilledForm: |
| billradar/forms.py | 125 | fill_memorial | code | 2026-10-26 |     blank = source.form_path("memorial-fef") |
| billradar/forms.py | 126 | fill_memorial | code | 2026-10-26 |     if not blank.exists(): |
| billradar/forms.py | 127 | fill_memorial | string | 2026-10-26 |         raise FileNotFoundError("run scripts/fetch_policies.py to download the blank form") |
| billradar/forms.py | 128 | fill_memorial | code | 2026-10-26 |     values = memorial_values(case) |
| billradar/forms.py | 137 | fill_memorial | code | 2026-10-26 |     out = io.BytesIO() |
| billradar/forms.py | 184 | _appeal_fields | code | 2026-10-26 |             c.setFillColor(INK) |
| billradar/forms.py | 185 | _appeal_fields | code | 2026-10-26 |             c.setFont("Helvetica", 9.5) |
| billradar/forms.py | 206 | _appeal_stamp | code | 2026-10-26 |     c.setFillColor(STAMP) |
| billradar/forms.py | 207 | _appeal_stamp | code | 2026-10-26 |     c.setFont("Helvetica-Bold", 30) |
| billradar/forms.py | 209 | _appeal_stamp | code | 2026-10-26 |     c.setFont("Helvetica-Bold", 12) |
| billradar/fpl.py | 5 | (module) | doc | 2026-10-26 | """ |
| billradar/fpl.py | 7 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/fpl.py | 9 | (module) | import | 2026-10-26 | from decimal import ROUND_HALF_UP, Decimal |
| billradar/fpl.py | 11 | (module) | code | 2026-10-26 | GUIDELINES = { |
| billradar/fpl.py | 12 | (module) | code | 2026-10-26 |     2026: {"base": [15960, 21640, 27320, 33000, 38680, 44360, 50040, 55720], "each_extra": 5680}, |
| billradar/fpl.py | 13 | (module) | punct | 2026-10-26 | } |
| billradar/fpl.py | 23 | guideline | signature | 2026-10-26 | def guideline(household_size: int, year: int = 2026) -> Decimal: |
| billradar/fpl.py | 24 | guideline | code | 2026-10-26 |     if household_size < 1: |
| billradar/fpl.py | 25 | guideline | code | 2026-10-26 |         raise ValueError("household size must be at least 1") |
| billradar/fpl.py | 33 | percent_of_guideline | signature | 2026-10-26 | def percent_of_guideline(annual_income: Decimal, household_size: int, year: int = 2026) -> Decimal: |
| billradar/highlight.py | 10 | (module) | doc | 2026-10-26 | """ |
| billradar/highlight.py | 12 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/highlight.py | 14 | (module) | import | 2026-10-26 | import io |
| billradar/highlight.py | 15 | (module) | import | 2026-10-26 | import json |
| billradar/highlight.py | 94 | _outline | code | 2026-10-26 |     contours, _ = cv2.findContours((det.mask * 255).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE) |
| billradar/history.py | 7 | (module) | doc | 2026-10-26 | """ |
| billradar/history.py | 9 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/history.py | 11 | (module) | import | 2026-10-26 | import hashlib |
| billradar/history.py | 12 | (module) | import | 2026-10-26 | import json |
| billradar/laws.py | 8 | (module) | doc | 2026-10-26 | """ |
| billradar/laws.py | 10 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/laws.py | 12 | (module) | import | 2026-10-26 | import json |
| billradar/laws.py | 13 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/laws.py | 15 | (module) | import | 2026-10-26 | from functools import cache |
| billradar/laws.py | 16 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/laws.py | 19 | (module) | import | 2026-10-26 | from billradar.case import Case |
| billradar/laws.py | 20 | (module) | import | 2026-10-26 | from billradar.policies import source |
| billradar/ledger.py | 14 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/ledger.py | 15 | (module) | import | 2026-10-26 | from datetime import date |
| billradar/ledger.py | 16 | (module) | import | 2026-10-26 | from decimal import Decimal |
| billradar/meta_client.py | 7 | (module) | doc | 2026-10-26 | """ |
| billradar/meta_client.py | 9 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/meta_client.py | 11 | (module) | import | 2026-10-26 | import base64 |
| billradar/meta_client.py | 13 | (module) | import | 2026-10-26 | import hashlib |
| billradar/meta_client.py | 14 | (module) | import | 2026-10-26 | import json |
| billradar/meta_client.py | 15 | (module) | import | 2026-10-26 | import os |
| billradar/meta_client.py | 16 | (module) | import | 2026-10-26 | import random |
| billradar/meta_client.py | 18 | (module) | import | 2026-10-26 | import time |
| billradar/meta_client.py | 19 | (module) | import | 2026-10-26 | from collections.abc import Iterator |
| billradar/meta_client.py | 20 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/meta_client.py | 21 | (module) | import | 2026-10-26 | from datetime import datetime, timezone |
| billradar/meta_client.py | 22 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/meta_client.py | 24 | (module) | import | 2026-10-26 | import requests |
| billradar/meta_client.py | 26 | (module) | code | 2026-10-26 | API_URL = "https://api.meta.ai/v1/responses" |
| billradar/meta_client.py | 34 | (module) | code | 2026-10-26 | ROOT = Path(__file__).resolve().parents[1] |
| billradar/meta_client.py | 35 | (module) | code | 2026-10-26 | RECORDINGS = ROOT / "tests" / "fixtures" / "recordings" |
| billradar/meta_client.py | 36 | (module) | code | 2026-10-26 | JOURNAL = ROOT / "runs" / "requests.jsonl" |
| billradar/meta_client.py | 40 | (module) | code | 2026-10-26 | RETRY_STATUS = {429, 500, 503} |
| billradar/meta_client.py | 55 | MetaAPIError (class) | signature | 2026-10-26 | class MetaAPIError(RuntimeError): |
| billradar/meta_client.py | 56 | MetaAPIError (class) | punct | 2026-10-26 |     pass |
| billradar/meta_client.py | 59 | ReplayMissing (class) | signature | 2026-10-26 | class ReplayMissing(MetaAPIError): |
| billradar/meta_client.py | 60 | ReplayMissing (class) | punct | 2026-10-26 |     pass |
| billradar/meta_client.py | 107 | data_url | signature | 2026-10-26 | def data_url(raw: bytes, mime: str) -> str: |
| billradar/meta_client.py | 111 | _media_digest | signature | 2026-10-26 | def _media_digest(url: str) -> str: |
| billradar/meta_client.py | 115 | _strip_media | signature | 2026-10-26 | def _strip_media(obj): |
| billradar/meta_client.py | 119 | _strip_media | code | 2026-10-26 |     if isinstance(obj, dict): |
| billradar/meta_client.py | 124 | _strip_media | code | 2026-10-26 |     if isinstance(obj, list): |
| billradar/meta_client.py | 129 | _strip_media | code | 2026-10-26 |     return obj |
| billradar/meta_client.py | 144 | request_key | signature | 2026-10-26 | def request_key(body: dict) -> str: |
| billradar/meta_client.py | 151 | _count_media | signature | 2026-10-26 | def _count_media(body: dict) -> tuple[int, int, int]: |
| billradar/meta_client.py | 154 | _count_media | code | 2026-10-26 |     for item in body.get("input", []): |
| billradar/meta_client.py | 177 | worst_case | code | 2026-10-26 |     for item in body.get("input", []): |
| billradar/meta_client.py | 232 | check_body | signature | 2026-10-26 | def check_body(body: dict) -> None: |
| billradar/meta_client.py | 234 | check_body | code | 2026-10-26 |     model = body.get("model") |
| billradar/meta_client.py | 236 | check_body | code | 2026-10-26 |     if model not in ALLOWED_MODELS: |
| billradar/meta_client.py | 248 | parse_sse | signature | 2026-10-26 | def parse_sse(lines: Iterator[bytes]) -> Iterator[dict]: |
| billradar/meta_client.py | 250 | parse_sse | code | 2026-10-26 |     for raw in lines: |
| billradar/meta_client.py | 261 | Result (class) | signature | 2026-10-26 | @dataclass |
| billradar/meta_client.py | 262 | Result (class) | signature | 2026-10-26 | class Result: |
| billradar/meta_client.py | 263 | Result (class) | field | 2026-10-26 |     text: str |
| billradar/meta_client.py | 264 | Result (class) | field | 2026-10-26 |     events: list[dict] |
| billradar/meta_client.py | 265 | Result (class) | field | 2026-10-26 |     usage: dict = field(default_factory=dict) |
| billradar/meta_client.py | 266 | Result (class) | field | 2026-10-26 |     response_id: str = "" |
| billradar/meta_client.py | 267 | Result (class) | field | 2026-10-26 |     replayed: bool = False |
| billradar/meta_client.py | 268 | Result (class) | field | 2026-10-26 |     seconds: float = 0.0 |
| billradar/meta_client.py | 274 | collect | signature | 2026-10-26 | def collect(events: list[dict]) -> tuple[str, dict, str]: |
| billradar/meta_client.py | 282 | collect | string | 2026-10-26 |         raise MetaAPIError("stream ended without a final event (partial output)") |
| billradar/meta_client.py | 297 | asr_key | code | 2026-10-26 |     return hashlib.sha256(canon.encode()).hexdigest()[:20] |
| billradar/meta_client.py | 309 | LiveTransport (class) | signature | 2026-10-26 | class LiveTransport: |
| billradar/meta_client.py | 311 | LiveTransport.__init__ | code | 2026-10-26 |         self.api_key = api_key |
| billradar/meta_client.py | 312 | LiveTransport.__init__ | code | 2026-10-26 |         self.attempts = attempts |
| billradar/meta_client.py | 313 | LiveTransport.__init__ | code | 2026-10-26 |         self.timeout = timeout |
| billradar/meta_client.py | 347 | LiveTransport._post_retrying | code | 2026-10-26 |         raise MetaAPIError("retries exhausted") |
| billradar/meta_client.py | 349 | LiveTransport.events | signature | 2026-10-26 |     def events(self, body: dict) -> list[dict]: |
| billradar/meta_client.py | 355 | LiveTransport.events | code | 2026-10-26 |         delay = 0.75 |
| billradar/meta_client.py | 359 | LiveTransport.events | code | 2026-10-26 |             if r.status_code == 200: |
| billradar/meta_client.py | 375 | LiveTransport.events | code | 2026-10-26 |                 delay *= 2 |
| billradar/meta_client.py | 376 | LiveTransport.events | punct | 2026-10-26 |                 continue |
| billradar/meta_client.py | 379 | LiveTransport.events | code | 2026-10-26 |         raise MetaAPIError("retries exhausted") |
| billradar/meta_client.py | 406 | ReplayTransport (class) | signature | 2026-10-26 | class ReplayTransport: |
| billradar/meta_client.py | 407 | ReplayTransport.__init__ | signature | 2026-10-26 |     def __init__(self, directory: Path = RECORDINGS): |
| billradar/meta_client.py | 408 | ReplayTransport.__init__ | code | 2026-10-26 |         self.directory = directory |
| billradar/meta_client.py | 416 | ReplayTransport.path | signature | 2026-10-26 |     def path(self, body: dict) -> Path: |
| billradar/meta_client.py | 419 | ReplayTransport.events | signature | 2026-10-26 |     def events(self, body: dict) -> list[dict]: |
| billradar/meta_client.py | 437 | MetaClient (class) | signature | 2026-10-26 | class MetaClient: |
| billradar/meta_client.py | 440 | MetaClient.__init__ | signature | 2026-10-26 |     def __init__(self, transport=None, record_to: Path \| None = RECORDINGS, journal: Path \| None = JOURNAL): |
| billradar/meta_client.py | 442 | MetaClient.__init__ | code | 2026-10-26 |         self.record_to = record_to |
| billradar/meta_client.py | 443 | MetaClient.__init__ | code | 2026-10-26 |         self.journal = journal |
| billradar/meta_client.py | 454 | MetaClient._timed | code | 2026-10-26 |         started = time.monotonic() |
| billradar/meta_client.py | 462 | MetaClient._record | code | 2026-10-26 |         self.record_to.mkdir(parents=True, exist_ok=True) |
| billradar/meta_client.py | 473 | MetaClient._default_transport | signature | 2026-10-26 |     @staticmethod |
| billradar/meta_client.py | 474 | MetaClient._default_transport | signature | 2026-10-26 |     def _default_transport(): |
| billradar/meta_client.py | 475 | MetaClient._default_transport | code | 2026-10-26 |         key = os.environ.get("MODEL_API_KEY", "") |
| billradar/meta_client.py | 476 | MetaClient._default_transport | code | 2026-10-26 |         if key and os.environ.get("BILLRADAR_LIVE") == "1": |
| billradar/meta_client.py | 477 | MetaClient._default_transport | code | 2026-10-26 |             return LiveTransport(key) |
| billradar/meta_client.py | 478 | MetaClient._default_transport | code | 2026-10-26 |         return ReplayTransport() |
| billradar/meta_client.py | 480 | MetaClient.live | signature | 2026-10-26 |     @property |
| billradar/meta_client.py | 481 | MetaClient.live | signature | 2026-10-26 |     def live(self) -> bool: |
| billradar/meta_client.py | 484 | MetaClient.respond | signature | 2026-10-26 |     def respond(self, body: dict, label: str = "") -> Result: |
| billradar/meta_client.py | 533 | MetaClient._going_out | code | 2026-10-26 |             self.journal.parent.mkdir(parents=True, exist_ok=True) |
| billradar/meta_client.py | 534 | MetaClient._going_out | code | 2026-10-26 |             with self.journal.open("a") as f: |
| billradar/meta_client.py | 540 | MetaClient._write | code | 2026-10-26 |         if not self.journal: |
| billradar/meta_client.py | 541 | MetaClient._write | punct | 2026-10-26 |             return |
| billradar/meta_client.py | 542 | MetaClient._write | code | 2026-10-26 |         self.journal.parent.mkdir(parents=True, exist_ok=True) |
| billradar/open_lines.py | 16 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/open_lines.py | 17 | (module) | import | 2026-10-26 | from datetime import date |
| billradar/open_lines.py | 18 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/pdfpages.py | 169 | sent_view | code | 2026-10-26 |         r, c = divmod(i, per_row) |
| billradar/pdfpages.py | 170 | sent_view | code | 2026-10-26 |         x, y = gap + c * (cell_w + gap), gap + r * (cell_h + label_h + gap) |
| billradar/pdfpages.py | 171 | sent_view | code | 2026-10-26 |         t = img.copy() |
| billradar/pdfpages.py | 172 | sent_view | code | 2026-10-26 |         t.thumbnail((cell_w, cell_h)) |
| billradar/pipeline.py | 7 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/pipeline.py | 9 | (module) | import | 2026-10-26 | import json |
| billradar/pipeline.py | 14 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/pipeline.py | 15 | (module) | import | 2026-10-26 | from datetime import date |
| billradar/pipeline.py | 16 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/pipeline.py | 26 | CaseRun (class) | signature | 2026-10-26 | @dataclass |
| billradar/pipeline.py | 27 | CaseRun (class) | signature | 2026-10-26 | class CaseRun: |
| billradar/pipeline.py | 28 | CaseRun (class) | field | 2026-10-26 |     case: Case |
| billradar/pipeline.py | 29 | CaseRun (class) | field | 2026-10-26 |     report: checks.Report |
| billradar/pipeline.py | 30 | CaseRun (class) | field | 2026-10-26 |     sheets: list[sam.Sheet] |
| billradar/pipeline.py | 31 | CaseRun (class) | field | 2026-10-26 |     overlays: list[bytes]  # one numbered overlay per table photo, JPEG |
| billradar/pipeline.py | 32 | CaseRun (class) | field | 2026-10-26 |     sent_views: list[bytes] = field(default_factory=list)  # private mode: the covered photo, as the models got it |
| billradar/pipeline.py | 33 | CaseRun (class) | field | 2026-10-26 |     problems: list[str] = field(default_factory=list) |
| billradar/pipeline.py | 34 | CaseRun (class) | field | 2026-10-26 |     timings: dict[str, float] = field(default_factory=dict) |
| billradar/pipeline.py | 35 | CaseRun (class) | field | 2026-10-26 |     replayed: bool = True |
| billradar/pipeline.py | 36 | CaseRun (class) | field | 2026-10-26 |     verdict: verifier.Verdict \| None = None |
| billradar/pipeline.py | 37 | CaseRun (class) | field | 2026-10-26 |     redacted: bool = False |
| billradar/pipeline.py | 46 | _jpeg | signature | 2026-10-26 | def _jpeg(img) -> bytes: |
| billradar/pipeline.py | 50 | RealDataGate (class) | signature | 2026-10-26 | class RealDataGate(RuntimeError): |
| billradar/pipeline.py | 51 | RealDataGate (class) | punct | 2026-10-26 |     pass |
| billradar/pipeline.py | 86 | run | signature | 2026-10-26 | def run(client: MetaClient, photos: list[bytes], files: list[tuple[str, bytes]], profile: Profile, |
| billradar/pipeline.py | 87 | run | signature | 2026-10-26 |         policy_id: str, letterhead: str = "", today: date \| None = None, case_id: str = "case", |
| billradar/pipeline.py | 182 | _prepare | code | 2026-10-26 |     if client.live and not fictional: |
| billradar/pipeline.py | 183 | _prepare | string | 2026-10-26 |         raise RealDataGate("live model calls are allowed only on fictional packs (mark the pack fictional)") |
| billradar/pipeline.py | 188 | _prepare | code | 2026-10-26 |     vault = _vault(profile) if private else None |
| billradar/pipeline.py | 189 | _prepare | code | 2026-10-26 |     problems: list[str] = [] |
| billradar/pipeline.py | 190 | _prepare | code | 2026-10-26 |     timings: dict[str, float] = {} |
| billradar/pipeline.py | 191 | _prepare | code | 2026-10-26 |     replayed = True |
| billradar/pipeline.py | 212 | _prepare | code | 2026-10-26 |     for photo in photos: |
| billradar/pipeline.py | 217 | _prepare | punct | 2026-10-26 |         else: |
| billradar/pipeline.py | 342 | _finish | code | 2026-10-26 |         profile = profile.model_copy(deep=True) |
| billradar/pipeline.py | 344 | _finish | code | 2026-10-26 |             profile.local.tokens.setdefault(secret.token.strip("[]"), secret.value) |
| billradar/pipeline.py | 352 | _finish | code | 2026-10-26 |     problems += [f"reader: {p}" for p in read.problems] |
| billradar/pipeline.py | 373 | _finish | code | 2026-10-26 |     report = checks.run(case) |
| billradar/pipeline.py | 406 | sheets_not_sent | code | 2026-10-26 |         for f in report.findings: |
| billradar/pipeline.py | 420 | pages_maybe_unread | code | 2026-10-26 |     for f in report.findings: |
| billradar/pipeline.py | 442 | device_confirms | code | 2026-10-26 |     for f in report.findings: |
| billradar/pipeline.py | 698 | _what_was_sent | import | 2026-10-26 |     from PIL import Image, ImageDraw |
| billradar/pipeline.py | 711 | _what_was_sent | code | 2026-10-26 |     return canvas |
| billradar/pipeline.py | 719 | _vault | signature | 2026-10-26 | def _vault(profile: Profile) -> redact.Vault: |
| billradar/pipeline.py | 745 | _no_leaks | signature | 2026-10-26 | def _no_leaks(img, vault: redact.Vault, doc_id: str): |
| billradar/pipeline.py | 749 | _no_leaks | code | 2026-10-26 |     if left: |
| billradar/pipeline.py | 752 | _no_leaks | code | 2026-10-26 |     return img |
| billradar/pipeline.py | 811 | save | signature | 2026-10-26 | def save(run_: CaseRun, out: Path) -> None: |
| billradar/plans.py | 11 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/plans.py | 13 | (module) | import | 2026-10-26 | import io |
| billradar/plans.py | 14 | (module) | import | 2026-10-26 | import json |
| billradar/plans.py | 15 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/plans.py | 16 | (module) | import | 2026-10-26 | from functools import cache |
| billradar/plans.py | 17 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/plans.py | 30 | Fragment (class) | field | 2026-10-26 |     fragment_id: str |
| billradar/plans.py | 31 | Fragment (class) | field | 2026-10-26 |     page: int |
| billradar/plans.py | 32 | Fragment (class) | field | 2026-10-26 |     quote: str |
| billradar/plans.py | 34 | Fragment.ref | signature | 2026-10-26 |     @property |
| billradar/plans.py | 35 | Fragment.ref | signature | 2026-10-26 |     def ref(self) -> str: |
| billradar/plans.py | 63 | Plan.fragment | signature | 2026-10-26 |     def fragment(self, fragment_id: str) -> Fragment: |
| billradar/plans.py | 64 | Plan.fragment | code | 2026-10-26 |         return self.fragments[fragment_id] |
| billradar/plans.py | 120 | verify | code | 2026-10-26 |     elsewhere = next((i + 1 for i, p in enumerate(pages) if needle in p), None) |
| billradar/plans.py | 121 | verify | code | 2026-10-26 |     if elsewhere: |
| billradar/policies/baptist-2026-09.json | 1 | (file) | data | 2026-10-26 | { |
| billradar/policies/baptist-2026-09.json | 2 | (file) | data | 2026-10-26 |   "policy_id": "baptist-2026-09", |
| billradar/policies/baptist-2026-09.json | 3 | (file) | data | 2026-10-26 |   "hospital": "Baptist Health South Florida (Baptist Hospital of Miami)", |
| billradar/policies/baptist-2026-09.json | 4 | (file) | data | 2026-10-26 |   "title": "Financial Assistance Policy BHSF-355.14, revised 09/29/2026", |
| billradar/policies/baptist-2026-09.json | 5 | (file) | data | 2026-10-26 |   "url": "https://baptisthealth.net/-/media/FAB30007578640E2B1F902CBF6256B95.ashx", |
| billradar/policies/baptist-2026-09.json | 7 | (file) | data | 2026-10-26 |   "covers_insured_balances": false, |
| billradar/policies/baptist-2026-09.json | 8 | (file) | data | 2026-10-26 |   "min_request_total": null, |
| billradar/policies/baptist-2026-09.json | 9 | (file) | data | 2026-10-26 |   "liquid_assets_limit_for_free_care": null, |
| billradar/policies/baptist-2026-09.json | 10 | (file) | data | 2026-10-26 |   "income_cap_pct": null, |
| billradar/policies/baptist-2026-09.json | 11 | (file) | data | 2026-10-26 |   "tiers": [ |
| billradar/policies/baptist-2026-09.json | 12 | (file) | data | 2026-10-26 |     {"max_fpl_pct": 200, "discount_pct": 100, "fragment": "levels"}, |
| billradar/policies/baptist-2026-09.json | 13 | (file) | data | 2026-10-26 |     {"max_fpl_pct": 300, "discount_pct": 100, "fragment": "levels"} |
| billradar/policies/baptist-2026-09.json | 14 | (file) | data | 2026-10-26 |   ], |
| billradar/policies/baptist-2026-09.json | 15 | (file) | data | 2026-10-26 |   "window": { |
| billradar/policies/baptist-2026-09.json | 16 | (file) | data | 2026-10-26 |     "after_first_statement_days": 240, |
| billradar/policies/baptist-2026-09.json | 17 | (file) | data | 2026-10-26 |     "after_ecas_notice_days": 30, |
| billradar/policies/baptist-2026-09.json | 18 | (file) | data | 2026-10-26 |     "fragment": "window" |
| billradar/policies/baptist-2026-09.json | 19 | (file) | data | 2026-10-26 |   }, |
| billradar/policies/baptist-2026-09.json | 20 | (file) | data | 2026-10-26 |   "fragments": { |
| billradar/policies/baptist-2026-09.json | 21 | (file) | data | 2026-10-26 |     "uninsured-only": { |
| billradar/policies/baptist-2026-09.json | 22 | (file) | data | 2026-10-26 |       "page": 5, |
| billradar/policies/baptist-2026-09.json | 23 | (file) | data | 2026-10-26 |       "quote": "The designation of uninsured does not extend to a patient for the patient's out-of-pocket obligation for co-pays, deductibles or co-insurance." |
| billradar/policies/baptist-2026-09.json | 24 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/baptist-2026-09.json | 25 | (file) | data | 2026-10-26 |     "applies-to": { |
| billradar/policies/baptist-2026-09.json | 26 | (file) | data | 2026-10-26 |       "page": 1, |
| billradar/policies/baptist-2026-09.json | 27 | (file) | data | 2026-10-26 |       "quote": "This policy applies to patient service charges which no health insurance or any other payor source" |
| billradar/policies/baptist-2026-09.json | 28 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/baptist-2026-09.json | 29 | (file) | data | 2026-10-26 |     "levels": { |
| billradar/policies/baptist-2026-09.json | 30 | (file) | data | 2026-10-26 |       "page": 4, |
| billradar/policies/baptist-2026-09.json | 31 | (file) | data | 2026-10-26 |       "quote": "Family income of 200% FPL or less 100% Special needs financial assistance 2 Vice President of Revenue Management Family income of 200 to 300% FPL 100%" |
| billradar/policies/baptist-2026-09.json | 32 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/baptist-2026-09.json | 33 | (file) | data | 2026-10-26 |     "free-care": { |
| billradar/policies/baptist-2026-09.json | 34 | (file) | data | 2026-10-26 |       "page": 4, |
| billradar/policies/baptist-2026-09.json | 35 | (file) | data | 2026-10-26 |       "quote": "Patients qualifying for financial assistance under this policy receive a 100% discount (i.e., free care)." |
| billradar/policies/baptist-2026-09.json | 36 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/baptist-2026-09.json | 37 | (file) | data | 2026-10-26 |     "window": { |
| billradar/policies/baptist-2026-09.json | 38 | (file) | data | 2026-10-26 |       "page": 5, |
| billradar/policies/baptist-2026-09.json | 39 | (file) | data | 2026-10-26 |       "quote": "ends on the later of the 240th day after the date that the first post-discharge billing statement for the care is provided or at least 30 days after Baptist Health provides the individual with a written notice" |
| billradar/policies/baptist-2026-09.json | 40 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/baptist-2026-09.json | 41 | (file) | data | 2026-10-26 |     "refund": { |
| billradar/policies/baptist-2026-09.json | 42 | (file) | data | 2026-10-26 |       "page": 9, |
| billradar/policies/baptist-2026-09.json | 43 | (file) | data | 2026-10-26 |       "quote": "Refund any payments received for the service covered by the financial assistance approval (unless such excess amount is less than $5" |
| billradar/policies/baptist-2026-09.json | 44 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/baptist-2026-09.json | 45 | (file) | data | 2026-10-26 |     "facility-only": { |
| billradar/policies/baptist-2026-09.json | 46 | (file) | data | 2026-10-26 |       "page": 3, |
| billradar/policies/baptist-2026-09.json | 47 | (file) | data | 2026-10-26 |       "quote": "This policy applies only to facility charges and employed physician charges." |
| billradar/policies/baptist-2026-09.json | 48 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/baptist-2026-09.json | 49 | (file) | data | 2026-10-26 |     "residence": { |
| billradar/policies/baptist-2026-09.json | 50 | (file) | data | 2026-10-26 |       "page": 3, |
| billradar/policies/baptist-2026-09.json | 51 | (file) | data | 2026-10-26 |       "quote": "In Miami-Dade County" |
| billradar/policies/baptist-2026-09.json | 52 | (file) | data | 2026-10-26 |     } |
| billradar/policies/baptist-2026-09.json | 53 | (file) | data | 2026-10-26 |   } |
| billradar/policies/baptist-2026-09.json | 54 | (file) | data | 2026-10-26 | } |
| billradar/policies/federal-501r.json | 1 | (file) | data | 2026-10-26 | { |
| billradar/policies/federal-501r.json | 2 | (file) | data | 2026-10-26 |   "policy_id": "federal-501r", |
| billradar/policies/federal-501r.json | 3 | (file) | data | 2026-10-26 |   "hospital": "Any nonprofit 501(c)(3) hospital", |
| billradar/policies/federal-501r.json | 4 | (file) | data | 2026-10-26 |   "title": "26 CFR 1.501(r)-1(b)(3), application period", |
| billradar/policies/federal-501r.json | 5 | (file) | data | 2026-10-26 |   "url": "https://www.ecfr.gov/current/title-26/section-1.501(r)-1", |
| billradar/policies/federal-501r.json | 6 | (file) | data | 2026-10-26 |   "fragments": { |
| billradar/policies/federal-501r.json | 7 | (file) | data | 2026-10-26 |     "application-period": { |
| billradar/policies/federal-501r.json | 8 | (file) | data | 2026-10-26 |       "page": 1, |
| billradar/policies/federal-501r.json | 9 | (file) | data | 2026-10-26 |       "quote": "the application period begins on the date the care is provided and ends on the later of the 240th day after the date that the first post-discharge billing statement for the care is provided" |
| billradar/policies/federal-501r.json | 10 | (file) | data | 2026-10-26 |     } |
| billradar/policies/federal-501r.json | 11 | (file) | data | 2026-10-26 |   } |
| billradar/policies/federal-501r.json | 12 | (file) | data | 2026-10-26 | } |
| billradar/policies/fl-395-301.json | 1 | (file) | data | 2026-10-26 | { |
| billradar/policies/fl-395-301.json | 2 | (file) | data | 2026-10-26 |   "policy_id": "fl-395-301", |
| billradar/policies/fl-395-301.json | 3 | (file) | data | 2026-10-26 |   "hospital": "Any hospital licensed in Florida", |
| billradar/policies/fl-395-301.json | 4 | (file) | data | 2026-10-26 |   "title": "Florida Statutes 395.301, 2026", |
| billradar/policies/fl-395-301.json | 5 | (file) | data | 2026-10-26 |   "url": "https://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0300-0399/0395/Sections/0395.301.html", |
| billradar/policies/fl-395-301.json | 6 | (file) | data | 2026-10-26 |   "fragments": { |
| billradar/policies/fl-395-301.json | 7 | (file) | data | 2026-10-26 |     "itemized-7-days": { |
| billradar/policies/fl-395-301.json | 8 | (file) | data | 2026-10-26 |       "page": 1, |
| billradar/policies/fl-395-301.json | 9 | (file) | data | 2026-10-26 |       "quote": "The initial statement or bill shall be provided within 7 days after the patient's discharge or release or after a request for such statement or bill, whichever is later." |
| billradar/policies/fl-395-301.json | 10 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/fl-395-301.json | 11 | (file) | data | 2026-10-26 |     "itemized-on-request": { |
| billradar/policies/fl-395-301.json | 12 | (file) | data | 2026-10-26 |       "page": 1, |
| billradar/policies/fl-395-301.json | 13 | (file) | data | 2026-10-26 |       "quote": "Upon request, and after the patient's discharge or release from a facility, the facility must provide to the patient or to the patient's survivor or legal guardian, as appropriate, an itemized statement or a bill detailing in plain language" |
| billradar/policies/fl-395-301.json | 14 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/fl-395-301.json | 15 | (file) | data | 2026-10-26 |     "grievance-7-days": { |
| billradar/policies/fl-395-301.json | 16 | (file) | data | 2026-10-26 |       "page": 1, |
| billradar/policies/fl-395-301.json | 17 | (file) | data | 2026-10-26 |       "quote": "The facility must provide an initial response to a patient grievance within 7 business days after the patient formally files a grievance disputing all or a portion of an itemized statement or bill." |
| billradar/policies/fl-395-301.json | 26 | (file) | data | 2026-10-26 |     } |
| billradar/policies/fl-395-301.json | 27 | (file) | data | 2026-10-26 |   } |
| billradar/policies/fl-395-301.json | 28 | (file) | data | 2026-10-26 | } |
| billradar/policies/memorial-2026-05.json | 1 | (file) | data | 2026-10-26 | { |
| billradar/policies/memorial-2026-05.json | 2 | (file) | data | 2026-10-26 |   "policy_id": "memorial-2026-05", |
| billradar/policies/memorial-2026-05.json | 3 | (file) | data | 2026-10-26 |   "hospital": "Memorial Healthcare System (Memorial Regional Hospital, Hollywood FL)", |
| billradar/policies/memorial-2026-05.json | 4 | (file) | data | 2026-10-26 |   "title": "Financial Assistance Policy, Revised May 2026", |
| billradar/policies/memorial-2026-05.json | 5 | (file) | data | 2026-10-26 |   "url": "https://www.mhs.net/-/media/mhs/files/patients-and-visitors/financial-assistance/en/full-policy.pdf", |
| billradar/policies/memorial-2026-05.json | 7 | (file) | data | 2026-10-26 |   "covers_insured_balances": true, |
| billradar/policies/memorial-2026-05.json | 8 | (file) | data | 2026-10-26 |   "min_request_total": "500.00", |
| billradar/policies/memorial-2026-05.json | 9 | (file) | data | 2026-10-26 |   "liquid_assets_limit_for_free_care": "10000.00", |
| billradar/policies/memorial-2026-05.json | 10 | (file) | data | 2026-10-26 |   "income_cap_pct": 10, |
| billradar/policies/memorial-2026-05.json | 11 | (file) | data | 2026-10-26 |   "tiers": [ |
| billradar/policies/memorial-2026-05.json | 12 | (file) | data | 2026-10-26 |     {"max_fpl_pct": 200, "discount_pct": 100, "fragment": "tier-200"}, |
| billradar/policies/memorial-2026-05.json | 13 | (file) | data | 2026-10-26 |     {"max_fpl_pct": 250, "discount_pct": 90, "fragment": "scale-mrh"}, |
| billradar/policies/memorial-2026-05.json | 14 | (file) | data | 2026-10-26 |     {"max_fpl_pct": 300, "discount_pct": 85, "fragment": "scale-mrh"}, |
| billradar/policies/memorial-2026-05.json | 15 | (file) | data | 2026-10-26 |     {"max_fpl_pct": 350, "discount_pct": 83, "fragment": "scale-mrh"}, |
| billradar/policies/memorial-2026-05.json | 16 | (file) | data | 2026-10-26 |     {"max_fpl_pct": 400, "discount_pct": 83, "fragment": "scale-mrh"} |
| billradar/policies/memorial-2026-05.json | 17 | (file) | data | 2026-10-26 |   ], |
| billradar/policies/memorial-2026-05.json | 18 | (file) | data | 2026-10-26 |   "window": { |
| billradar/policies/memorial-2026-05.json | 19 | (file) | data | 2026-10-26 |     "after_service_days": 365, |
| billradar/policies/memorial-2026-05.json | 20 | (file) | data | 2026-10-26 |     "after_last_insurance_payment_months": 12, |
| billradar/policies/memorial-2026-05.json | 21 | (file) | data | 2026-10-26 |     "fragment": "window" |
| billradar/policies/memorial-2026-05.json | 22 | (file) | data | 2026-10-26 |   }, |
| billradar/policies/memorial-2026-05.json | 23 | (file) | data | 2026-10-26 |   "fragments": { |
| billradar/policies/memorial-2026-05.json | 24 | (file) | data | 2026-10-26 |     "insured-balances": { |
| billradar/policies/memorial-2026-05.json | 25 | (file) | data | 2026-10-26 |       "page": 3, |
| billradar/policies/memorial-2026-05.json | 26 | (file) | data | 2026-10-26 |       "quote": "This means all uninsured patient responsibility amounts as well as insured patient balances after insurance payment. This includes deductibles, coinsurance, copayments, and non-covered charges." |
| billradar/policies/memorial-2026-05.json | 27 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/memorial-2026-05.json | 28 | (file) | data | 2026-10-26 |     "min-request": { |
| billradar/policies/memorial-2026-05.json | 29 | (file) | data | 2026-10-26 |       "page": 2, |
| billradar/policies/memorial-2026-05.json | 30 | (file) | data | 2026-10-26 |       "quote": "The amount of the requested financial assistance must be more than $500, for all accounts combined." |
| billradar/policies/memorial-2026-05.json | 31 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/memorial-2026-05.json | 32 | (file) | data | 2026-10-26 |     "tier-200": { |
| billradar/policies/memorial-2026-05.json | 33 | (file) | data | 2026-10-26 |       "page": 3, |
| billradar/policies/memorial-2026-05.json | 34 | (file) | data | 2026-10-26 |       "quote": "has a total household income of less than or equal to 200% of the FPG" |
| billradar/policies/memorial-2026-05.json | 35 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/memorial-2026-05.json | 36 | (file) | data | 2026-10-26 |     "liquid-assets": { |
| billradar/policies/memorial-2026-05.json | 37 | (file) | data | 2026-10-26 |       "page": 3, |
| billradar/policies/memorial-2026-05.json | 38 | (file) | data | 2026-10-26 |       "quote": "The Patient or responsible party has household liquid assets less than $10,000." |
| billradar/policies/memorial-2026-05.json | 39 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/memorial-2026-05.json | 40 | (file) | data | 2026-10-26 |     "scale": { |
| billradar/policies/memorial-2026-05.json | 41 | (file) | data | 2026-10-26 |       "page": 4, |
| billradar/policies/memorial-2026-05.json | 42 | (file) | data | 2026-10-26 |       "quote": "Patient or responsible party has a total household income of between 201% and 400%" |
| billradar/policies/memorial-2026-05.json | 43 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/memorial-2026-05.json | 44 | (file) | data | 2026-10-26 |     "income-cap": { |
| billradar/policies/memorial-2026-05.json | 45 | (file) | data | 2026-10-26 |       "page": 4, |
| billradar/policies/memorial-2026-05.json | 46 | (file) | data | 2026-10-26 |       "quote": "At no point will a patient who qualifies for financial assistance be responsible for more than 10% of their annual total household income." |
| billradar/policies/memorial-2026-05.json | 47 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/memorial-2026-05.json | 48 | (file) | data | 2026-10-26 |     "prior-accounts": { |
| billradar/policies/memorial-2026-05.json | 49 | (file) | data | 2026-10-26 |       "page": 5, |
| billradar/policies/memorial-2026-05.json | 50 | (file) | data | 2026-10-26 |       "quote": "When MHS approves financial assistance for a Patient or responsible party, MHS will also consider accounts incurred within the prior twelve months." |
| billradar/policies/memorial-2026-05.json | 51 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/memorial-2026-05.json | 52 | (file) | data | 2026-10-26 |     "window": { |
| billradar/policies/memorial-2026-05.json | 53 | (file) | data | 2026-10-26 |       "page": 5, |
| billradar/policies/memorial-2026-05.json | 54 | (file) | data | 2026-10-26 |       "quote": "Patients or responsible parties can apply for financial assistance for up to one year after the date of service or twelve months after last insurance payment." |
| billradar/policies/memorial-2026-05.json | 55 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/memorial-2026-05.json | 56 | (file) | data | 2026-10-26 |     "facilities-only": { |
| billradar/policies/memorial-2026-05.json | 57 | (file) | data | 2026-10-26 |       "page": 5, |
| billradar/policies/memorial-2026-05.json | 58 | (file) | data | 2026-10-26 |       "quote": "This Financial Assistance Policy only applies to services provided by MHS at its facilities and services provided by MHS employed physicians." |
| billradar/policies/memorial-2026-05.json | 59 | (file) | data | 2026-10-26 |     }, |
| billradar/policies/memorial-2026-05.json | 60 | (file) | data | 2026-10-26 |     "scale-mrh": { |
| billradar/policies/memorial-2026-05.json | 61 | (file) | data | 2026-10-26 |       "page": 11, |
| billradar/policies/memorial-2026-05.json | 62 | (file) | data | 2026-10-26 |       "quote": "Memorial Regional Hospital BALANCES DUE FROM PATIENT INCOME AMOUNT OF DISCOUNT Up to 200% of FPG 100% Discount 201% - 250% of FPG 90% Discount 251% - 300% of FPG 85% Discount 301% - 350% of FPG 83% Discount 351% - 400% of FPG 83% Discount" |
| billradar/policies/memorial-2026-05.json | 63 | (file) | data | 2026-10-26 |     } |
| billradar/policies/memorial-2026-05.json | 64 | (file) | data | 2026-10-26 |   } |
| billradar/policies/memorial-2026-05.json | 65 | (file) | data | 2026-10-26 | } |
| billradar/policies/source.py | 4 | (module) | doc | 2026-10-26 | """ |
| billradar/policies/source.py | 6 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/policies/source.py | 8 | (module) | import | 2026-10-26 | import hashlib |
| billradar/policies/source.py | 9 | (module) | import | 2026-10-26 | import html |
| billradar/policies/source.py | 10 | (module) | import | 2026-10-26 | import re |
| billradar/policies/source.py | 11 | (module) | import | 2026-10-26 | from dataclasses import dataclass |
| billradar/policies/source.py | 12 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/policies/source.py | 14 | (module) | import | 2026-10-26 | from pypdf import PdfReader |
| billradar/policies/source.py | 16 | (module) | code | 2026-10-26 | ROOT = Path(__file__).resolve().parents[2] |
| billradar/policies/source.py | 17 | (module) | code | 2026-10-26 | CACHE = ROOT / ".cache" / "policies" |
| billradar/policies/source.py | 20 | PolicySource (class) | signature | 2026-10-26 | @dataclass(frozen=True) |
| billradar/policies/source.py | 21 | PolicySource (class) | signature | 2026-10-26 | class PolicySource: |
| billradar/policies/source.py | 22 | PolicySource (class) | field | 2026-10-26 |     policy_id: str |
| billradar/policies/source.py | 23 | PolicySource (class) | field | 2026-10-26 |     hospital: str |
| billradar/policies/source.py | 24 | PolicySource (class) | field | 2026-10-26 |     url: str |
| billradar/policies/source.py | 25 | PolicySource (class) | field | 2026-10-26 |     kind: str = "pdf"  # "pdf", "ecfr" (eCFR versioner XML) or "html" (a statute page); xml/html are one "page" |
| billradar/policies/source.py | 28 | (module) | code | 2026-10-26 | SOURCES = { |
| billradar/policies/source.py | 29 | (module) | code | 2026-10-26 |     "memorial-2026-05": PolicySource( |
| billradar/policies/source.py | 30 | (module) | code | 2026-10-26 |         "memorial-2026-05", |
| billradar/policies/source.py | 31 | (module) | string | 2026-10-26 |         "Memorial Healthcare System (Memorial Regional Hospital, Hollywood FL)", |
| billradar/policies/source.py | 32 | (module) | string | 2026-10-26 |         "https://www.mhs.net/-/media/mhs/files/patients-and-visitors/financial-assistance/en/full-policy.pdf", |
| billradar/policies/source.py | 33 | (module) | punct | 2026-10-26 |     ), |
| billradar/policies/source.py | 34 | (module) | code | 2026-10-26 |     "baptist-2026-09": PolicySource( |
| billradar/policies/source.py | 35 | (module) | code | 2026-10-26 |         "baptist-2026-09", |
| billradar/policies/source.py | 36 | (module) | string | 2026-10-26 |         "Baptist Health South Florida (Baptist Hospital of Miami)", |
| billradar/policies/source.py | 37 | (module) | string | 2026-10-26 |         "https://baptisthealth.net/-/media/FAB30007578640E2B1F902CBF6256B95.ashx", |
| billradar/policies/source.py | 38 | (module) | punct | 2026-10-26 |     ), |
| billradar/policies/source.py | 39 | (module) | code | 2026-10-26 |     "federal-501r": PolicySource( |
| billradar/policies/source.py | 40 | (module) | code | 2026-10-26 |         "federal-501r", |
| billradar/policies/source.py | 41 | (module) | string | 2026-10-26 |         "26 CFR 1.501(r)-1 (federal rules for nonprofit hospitals)", |
| billradar/policies/source.py | 42 | (module) | string | 2026-10-26 |         "https://www.ecfr.gov/api/versioner/v1/full/2026-10-01/title-26.xml?part=1&section=1.501(r)-1", |
| billradar/policies/source.py | 43 | (module) | code | 2026-10-26 |         kind="ecfr", |
| billradar/policies/source.py | 44 | (module) | punct | 2026-10-26 |     ), |
| billradar/policies/source.py | 99 | (module) | code | 2026-10-26 |     "fl-395-301": PolicySource( |
| billradar/policies/source.py | 100 | (module) | code | 2026-10-26 |         "fl-395-301", |
| billradar/policies/source.py | 101 | (module) | string | 2026-10-26 |         "Florida Statutes 395.301 (itemized statement, billing disputes)", |
| billradar/policies/source.py | 102 | (module) | string | 2026-10-26 |         "https://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0300-0399/0395/Sections/0395.301.html", |
| billradar/policies/source.py | 103 | (module) | code | 2026-10-26 |         kind="html", |
| billradar/policies/source.py | 104 | (module) | punct | 2026-10-26 |     ), |
| billradar/policies/source.py | 105 | (module) | punct | 2026-10-26 | } |
| billradar/policies/source.py | 121 | (module) | code | 2026-10-26 | FORMS = { |
| billradar/policies/source.py | 122 | (module) | code | 2026-10-26 |     "memorial-fef": ( |
| billradar/policies/source.py | 123 | (module) | string | 2026-10-26 |         "Memorial Healthcare System Financial Evaluation Form 2310-10040 (5-19)", |
| billradar/policies/source.py | 124 | (module) | string | 2026-10-26 |         "https://www.mhs.net/-/media/mhs/files/patients-and-visitors/financial-assistance/en/financial-evaluation-form-english.pdf", |
| billradar/policies/source.py | 125 | (module) | punct | 2026-10-26 |     ), |
| billradar/policies/source.py | 126 | (module) | punct | 2026-10-26 | } |
| billradar/policies/source.py | 141 | form_path | signature | 2026-10-26 | def form_path(form_id: str) -> Path: |
| billradar/policies/source.py | 142 | form_path | code | 2026-10-26 |     return CACHE.parent / "forms" / f"{form_id}.pdf" |
| billradar/policies/source.py | 145 | pdf_path | signature | 2026-10-26 | def pdf_path(policy_id: str) -> Path: |
| billradar/policies/source.py | 147 | pdf_path | code | 2026-10-26 |     return CACHE / f"{policy_id}.{ext}" |
| billradar/policies/source.py | 150 | is_cached | signature | 2026-10-26 | def is_cached(policy_id: str) -> bool: |
| billradar/policies/source.py | 151 | is_cached | code | 2026-10-26 |     return pdf_path(policy_id).exists() |
| billradar/policies/source.py | 154 | normalize | signature | 2026-10-26 | def normalize(text: str) -> str: |
| billradar/policies/source.py | 160 | compact | signature | 2026-10-26 | def compact(text: str) -> str: |
| billradar/policies/source.py | 186 | page_texts | signature | 2026-10-26 | def page_texts(policy_id: str) -> list[str]: |
| billradar/policies/source.py | 187 | page_texts | code | 2026-10-26 |     path = pdf_path(policy_id) |
| billradar/policies/source.py | 193 | sha256 | signature | 2026-10-26 | def sha256(policy_id: str) -> str: |
| billradar/policies/source.py | 194 | sha256 | code | 2026-10-26 |     return hashlib.sha256(pdf_path(policy_id).read_bytes()).hexdigest() |
| billradar/policy.py | 6 | (module) | doc | 2026-10-26 | """ |
| billradar/policy.py | 8 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/policy.py | 10 | (module) | import | 2026-10-26 | import json |
| billradar/policy.py | 11 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/policy.py | 12 | (module) | import | 2026-10-26 | from decimal import Decimal |
| billradar/policy.py | 13 | (module) | import | 2026-10-26 | from functools import cache |
| billradar/policy.py | 14 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/policy.py | 16 | (module) | import | 2026-10-26 | from billradar.policies import source |
| billradar/policy.py | 18 | (module) | code | 2026-10-26 | POLICY_DIR = Path(__file__).parent / "policies" |
| billradar/policy.py | 25 | Fragment (class) | signature | 2026-10-26 | @dataclass(frozen=True) |
| billradar/policy.py | 26 | Fragment (class) | signature | 2026-10-26 | class Fragment: |
| billradar/policy.py | 27 | Fragment (class) | field | 2026-10-26 |     policy_id: str |
| billradar/policy.py | 28 | Fragment (class) | field | 2026-10-26 |     fragment_id: str |
| billradar/policy.py | 29 | Fragment (class) | field | 2026-10-26 |     page: int |
| billradar/policy.py | 30 | Fragment (class) | field | 2026-10-26 |     quote: str |
| billradar/policy.py | 32 | Fragment.ref | signature | 2026-10-26 |     @property |
| billradar/policy.py | 33 | Fragment.ref | signature | 2026-10-26 |     def ref(self) -> str: |
| billradar/policy.py | 34 | Fragment.ref | code | 2026-10-26 |         return f"{self.policy_id}#{self.fragment_id}" |
| billradar/policy.py | 37 | Tier (class) | signature | 2026-10-26 | @dataclass(frozen=True) |
| billradar/policy.py | 38 | Tier (class) | signature | 2026-10-26 | class Tier: |
| billradar/policy.py | 39 | Tier (class) | field | 2026-10-26 |     max_fpl_pct: int |
| billradar/policy.py | 40 | Tier (class) | field | 2026-10-26 |     discount_pct: int |
| billradar/policy.py | 41 | Tier (class) | field | 2026-10-26 |     fragment: str |
| billradar/policy.py | 44 | Policy (class) | signature | 2026-10-26 | @dataclass |
| billradar/policy.py | 45 | Policy (class) | signature | 2026-10-26 | class Policy: |
| billradar/policy.py | 46 | Policy (class) | field | 2026-10-26 |     policy_id: str |
| billradar/policy.py | 47 | Policy (class) | field | 2026-10-26 |     hospital: str |
| billradar/policy.py | 48 | Policy (class) | field | 2026-10-26 |     title: str |
| billradar/policy.py | 49 | Policy (class) | field | 2026-10-26 |     url: str |
| billradar/policy.py | 50 | Policy (class) | field | 2026-10-26 |     fragments: dict[str, Fragment] |
| billradar/policy.py | 51 | Policy (class) | field | 2026-10-26 |     covers_insured_balances: bool = True |
| billradar/policy.py | 52 | Policy (class) | field | 2026-10-26 |     min_request_total: Decimal \| None = None |
| billradar/policy.py | 53 | Policy (class) | field | 2026-10-26 |     liquid_assets_limit_for_free_care: Decimal \| None = None |
| billradar/policy.py | 54 | Policy (class) | field | 2026-10-26 |     income_cap_pct: int \| None = None |
| billradar/policy.py | 56 | Policy (class) | field | 2026-10-26 |     tiers: list[Tier] = field(default_factory=list) |
| billradar/policy.py | 57 | Policy (class) | field | 2026-10-26 |     window: dict = field(default_factory=dict) |
| billradar/policy.py | 59 | Policy.tier_for | signature | 2026-10-26 |     def tier_for(self, fpl_pct: Decimal) -> Tier \| None: |
| billradar/policy.py | 64 | Policy.fragment | signature | 2026-10-26 |     def fragment(self, fragment_id: str) -> Fragment: |
| billradar/policy.py | 65 | Policy.fragment | code | 2026-10-26 |         return self.fragments[fragment_id] |
| billradar/policy.py | 68 | load | signature | 2026-10-26 | @cache |
| billradar/policy.py | 69 | load | signature | 2026-10-26 | def load(policy_id: str) -> Policy: |
| billradar/policy.py | 87 | available | signature | 2026-10-26 | def available() -> list[str]: |
| billradar/policy.py | 91 | QuoteCheck (class) | signature | 2026-10-26 | @dataclass(frozen=True) |
| billradar/policy.py | 92 | QuoteCheck (class) | signature | 2026-10-26 | class QuoteCheck: |
| billradar/policy.py | 93 | QuoteCheck (class) | field | 2026-10-26 |     ref: str |
| billradar/policy.py | 94 | QuoteCheck (class) | field | 2026-10-26 |     found: bool |
| billradar/policy.py | 95 | QuoteCheck (class) | field | 2026-10-26 |     page: int |
| billradar/policy.py | 96 | QuoteCheck (class) | field | 2026-10-26 |     found_on_page: int \| None |
| billradar/policy.py | 97 | QuoteCheck (class) | field | 2026-10-26 |     detail: str |
| billradar/policy.py | 100 | verify_fragment | signature | 2026-10-26 | def verify_fragment(frag: Fragment) -> QuoteCheck: |
| billradar/policy.py | 105 | verify_fragment | code | 2026-10-26 |     if not source.is_cached(frag.policy_id): |
| billradar/policy.py | 119 | verified | signature | 2026-10-26 | @cache |
| billradar/policy.py | 120 | verified | signature | 2026-10-26 | def verified(ref: str) -> bool: |
| billradar/policy.py | 121 | verified | code | 2026-10-26 |     policy_id, fragment_id = ref.split("#", 1) |
| billradar/policy.py | 122 | verified | code | 2026-10-26 |     return verify_fragment(load(policy_id).fragment(fragment_id)).found |
| billradar/policy_finder.py | 24 | (module) | import | 2026-10-26 | from datetime import datetime, timezone |
| billradar/policy_finder.py | 25 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/portal_job.py | 14 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/portal_job.py | 15 | (module) | import | 2026-10-26 | from datetime import date |
| billradar/prices.py | 21 | (module) | import | 2026-10-26 | from decimal import Decimal, InvalidOperation |
| billradar/prices.py | 22 | (module) | import | 2026-10-26 | from functools import cache |
| billradar/prices.py | 23 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/prices.py | 25 | (module) | import | 2026-10-26 | from billradar.policies import source |
| billradar/qa_cite.py | 138 | request_body | code | 2026-10-26 |         {"role": "developer", "content": [{"type": "input_text", "text": INSTRUCTIONS}]}, |
| billradar/qa_cite.py | 139 | request_body | code | 2026-10-26 |         {"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload, default=str)}]}, |
| billradar/reader.py | 6 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/reader.py | 8 | (module) | import | 2026-10-26 | import json |
| billradar/reader.py | 10 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/reader.py | 12 | (module) | import | 2026-10-26 | from billradar.case import Document, DocKind, Line, Source, parse_date, parse_money |
| billradar/reader.py | 13 | (module) | import | 2026-10-26 | from billradar.meta_client import MetaAPIError, MetaClient, data_url |
| billradar/reader.py | 15 | (module) | code | 2026-10-26 | MODEL = "muse-spark-1.3" |
| billradar/reader.py | 17 | (module) | code | 2026-10-26 | _s = {"type": "string"} |
| billradar/reader.py | 18 | (module) | code | 2026-10-26 | _b = {"type": "boolean"} |
| billradar/reader.py | 42 | (module) | code | 2026-10-26 |     "doc_id": _s, |
| billradar/reader.py | 43 | (module) | code | 2026-10-26 |     "kind": {"type": "string", "enum": [k.value for k in DocKind]}, |
| billradar/reader.py | 63 | (module) | code | 2026-10-26 |     "lines": {"type": "array", "items": LINE_SCHEMA}, |
| billradar/reader.py | 123 | ReadResult (class) | signature | 2026-10-26 | @dataclass |
| billradar/reader.py | 124 | ReadResult (class) | signature | 2026-10-26 | class ReadResult: |
| billradar/reader.py | 125 | ReadResult (class) | field | 2026-10-26 |     documents: list[Document] |
| billradar/reader.py | 126 | ReadResult (class) | field | 2026-10-26 |     problems: list[str] = field(default_factory=list) |
| billradar/reader.py | 127 | ReadResult (class) | field | 2026-10-26 |     usage: dict = field(default_factory=dict) |
| billradar/reader.py | 128 | ReadResult (class) | field | 2026-10-26 |     seconds: float = 0.0 |
| billradar/reader.py | 129 | ReadResult (class) | field | 2026-10-26 |     replayed: bool = True |
| billradar/reader.py | 132 | request_body | signature | 2026-10-26 | def request_body(sheets: list[tuple[str, bytes]], files: list[tuple[str, str, bytes]], |
| billradar/reader.py | 158 | (module) | code | 2026-10-26 | _MONEY = ("charges", "insurance_paid", "adjustment", "fa_discount", "patient_responsibility") |
| billradar/reader.py | 160 | (module) | code | 2026-10-26 | _DOC_DATES = ("statement_date", "service_from", "service_to", "insurance_payment_date") |
| billradar/reader.py | 163 | _money | signature | 2026-10-26 | def _money(raw: dict, key: str, where: str, problems: list[str]): |
| billradar/reader.py | 164 | _money | code | 2026-10-26 |     text = raw.get(key, "") |
| billradar/reader.py | 168 | _money | code | 2026-10-26 |     value = parse_money(text) |
| billradar/reader.py | 170 | _money | code | 2026-10-26 |         problems.append(f"{where}: {key} {text!r} is not an amount; left empty") |
| billradar/reader.py | 171 | _money | code | 2026-10-26 |     return value |
| billradar/reader.py | 192 | _date | signature | 2026-10-26 | def _date(raw: dict, key: str, where: str, problems: list[str]): |
| billradar/reader.py | 193 | _date | code | 2026-10-26 |     text = raw.get(key, "") |
| billradar/reader.py | 203 | _date | code | 2026-10-26 |         problems.append(f"{where}: {key} {text!r} is not a date; left empty") |
| billradar/reader.py | 222 | to_documents | signature | 2026-10-26 | def to_documents(payload: dict, expected: dict[str, Source]) -> tuple[list[Document], list[str]]: |
| billradar/reader.py | 224 | to_documents | code | 2026-10-26 |     problems: list[str] = [] |
| billradar/reader.py | 225 | to_documents | code | 2026-10-26 |     for raw in payload.get("documents", []): |
| billradar/reader.py | 227 | to_documents | code | 2026-10-26 |         if doc_id not in expected: |
| billradar/reader.py | 228 | to_documents | code | 2026-10-26 |             problems.append(f"model returned unknown document {doc_id!r}; ignored") |
| billradar/reader.py | 229 | to_documents | punct | 2026-10-26 |             continue |
| billradar/reader.py | 231 | to_documents | code | 2026-10-26 |             problems.append(f"model returned {doc_id} twice; second copy ignored") |
| billradar/reader.py | 232 | to_documents | punct | 2026-10-26 |             continue |
| billradar/reader.py | 248 | to_documents | code | 2026-10-26 |             member_ref=raw.get("member_ref", "").strip(), |
| billradar/reader.py | 261 | to_documents | code | 2026-10-26 |     if missing: |
| billradar/reader.py | 262 | to_documents | code | 2026-10-26 |         problems.append(f"model did not return {', '.join(missing)}") |
| billradar/reader.py | 283 | read_case | signature | 2026-10-26 | def read_case(client: MetaClient, sheets: list[tuple[str, bytes]], files: list[tuple[str, str, bytes]], |
| billradar/redact.py | 11 | (module) | doc | 2026-10-26 | """ |
| billradar/redact.py | 13 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/redact.py | 17 | (module) | import | 2026-10-26 | import re |
| billradar/redact.py | 21 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/redact.py | 22 | (module) | import | 2026-10-26 | from functools import cache |
| billradar/redact.py | 24 | (module) | import | 2026-10-26 | import numpy as np |
| billradar/redact.py | 25 | (module) | import | 2026-10-26 | from PIL import Image, ImageDraw, ImageFilter, ImageFont |
| billradar/redact.py | 29 | (module) | code | 2026-10-26 | LABELS: list[tuple[str, list[str]]] = [  # longest first inside each kind; order of kinds matters for "name" |
| billradar/redact.py | 32 | (module) | code | 2026-10-26 |     ("SSN", ["social security number", "social security", "ssn"]), |
| billradar/redact.py | 34 | (module) | code | 2026-10-26 |     ("DOB", ["date of birth", "birth date", "dob"]), |
| billradar/redact.py | 35 | (module) | code | 2026-10-26 |     ("MEMBER", ["member id", "member #", "member number", "subscriber id", "subscriber #", "policy number", |
| billradar/redact.py | 36 | (module) | code | 2026-10-26 |                 "policy #", "group number", "group #", "medical record number", "medical record", "mrn", "mr number", |
| billradar/redact.py | 37 | (module) | code | 2026-10-26 |                 "mr #", "id #", "id number"]), |
| billradar/redact.py | 41 | (module) | code | 2026-10-26 |     ("CLAIM", ["claim number", "claim #", "claim no", "claim id", "claim"]), |
| billradar/redact.py | 42 | (module) | code | 2026-10-26 |     ("PATIENT", ["patient name", "patient", "guarantor", "subscriber", "member name", "member", "name"]), |
| billradar/redact.py | 43 | (module) | code | 2026-10-26 |     ("ADDR", ["address", "street"]), |
| billradar/redact.py | 44 | (module) | code | 2026-10-26 |     ("PHONE", ["telephone", "phone", "tel"]), |
| billradar/redact.py | 45 | (module) | punct | 2026-10-26 | ] |
| billradar/redact.py | 47 | (module) | code | 2026-10-26 | PATTERNS = [ |
| billradar/redact.py | 48 | (module) | code | 2026-10-26 |     ("SSN", re.compile(r"\\b\\d{3}-\\d{2}-\\d{4}\\b")), |
| billradar/redact.py | 49 | (module) | code | 2026-10-26 |     ("PHONE", re.compile(r"\\(?\\b\\d{3}\\)?[\\s.-]?\\d{3}-\\d{4}\\b")), |
| billradar/redact.py | 64 | (module) | punct | 2026-10-26 | ] |
| billradar/redact.py | 84 | (module) | code | 2026-10-26 | SEP = re.compile(r"^[\\s:#.\\-]*") |
| billradar/redact.py | 97 | compact | signature | 2026-10-26 | def compact(text: str) -> str: |
| billradar/redact.py | 123 | Line (class) | signature | 2026-10-26 | @dataclass |
| billradar/redact.py | 124 | Line (class) | signature | 2026-10-26 | class Line: |
| billradar/redact.py | 125 | Line (class) | field | 2026-10-26 |     box: np.ndarray  # 4x2 corners |
| billradar/redact.py | 126 | Line (class) | field | 2026-10-26 |     text: str |
| billradar/redact.py | 127 | Line (class) | field | 2026-10-26 |     score: float |
| billradar/redact.py | 194 | Secret (class) | signature | 2026-10-26 | @dataclass |
| billradar/redact.py | 195 | Secret (class) | signature | 2026-10-26 | class Secret: |
| billradar/redact.py | 196 | Secret (class) | field | 2026-10-26 |     kind: str |
| billradar/redact.py | 197 | Secret (class) | field | 2026-10-26 |     value: str |
| billradar/redact.py | 198 | Secret (class) | field | 2026-10-26 |     token: str |
| billradar/redact.py | 201 | Redaction (class) | signature | 2026-10-26 | @dataclass |
| billradar/redact.py | 202 | Redaction (class) | signature | 2026-10-26 | class Redaction: |
| billradar/redact.py | 203 | Redaction (class) | field | 2026-10-26 |     image: Image.Image |
| billradar/redact.py | 204 | Redaction (class) | field | 2026-10-26 |     secrets: list[Secret] = field(default_factory=list)  # every value covered on this image |
| billradar/redact.py | 205 | Redaction (class) | field | 2026-10-26 |     covered: int = 0 |
| billradar/redact.py | 207 | Redaction.tokens | signature | 2026-10-26 |     @property |
| billradar/redact.py | 208 | Redaction.tokens | signature | 2026-10-26 |     def tokens(self) -> dict[str, str]: |
| billradar/redact.py | 209 | Redaction.tokens | code | 2026-10-26 |         return {s.token: s.value for s in self.secrets} |
| billradar/redact.py | 294 | Vault (class) | signature | 2026-10-26 | class Vault: |
| billradar/redact.py | 295 | Vault (class) | doc | 2026-10-26 |     """Value -> token, shared across all images of one case so the same account gets the same token.""" |
| billradar/redact.py | 297 | Vault.__init__ | signature | 2026-10-26 |     def __init__(self, known: list[tuple[str, str]] \| None = None, seed: dict[tuple[str, str], str] \| None = None): |
| billradar/redact.py | 299 | Vault.__init__ | code | 2026-10-26 |         self.by_value: dict[tuple[str, str], Secret] = {} |
| billradar/redact.py | 300 | Vault.__init__ | code | 2026-10-26 |         self.counts: dict[str, int] = {} |
| billradar/redact.py | 306 | Vault.__init__ | code | 2026-10-26 |             self.by_value[(kind, compact(value))] = Secret(kind, value, token) |
| billradar/redact.py | 310 | Vault.__init__ | code | 2026-10-26 |         self.seeded = dict(self.by_value) |
| billradar/redact.py | 330 | Vault.token_for_label | signature | 2026-10-26 |     def token_for_label(self, kind: str, value: str) -> Secret: |
| billradar/redact.py | 336 | Vault.token | signature | 2026-10-26 |     def token(self, kind: str, value: str) -> Secret: |
| billradar/redact.py | 340 | Vault.token | code | 2026-10-26 |         self.counts[kind] = self.counts.get(kind, 0) + 1 |
| billradar/redact.py | 363 | Vault.secrets | signature | 2026-10-26 |     @property |
| billradar/redact.py | 364 | Vault.secrets | signature | 2026-10-26 |     def secrets(self) -> list[Secret]: |
| billradar/redact.py | 365 | Vault.secrets | code | 2026-10-26 |         return list(self.by_value.values()) |
| billradar/redact.py | 380 | _by_label | code | 2026-10-26 |     for kind, labels in LABELS: |
| billradar/redact.py | 381 | _by_label | code | 2026-10-26 |         for label in labels: |
| billradar/redact.py | 384 | _by_label | punct | 2026-10-26 |                 continue |
| billradar/redact.py | 393 | _by_label | code | 2026-10-26 |             if len(compact(value)) < 3: |
| billradar/redact.py | 394 | _by_label | punct | 2026-10-26 |                 continue |
| billradar/redact.py | 396 | _by_label | code | 2026-10-26 |             if kind in WORD_KINDS: |
| billradar/redact.py | 401 | _by_label | punct | 2026-10-26 |                     continue |
| billradar/redact.py | 438 | _known_values | code | 2026-10-26 |         needle = compact(value) |
| billradar/redact.py | 510 | _everything_known | code | 2026-10-26 |     for kind, value in vault.known: |
| billradar/redact.py | 530 | _font | signature | 2026-10-26 | @cache |
| billradar/redact.py | 531 | _font | signature | 2026-10-26 | def _font(size: int): |
| billradar/redact.py | 536 | _font | punct | 2026-10-26 |         try: |
| billradar/redact.py | 538 | _font | code | 2026-10-26 |         except OSError: |
| billradar/redact.py | 684 | _cover_box | code | 2026-10-26 |     draw.rectangle(rect, fill=(250, 250, 248)) |
| billradar/redact.py | 795 | sam_copy | signature | 2026-10-26 | def sam_copy(img: Image.Image, max_side: int = 900, secrets: list[Secret] \| None = None, |
| billradar/redact.py | 796 | sam_copy | signature | 2026-10-26 |              tries: int = 4) -> Image.Image: |
| billradar/redact.py | 797 | sam_copy | doc | 2026-10-26 |     """What SAM gets: small and soft, enough to see the sheets' edges, not to read them. |
| billradar/redact.py | 798 | sam_copy | doc | 2026-10-26 |     With `secrets`, the copy is checked by OCR and blurred more until none of them can be read.""" |
| billradar/redact.py | 799 | sam_copy | code | 2026-10-26 |     small = img.convert("RGB").copy() |
| billradar/redact.py | 800 | sam_copy | code | 2026-10-26 |     small.thumbnail((max_side, max_side), Image.Resampling.LANCZOS) |
| billradar/redact.py | 801 | sam_copy | code | 2026-10-26 |     radius = max_side / 150 |
| billradar/redact.py | 802 | sam_copy | code | 2026-10-26 |     for _ in range(tries): |
| billradar/redact.py | 803 | sam_copy | code | 2026-10-26 |         soft = small.filter(ImageFilter.GaussianBlur(radius=radius)) |
| billradar/redact.py | 805 | sam_copy | code | 2026-10-26 |             return soft |
| billradar/redact.py | 806 | sam_copy | code | 2026-10-26 |         radius *= 1.6 |
| billradar/redact.py | 807 | sam_copy | string | 2026-10-26 |     raise RuntimeError("could not make the photo unreadable for SAM; not sending it") |
| billradar/redact.py | 899 | ocr | signature | 2026-10-26 | def ocr(img: Image.Image) -> list[Line]: |
| billradar/sam.py | 7 | (module) | doc | 2026-10-26 | """ |
| billradar/sam.py | 9 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/sam.py | 11 | (module) | import | 2026-10-26 | import io |
| billradar/sam.py | 12 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/sam.py | 14 | (module) | import | 2026-10-26 | import cv2 |
| billradar/sam.py | 15 | (module) | import | 2026-10-26 | import numpy as np |
| billradar/sam.py | 16 | (module) | import | 2026-10-26 | from meta_sam_parser import ( |
| billradar/sam.py | 17 | (module) | import | 2026-10-26 |     CompletedOutcome, |
| billradar/sam.py | 18 | (module) | import | 2026-10-26 |     SegmentationBoxRecord, |
| billradar/sam.py | 19 | (module) | import | 2026-10-26 |     SegmentationMaskRecord, |
| billradar/sam.py | 20 | (module) | import | 2026-10-26 |     decode_mask_to_raster, |
| billradar/sam.py | 21 | (module) | import | 2026-10-26 |     image_segmentation_format, |
| billradar/sam.py | 22 | (module) | import | 2026-10-26 | ) |
| billradar/sam.py | 23 | (module) | import | 2026-10-26 | from PIL import Image, ImageOps |
| billradar/sam.py | 25 | (module) | import | 2026-10-26 | from billradar.meta_client import MetaClient, data_url |
| billradar/sam.py | 27 | (module) | code | 2026-10-26 | PHRASE = "sheet of paper" |
| billradar/sam.py | 28 | (module) | code | 2026-10-26 | SAM_MAX_SIDE = 1600  # the copy sent to SAM; sheets are cut from the original |
| billradar/sam.py | 29 | (module) | code | 2026-10-26 | MIN_AREA_FRACTION = 0.012 |
| billradar/sam.py | 30 | (module) | code | 2026-10-26 | ASPECT_RANGE = (0.33, 3.0) |
| billradar/sam.py | 31 | (module) | code | 2026-10-26 | NMS_IOU = 0.5 |
| billradar/sam.py | 32 | (module) | code | 2026-10-26 | SHEET_COLORS = [(232, 106, 90), (214, 164, 72), (52, 160, 150), (139, 104, 196), (74, 136, 214), (232, 110, 150)] |
| billradar/sam.py | 35 | Detection (class) | signature | 2026-10-26 | @dataclass |
| billradar/sam.py | 36 | Detection (class) | signature | 2026-10-26 | class Detection: |
| billradar/sam.py | 37 | Detection (class) | field | 2026-10-26 |     object_id: str |
| billradar/sam.py | 38 | Detection (class) | field | 2026-10-26 |     box: tuple[float, float, float, float]  # left, top, right, bottom in ORIGINAL pixels, half-open |
| billradar/sam.py | 39 | Detection (class) | field | 2026-10-26 |     confidence: float \| None |
| billradar/sam.py | 40 | Detection (class) | field | 2026-10-26 |     mask: np.ndarray \| None = None  # uint8 0/1, size of the box in original pixels |
| billradar/sam.py | 42 | Detection.area | signature | 2026-10-26 |     @property |
| billradar/sam.py | 43 | Detection.area | signature | 2026-10-26 |     def area(self) -> float: |
| billradar/sam.py | 48 | Sheet (class) | signature | 2026-10-26 | @dataclass |
| billradar/sam.py | 49 | Sheet (class) | signature | 2026-10-26 | class Sheet: |
| billradar/sam.py | 50 | Sheet (class) | field | 2026-10-26 |     doc_id: str  # S1, S2 ... in reading order; the number painted on screen |
| billradar/sam.py | 51 | Sheet (class) | field | 2026-10-26 |     box: tuple[int, int, int, int] |
| billradar/sam.py | 52 | Sheet (class) | field | 2026-10-26 |     confidence: float \| None |
| billradar/sam.py | 53 | Sheet (class) | field | 2026-10-26 |     corners: list[tuple[int, int]] \| None  # 4 corners in original pixels when the mask gave them |
| billradar/sam.py | 54 | Sheet (class) | field | 2026-10-26 |     image: Image.Image  # straightened (or box-cropped) sheet from the full-size original |
| billradar/sam.py | 55 | Sheet (class) | field | 2026-10-26 |     straightened: bool |
| billradar/sam.py | 58 | SheetsResult (class) | signature | 2026-10-26 | @dataclass |
| billradar/sam.py | 59 | SheetsResult (class) | signature | 2026-10-26 | class SheetsResult: |
| billradar/sam.py | 60 | SheetsResult (class) | field | 2026-10-26 |     sheets: list[Sheet] |
| billradar/sam.py | 61 | SheetsResult (class) | field | 2026-10-26 |     dropped: list[str] = field(default_factory=list)  # why each detection was not kept |
| billradar/sam.py | 62 | SheetsResult (class) | field | 2026-10-26 |     phrase: str = PHRASE |
| billradar/sam.py | 63 | SheetsResult (class) | field | 2026-10-26 |     sent_size: tuple[int, int] = (0, 0) |
| billradar/sam.py | 64 | SheetsResult (class) | field | 2026-10-26 |     original_size: tuple[int, int] = (0, 0) |
| billradar/sam.py | 65 | SheetsResult (class) | field | 2026-10-26 |     seconds: float = 0.0 |
| billradar/sam.py | 66 | SheetsResult (class) | field | 2026-10-26 |     replayed: bool = True |
| billradar/sam.py | 69 | load_photo | signature | 2026-10-26 | def load_photo(raw: bytes) -> Image.Image: |
| billradar/sam.py | 74 | to_jpeg | signature | 2026-10-26 | def to_jpeg(img: Image.Image, max_side: int \| None = None, quality: int = 88) -> bytes: |
| billradar/sam.py | 75 | to_jpeg | code | 2026-10-26 |     if max_side and max(img.size) > max_side: |
| billradar/sam.py | 78 | to_jpeg | code | 2026-10-26 |     buf = io.BytesIO() |
| billradar/sam.py | 79 | to_jpeg | code | 2026-10-26 |     img.save(buf, format="JPEG", quality=quality) |
| billradar/sam.py | 80 | to_jpeg | code | 2026-10-26 |     return buf.getvalue() |
| billradar/sam.py | 83 | request_body | signature | 2026-10-26 | def request_body(jpeg: bytes, phrase: str = PHRASE) -> dict: |
| billradar/sam.py | 84 | request_body | code | 2026-10-26 |     return { |
| billradar/sam.py | 85 | request_body | code | 2026-10-26 |         "model": "sam-3.1", |
| billradar/sam.py | 90 | request_body | code | 2026-10-26 |                 {"type": "input_text", "text": phrase}, |
| billradar/sam.py | 91 | request_body | code | 2026-10-26 |                 {"type": "input_image", "image_url": data_url(jpeg, "image/jpeg")}, |
| billradar/sam.py | 94 | request_body | code | 2026-10-26 |         "stream": True, |
| billradar/sam.py | 95 | request_body | code | 2026-10-26 |         "metadata": {"mask_encoding": "one_bit", "include_confidence": "true"}, |
| billradar/sam.py | 96 | request_body | punct | 2026-10-26 |     } |
| billradar/sam.py | 99 | parse | signature | 2026-10-26 | def parse(text: str, scale: tuple[float, float] = (1.0, 1.0)) -> tuple[list[Detection], list[str]]: |
| billradar/sam.py | 101 | parse | code | 2026-10-26 |     parser = image_segmentation_format().create_parser() |
| billradar/sam.py | 103 | parse | code | 2026-10-26 |         parser.push(text) |
| billradar/sam.py | 104 | parse | code | 2026-10-26 |     result = parser.finish(CompletedOutcome()).result |
| billradar/sam.py | 109 | parse | code | 2026-10-26 |     for rec in result.records: |
| billradar/sam.py | 124 | parse | punct | 2026-10-26 |         try: |
| billradar/sam.py | 136 | _iou | signature | 2026-10-26 | def _iou(a, b) -> float: |
| billradar/sam.py | 138 | _iou | code | 2026-10-26 |     union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter |
| billradar/sam.py | 142 | clean | signature | 2026-10-26 | def clean(dets: list[Detection], size: tuple[int, int]) -> tuple[list[Detection], list[str]]: |
| billradar/sam.py | 159 | clean | code | 2026-10-26 |             kept.append(d) |
| billradar/sam.py | 163 | reading_order | signature | 2026-10-26 | def reading_order(dets: list[Detection]) -> list[Detection]: |
| billradar/sam.py | 164 | reading_order | code | 2026-10-26 |     if not dets: |
| billradar/sam.py | 165 | reading_order | code | 2026-10-26 |         return [] |
| billradar/sam.py | 167 | reading_order | code | 2026-10-26 |     heights = sorted(d.box[3] - d.box[1] for d in dets) |
| billradar/sam.py | 179 | reading_order | punct | 2026-10-26 |         else: |
| billradar/sam.py | 188 | _order_corners | signature | 2026-10-26 | def _order_corners(pts: np.ndarray) -> np.ndarray: |
| billradar/sam.py | 194 | corners_from_mask | signature | 2026-10-26 | def corners_from_mask(det: Detection) -> np.ndarray \| None: |
| billradar/sam.py | 197 | corners_from_mask | punct | 2026-10-26 |         return None |
| billradar/sam.py | 199 | corners_from_mask | code | 2026-10-26 |     if not contours: |
| billradar/sam.py | 200 | corners_from_mask | punct | 2026-10-26 |         return None |
| billradar/sam.py | 203 | corners_from_mask | punct | 2026-10-26 |         return None |
| billradar/sam.py | 212 | straighten | signature | 2026-10-26 | def straighten(original: np.ndarray, corners: np.ndarray) -> np.ndarray: |
| billradar/sam.py | 213 | straighten | code | 2026-10-26 |     tl, tr, br, bl = corners |
| billradar/sam.py | 221 | find_sheets | signature | 2026-10-26 | def find_sheets(client: MetaClient, photo: bytes, phrase: str = PHRASE, max_side: int = SAM_MAX_SIDE, |
| billradar/sam.py | 222 | find_sheets | signature | 2026-10-26 |                 send: Image.Image \| None = None, crop_from: Image.Image \| None = None) -> SheetsResult: |
| billradar/sam.py | 244 | _cut_sheets | code | 2026-10-26 |     sheets = [] |
| billradar/sam.py | 250 | _cut_sheets | punct | 2026-10-26 |         else: |
| billradar/sam.py | 256 | overlay | signature | 2026-10-26 | def overlay(photo: bytes, result: SheetsResult, max_side: int = 1400) -> Image.Image: |
| billradar/sam.py | 257 | overlay | code | 2026-10-26 |     img = load_photo(photo) |
| billradar/sam.py | 267 | overlay | code | 2026-10-26 |         color = SHEET_COLORS[n % len(SHEET_COLORS)] |
| billradar/sam.py | 270 | overlay | punct | 2026-10-26 |         else: |
| billradar/sam.py | 282 | overlay | code | 2026-10-26 |                     (255, 255, 255), 2, cv2.LINE_AA) |
| billradar/sam.py | 283 | overlay | code | 2026-10-26 |     return Image.fromarray(canvas) |
| billradar/sheet_checks.py | 7 | (module) | doc | 2026-10-26 | """ |
| billradar/sheet_checks.py | 9 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/sheet_checks.py | 11 | (module) | import | 2026-10-26 | import re |
| billradar/sheet_checks.py | 14 | (module) | import | 2026-10-26 | from decimal import Decimal |
| billradar/sheet_checks.py | 24 | _is_newborn_code | signature | 2026-10-26 | def _is_newborn_code(code: str) -> bool: |
| billradar/sheet_checks.py | 25 | _is_newborn_code | code | 2026-10-26 |     c = code.strip().upper() |
| billradar/sheet_checks.py | 65 | _repeats | punct | 2026-10-26 |             continue |
| billradar/sheet_checks.py | 69 | _repeats | punct | 2026-10-26 |             continue |
| billradar/sheet_checks.py | 150 | page_doubles | punct | 2026-10-26 |                     continue |
| billradar/sheet_checks.py | 166 | duplicates | signature | 2026-10-26 | def duplicates(case: Case) -> list[Finding]: |
| billradar/sheet_checks.py | 220 | _balance_credit | string | 2026-10-26 |                        detail="The balance is in your favor. Ask for a refund instead of leaving it on the account.", |
| billradar/sheet_checks.py | 242 | credits | signature | 2026-10-26 | def credits(case: Case) -> list[Finding]: |
| billradar/sheet_checks.py | 263 | two_amounts | signature | 2026-10-26 | def two_amounts(case: Case) -> list[Finding]: |
| billradar/sheet_checks.py | 269 | two_amounts | punct | 2026-10-26 |             continue |
| billradar/sheet_checks.py | 363 | baby_under_mother | signature | 2026-10-26 | def baby_under_mother(case: Case) -> list[Finding]: |
| billradar/sheet_checks.py | 449 | missing_pages | signature | 2026-10-26 | def missing_pages(case: Case) -> list[Finding]: |
| billradar/sheet_checks.py | 454 | run | signature | 2026-10-26 | def run(case: Case) -> list[Finding]: |
| billradar/submit_agent.py | 17 | (module) | doc | 2026-10-26 | """ |
| billradar/submit_agent.py | 19 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/submit_agent.py | 21 | (module) | import | 2026-10-26 | import json |
| billradar/submit_agent.py | 22 | (module) | import | 2026-10-26 | import re |
| billradar/submit_agent.py | 23 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/submit_agent.py | 28 | (module) | import | 2026-10-26 | from billradar.meta_client import MetaClient, data_url |
| billradar/tavily_client.py | 25 | (module) | import | 2026-10-26 | from datetime import datetime, timezone |
| billradar/tavily_client.py | 26 | (module) | import | 2026-10-26 | from pathlib import Path |
| billradar/tavily_client.py | 28 | (module) | import | 2026-10-26 | import requests |
| billradar/tavily_client.py | 54 | request_key | code | 2026-10-26 |     return hashlib.sha256(canon.encode()).hexdigest()[:20] |
| billradar/tavily_client.py | 135 | ReplayTransport (class) | signature | 2026-10-26 | class ReplayTransport: |
| billradar/tavily_client.py | 136 | ReplayTransport.__init__ | signature | 2026-10-26 |     def __init__(self, directory: Path = RECORDINGS): |
| billradar/tavily_client.py | 137 | ReplayTransport.__init__ | code | 2026-10-26 |         self.directory = directory |
| billradar/tavily_client.py | 152 | TavilyClient.__init__ | signature | 2026-10-26 |     def __init__(self, transport=None, record_to: Path \| None = RECORDINGS, journal: Path \| None = JOURNAL): |
| billradar/tavily_client.py | 153 | TavilyClient.__init__ | code | 2026-10-26 |         self.transport = transport or self._default_transport() |
| billradar/tavily_client.py | 154 | TavilyClient.__init__ | code | 2026-10-26 |         self.record_to = record_to |
| billradar/tavily_client.py | 155 | TavilyClient.__init__ | code | 2026-10-26 |         self.journal = journal |
| billradar/tavily_client.py | 161 | TavilyClient._default_transport | code | 2026-10-26 |         if key and os.environ.get("BILLRADAR_LIVE") == "1": |
| billradar/tavily_client.py | 162 | TavilyClient._default_transport | code | 2026-10-26 |             return LiveTransport(key) |
| billradar/tavily_client.py | 163 | TavilyClient._default_transport | code | 2026-10-26 |         return ReplayTransport() |
| billradar/tavily_client.py | 165 | TavilyClient.live | signature | 2026-10-26 |     @property |
| billradar/tavily_client.py | 166 | TavilyClient.live | signature | 2026-10-26 |     def live(self) -> bool: |
| billradar/tavily_client.py | 167 | TavilyClient.live | code | 2026-10-26 |         return isinstance(self.transport, LiveTransport) |
| billradar/verifier.py | 7 | (module) | doc | 2026-10-26 | """ |
| billradar/verifier.py | 9 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/verifier.py | 11 | (module) | import | 2026-10-26 | import json |
| billradar/verifier.py | 12 | (module) | import | 2026-10-26 | import re |
| billradar/verifier.py | 13 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/verifier.py | 15 | (module) | import | 2026-10-26 | from decimal import ROUND_HALF_UP, Decimal |
| billradar/verifier.py | 18 | (module) | import | 2026-10-26 | from billradar import fpl, policy |
| billradar/verifier.py | 19 | (module) | import | 2026-10-26 | from billradar import writer |
| billradar/verifier.py | 21 | (module) | import | 2026-10-26 | from billradar.checks import Finding, Kind, Report |
| billradar/verifier.py | 23 | (module) | import | 2026-10-26 | from billradar.meta_client import MetaClient |
| billradar/verifier.py | 24 | (module) | import | 2026-10-26 | from billradar.writer import Letter |
| billradar/verifier.py | 26 | (module) | code | 2026-10-26 | CENT = Decimal("0.01") |
| billradar/verifier.py | 27 | (module) | code | 2026-10-26 | RISKY_WORDS = ["diagnos", "treatment plan", "medical advice", "you should take", "we will send", "guarantee", |
| billradar/verifier.py | 28 | (module) | code | 2026-10-26 |                "we promise", "you will get", "lawsuit", "sue "] |
| billradar/verifier.py | 31 | _q | signature | 2026-10-26 | def _q(x: Decimal) -> Decimal: |
| billradar/verifier.py | 33 | _q | code | 2026-10-26 |     return x.quantize(CENT, rounding=ROUND_HALF_UP) |
| billradar/verifier.py | 36 | Issue (class) | signature | 2026-10-26 | @dataclass |
| billradar/verifier.py | 37 | Issue (class) | signature | 2026-10-26 | class Issue: |
| billradar/verifier.py | 38 | Issue (class) | field | 2026-10-26 |     subject: str  # "F3 #1", "letter dispute", ... |
| billradar/verifier.py | 40 | Issue (class) | field | 2026-10-26 |     what: str |
| billradar/verifier.py | 43 | Verdict (class) | signature | 2026-10-26 | @dataclass |
| billradar/verifier.py | 44 | Verdict (class) | signature | 2026-10-26 | class Verdict: |
| billradar/verifier.py | 45 | Verdict (class) | field | 2026-10-26 |     issues: list[Issue] = field(default_factory=list) |
| billradar/verifier.py | 46 | Verdict (class) | field | 2026-10-26 |     checked: int = 0 |
| billradar/verifier.py | 47 | Verdict (class) | field | 2026-10-26 |     model_notes: list[dict] = field(default_factory=list) |
| billradar/verifier.py | 50 | Verdict.ok | signature | 2026-10-26 |     @property |
| billradar/verifier.py | 51 | Verdict.ok | signature | 2026-10-26 |     def ok(self) -> bool: |
| billradar/verifier.py | 52 | Verdict.ok | code | 2026-10-26 |         return not any(i.severity == "error" for i in self.issues) |
| billradar/verifier.py | 54 | Verdict.errors_for | signature | 2026-10-26 |     def errors_for(self, subject: str) -> list[Issue]: |
| billradar/verifier.py | 58 | subject | signature | 2026-10-26 | def subject(f: Finding, n: int) -> str: |
| billradar/verifier.py | 65 | _line | signature | 2026-10-26 | def _line(case: Case, doc_id: str, line_no: int \| None): |
| billradar/verifier.py | 73 | _expect_e1 | signature | 2026-10-26 | def _expect_e1(case: Case, f: Finding) -> Decimal \| None: |
| billradar/verifier.py | 83 | _expect_e1 | punct | 2026-10-26 |             return None |
| billradar/verifier.py | 92 | _tier_pct | signature | 2026-10-26 | def _tier_pct(case: Case) -> Decimal \| None: |
| billradar/verifier.py | 94 | _tier_pct | code | 2026-10-26 |     pol = policy.load(case.policy_id) |
| billradar/verifier.py | 102 | _tier_pct | punct | 2026-10-26 |     return None |
| billradar/verifier.py | 162 | _expect_discount | signature | 2026-10-26 | def _expect_discount(case: Case, f: Finding, report: Report) -> Decimal \| None: |
| billradar/verifier.py | 163 | _expect_discount | code | 2026-10-26 |     target = next((e for e in f.evidence if e.note == "no discount"), None) |
| billradar/verifier.py | 164 | _expect_discount | code | 2026-10-26 |     if target is None: |
| billradar/verifier.py | 165 | _expect_discount | punct | 2026-10-26 |         return None |
| billradar/verifier.py | 169 | _expect_discount | punct | 2026-10-26 |         return None |
| billradar/verifier.py | 278 | _stay_deadline | code | 2026-10-26 |     options = [first + timedelta(days=240)] |
| billradar/verifier.py | 294 | _expect_deadline | signature | 2026-10-26 | def _expect_deadline(case: Case): |
| billradar/verifier.py | 315 | _names | code | 2026-10-26 |     for f in report.findings: |
| billradar/verifier.py | 445 | _deadline_issues | code | 2026-10-26 |     want = _expect_deadline(case) |
| billradar/verifier.py | 478 | _finding_issues | code | 2026-10-26 |         elif e.line_no is not None and ln is None: |
| billradar/verifier.py | 480 | _finding_issues | code | 2026-10-26 |     for ref in f.policy_refs: |
| billradar/verifier.py | 481 | _finding_issues | code | 2026-10-26 |         if not policy.verified(ref): |
| billradar/verifier.py | 486 | check_findings | signature | 2026-10-26 | def check_findings(case: Case, report: Report) -> Verdict: |
| billradar/verifier.py | 492 | check_findings | code | 2026-10-26 |     total = _q(sum((f.amount for f in report.findings if f.amount is not None), Decimal(0))) |
| billradar/verifier.py | 493 | check_findings | code | 2026-10-26 |     if total != report.total_may_come_off: |
| billradar/verifier.py | 494 | check_findings | code | 2026-10-26 |         v.issues.append(Issue("total", "error", f"total {report.total_may_come_off} but findings add up to {total}")) |
| billradar/verifier.py | 495 | check_findings | code | 2026-10-26 |     return v |
| billradar/verifier.py | 514 | _letter_errors | code | 2026-10-26 |     text = " ".join(p.text for p in letter.paragraphs) |
| billradar/verifier.py | 525 | check_letters | signature | 2026-10-26 | def check_letters(case: Case, report: Report, letters: list[Letter], v: Verdict \| None = None) -> Verdict: |
| billradar/verifier.py | 528 | check_letters | code | 2026-10-26 |     for letter in letters: |
| billradar/verifier.py | 530 | check_letters | code | 2026-10-26 |         v.checked += 1 |
| billradar/verifier.py | 532 | check_letters | code | 2026-10-26 |         if letter.dropped: |
| billradar/verifier.py | 534 | check_letters | code | 2026-10-26 |     return v |
| billradar/verifier.py | 538 | (module) | code | 2026-10-26 | MODEL = "muse-wonder-1.0" |
| billradar/verifier.py | 539 | (module) | code | 2026-10-26 | REVIEW_SCHEMA = { |
| billradar/verifier.py | 543 | (module) | code | 2026-10-26 |     "properties": {"items": {"type": "array", "items": { |
| billradar/verifier.py | 546 | (module) | code | 2026-10-26 |         "required": ["subject", "verdict", "reason"], |
| billradar/verifier.py | 547 | (module) | code | 2026-10-26 |         "properties": { |
| billradar/verifier.py | 548 | (module) | code | 2026-10-26 |             "subject": {"type": "string"}, |
| billradar/verifier.py | 549 | (module) | code | 2026-10-26 |             "verdict": {"type": "string", "enum": ["confirmed", "problem", "cannot_tell"]}, |
| billradar/verifier.py | 550 | (module) | code | 2026-10-26 |             "reason": {"type": "string"}, |
| billradar/verifier.py | 553 | (module) | punct | 2026-10-26 | } |
| billradar/verifier.py | 573 | redacted | signature | 2026-10-26 | def redacted(case: Case) -> Case: |
| billradar/verifier.py | 575 | redacted | code | 2026-10-26 |     people = [p.model_copy(update={"name": "", "birth_date": "", "employer": ""}) for p in case.profile.people] |
| billradar/verifier.py | 578 | redacted | code | 2026-10-26 |     return case.model_copy(update={"profile": profile}) |
| billradar/verifier.py | 602 | _reference | code | 2026-10-26 |     pol = policy.load(case.policy_id) |
| billradar/verifier.py | 621 | review_body | signature | 2026-10-26 | def review_body(case: Case, report: Report, letters: list[Letter]) -> dict: |
| billradar/verifier.py | 627 | review_body | code | 2026-10-26 |     payload = { |
| billradar/verifier.py | 630 | review_body | code | 2026-10-26 |         "findings": findings, |
| billradar/verifier.py | 631 | review_body | code | 2026-10-26 |         "letters": [{"subject": f"letter {x.kind}", "text": [p.text for p in x.paragraphs], "quotes": x.refs} |
| billradar/verifier.py | 633 | review_body | punct | 2026-10-26 |     } |
| billradar/verifier.py | 642 | model_review | signature | 2026-10-26 | def model_review(client: MetaClient, case: Case, report: Report, letters: list[Letter], v: Verdict) -> Verdict: |
| billradar/verifier.py | 662 | model_review | code | 2026-10-26 |     return v |
| billradar/verifier.py | 674 | verify | signature | 2026-10-26 | def verify(case: Case, report: Report, letters: list[Letter]) -> Verdict: |
| billradar/verifier.py | 675 | verify | code | 2026-10-26 |     return check_letters(case, report, letters, check_findings(case, report)) |
| billradar/verifier.py | 687 | subjects | code | 2026-10-26 |     for f in report.findings: |
| billradar/verifier.py | 688 | subjects | code | 2026-10-26 |         counts[f.kind.value] = counts.get(f.kind.value, 0) + 1 |
| billradar/verifier.py | 727 | grade | code | 2026-10-26 |     for f in report.findings: |
| billradar/video.py | 26 | (module) | import | 2026-10-26 | import cv2 |
| billradar/video.py | 27 | (module) | import | 2026-10-26 | import numpy as np |
| billradar/video.py | 28 | (module) | import | 2026-10-26 | from meta_sam_parser import ( |
| billradar/video.py | 29 | (module) | import | 2026-10-26 |     CompletedOutcome, |
| billradar/video.py | 30 | (module) | import | 2026-10-26 |     SegmentationMaskRecord, |
| billradar/video.py | 31 | (module) | import | 2026-10-26 |     decode_mask_to_raster, |
| billradar/video.py | 226 | with_masks | code | 2026-10-26 |     result = parser.finish(CompletedOutcome()).result |
| billradar/view.py | 10 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/view.py | 16 | (module) | import | 2026-10-26 | from decimal import ROUND_DOWN, Decimal |
| billradar/view.py | 19 | (module) | import | 2026-10-26 | from billradar.case import Case, Document, DocKind, Role, Source |
| billradar/view.py | 20 | (module) | import | 2026-10-26 | from billradar.checks import Finding, Kind, Report |
| billradar/view.py | 22 | (module) | code | 2026-10-26 | KIND_LABEL = { |
| billradar/view.py | 23 | (module) | code | 2026-10-26 |     DocKind.HOSPITAL_STATEMENT: "Hospital statement", |
| billradar/view.py | 24 | (module) | code | 2026-10-26 |     DocKind.ITEMIZED_BILL: "Itemized bill", |
| billradar/view.py | 25 | (module) | code | 2026-10-26 |     DocKind.EOB: "EOB", |
| billradar/view.py | 26 | (module) | code | 2026-10-26 |     DocKind.FA_LETTER: "Financial assistance letter", |
| billradar/view.py | 27 | (module) | code | 2026-10-26 |     DocKind.PAYMENT_RECEIPT: "Payment", |
| billradar/view.py | 28 | (module) | code | 2026-10-26 |     DocKind.OTHER: "Document", |
| billradar/view.py | 29 | (module) | punct | 2026-10-26 | } |
| billradar/view.py | 30 | (module) | code | 2026-10-26 | TONE = {Kind.F1: "good", Kind.F2: "time", Kind.F3: "problem", Kind.E1: "problem", Kind.E2: "problem", |
| billradar/view.py | 32 | (module) | code | 2026-10-26 | SHEET_COLORS = 6 |
| billradar/view.py | 35 | Chip (class) | signature | 2026-10-26 | @dataclass |
| billradar/view.py | 36 | Chip (class) | signature | 2026-10-26 | class Chip: |
| billradar/view.py | 37 | Chip (class) | field | 2026-10-26 |     label: str |
| billradar/view.py | 38 | Chip (class) | field | 2026-10-26 |     kind: str  # "sheet", "policy", "profile" |
| billradar/view.py | 39 | Chip (class) | field | 2026-10-26 |     color: int \| None = None  # sheet color index |
| billradar/view.py | 40 | Chip (class) | field | 2026-10-26 |     title: str = "" |
| billradar/view.py | 43 | Card (class) | signature | 2026-10-26 | @dataclass |
| billradar/view.py | 44 | Card (class) | signature | 2026-10-26 | class Card: |
| billradar/view.py | 45 | Card (class) | field | 2026-10-26 |     kind: str |
| billradar/view.py | 46 | Card (class) | field | 2026-10-26 |     tone: str |
| billradar/view.py | 47 | Card (class) | field | 2026-10-26 |     title: str |
| billradar/view.py | 48 | Card (class) | field | 2026-10-26 |     detail: str  # one or two short lines, like the picked screen |
| billradar/view.py | 49 | Card (class) | field | 2026-10-26 |     chips: list[Chip] |
| billradar/view.py | 50 | Card (class) | field | 2026-10-26 |     pill: str = "" |
| billradar/view.py | 51 | Card (class) | field | 2026-10-26 |     full: str = ""  # the whole explanation from the checks, on hover / expand |
| billradar/view.py | 54 | DocRow (class) | signature | 2026-10-26 | @dataclass |
| billradar/view.py | 55 | DocRow (class) | signature | 2026-10-26 | class DocRow: |
| billradar/view.py | 56 | DocRow (class) | field | 2026-10-26 |     doc_id: str |
| billradar/view.py | 57 | DocRow (class) | field | 2026-10-26 |     number: str |
| billradar/view.py | 58 | DocRow (class) | field | 2026-10-26 |     color: int \| None |
| billradar/view.py | 59 | DocRow (class) | field | 2026-10-26 |     label: str |
| billradar/view.py | 62 | Screen (class) | signature | 2026-10-26 | @dataclass |
| billradar/view.py | 63 | Screen (class) | signature | 2026-10-26 | class Screen: |
| billradar/view.py | 64 | Screen (class) | field | 2026-10-26 |     case_title: str |
| billradar/view.py | 65 | Screen (class) | field | 2026-10-26 |     letterhead: str |
| billradar/view.py | 66 | Screen (class) | field | 2026-10-26 |     headline: str |
| billradar/view.py | 67 | Screen (class) | field | 2026-10-26 |     subline: str |
| billradar/view.py | 68 | Screen (class) | field | 2026-10-26 |     cards: list[Card] |
| billradar/view.py | 69 | Screen (class) | field | 2026-10-26 |     quiet: list[Card] |
| billradar/view.py | 70 | Screen (class) | field | 2026-10-26 |     paper: list[DocRow] |
| billradar/view.py | 71 | Screen (class) | field | 2026-10-26 |     digital: list[DocRow] |
| billradar/view.py | 72 | Screen (class) | field | 2026-10-26 |     overlays: list[str] = field(default_factory=list) |
| billradar/view.py | 73 | Screen (class) | field | 2026-10-26 |     replayed: bool = True |
| billradar/view.py | 84 | money | signature | 2026-10-26 | def money(x: Decimal) -> str: |
| billradar/view.py | 94 | person | signature | 2026-10-26 | def person(case: Case, token: str) -> str: |
| billradar/view.py | 107 | person | code | 2026-10-26 |     return token or "—" |
| billradar/view.py | 110 | doc_label | signature | 2026-10-26 | def doc_label(case: Case, d: Document) -> str: |
| billradar/view.py | 111 | doc_label | code | 2026-10-26 |     if d.first_after_discharge and d.statement_date: |
| billradar/view.py | 113 | doc_label | code | 2026-10-26 |     parts = [KIND_LABEL[d.kind], person(case, d.patient)] |
| billradar/view.py | 123 | doc_label | code | 2026-10-26 |     return " · ".join(p for p in parts if p) |
| billradar/view.py | 126 | _policy_chip | signature | 2026-10-26 | def _policy_chip(ref: str) -> Chip: |
| billradar/view.py | 133 | _sheet | signature | 2026-10-26 | def _sheet(doc_id: str) -> str: |
| billradar/view.py | 137 | _tier_range | signature | 2026-10-26 | def _tier_range(policy_id: str, pct: Decimal) -> str: |
| billradar/view.py | 138 | _tier_range | code | 2026-10-26 |     pol = policy.load(policy_id) |
| billradar/view.py | 139 | _tier_range | code | 2026-10-26 |     tier = pol.tier_for(pct) |
| billradar/view.py | 141 | _tier_range | code | 2026-10-26 |         return "" |
| billradar/view.py | 203 | short | signature | 2026-10-26 | def short(f: Finding, case: Case, policy_id: str) -> str: |
| billradar/view.py | 236 | short | code | 2026-10-26 |     return f.detail |
| billradar/view.py | 240 | _paper_chips | code | 2026-10-26 |     chips, seen = [], set() |
| billradar/view.py | 241 | _paper_chips | code | 2026-10-26 |     for e in f.evidence: |
| billradar/view.py | 244 | _paper_chips | code | 2026-10-26 |         seen.add(e.doc_id) |
| billradar/view.py | 247 | _paper_chips | code | 2026-10-26 |             label += f" · line {e.line_no}" |
| billradar/view.py | 248 | _paper_chips | code | 2026-10-26 |         chips.append(Chip(label, "sheet", colors.get(e.doc_id), e.note)) |
| billradar/view.py | 254 | _ref_chips | code | 2026-10-26 |     for ref in f.policy_refs: |
| billradar/view.py | 273 | card | code | 2026-10-26 |     if f.kind == Kind.F1 and "fpl_pct" in f.math: |
| billradar/view.py | 290 | _case_title | code | 2026-10-26 |     mother = next((p for p in case.profile.people if p.role == Role.MOTHER), None) |
| billradar/view.py | 292 | _case_title | code | 2026-10-26 |     if any(p.role == Role.NEWBORN for p in case.profile.people): |
| billradar/view.py | 307 | build | code | 2026-10-26 |     total = report.total_may_come_off |
| billradar/view.py | 321 | build | code | 2026-10-26 |     paper_docs = [d for d in case.documents if d.source == Source.PAPER] |
| billradar/view.py | 322 | build | code | 2026-10-26 |     digital_docs = [d for d in case.documents if d.source != Source.PAPER] |
| billradar/view.py | 325 | build | code | 2026-10-26 |     if report.apply_by: |
| billradar/view.py | 333 | build | code | 2026-10-26 |     return Screen( |
| billradar/view.py | 337 | build | code | 2026-10-26 |         paper=[DocRow(d.doc_id, d.doc_id[1:], colors[d.doc_id], doc_label(case, d)) for d in paper_docs], |
| billradar/view.py | 338 | build | code | 2026-10-26 |         digital=[DocRow(d.doc_id, d.doc_id[1:], None, doc_label(case, d)) for d in digital_docs], |
| billradar/view.py | 557 | row | code | 2026-10-26 |     for ref in f.policy_refs: |
| billradar/view.py | 558 | row | code | 2026-10-26 |         c = _policy_chip(ref) |
| billradar/voice.py | 13 | (module) | doc | 2026-10-26 | """ |
| billradar/voice.py | 15 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/voice.py | 17 | (module) | import | 2026-10-26 | import json |
| billradar/voice.py | 18 | (module) | import | 2026-10-26 | import re |
| billradar/voice.py | 19 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/web/static/app.css | 2 | (file) | template | 2026-10-26 | :root { |
| billradar/web/static/app.css | 27 | (file) | template | 2026-10-26 | } |
| billradar/web/static/app.css | 29 | (file) | template | 2026-10-26 | * { box-sizing: border-box; } |
| billradar/web/static/app.css | 38 | (file) | template | 2026-10-26 | a { color: inherit; } |
| billradar/web/static/app.css | 360 | (file) | template | 2026-10-26 | .upload .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; } |
| billradar/web/static/app.css | 362 | (file) | template | 2026-10-26 | .upload .check input { width: auto; } |
| billradar/web/static/app.css | 460 | (file) | template | 2026-10-26 | .letter .meta { color: var(--muted); font-size: 14px; margin-bottom: 18px; } |
| billradar/web/static/app.css | 461 | (file) | template | 2026-10-26 | .letter h1 { font-size: 20px; margin: 18px 0 14px; } |
| billradar/web/static/app.css | 462 | (file) | template | 2026-10-26 | .letter .sig { margin-top: 28px; } |
| billradar/web/static/app.css | 463 | (file) | template | 2026-10-26 | .letter .sig .line { margin-top: 30px; border-top: 1px solid var(--ink); width: 240px; padding-top: 4px; font-size: 13px; color: var(--muted); } |
| billradar/web/static/app.css | 464 | (file) | template | 2026-10-26 | .letter .sources { margin-top: 28px; border-top: 1px dashed var(--line); padding-top: 12px; font-size: 13px; color: var(--muted); } |
| billradar/web/static/app.css | 465 | (file) | template | 2026-10-26 | .letter .sources q { color: var(--ink); } |
| billradar/web/static/app.css | 466 | (file) | template | 2026-10-26 | .letter .stamp { color: #c4573c; font-weight: 800; letter-spacing: .5px; font-size: 13px; } |
| billradar/web/static/app.css | 468 | (file) | template | 2026-10-26 | .toolbar a, .toolbar button { font: inherit; font-weight: 700; color: var(--teal-dark); background: none; border: 0; cursor: pointer; padding: 0; text-decoration: underline; } |
| billradar/web/templates/base.html | 1 | (file) | template | 2026-10-26 | <!doctype html> |
| billradar/web/templates/base.html | 2 | (file) | template | 2026-10-26 | <html lang="en"> |
| billradar/web/templates/base.html | 3 | (file) | template | 2026-10-26 | <head> |
| billradar/web/templates/base.html | 4 | (file) | template | 2026-10-26 |   <meta charset="utf-8"> |
| billradar/web/templates/base.html | 5 | (file) | template | 2026-10-26 |   <meta name="viewport" content="width=device-width, initial-scale=1"> |
| billradar/web/templates/base.html | 7 | (file) | template | 2026-10-26 |   <title>{% block title %}BillRadar{% endblock %}</title> |
| billradar/web/templates/base.html | 9 | (file) | template | 2026-10-26 |   <link rel="icon" href="/static/brand/shield.png"> |
| billradar/web/templates/base.html | 10 | (file) | template | 2026-10-26 |   <link rel="preconnect" href="https://fonts.googleapis.com"> |
| billradar/web/templates/base.html | 14 | (file) | template | 2026-10-26 | </head> |
| billradar/web/templates/base.html | 37 | (file) | template | 2026-10-26 | </body> |
| billradar/web/templates/base.html | 38 | (file) | template | 2026-10-26 | </html> |
| billradar/web/templates/case.html | 1 | (file) | template | 2026-10-26 | {% extends "base.html" %} |
| billradar/web/templates/case.html | 3 | (file) | template | 2026-10-26 | {% block title %}{{ s.case_title }} · BillRadar{% endblock %} |
| billradar/web/templates/case.html | 8 | (file) | template | 2026-10-26 | {%- endmacro %} |
| billradar/web/templates/case.html | 13 | (file) | template | 2026-10-26 | {% block body %} |
| billradar/web/templates/case.html | 61 | (file) | template | 2026-10-26 |     </div> |
| billradar/web/templates/case.html | 62 | (file) | template | 2026-10-26 |     {% if sent %} |
| billradar/web/templates/case.html | 68 | (file) | template | 2026-10-26 |     </div> |
| billradar/web/templates/case.html | 69 | (file) | template | 2026-10-26 |     {% endif %} |
| billradar/web/templates/case.html | 82 | (file) | template | 2026-10-26 |       </div> |
| billradar/web/templates/case.html | 86 | (file) | template | 2026-10-26 |       </div> |
| billradar/web/templates/case.html | 91 | (file) | template | 2026-10-26 |       </div> |
| billradar/web/templates/case.html | 92 | (file) | template | 2026-10-26 |     </div> |
| billradar/web/templates/case.html | 118 | (file) | template | 2026-10-26 |     </div> |
| billradar/web/templates/case.html | 120 | (file) | template | 2026-10-26 |     <p class="note">Estimates from the hospital's published policy. The hospital decides. |
| billradar/web/templates/case.html | 164 | (file) | template | 2026-10-26 |   </section> |
| billradar/web/templates/case.html | 175 | (file) | template | 2026-10-26 |     </div> |
| billradar/web/templates/case.html | 212 | (file) | template | 2026-10-26 |     </div> |
| billradar/web/templates/case.html | 215 | (file) | template | 2026-10-26 | </div> |
| billradar/web/templates/case.html | 252 | (file) | template | 2026-10-26 | {% endblock %} |
| billradar/web/templates/letter.html | 1 | (file) | template | 2026-10-26 | {% extends "base.html" %} |
| billradar/web/templates/letter.html | 2 | (file) | template | 2026-10-26 | {% block title %}{{ l.subject }} · BillRadar{% endblock %} |
| billradar/web/templates/letter.html | 4 | (file) | template | 2026-10-26 | {% block body %} |
| billradar/web/templates/letter.html | 35 | (file) | template | 2026-10-26 |       {% if case.demo %}<p class="stamp">SAMPLE — FICTIONAL DATA. NOT A REAL LETTER.</p>{% endif %} |
| billradar/web/templates/letter.html | 36 | (file) | template | 2026-10-26 |       <div class="meta">{{ today.strftime("%B %-d, %Y") }}<br>To: {{ l.to }}</div> |
| billradar/web/templates/letter.html | 37 | (file) | template | 2026-10-26 |       <h1>{{ l.subject }}</h1> |
| billradar/web/templates/letter.html | 40 | (file) | template | 2026-10-26 |       {% if l.attachments %}<p>Attached: {{ l.attachments\|join("; ") }}.</p>{% endif %} |
| billradar/web/templates/letter.html | 41 | (file) | template | 2026-10-26 |       <div class="sig">Sincerely,<br>{% for line in signature %}{{ line }}<br>{% endfor %} |
| billradar/web/templates/letter.html | 42 | (file) | template | 2026-10-26 |         <div class="line">Signature</div></div> |
| billradar/web/templates/letter.html | 43 | (file) | template | 2026-10-26 |       {% if sources %} |
| billradar/web/templates/letter.html | 44 | (file) | template | 2026-10-26 |       <div class="sources"><strong>Where this comes from</strong> (for you, not part of the letter) |
| billradar/web/templates/letter.html | 45 | (file) | template | 2026-10-26 |         <ul>{% for s in sources %}<li>{{ s.title }}, page {{ s.page }}: <q>{{ s.quote }}</q></li>{% endfor %}</ul> |
| billradar/web/templates/letter.html | 47 | (file) | template | 2026-10-26 |       </div>{% endif %} |
| billradar/web/templates/letter.html | 48 | (file) | template | 2026-10-26 |     </article> |
| billradar/web/templates/letter.html | 95 | (file) | template | 2026-10-26 | {% endblock %} |
| billradar/web/templates/upload.html | 1 | (file) | template | 2026-10-26 | {% extends "base.html" %} |
| billradar/web/templates/upload.html | 10 | (file) | template | 2026-10-26 | {% block body %} |
| billradar/web/templates/upload.html | 25 | (file) | template | 2026-10-26 |   <h1>Put your hospital papers in one place</h1> |
| billradar/web/templates/upload.html | 31 | (file) | template | 2026-10-26 | <form class="upload" method="post" action="/cases" enctype="multipart/form-data"> |
| billradar/web/templates/upload.html | 32 | (file) | template | 2026-10-26 |   <h1>Put your hospital papers in one place</h1> |
| billradar/web/templates/upload.html | 34 | (file) | template | 2026-10-26 |   <p>Lay the paper sheets on a table without overlap and take one photo from above. Add PDFs or screenshots from the hospital portal.{% if not live %} <span class="replay">replay mode</span>{% endif %}</p> |
| billradar/web/templates/upload.html | 46 | (file) | template | 2026-10-26 |   <label for="policy_id">Hospital policy to check against</label> |
| billradar/web/templates/upload.html | 47 | (file) | template | 2026-10-26 |   <select id="policy_id" name="policy_id"> |
| billradar/web/templates/upload.html | 49 | (file) | template | 2026-10-26 |   </select> |
| billradar/web/templates/upload.html | 52 | (file) | template | 2026-10-26 |   <div class="row"> |
| billradar/web/templates/upload.html | 55 | (file) | template | 2026-10-26 |   </div> |
| billradar/web/templates/upload.html | 56 | (file) | template | 2026-10-26 |   <div class="row"> |
| billradar/web/templates/upload.html | 59 | (file) | template | 2026-10-26 |   </div> |
| billradar/web/templates/upload.html | 68 | (file) | template | 2026-10-26 | </form> |
| billradar/web/templates/upload.html | 70 | (file) | template | 2026-10-26 | {% endblock %} |
| billradar/web_answer.py | 14 | (module) | doc | 2026-10-26 | """ |
| billradar/web_answer.py | 16 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/web_answer.py | 18 | (module) | import | 2026-10-26 | import json |
| billradar/web_answer.py | 19 | (module) | import | 2026-10-26 | import re |
| billradar/writer.py | 9 | (module) | doc | 2026-10-26 | """ |
| billradar/writer.py | 11 | (module) | import | 2026-10-26 | from __future__ import annotations |
| billradar/writer.py | 15 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| billradar/writer.py | 16 | (module) | import | 2026-10-26 | from datetime import date |
| billradar/writer.py | 17 | (module) | import | 2026-10-26 | from decimal import Decimal |
| billradar/writer.py | 25 | Paragraph (class) | signature | 2026-10-26 | @dataclass |
| billradar/writer.py | 26 | Paragraph (class) | signature | 2026-10-26 | class Paragraph: |
| billradar/writer.py | 27 | Paragraph (class) | field | 2026-10-26 |     text: str |
| billradar/writer.py | 28 | Paragraph (class) | field | 2026-10-26 |     refs: list[str] = field(default_factory=list) |
| billradar/writer.py | 31 | Letter (class) | signature | 2026-10-26 | @dataclass |
| billradar/writer.py | 32 | Letter (class) | signature | 2026-10-26 | class Letter: |
| billradar/writer.py | 33 | Letter (class) | field | 2026-10-26 |     kind: str |
| billradar/writer.py | 34 | Letter (class) | field | 2026-10-26 |     button: str |
| billradar/writer.py | 35 | Letter (class) | field | 2026-10-26 |     to: str |
| billradar/writer.py | 36 | Letter (class) | field | 2026-10-26 |     subject: str |
| billradar/writer.py | 37 | Letter (class) | field | 2026-10-26 |     paragraphs: list[Paragraph] |
| billradar/writer.py | 38 | Letter (class) | field | 2026-10-26 |     attachments: list[str] = field(default_factory=list) |
| billradar/writer.py | 39 | Letter (class) | field | 2026-10-26 |     dropped: list[str] = field(default_factory=list)  # paragraphs removed because a quote did not verify |
| billradar/writer.py | 43 | Letter.refs | signature | 2026-10-26 |     @property |
| billradar/writer.py | 44 | Letter.refs | signature | 2026-10-26 |     def refs(self) -> list[str]: |
| billradar/writer.py | 45 | Letter.refs | code | 2026-10-26 |         return [r for p in self.paragraphs for r in p.refs] |
| billradar/writer.py | 48 | _money | signature | 2026-10-26 | def _money(x) -> str: |
| billradar/writer.py | 49 | _money | code | 2026-10-26 |     return f"${x:,.2f}" |
| billradar/writer.py | 52 | _a | signature | 2026-10-26 | def _a(number: int) -> str: |
| billradar/writer.py | 57 | _date | signature | 2026-10-26 | def _date(d: date \| None) -> str: |
| billradar/writer.py | 61 | _account | signature | 2026-10-26 | def _account(case: Case, doc: Document) -> str: |
| billradar/writer.py | 65 | _name | signature | 2026-10-26 | def _name(case: Case, token: str, fallback: str) -> str: |
| billradar/writer.py | 69 | _mother | signature | 2026-10-26 | def _mother(case: Case) -> str: |
| billradar/writer.py | 73 | _billing_office | signature | 2026-10-26 | def _billing_office(case: Case) -> str: |
| billradar/writer.py | 102 | _finalize | signature | 2026-10-26 | def _finalize(letter: Letter) -> Letter: |
| billradar/writer.py | 107 | _finalize | code | 2026-10-26 |     return letter |
| billradar/writer.py | 139 | itemized_bill | signature | 2026-10-26 | def itemized_bill(case: Case) -> Letter: |
| billradar/writer.py | 141 | itemized_bill | code | 2026-10-26 |     return _finalize(Letter( |
| billradar/writer.py | 142 | itemized_bill | code | 2026-10-26 |         kind="itemized", button="Letter: request itemized bill", to=_billing_office(case), |
| billradar/writer.py | 143 | itemized_bill | code | 2026-10-26 |         subject="Request for an itemized statement", |
| billradar/writer.py | 144 | itemized_bill | code | 2026-10-26 |         paragraphs=[ |
| billradar/writer.py | 148 | itemized_bill | code | 2026-10-26 |                       ["fl-395-301#itemized-on-request", "fl-395-301#itemized-7-days"]), |
| billradar/writer.py | 149 | itemized_bill | string | 2026-10-26 |             Paragraph("Please send it to the address below. Thank you."), |
| billradar/writer.py | 150 | itemized_bill | punct | 2026-10-26 |         ])) |
| billradar/writer.py | 157 | apply_discount | signature | 2026-10-26 | def apply_discount(case: Case, report: Report) -> Letter \| None: |
| billradar/writer.py | 160 | apply_discount | punct | 2026-10-26 |         return None |
| billradar/writer.py | 161 | apply_discount | code | 2026-10-26 |     pol = policy.load(case.policy_id) |
| billradar/writer.py | 171 | apply_discount | code | 2026-10-26 |     return _finalize(Letter( |
| billradar/writer.py | 175 | apply_discount | code | 2026-10-26 |         paragraphs=[ |
| billradar/writer.py | 180 | apply_discount | string | 2026-10-26 |             Paragraph("Please send me a corrected statement. Thank you."), |
| billradar/writer.py | 186 | _window_paragraphs | code | 2026-10-26 |     window = next((f for f in report.findings if f.kind == Kind.F2), None) |
| billradar/writer.py | 197 | application | signature | 2026-10-26 | def application(case: Case, report: Report) -> Letter \| None: |
| billradar/writer.py | 199 | application | punct | 2026-10-26 |         return None |
| billradar/writer.py | 200 | application | code | 2026-10-26 |     pol = policy.load(case.policy_id) |
| billradar/writer.py | 201 | application | code | 2026-10-26 |     tier = pol.tier_for(report.fpl_pct) |
| billradar/writer.py | 202 | application | code | 2026-10-26 |     if tier is None: |
| billradar/writer.py | 203 | application | punct | 2026-10-26 |         return None |
| billradar/writer.py | 207 | application | code | 2026-10-26 |     return _finalize(Letter( |
| billradar/writer.py | 210 | application | code | 2026-10-26 |         paragraphs=[ |
| billradar/writer.py | 248 | dispute | signature | 2026-10-26 | def dispute(case: Case, report: Report) -> Letter \| None: |
| billradar/writer.py | 273 | _overcharge_paragraph | code | 2026-10-26 |     code = f" (code {line.code})" if line.code else "" |
| billradar/writer.py | 274 | _overcharge_paragraph | code | 2026-10-26 |     claim = f" for claim {line.claim_ref}" if line.claim_ref else "" |
| billradar/writer.py | 297 | _dispute | code | 2026-10-26 |     return _finalize(Letter( |
| billradar/writer.py | 307 | all_letters | signature | 2026-10-26 | def all_letters(case: Case, report: Report) -> list[Letter]: |
| billradar/writer.py | 316 | signature | signature | 2026-10-26 | def signature(case: Case) -> list[str]: |
| billradar/writer.py | 394 | appeal | code | 2026-10-26 |     return _finalize(Letter( |
| docs/BUILD-LOG.md | 1 | (file) | text | 2026-10-26 | # BillRadar build log |
| docs/BUILD-LOG.md | 3 | (file) | text | 2026-10-26 | Idea, research and logo were prepared before the hackathon. All code, screens and the demo were built October 26 – November 4. |
| docs/BUILD-LOG.md | 5 | (file) | text | 2026-10-26 | Every entry has a UTC time. What we tried and what did not work goes here too. |
| docs/BUILD-LOG.md | 7 | (file) | text | 2026-10-26 | ## 2026-10-26 (Mon) — day 1 |
| docs/BUILD-LOG.md | 9 | (file) | text | 2026-10-26 | - **15:25Z** Started the code. Python 3.12, FastAPI, Pydantic, OpenCV, pypdf. Meta Model API through our own small Responses client (next entry). |
| docs/BUILD-LOG.md | 10 | (file) | text | 2026-10-26 | - **15:31Z** `scripts/fetch_policies.py` downloads two public financial assistance policies straight from the hospitals' websites (Memorial Healthcare System, revised May 2026; Baptist Health South Florida BHSF-355.14, revised 09/29/2026) and the federal application-period rule (26 CFR 1.501(r)-1) from eCFR. The PDFs are not stored in this repo, only short quotes. |
| docs/BUILD-LOG.md | 11 | (file) | text | 2026-10-26 | - **15:31Z** Policies as data (`billradar/policies/*.json`): every rule points to a quote and a page. `policy.verify_fragment` looks for the quote on that page of the hospital's own text. 19 of 19 quotes found; a made-up quote is rejected; a real quote with the wrong page number is rejected. pdf text layers split words at random ("balan ces"), so matching ignores whitespace. |
| docs/BUILD-LOG.md | 12 | (file) | text | 2026-10-26 | - **15:31Z** Checks in code (`billradar/checks.py`): E1 bill asks more than the insurance statement, F1 qualifies but no discount, F3 discount on mom's bill but not on the baby's, F2 last day to apply, plus honest "no money here, and why" notes. A finding whose quote is not verified is held back, not shown. E1 runs first so one dollar is never counted twice. |
| docs/BUILD-LOG.md | 13 | (file) | text | 2026-10-26 |   - Found while writing: Baptist's policy is for uninsured patients only and says copays, deductibles and coinsurance are not covered. For an insured family BillRadar now says so instead of promising a discount. |
| docs/BUILD-LOG.md | 16 | (file) | text | 2026-10-26 | - **15:34Z** Meta Model API client (`billradar/meta_client.py`): Responses API over SSE, retries 429/500/503 with backoff, never retries 504 as-is, refuses `-contributor` models (they may train on what we send) and any Spark request without `store: false`. Two modes: live (only with `MODEL_API_KEY` and `BILLRADAR_LIVE=1`, every answer recorded) and replay (a missing recording is an error, not a silent fallback). Every request goes to a local journal `runs/requests.jsonl` with model, image count and size, never the images. |
| docs/BUILD-LOG.md | 17 | (file) | text | 2026-10-26 | - **15:34Z** SAM 3.1 sheet finder (`billradar/sam.py`): photo -> smaller copy -> `sheet of paper` -> boxes and masks parsed by Meta's official `meta-sam-parser` (pure Python, no network; read before adding) -> back to full-size pixels -> drop tiny, odd-shaped and duplicate objects with a written reason -> reading order S1..Sn -> straighten each sheet from its mask corners -> outline and number on the photo for the case screen. |
| docs/BUILD-LOG.md | 18 | (file) | text | 2026-10-26 |   - New since our notes from Oct 18 (read in the parser's own docs today): SAM can return a confidence per object when the request sets `include_confidence`, boxes on the wire are inclusive (the parser turns them half-open), and SAM also accepts box and point prompts, not only text. Not yet checked against the live API. |
| docs/BUILD-LOG.md | 19 | (file) | text | 2026-10-26 |   - Tests use a drawn table photo and a SAM answer written in the documented format (SYNTHETIC, `tests/synth.py`). First run caught our own bug: the test helper wrote the mask marker twice, masks failed to decode and the code quietly fell back to box crops. The straightening test failed as it should; helper fixed. 35 tests pass. |
| docs/BUILD-LOG.md | 20 | (file) | text | 2026-10-26 | - **15:36Z** Muse Spark reader (`billradar/reader.py`): all sheets and digital files in one request, strict JSON schema (`text.format`, every object closed, all keys required), stable instructions first so the prefix cache can work, `store: false`, `reasoning.effort: low` to start. Spark copies amounts and dates as printed; code parses them and leaves a field empty with a written problem when it cannot (never guesses). Unknown or duplicate documents from the model are ignored and reported; a missing one is reported. |
| docs/BUILD-LOG.md | 21 | (file) | text | 2026-10-26 | - **15:36Z** Pipeline and CLI (`billradar/pipeline.py`, `billradar/cli.py`): photos -> SAM sheets numbered across photos -> Spark case -> checks -> `runs/<pack>/` with case.json, report.json, overlays and straightened sheets. `billradar check case.json` runs the checks alone. |
| docs/BUILD-LOG.md | 23 | (file) | text | 2026-10-26 | - **15:44Z** Case screen (`billradar/app.py`, `billradar/view.py`, `billradar/web/`), built from the screen picked on Oct 18 ("case screen C2") and the logo as drawn (only cropped): headline with the total that may come off (whole dollars, rounded down so "up to" never promises more), the table photo with numbered sheets, one card per finding with chips for the sheets and the policy pages behind it, honest "checked, no money here" lines, paper and digital lists, next steps. Upload form posts photos, PDFs and the household numbers; names stay on the device, the model sees tokens. |
| docs/BUILD-LOG.md | 24 | (file) | text | 2026-10-26 |   - `scripts/demo_synthetic.py` draws five SAMPLE sheets of a fictional "Lakeview Demo Hospital" on a table and runs the whole pipeline on SYNTHETIC answers, so the screen can be worked on before the credits. The screen shows a "replay" badge whenever answers were not live. |
| docs/BUILD-LOG.md | 25 | (file) | text | 2026-10-26 |   - First screenshot was too big against the picked screen and the card texts were long paragraphs; cards now get one short line built from each finding's own numbers, with the full explanation on hover. 45 tests pass. |
| docs/BUILD-LOG.md | 26 | (file) | text | 2026-10-26 | - **15:46Z** Logo on the screen is now the full logo as drawn: the shield with the gold check next to the wordmark. Who sends the letters is not decided yet, so the screen, the upload form and the README now say only "You review and sign every letter." Screenshots are now taken from a static render opened as a file, so no dev server stays listening. |
| docs/BUILD-LOG.md | 27 | (file) | text | 2026-10-26 | - **15:52Z** Letters (`billradar/writer.py`) and the hospital's real form (`billradar/forms.py`): |
| docs/BUILD-LOG.md | 28 | (file) | text | 2026-10-26 |   - Four letters, built in code from the case and the findings: request an itemized bill, apply the discount to the baby's account, fix an amount that does not match the insurance statement, apply for financial assistance. Each letter shows "where this comes from" (the quotes behind it) on screen; that part does not print. A paragraph whose quote does not verify is dropped and reported. A test checks that every dollar amount in every letter appears in the case or the findings. |
| docs/BUILD-LOG.md | 29 | (file) | text | 2026-10-26 |   - Florida Statutes 395.301 added as a verified source (itemized statement within 7 days of the request; first answer to a billing dispute within 7 business days), fetched from leg.state.fl.us. |
| docs/BUILD-LOG.md | 30 | (file) | text | 2026-10-26 |   - Memorial's Financial Evaluation Form (2310-10040) has no form fields, so values are drawn on page 1 at the positions of its printed labels; pages 2-4 stay as they are. Demo data gets a "SAMPLE - FICTIONAL DATA" stamp on the form and on every letter. The form tells the family which fields are still theirs to write (signature, date, witness, anything we do not know). |
| docs/BUILD-LOG.md | 31 | (file) | text | 2026-10-26 |   - One wording catch while reading the letters: the baby-bill letter first said "the same 85% discount", but the code had not checked the percent actually printed on mom's bill. It now asks for "the same financial assistance" without a number. 56 tests pass; turning off the unverified-quote filter makes a test fail, as it should. |
| docs/BUILD-LOG.md | 33 | (file) | text | 2026-10-26 |   - E2 the same service billed twice (same day, same code, same price). If the insurance statement repeats the same double line, it joins the bill's finding as evidence instead of being counted a second time. |
| docs/BUILD-LOG.md | 34 | (file) | text | 2026-10-26 |   - E3 a credit or overpayment left on the account (negative lines on insurance statements are reversals, not credits). |
| docs/BUILD-LOG.md | 35 | (file) | text | 2026-10-26 |   - E4 one sheet that prints two different amounts to pay ("balance $0.00" and a coupon asking for more). |
| docs/BUILD-LOG.md | 36 | (file) | text | 2026-10-26 |   - B1 newborn care codes billed under the mother's insurance ID, with any denial codes. |
| docs/BUILD-LOG.md | 37 | (file) | text | 2026-10-26 |   - P1 "Page N of M": pages missing from a statement. |
| docs/BUILD-LOG.md | 38 | (file) | text | 2026-10-26 |   - Spark's reading schema now also asks for page numbers, the member ID, line denial codes and the coupon amount. A duplicate's extra charge is taken off before the policy discount is computed, so the same dollars are not counted twice. The dispute letter now covers duplicates too. 66 tests pass; two mutations (no cross-sheet merge, EOB reversals as credits) each fail a test. |
| docs/BUILD-LOG.md | 39 | (file) | text | 2026-10-26 | - **15:59Z** Read-only checker (`billradar/verifier.py`), the fourth role next to reader, matcher and writer: |
| docs/BUILD-LOG.md | 40 | (file) | text | 2026-10-26 |   - It recomputes every amount and date from the sheet lines and the policy along its own path (not from the finding's math), checks that every sheet and line a finding points to exists, that every quote is on its page, and that the total adds up. In letters it checks that every dollar amount comes from the case, that no token is left instead of a real value, and flags wording that sounds like medical advice or a promise. |
| docs/BUILD-LOG.md | 41 | (file) | text | 2026-10-26 |   - The pipeline holds back any finding the checker cannot confirm; the screen says how many items were re-checked. On the demo case: 7 checked, 0 problems. |
| docs/BUILD-LOG.md | 42 | (file) | text | 2026-10-26 |   - Muse Wonder review: prompt and strict schema ready, read-only (its notes never remove or edit anything). Runs on replay until the credits arrive. |
| docs/BUILD-LOG.md | 43 | (file) | text | 2026-10-26 |   - A test caught a privacy bug before any live call: the review would have sent letter texts with the family's names and real account numbers. Letters for the model are now rebuilt from a redacted copy of the case. |
| docs/BUILD-LOG.md | 44 | (file) | text | 2026-10-26 |   - "Add the deadline to my calendar": a calendar file for the last day to apply, with reminders 30 and 7 days before. 73 tests pass; making the checker trust the finding's own amount fails a test. |
| docs/BUILD-LOG.md | 45 | (file) | text | 2026-10-26 | - **16:00Z** Privacy gate, in code: live model calls run only on packs marked as fictional (`"fictional": true` in a pack's profile, or the checkbox on the upload form, which also stamps everything SAMPLE). Real papers will not go to SAM, Spark or Wonder until all three exist: names, IDs, addresses and account numbers covered on the images on the device before upload, a test that proves it, and the owner's explicit yes to sending the covered sheets. A test checks that without the fictional mark nothing leaves the machine. |
| docs/BUILD-LOG.md | 46 | (file) | text | 2026-10-26 | - **16:06Z** Measurement harness (`billradar/evaluation.py`, `scripts/eval_run.py`, `eval/README.md`): the same model on the same sheets three ways: a simple question, a strong prompt (full policy, household, our list of checks and schema, no code), and BillRadar. The strong prompt gets exactly the sheets SAM cut for BillRadar, so the comparison is about what happens after the cut. The simple path answers in free text; a judge maps it to the key and its raw answer is kept. Scored per class: found k of n, false findings, wrong amounts, found-but-no-amount, wrong deadlines. |
| docs/BUILD-LOG.md | 47 | (file) | text | 2026-10-26 |   - Held-out keys get sealed: their hashes go to `eval/SEALED.txt` before any run, and the run refuses a key that changed (formatting changes do not count). |
| docs/BUILD-LOG.md | 48 | (file) | text | 2026-10-26 |   - First version counted "found it but gave no amount" as a wrong amount; split into its own column so the table is fair to the simple path. 81 tests pass. No packs yet: fictional packs are being made, and the run needs the model credits. A run on recorded answers is labelled "REPLAYED (not a measurement)". |
| docs/BUILD-LOG.md | 49 | (file) | text | 2026-10-26 | - **16:08Z** The screen line "Names and account numbers are hidden before anything leaves this device" was not true yet, so until covering existed the screen said "Sample papers only for now" instead. |
| docs/BUILD-LOG.md | 50 | (file) | text | 2026-10-26 | - **16:14Z** On-device covering (`billradar/redact.py`), private mode in the pipeline: |
| docs/BUILD-LOG.md | 52 | (file) | text | 2026-10-26 |   - Covered: values after labels (Patient, Account, Member ID, Claim, Address, DOB, SSN, Phone), SSN and phone patterns anywhere, and names, street and account numbers the family typed in on the device. One value gets one token on every sheet ("[ACCT_1]"); a labelled name that contains a known name keeps that person's token ("[PATIENT_1]" is mom), so the model can still tell whose bill it is. Dates of service, codes and amounts stay readable. |
| docs/BUILD-LOG.md | 53 | (file) | text | 2026-10-26 |   - What SAM gets is the covered photo, small and blurred, checked by OCR and blurred more until nothing private can be read. Every cut sheet is read back by OCR before it may go to Spark; whatever the photo pass missed gets a second pass, and a sheet that still leaks is not sent at all. PDFs are not sent in private mode yet (covering PDFs is not built), and the run says so. |
| docs/BUILD-LOG.md | 54 | (file) | text | 2026-10-26 |   - Tests check both sides on SYNTHETIC sheets: every private value is readable before (so the check is not blind) and unreadable after; amounts, dates and codes still readable; a header like "Patient responsibility $2,575.10" is not mistaken for a name. End to end: names readable on what Spark gets without private mode, unreadable on everything sent with it. Turning off private mode fails the test. |
| docs/BUILD-LOG.md | 55 | (file) | text | 2026-10-26 |   - Bugs found on the way: blur on the SAM copy was too weak (text still readable on a close-up); a labelled full name got a new token instead of mom's; the cover box nicked the line above. All fixed. Not checked yet: whether SAM still finds sheets on the blurred copy (needs a live call). 88 tests pass. |
| docs/BUILD-LOG.md | 56 | (file) | text | 2026-10-26 |   - With covering on, the screen shows the picked design's line again. |
| docs/BUILD-LOG.md | 57 | (file) | text | 2026-10-26 | - **16:17Z** "What Meta's models saw" on the case screen: a switch next to the table photo. The view is built from exactly the images that left the device (the blurred photo SAM got, then every covered sheet as Spark got it), not from an intermediate step, so it cannot show a name the models never saw or hide one they did. The test reads that view back with OCR: no name is readable. |
| docs/BUILD-LOG.md | 59 | (file) | text | 2026-10-26 | ### State at the end of day 1 (16:19Z) |
| docs/BUILD-LOG.md | 61 | (file) | text | 2026-10-26 | - **Done, tested on synthetic data (89 tests):** policies as quoted data (Memorial, Baptist, federal application period, Florida 395.301); reading schema for Muse Spark; checks F1, F2, F3, E1, E2, E3, E4, B1, P1 and "no money here" notes; letters and Memorial's real form filled on the device; the read-only checker; on-device covering of private values; the case screen with "what Meta's models saw"; the measurement harness with sealed held-out keys; a privacy gate (live calls only on fictional packs). |
| docs/BUILD-LOG.md | 62 | (file) | text | 2026-10-26 | - **Not done because it needs live calls:** no Meta Model API call yet. Waiting for the hackathon credits. First live steps: SAM 3.1 on a real photo of fictional sheets (does it find each sheet; does it still find them on the blurred copy), one Spark reading (does `text.format` work as written), record both as the first real replays. |
| docs/BUILD-LOG.md | 64 | (file) | text | 2026-10-26 | - **Next after credits:** live recordings; video of the table (SAM 3.1 tracking), voice to letter (Muse Voice Transcribe); then the measurement on the held-out packs. |
| eval/README.md | 8 | (file) | text | 2026-10-26 | \|---\|---\| |
| pyproject.toml | 1 | (file) | config | 2026-10-26 | [project] |
| pyproject.toml | 3 | (file) | config | 2026-10-26 | name = "billradar" |
| pyproject.toml | 4 | (file) | config | 2026-10-26 | version = "0.1.0" |
| pyproject.toml | 5 | (file) | config | 2026-10-26 | description = "Find missed hospital financial assistance and billing errors in a family's pile of medical bills." |
| pyproject.toml | 6 | (file) | config | 2026-10-26 | readme = "README.md" |
| pyproject.toml | 7 | (file) | config | 2026-10-26 | requires-python = ">=3.12" |
| pyproject.toml | 8 | (file) | config | 2026-10-26 | dependencies = [ |
| pyproject.toml | 9 | (file) | config | 2026-10-26 |     "fastapi>=0.115", |
| pyproject.toml | 10 | (file) | config | 2026-10-26 |     "uvicorn>=0.32", |
| pyproject.toml | 11 | (file) | config | 2026-10-26 |     "python-multipart>=0.0.12", |
| pyproject.toml | 12 | (file) | config | 2026-10-26 |     "pydantic>=2.9", |
| pyproject.toml | 13 | (file) | config | 2026-10-26 |     "requests>=2.32", |
| pyproject.toml | 14 | (file) | config | 2026-10-26 |     "pillow>=11.0", |
| pyproject.toml | 15 | (file) | config | 2026-10-26 |     "numpy>=2.1", |
| pyproject.toml | 16 | (file) | config | 2026-10-26 |     "opencv-python-headless>=4.10", |
| pyproject.toml | 17 | (file) | config | 2026-10-26 |     "pypdf>=5.1", |
| pyproject.toml | 18 | (file) | config | 2026-10-26 |     "jinja2>=3.1", |
| pyproject.toml | 19 | (file) | config | 2026-10-26 |     "meta-sam-parser==0.1.0", |
| pyproject.toml | 23 | (file) | config | 2026-10-26 |     "reportlab>=4.2", |
| pyproject.toml | 25 | (file) | config | 2026-10-26 |     "pyclipper>=1.3", |
| pyproject.toml | 26 | (file) | config | 2026-10-26 |     "shapely>=2.0", |
| pyproject.toml | 27 | (file) | config | 2026-10-26 |     "pyyaml>=6.0", |
| pyproject.toml | 28 | (file) | config | 2026-10-26 |     "tqdm>=4.66", |
| pyproject.toml | 29 | (file) | config | 2026-10-26 | ] |
| pyproject.toml | 31 | (file) | config | 2026-10-26 | [project.optional-dependencies] |
| pyproject.toml | 32 | (file) | config | 2026-10-26 | dev = ["pytest>=8.3", "httpx>=0.27"] |
| pyproject.toml | 36 | (file) | config | 2026-10-26 | [project.scripts] |
| pyproject.toml | 37 | (file) | config | 2026-10-26 | billradar = "billradar.cli:main" |
| pyproject.toml | 39 | (file) | config | 2026-10-26 | [build-system] |
| pyproject.toml | 40 | (file) | config | 2026-10-26 | requires = ["hatchling"] |
| pyproject.toml | 41 | (file) | config | 2026-10-26 | build-backend = "hatchling.build" |
| pyproject.toml | 43 | (file) | config | 2026-10-26 | [tool.hatch.build.targets.wheel] |
| pyproject.toml | 44 | (file) | config | 2026-10-26 | packages = ["billradar"] |
| pyproject.toml | 46 | (file) | config | 2026-10-26 | [tool.pytest.ini_options] |
| pyproject.toml | 47 | (file) | config | 2026-10-26 | testpaths = ["tests"] |
| pyproject.toml | 48 | (file) | config | 2026-10-26 | markers = ["policy_text: needs policy PDFs downloaded by scripts/fetch_policies.py"] |
| samples/gen/build.py | 14 | (module) | import | 2026-10-26 | from __future__ import annotations |
| samples/gen/build.py | 16 | (module) | import | 2026-10-26 | import argparse |
| samples/gen/build.py | 17 | (module) | import | 2026-10-26 | import json |
| samples/gen/doc_c.py | 11 | (module) | import | 2026-10-26 | from __future__ import annotations |
| samples/gen/doc_c.py | 13 | (module) | import | 2026-10-26 | from dataclasses import dataclass, field |
| scripts/demo_price.py | 15 | (module) | import | 2026-10-26 | from datetime import date |
| scripts/demo_price.py | 16 | (module) | import | 2026-10-26 | from decimal import Decimal |
| scripts/demo_price.py | 17 | (module) | import | 2026-10-26 | from pathlib import Path |
| scripts/demo_price.py | 19 | (module) | code | 2026-10-26 | ROOT = Path(__file__).resolve().parents[1] |
| scripts/demo_price.py | 20 | (module) | code | 2026-10-26 | sys.path.insert(0, str(ROOT)) |
| scripts/demo_synthetic.py | 3 | (module) | import | 2026-10-26 | from __future__ import annotations |
| scripts/demo_synthetic.py | 5 | (module) | import | 2026-10-26 | import sys |
| scripts/demo_synthetic.py | 6 | (module) | import | 2026-10-26 | from pathlib import Path |
| scripts/demo_synthetic.py | 8 | (module) | code | 2026-10-26 | ROOT = Path(__file__).resolve().parents[1] |
| scripts/demo_synthetic.py | 9 | (module) | code | 2026-10-26 | sys.path.insert(0, str(ROOT)) |
| scripts/demo_synthetic.py | 14 | main | signature | 2026-10-26 | def main() -> None: |
| scripts/demo_synthetic.py | 16 | main | code | 2026-10-26 |     out = ROOT / "runs" / "demo-synthetic" |
| scripts/demo_synthetic.py | 17 | main | code | 2026-10-26 |     pipeline.save(run, out) |
| scripts/demo_synthetic.py | 18 | main | code | 2026-10-26 |     print(f"saved {out}: {len(run.sheets)} sheets, total ${run.report.total_may_come_off}, problems: {run.problems}") |
| scripts/demo_synthetic.py | 21 | (module) | code | 2026-10-26 | if __name__ == "__main__": |
| scripts/demo_synthetic.py | 22 | (module) | code | 2026-10-26 |     main() |
| scripts/eval_run.py | 3 | (module) | import | 2026-10-26 | from __future__ import annotations |
| scripts/eval_run.py | 5 | (module) | import | 2026-10-26 | import io |
| scripts/eval_run.py | 6 | (module) | import | 2026-10-26 | import json |
| scripts/eval_run.py | 9 | (module) | import | 2026-10-26 | import sys |
| scripts/eval_run.py | 11 | (module) | import | 2026-10-26 | from datetime import date, datetime, timezone |
| scripts/eval_run.py | 12 | (module) | import | 2026-10-26 | from pathlib import Path |
| scripts/eval_run.py | 14 | (module) | code | 2026-10-26 | ROOT = Path(__file__).resolve().parents[1] |
| scripts/eval_run.py | 15 | (module) | code | 2026-10-26 | sys.path.insert(0, str(ROOT)) |
| scripts/eval_run.py | 17 | (module) | import | 2026-10-26 | from billradar import evaluation as ev  # noqa: E402 |
| scripts/eval_run.py | 19 | (module) | import | 2026-10-26 | from billradar.case import Profile  # noqa: E402 |
| scripts/eval_run.py | 20 | (module) | import | 2026-10-26 | from billradar.meta_client import MetaClient  # noqa: E402 |
| scripts/eval_run.py | 22 | (module) | code | 2026-10-26 | PACKS = ROOT / "eval" / "packs" |
| scripts/eval_run.py | 23 | (module) | code | 2026-10-26 | LEDGER = ROOT / "eval" / "SEALED.txt" |
| scripts/eval_run.py | 29 | jpeg | signature | 2026-10-26 | def jpeg(img) -> bytes: |
| scripts/eval_run.py | 30 | jpeg | code | 2026-10-26 |     buf = io.BytesIO() |
| scripts/eval_run.py | 31 | jpeg | code | 2026-10-26 |     img.save(buf, format="JPEG", quality=88) |
| scripts/eval_run.py | 32 | jpeg | code | 2026-10-26 |     return buf.getvalue() |
| scripts/eval_run.py | 102 | run_pack | signature | 2026-10-26 | def run_pack(client: MetaClient, pack: Path, out: Path) -> dict[str, ev.Score]: |
| scripts/eval_run.py | 103 | run_pack | code | 2026-10-26 |     meta = json.loads((pack / "profile.json").read_text()) |
| scripts/eval_run.py | 104 | run_pack | code | 2026-10-26 |     key = ev.Key.model_validate_json((pack / "key.json").read_text()) |
| scripts/eval_run.py | 106 | run_pack | code | 2026-10-26 |     profile = Profile.model_validate(meta["profile"]) |
| scripts/eval_run.py | 107 | run_pack | code | 2026-10-26 |     out.mkdir(parents=True, exist_ok=True) |
| scripts/eval_run.py | 110 | run_pack | code | 2026-10-26 |         run = pipeline.run(client, photos, pdfs, profile, meta["policy_id"], meta.get("letterhead", ""), |
| scripts/eval_run.py | 113 | run_pack | code | 2026-10-26 |         pipeline.save(run, out / "billradar") |
| scripts/eval_run.py | 155 | _markdown | code | 2026-10-26 |     mode = "live" if client.live else "REPLAYED (not a measurement)" |
| scripts/eval_run.py | 162 | _seal_split | code | 2026-10-26 |         print(line) |
| scripts/eval_run.py | 163 | _seal_split | code | 2026-10-26 |     return 0 |
| scripts/eval_run.py | 170 | _measure | code | 2026-10-26 |     for pack in packs: |
| scripts/eval_run.py | 198 | _run_split | code | 2026-10-26 |     print(report) |
| scripts/eval_run.py | 199 | _run_split | code | 2026-10-26 |     return 0 |
| scripts/eval_run.py | 202 | main | signature | 2026-10-26 | def main(argv: list[str]) -> int: |
| scripts/eval_run.py | 207 | (module) | code | 2026-10-26 | if __name__ == "__main__": |
| scripts/eval_run.py | 208 | (module) | code | 2026-10-26 |     sys.exit(main(sys.argv[1:])) |
| scripts/fetch_policies.py | 3 | (module) | import | 2026-10-26 | from __future__ import annotations |
| scripts/fetch_policies.py | 5 | (module) | import | 2026-10-26 | import sys |
| scripts/fetch_policies.py | 7 | (module) | import | 2026-10-26 | import requests |
| scripts/fetch_policies.py | 9 | (module) | import | 2026-10-26 | from billradar.policies.source import CACHE, FORMS, SOURCES, form_path, page_texts, pdf_path, sha256 |
| scripts/fetch_policies.py | 11 | (module) | string | 2026-10-26 | HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) BillRadar policy fetch"} |
| scripts/fetch_policies.py | 49 | main | signature | 2026-10-26 | def main() -> int: |
| scripts/fetch_policies.py | 50 | main | code | 2026-10-26 |     CACHE.mkdir(parents=True, exist_ok=True) |
| scripts/fetch_policies.py | 58 | (module) | code | 2026-10-26 | if __name__ == "__main__": |
| scripts/fetch_policies.py | 59 | (module) | code | 2026-10-26 |     sys.exit(main()) |
| scripts/fetch_prices.py | 60 | main | code | 2026-10-26 |     print(f"errors: {failed}") |
| scripts/fetch_prices.py | 61 | main | code | 2026-10-26 |     return 1 if failed else 0 |
| scripts/fetch_prices.py | 64 | (module) | code | 2026-10-26 | if __name__ == "__main__": |
| scripts/live_smoke.py | 18 | (module) | import | 2026-10-26 | from datetime import date |
| scripts/live_smoke.py | 19 | (module) | import | 2026-10-26 | from pathlib import Path |
| scripts/live_smoke.py | 23 | (module) | code | 2026-10-26 | ROOT = Path(__file__).resolve().parents[1] |
| scripts/live_smoke.py | 24 | (module) | code | 2026-10-26 | sys.path.insert(0, str(ROOT)) |
| scripts/money_table.py | 4 | (module) | doc | 2026-10-26 | """ |
| scripts/money_table.py | 6 | (module) | import | 2026-10-26 | from __future__ import annotations |
| scripts/money_table.py | 8 | (module) | import | 2026-10-26 | import sys |
| scripts/money_table.py | 9 | (module) | import | 2026-10-26 | from pathlib import Path |
| scripts/record_example.py | 20 | (module) | code | 2026-10-26 | ROOT = Path(__file__).resolve().parents[1] |
| scripts/record_example.py | 21 | (module) | code | 2026-10-26 | sys.path.insert(0, str(ROOT)) |
| scripts/record_video.py | 15 | (module) | code | 2026-10-26 | ROOT = Path(__file__).resolve().parents[1] |
| scripts/record_video.py | 16 | (module) | code | 2026-10-26 | sys.path.insert(0, str(ROOT)) |
| scripts/replay_pack.py | 11 | (module) | import | 2026-10-26 | from __future__ import annotations |
| scripts/replay_pack.py | 13 | (module) | import | 2026-10-26 | import argparse |
| scripts/replay_pack.py | 17 | (module) | code | 2026-10-26 | ROOT = Path(__file__).resolve().parents[1] |
| scripts/replay_pack.py | 18 | (module) | code | 2026-10-26 | sys.path.insert(0, str(ROOT)) |
| scripts/replay_pack.py | 20 | (module) | import | 2026-10-26 | from billradar import evaluation as ev  # noqa: E402 |
| scripts/replay_pack.py | 34 | main | code | 2026-10-26 |     key = ev.Key.model_validate_json((pack / "key.json").read_text()) |
| tests/fixtures/cases/anna-birth.json | 1 | (file) | data | 2026-10-26 | { |
| tests/fixtures/cases/anna-birth.json | 2 | (file) | data | 2026-10-26 |   "_note": "SYNTHETIC. Fictional family and fictional hospital letterhead. Checked against Memorial's public policy.", |
| tests/fixtures/cases/anna-birth.json | 3 | (file) | data | 2026-10-26 |   "case_id": "anna-birth", |
| tests/fixtures/cases/anna-birth.json | 4 | (file) | data | 2026-10-26 |   "letterhead": "Lakeview Demo Hospital", |
| tests/fixtures/cases/anna-birth.json | 5 | (file) | data | 2026-10-26 |   "policy_id": "memorial-2026-05", |
| tests/fixtures/cases/anna-birth.json | 7 | (file) | data | 2026-10-26 |   "profile": { |
| tests/fixtures/cases/anna-birth.json | 8 | (file) | data | 2026-10-26 |     "household_size": 4, |
| tests/fixtures/cases/anna-birth.json | 9 | (file) | data | 2026-10-26 |     "annual_income": "85000", |
| tests/fixtures/cases/anna-birth.json | 10 | (file) | data | 2026-10-26 |     "liquid_assets": "6000", |
| tests/fixtures/cases/anna-birth.json | 11 | (file) | data | 2026-10-26 |     "insured": true, |
| tests/fixtures/cases/anna-birth.json | 12 | (file) | data | 2026-10-26 |     "people": [ |
| tests/fixtures/cases/anna-birth.json | 13 | (file) | data | 2026-10-26 |       {"token": "PATIENT_1", "role": "mother"}, |
| tests/fixtures/cases/anna-birth.json | 14 | (file) | data | 2026-10-26 |       {"token": "PATIENT_2", "role": "newborn"} |
| tests/fixtures/cases/anna-birth.json | 15 | (file) | data | 2026-10-26 |     ] |
| tests/fixtures/cases/anna-birth.json | 16 | (file) | data | 2026-10-26 |   }, |
| tests/fixtures/cases/anna-birth.json | 17 | (file) | data | 2026-10-26 |   "documents": [ |
| tests/fixtures/cases/anna-birth.json | 18 | (file) | data | 2026-10-26 |     { |
| tests/fixtures/cases/anna-birth.json | 19 | (file) | data | 2026-10-26 |       "doc_id": "S1", "source": "paper", "kind": "hospital_statement", "patient": "PATIENT_1", |
| tests/fixtures/cases/anna-birth.json | 20 | (file) | data | 2026-10-26 |       "provider": "Lakeview Demo Hospital", "account_ref": "[ACCT_1]", |
| tests/fixtures/cases/anna-birth.json | 23 | (file) | data | 2026-10-26 |       "lines": [ |
| tests/fixtures/cases/anna-birth.json | 26 | (file) | data | 2026-10-26 |       ] |
| tests/fixtures/cases/anna-birth.json | 27 | (file) | data | 2026-10-26 |     }, |
| tests/fixtures/cases/anna-birth.json | 28 | (file) | data | 2026-10-26 |     { |
| tests/fixtures/cases/anna-birth.json | 29 | (file) | data | 2026-10-26 |       "doc_id": "S2", "source": "paper", "kind": "hospital_statement", "patient": "PATIENT_2", |
| tests/fixtures/cases/anna-birth.json | 30 | (file) | data | 2026-10-26 |       "provider": "Lakeview Demo Hospital", "account_ref": "[ACCT_2]", |
| tests/fixtures/cases/anna-birth.json | 32 | (file) | data | 2026-10-26 |       "total_charges": "6200.00", "insurance_paid": "4960.00", "patient_balance": "1240.00", |
| tests/fixtures/cases/anna-birth.json | 33 | (file) | data | 2026-10-26 |       "lines": [ |
| tests/fixtures/cases/anna-birth.json | 35 | (file) | data | 2026-10-26 |       ] |
| tests/fixtures/cases/anna-birth.json | 36 | (file) | data | 2026-10-26 |     }, |
| tests/fixtures/cases/anna-birth.json | 37 | (file) | data | 2026-10-26 |     { |
| tests/fixtures/cases/anna-birth.json | 38 | (file) | data | 2026-10-26 |       "doc_id": "S3", "source": "paper", "kind": "hospital_statement", "patient": "PATIENT_1", |
| tests/fixtures/cases/anna-birth.json | 39 | (file) | data | 2026-10-26 |       "provider": "Lakeview Demo Hospital", "account_ref": "[ACCT_1]", |
| tests/fixtures/cases/anna-birth.json | 41 | (file) | data | 2026-10-26 |       "first_after_discharge": true, "lines": [] |
| tests/fixtures/cases/anna-birth.json | 42 | (file) | data | 2026-10-26 |     }, |
| tests/fixtures/cases/anna-birth.json | 43 | (file) | data | 2026-10-26 |     { |
| tests/fixtures/cases/anna-birth.json | 44 | (file) | data | 2026-10-26 |       "doc_id": "S4", "source": "paper", "kind": "eob", "patient": "PATIENT_1", "provider": "Sample Health Plan", |
| tests/fixtures/cases/anna-birth.json | 46 | (file) | data | 2026-10-26 |       "lines": [ |
| tests/fixtures/cases/anna-birth.json | 49 | (file) | data | 2026-10-26 |       ] |
| tests/fixtures/cases/anna-birth.json | 50 | (file) | data | 2026-10-26 |     }, |
| tests/fixtures/cases/anna-birth.json | 51 | (file) | data | 2026-10-26 |     { |
| tests/fixtures/cases/anna-birth.json | 52 | (file) | data | 2026-10-26 |       "doc_id": "S6", "source": "paper", "kind": "eob", "patient": "PATIENT_2", "provider": "Sample Health Plan", |
| tests/fixtures/cases/anna-birth.json | 54 | (file) | data | 2026-10-26 |       "lines": [ |
| tests/fixtures/cases/anna-birth.json | 56 | (file) | data | 2026-10-26 |       ] |
| tests/fixtures/cases/anna-birth.json | 57 | (file) | data | 2026-10-26 |     } |
| tests/fixtures/cases/anna-birth.json | 58 | (file) | data | 2026-10-26 |   ] |
| tests/fixtures/cases/anna-birth.json | 59 | (file) | data | 2026-10-26 | } |
| tests/fixtures/cases/sample-appeal.json | 4 | (file) | data | 2026-10-26 |   "letterhead": "Lakeview Demo Hospital", |
| tests/fixtures/cases/sample-appeal.json | 5 | (file) | data | 2026-10-26 |   "policy_id": "memorial-2026-05", |
| tests/fixtures/cases/sample-appeal.json | 11 | (file) | data | 2026-10-26 |     "insured": true, |
| tests/fixtures/cases/sample-appeal.json | 12 | (file) | data | 2026-10-26 |     "people": [ |
| tests/fixtures/cases/sample-appeal.json | 13 | (file) | data | 2026-10-26 |       {"token": "PATIENT_1", "role": "mother"}, |
| tests/fixtures/cases/sample-appeal.json | 14 | (file) | data | 2026-10-26 |       {"token": "PATIENT_2", "role": "newborn"} |
| tests/fixtures/cases/sample-appeal.json | 15 | (file) | data | 2026-10-26 |     ] |
| tests/fixtures/cases/sample-appeal.json | 16 | (file) | data | 2026-10-26 |   }, |
| tests/fixtures/cases/sample-appeal.json | 17 | (file) | data | 2026-10-26 |   "documents": [ |
| tests/fixtures/cases/sample-appeal.json | 18 | (file) | data | 2026-10-26 |     { |
| tests/reading.py | 6 | (module) | import | 2026-10-26 | from PIL import Image, ImageDraw, ImageFont |
| tests/reading.py | 8 | (module) | import | 2026-10-26 | from billradar import redact |
| tests/synth.py | 3 | (module) | import | 2026-10-26 | from __future__ import annotations |
| tests/synth.py | 5 | (module) | import | 2026-10-26 | import base64 |
| tests/synth.py | 6 | (module) | import | 2026-10-26 | import io |
| tests/synth.py | 8 | (module) | import | 2026-10-26 | import cv2 |
| tests/synth.py | 9 | (module) | import | 2026-10-26 | import numpy as np |
| tests/synth.py | 10 | (module) | import | 2026-10-26 | from meta_sam_parser import SegmentationMask, decode_mask_to_raster |
| tests/synth.py | 11 | (module) | import | 2026-10-26 | from meta_sam_parser._mask_codec import _encode_raster  # test-only |
| tests/synth.py | 12 | (module) | import | 2026-10-26 | from PIL import Image |
| tests/synth.py | 20 | sheet_quad | signature | 2026-10-26 | def sheet_quad(cx: float, cy: float, w: float, h: float, angle_deg: float) -> np.ndarray: |
| tests/synth.py | 32 | table_photo | signature | 2026-10-26 | def table_photo(quads: list[np.ndarray], size=(2400, 1800)) -> bytes: |
| tests/synth.py | 49 | encode_mask | signature | 2026-10-26 | def encode_mask(raster: np.ndarray) -> str: |
| tests/synth.py | 56 | encode_mask | code | 2026-10-26 |     return payload |
| tests/synth.py | 59 | record | signature | 2026-10-26 | def record(obj_id: int, quad: np.ndarray, frame: tuple[int, int], mask_scale: float = 0.25, c: float \| None = 0.9) -> str: |
| tests/synth.py | 74 | sam_events | signature | 2026-10-26 | def sam_events(text: str, completed: bool = True) -> list[dict]: |
| tests/synth.py | 77 | sam_events | code | 2026-10-26 |     if completed: |
| tests/synth.py | 82 | sent_size | signature | 2026-10-26 | def sent_size(body: dict) -> tuple[int, int]: |
| tests/synth.py | 84 | sent_size | code | 2026-10-26 |     url = body["input"][0]["content"][1]["image_url"] |
| tests/synth.py | 89 | FakeSAM (class) | signature | 2026-10-26 | class FakeSAM: |
| tests/synth.py | 90 | FakeSAM (class) | doc | 2026-10-26 |     """Answers like SAM would for quads drawn on the ORIGINAL photo, scaled to what was sent.""" |
| tests/synth.py | 92 | FakeSAM.__init__ | signature | 2026-10-26 |     def __init__(self, quads: list[np.ndarray], original: tuple[int, int], extra: list[str] \| None = None, |
| tests/synth.py | 93 | FakeSAM.__init__ | signature | 2026-10-26 |                  completed: bool = True): |
| tests/synth.py | 98 | FakeSAM.__init__ | code | 2026-10-26 |         self.bodies: list[dict] = [] |
| tests/synth.py | 100 | FakeSAM.events | signature | 2026-10-26 |     def events(self, body: dict) -> list[dict]: |
| tests/synth.py | 101 | FakeSAM.events | code | 2026-10-26 |         self.bodies.append(body) |
| tests/test_app.py | 1 | (module) | import | 2026-10-26 | import html as htmllib |
| tests/test_app.py | 2 | (module) | import | 2026-10-26 | import re |
| tests/test_app.py | 3 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_app.py | 5 | (module) | import | 2026-10-26 | import pytest |
| tests/test_app.py | 6 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_app.py | 8 | (module) | import | 2026-10-26 | from billradar import app as app_module |
| tests/test_app.py | 9 | (module) | import | 2026-10-26 | from billradar import pipeline |
| tests/test_app.py | 10 | (module) | import | 2026-10-26 | from billradar.meta_client import MetaClient |
| tests/test_app.py | 11 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_app.py | 12 | (module) | import | 2026-10-26 | from tests.synth import FakeSAM, table_photo |
| tests/test_app.py | 13 | (module) | import | 2026-10-26 | from tests.test_pipeline import FakeMeta, profile, spark_payload_from_fixture |
| tests/test_app.py | 14 | (module) | import | 2026-10-26 | from tests.test_sam import QUADS, SIZE |
| tests/test_app.py | 19 | fake_client | signature | 2026-10-26 | def fake_client(): |
| tests/test_app.py | 25 | client | signature | 2026-10-26 | @pytest.fixture |
| tests/test_app.py | 26 | client | signature | 2026-10-26 | def client(tmp_path, monkeypatch): |
| tests/test_app.py | 28 | client | code | 2026-10-26 |     return TestClient(app_module.app) |
| tests/test_app.py | 31 | test_case_screen_shows_findings_with_their_evidence | signature | 2026-10-26 | @needs_text |
| tests/test_app.py | 39 | test_case_screen_shows_findings_with_their_evidence | code | 2026-10-26 |     pipeline.save(run, tmp_path / "t1") |
| tests/test_app.py | 62 | test_unknown_or_odd_case_ids_are_404 | signature | 2026-10-26 | def test_unknown_or_odd_case_ids_are_404(client): |
| tests/test_app.py | 63 | test_unknown_or_odd_case_ids_are_404 | code | 2026-10-26 |     assert client.get("/cases/nope").status_code == 404 |
| tests/test_app.py | 64 | test_unknown_or_odd_case_ids_are_404 | code | 2026-10-26 |     assert client.get("/cases/..%2F..%2Fetc").status_code == 404 |
| tests/test_app.py | 68 | test_upload_form_lists_hospital_policies_only | signature | 2026-10-26 | def test_upload_form_lists_hospital_policies_only(client): |
| tests/test_app.py | 75 | test_upload_runs_the_pipeline | signature | 2026-10-26 | @needs_text |
| tests/test_app.py | 76 | test_upload_runs_the_pipeline | signature | 2026-10-26 | def test_upload_runs_the_pipeline(client, monkeypatch): |
| tests/test_app.py | 88 | test_upload_runs_the_pipeline | code | 2026-10-26 |                        follow_redirects=False) |
| tests/test_appeal.py | 8 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_appeal.py | 9 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_appeal.py | 10 | (module) | import | 2026-10-26 | from pathlib import Path |
| tests/test_appeal.py | 12 | (module) | import | 2026-10-26 | import pytest |
| tests/test_appeal.py | 29 | case | code | 2026-10-26 |     raw = json.loads(FIX.read_text()) |
| tests/test_appeal.py | 30 | case | code | 2026-10-26 |     raw["profile"]["people"] = PEOPLE |
| tests/test_appeal.py | 33 | case | code | 2026-10-26 |     return Case.model_validate(raw) |
| tests/test_appeal.py | 36 | text_of | signature | 2026-10-26 | def text_of(letter: writer.Letter) -> str: |
| tests/test_appeal.py | 37 | text_of | code | 2026-10-26 |     return " ".join(p.text for p in letter.paragraphs) |
| tests/test_appeal.py | 126 | test_every_amount_comes_from_the_case_and_no_token_is_left | code | 2026-10-26 |     known = {Decimal(x).quantize(Decimal("0.01")) for x in re.findall(r'"(-?\\d+(?:\\.\\d+)?)"', blob)} |
| tests/test_appeal_tracking.py | 5 | (module) | import | 2026-10-26 | import json |
| tests/test_appeal_tracking.py | 6 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_appeal_tracking.py | 7 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_appeal_tracking.py | 9 | (module) | import | 2026-10-26 | import pytest |
| tests/test_bill_picture.py | 6 | (module) | import | 2026-10-26 | import json |
| tests/test_bill_picture.py | 7 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_bill_picture.py | 8 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_bill_picture.py | 15 | (module) | import | 2026-10-26 | from billradar.checks import Finding, Kind, Report |
| tests/test_call_live.py | 7 | (module) | import | 2026-10-26 | import pytest |
| tests/test_call_live.py | 8 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_call_live.py | 40 | client | signature | 2026-10-26 | @pytest.fixture |
| tests/test_call_live.py | 41 | client | signature | 2026-10-26 | def client(tmp_path, monkeypatch): |
| tests/test_call_live.py | 42 | client | code | 2026-10-26 |     monkeypatch.setattr(app_module, "RUNS", tmp_path) |
| tests/test_callprep.py | 12 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_callprep.py | 13 | (module) | code | 2026-10-26 |                                 reason="run scripts/fetch_policies.py first") |
| tests/test_calls.py | 6 | (module) | import | 2026-10-26 | import pytest |
| tests/test_calls.py | 7 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_calls.py | 15 | client | signature | 2026-10-26 | @pytest.fixture |
| tests/test_calls.py | 16 | client | signature | 2026-10-26 | def client(tmp_path, monkeypatch): |
| tests/test_checks.py | 2 | (module) | import | 2026-10-26 | import json |
| tests/test_checks.py | 3 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_checks.py | 4 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_checks.py | 5 | (module) | import | 2026-10-26 | from pathlib import Path |
| tests/test_checks.py | 7 | (module) | import | 2026-10-26 | import pytest |
| tests/test_checks.py | 9 | (module) | import | 2026-10-26 | from billradar import checks, fpl, policy |
| tests/test_checks.py | 10 | (module) | import | 2026-10-26 | from billradar.case import Case, parse_date, parse_money |
| tests/test_checks.py | 11 | (module) | import | 2026-10-26 | from billradar.checks import Kind |
| tests/test_checks.py | 12 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_checks.py | 14 | (module) | code | 2026-10-26 | FIX = Path(__file__).parent / "fixtures" / "cases" |
| tests/test_checks.py | 15 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_checks.py | 16 | (module) | code | 2026-10-26 |                                 reason="run scripts/fetch_policies.py first") |
| tests/test_checks.py | 23 | load | signature | 2026-10-26 | def load(name: str, **changes) -> Case: |
| tests/test_checks.py | 27 | load | code | 2026-10-26 |     raw = json.loads((FIX / f"{name}.json").read_text()) |
| tests/test_checks.py | 37 | load | code | 2026-10-26 |     return Case.model_validate(raw) |
| tests/test_checks.py | 40 | by_kind | signature | 2026-10-26 | def by_kind(report, kind): |
| tests/test_checks.py | 42 | by_kind | code | 2026-10-26 |     return [f for f in report.findings if f.kind == kind] |
| tests/test_checks.py | 46 | test_parse_money | signature | 2026-10-26 | @pytest.mark.parametrize("text,expected", [ |
| tests/test_checks.py | 48 | test_parse_money | signature | 2026-10-26 |     ("(312.40)", Decimal("-312.40")), |
| tests/test_checks.py | 49 | test_parse_money | signature | 2026-10-26 |     ("-$12", Decimal("-12.00")), |
| tests/test_checks.py | 50 | test_parse_money | signature | 2026-10-26 |     ("1,240.00 CR", Decimal("-1240.00")), |
| tests/test_checks.py | 51 | test_parse_money | signature | 2026-10-26 |     ("", None), |
| tests/test_checks.py | 52 | test_parse_money | signature | 2026-10-26 |     ("N/A", None), |
| tests/test_checks.py | 53 | test_parse_money | signature | 2026-10-26 |     ("1.2.3", None), |
| tests/test_checks.py | 54 | test_parse_money | signature | 2026-10-26 | ]) |
| tests/test_checks.py | 55 | test_parse_money | signature | 2026-10-26 | def test_parse_money(text, expected): |
| tests/test_checks.py | 56 | test_parse_money | code | 2026-10-26 |     assert parse_money(text) == expected |
| tests/test_checks.py | 59 | test_parse_date_never_guesses | signature | 2026-10-26 | @pytest.mark.parametrize("text,expected", [ |
| tests/test_checks.py | 69 | test_fpl_2026 | signature | 2026-10-26 | def test_fpl_2026(): |
| tests/test_checks.py | 77 | (module) | comment | 2026-10-26 | # --- policy quotes ---------------------------------------------------------------------------- |
| tests/test_checks.py | 84 | test_every_policy_quote_is_on_its_page | signature | 2026-10-26 | @needs_text |
| tests/test_checks.py | 85 | test_every_policy_quote_is_on_its_page | signature | 2026-10-26 | @pytest.mark.parametrize("policy_id", policy.available()) |
| tests/test_checks.py | 86 | test_every_policy_quote_is_on_its_page | signature | 2026-10-26 | def test_every_policy_quote_is_on_its_page(policy_id): |
| tests/test_checks.py | 100 | test_quote_check_catches_wrong_page | signature | 2026-10-26 | @needs_text |
| tests/test_checks.py | 101 | test_quote_check_catches_wrong_page | signature | 2026-10-26 | def test_quote_check_catches_wrong_page(): |
| tests/test_checks.py | 110 | test_quote_check_rejects_a_made_up_quote | signature | 2026-10-26 | @needs_text |
| tests/test_checks.py | 111 | test_quote_check_rejects_a_made_up_quote | signature | 2026-10-26 | def test_quote_check_rejects_a_made_up_quote(): |
| tests/test_checks.py | 112 | test_quote_check_rejects_a_made_up_quote | string | 2026-10-26 |     fake = policy.Fragment("memorial-2026-05", "fake", 5, "Patients get free ice cream every Tuesday.") |
| tests/test_checks.py | 118 | (module) | comment | 2026-10-26 | # --- the demo case ---------------------------------------------------------------------------- |
| tests/test_checks.py | 121 | test_anna_birth_case | signature | 2026-10-26 | @needs_text |
| tests/test_checks.py | 122 | test_anna_birth_case | signature | 2026-10-26 | def test_anna_birth_case(): |
| tests/test_checks.py | 123 | test_anna_birth_case | code | 2026-10-26 |     r = checks.run(load("anna-birth")) |
| tests/test_checks.py | 124 | test_anna_birth_case | code | 2026-10-26 |     assert r.fpl_pct == Decimal("257.6") |
| tests/test_checks.py | 127 | test_anna_birth_case | code | 2026-10-26 |     (e1,) = by_kind(r, Kind.E1) |
| tests/test_checks.py | 128 | test_anna_birth_case | code | 2026-10-26 |     assert e1.math["difference"] == "312.40" |
| tests/test_checks.py | 131 | test_anna_birth_case | code | 2026-10-26 |     (f3,) = by_kind(r, Kind.F3) |
| tests/test_checks.py | 132 | test_anna_birth_case | code | 2026-10-26 |     assert f3.amount == Decimal("1054.00")  # 85% of the baby's 1,240.00 |
| tests/test_checks.py | 133 | test_anna_birth_case | code | 2026-10-26 |     assert {e.doc_id for e in f3.evidence} == {"S1", "S2"} |
| tests/test_checks.py | 135 | test_anna_birth_case | code | 2026-10-26 |     (f2,) = by_kind(r, Kind.F2) |
| tests/test_checks.py | 146 | test_baptist_does_not_cover_insured_balances | signature | 2026-10-26 | @needs_text |
| tests/test_checks.py | 147 | test_baptist_does_not_cover_insured_balances | signature | 2026-10-26 | def test_baptist_does_not_cover_insured_balances(): |
| tests/test_checks.py | 148 | test_baptist_does_not_cover_insured_balances | code | 2026-10-26 |     r = checks.run(load("anna-birth", policy_id="baptist-2026-09")) |
| tests/test_checks.py | 152 | test_baptist_does_not_cover_insured_balances | code | 2026-10-26 |     assert e1.math["difference"] == "312.40" |
| tests/test_checks.py | 157 | test_free_care_level_asks_about_savings | signature | 2026-10-26 | @needs_text |
| tests/test_checks.py | 158 | test_free_care_level_asks_about_savings | signature | 2026-10-26 | def test_free_care_level_asks_about_savings(): |
| tests/test_checks.py | 159 | test_free_care_level_asks_about_savings | code | 2026-10-26 |     r = checks.run(load("anna-birth", **{"profile.annual_income": "60000", "profile.liquid_assets": "25000"})) |
| tests/test_checks.py | 165 | test_income_above_policy_limit | signature | 2026-10-26 | @needs_text |
| tests/test_checks.py | 166 | test_income_above_policy_limit | signature | 2026-10-26 | def test_income_above_policy_limit(): |
| tests/test_checks.py | 167 | test_income_above_policy_limit | code | 2026-10-26 |     r = checks.run(load("anna-birth", **{"profile.annual_income": "200000"})) |
| tests/test_checks.py | 173 | test_income_cap_adds_a_finding | signature | 2026-10-26 | @needs_text |
| tests/test_checks.py | 174 | test_income_cap_adds_a_finding | signature | 2026-10-26 | def test_income_cap_adds_a_finding(): |
| tests/test_checks.py | 187 | test_no_discount_anywhere_is_f1_on_each_bill | signature | 2026-10-26 | @needs_text |
| tests/test_checks.py | 188 | test_no_discount_anywhere_is_f1_on_each_bill | signature | 2026-10-26 | def test_no_discount_anywhere_is_f1_on_each_bill(): |
| tests/test_checks.py | 190 | test_no_discount_anywhere_is_f1_on_each_bill | code | 2026-10-26 |     f1 = by_kind(r, Kind.F1) |
| tests/test_checks.py | 198 | test_small_balances_under_memorial_minimum | signature | 2026-10-26 | @needs_text |
| tests/test_checks.py | 199 | test_small_balances_under_memorial_minimum | signature | 2026-10-26 | def test_small_balances_under_memorial_minimum(): |
| tests/test_checks.py | 210 | test_unverified_quote_is_held_back | signature | 2026-10-26 | def test_unverified_quote_is_held_back(monkeypatch): |
| tests/test_checks.py | 211 | test_unverified_quote_is_held_back | code | 2026-10-26 |     monkeypatch.setattr(policy, "verified", lambda ref: not ref.startswith("memorial")) |
| tests/test_checks.py | 212 | test_unverified_quote_is_held_back | code | 2026-10-26 |     r = checks.run(load("anna-birth")) |
| tests/test_checks.py | 213 | test_unverified_quote_is_held_back | code | 2026-10-26 |     assert {f.kind for f in r.findings} == {Kind.E1} |
| tests/test_checks.py | 214 | test_unverified_quote_is_held_back | code | 2026-10-26 |     assert {f.kind for f in r.held_back} == {Kind.F3, Kind.F2} |
| tests/test_checks.py | 222 | test_guideline_year_comes_from_the_policy_not_from_today | code | 2026-10-26 |     assert r.fpl_pct == Decimal("257.6") |
| tests/test_dates_true.py | 15 | (module) | import | 2026-10-26 | from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source |
| tests/test_dates_true.py | 16 | (module) | import | 2026-10-26 | from billradar.checks import Kind |
| tests/test_dates_true.py | 17 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_dates_true.py | 20 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_dates_true.py | 21 | (module) | code | 2026-10-26 |                                 reason="run scripts/fetch_policies.py first") |
| tests/test_demo_limits.py | 7 | (module) | import | 2026-10-26 | import pytest |
| tests/test_demo_limits.py | 8 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_demo_limits.py | 10 | (module) | import | 2026-10-26 | from billradar import app as app_module |
| tests/test_evaluation.py | 4 | (module) | import | 2026-10-26 | import json |
| tests/test_evaluation.py | 5 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_evaluation.py | 6 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_evaluation.py | 7 | (module) | import | 2026-10-26 | from pathlib import Path |
| tests/test_evaluation.py | 9 | (module) | import | 2026-10-26 | import pytest |
| tests/test_evaluation.py | 12 | (module) | import | 2026-10-26 | from billradar import evaluation as ev |
| tests/test_evaluation.py | 14 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_evaluation.py | 15 | (module) | import | 2026-10-26 | from tests.synth import FakeSAM, table_photo |
| tests/test_evaluation.py | 17 | (module) | import | 2026-10-26 | from tests.test_sam import QUADS, SIZE |
| tests/test_evaluation.py | 18 | (module) | import | 2026-10-26 | from tests.test_writer import case |
| tests/test_evaluation.py | 20 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_evaluation.py | 21 | (module) | code | 2026-10-26 |                                 reason="run scripts/fetch_policies.py first") |
| tests/test_evaluation.py | 24 | (module) | code | 2026-10-26 | KEY = ev.Key(pack_id="anna-birth", split="work", items=[ |
| tests/test_evaluation.py | 25 | (module) | code | 2026-10-26 |     ev.KeyItem(cls="E1", sheets=["S1", "S4"], amount=Decimal("46.86")), |
| tests/test_evaluation.py | 26 | (module) | code | 2026-10-26 |     ev.KeyItem(cls="F3", sheets=["S1", "S2"], amount=Decimal("1054.00")), |
| tests/test_evaluation.py | 28 | (module) | punct | 2026-10-26 | ]) |
| tests/test_evaluation.py | 49 | FakeModels.events | signature | 2026-10-26 |     def events(self, body): |
| tests/test_evaluation.py | 50 | FakeModels.events | code | 2026-10-26 |         if body["model"] == "sam-3.1": |
| tests/test_evaluation.py | 65 | _anna_pack | code | 2026-10-26 |     pack = tmp_path / "anna" |
| tests/test_evaluation.py | 66 | _anna_pack | code | 2026-10-26 |     pack.mkdir() |
| tests/test_evaluation.py | 67 | _anna_pack | code | 2026-10-26 |     (pack / "table.jpg").write_bytes(table_photo(QUADS, SIZE)) |
| tests/test_evaluation.py | 71 | _anna_pack | code | 2026-10-26 |     (pack / "key.json").write_text(KEY.model_dump_json()) |
| tests/test_evaluation.py | 79 | test_billradar_on_its_own_case_finds_everything | signature | 2026-10-26 | @needs_text |
| tests/test_evaluation.py | 80 | test_billradar_on_its_own_case_finds_everything | signature | 2026-10-26 | def test_billradar_on_its_own_case_finds_everything(): |
| tests/test_evaluation.py | 86 | test_scoring_counts_misses_falses_and_wrong_numbers | signature | 2026-10-26 | def test_scoring_counts_misses_falses_and_wrong_numbers(): |
| tests/test_evaluation.py | 87 | test_scoring_counts_misses_falses_and_wrong_numbers | code | 2026-10-26 |     preds = [ev.Prediction(cls="F3", sheets=["S2"], amount=Decimal("900.00")), |
| tests/test_evaluation.py | 98 | test_a_prediction_matches_only_one_key_item | signature | 2026-10-26 | def test_a_prediction_matches_only_one_key_item(): |
| tests/test_evaluation.py | 104 | test_seal_refuses_a_changed_key | signature | 2026-10-26 | def test_seal_refuses_a_changed_key(tmp_path): |
| tests/test_evaluation.py | 108 | test_seal_refuses_a_changed_key | code | 2026-10-26 |     ledger = tmp_path / "SEALED.txt" |
| tests/test_evaluation.py | 117 | test_seal_refuses_a_changed_key | code | 2026-10-26 |     data["items"][0]["amount"] = "50.00" |
| tests/test_evaluation.py | 122 | test_bodies_are_valid_requests | signature | 2026-10-26 | @needs_text |
| tests/test_evaluation.py | 123 | test_bodies_are_valid_requests | signature | 2026-10-26 | def test_bodies_are_valid_requests(): |
| tests/test_evaluation.py | 124 | test_bodies_are_valid_requests | code | 2026-10-26 |     sheets = [("S1", b"\\xff\\xd8fake"), ("S2", b"\\xff\\xd8fake")] |
| tests/test_evaluation.py | 125 | test_bodies_are_valid_requests | code | 2026-10-26 |     simple = ev.simple_body(sheets, []) |
| tests/test_evaluation.py | 126 | test_bodies_are_valid_requests | code | 2026-10-26 |     strong = ev.strong_body(sheets, [], "memorial-2026-05", {"size": 4}) |
| tests/test_evaluation.py | 127 | test_bodies_are_valid_requests | code | 2026-10-26 |     judge = ev.judge_body("You may qualify for a discount.", KEY) |
| tests/test_evaluation.py | 132 | test_bodies_are_valid_requests | code | 2026-10-26 |     assert simple["input"][0]["content"][0]["text"] == ev.SIMPLE_QUESTION |
| tests/test_evaluation.py | 139 | test_judge_and_strong_answers_parse | signature | 2026-10-26 | def test_judge_and_strong_answers_parse(): |
| tests/test_evaluation.py | 141 | test_judge_and_strong_answers_parse | code | 2026-10-26 |                          {"index": 0, "found": False, "amount": "", "deadline": ""}], |
| tests/test_evaluation.py | 152 | test_run_pack_end_to_end_on_synthetic_answers | signature | 2026-10-26 | @needs_text |
| tests/test_evaluation.py | 153 | test_run_pack_end_to_end_on_synthetic_answers | signature | 2026-10-26 | def test_run_pack_end_to_end_on_synthetic_answers(tmp_path): |
| tests/test_evaluation.py | 154 | test_run_pack_end_to_end_on_synthetic_answers | code | 2026-10-26 |     answers = { |
| tests/test_evaluation.py | 156 | test_run_pack_end_to_end_on_synthetic_answers | code | 2026-10-26 |         "judge": json.dumps({"items": [{"index": 1, "found": True, "amount": "", "deadline": ""}], "other_money_claims": 1}), |
| tests/test_evaluation.py | 157 | test_run_pack_end_to_end_on_synthetic_answers | code | 2026-10-26 |         "strong_baseline": json.dumps({"findings": [{"cls": "F3", "sheets": ["S2"], "amount": "1054.00", "deadline": "", |
| tests/test_evaluation.py | 158 | test_run_pack_end_to_end_on_synthetic_answers | code | 2026-10-26 |                                                      "explanation": ""}]}), |
| tests/test_evaluation.py | 159 | test_run_pack_end_to_end_on_synthetic_answers | string | 2026-10-26 |         None: "You may be able to ask the hospital for help with the baby's bill.", |
| tests/test_evaluation.py | 160 | test_run_pack_end_to_end_on_synthetic_answers | punct | 2026-10-26 |     } |
| tests/test_evaluation.py | 173 | test_run_pack_end_to_end_on_synthetic_answers | code | 2026-10-26 |     assert (tmp_path / "out" / "simple.txt").read_text().startswith("You may") |
| tests/test_explain.py | 3 | (module) | import | 2026-10-26 | import json |
| tests/test_explain.py | 4 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_explain.py | 5 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_fix_after_sealed_run.py | 4 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_fix_after_sealed_run.py | 5 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_highlight.py | 4 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_highlight.py | 5 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_highlight.py | 12 | (module) | import | 2026-10-26 | from billradar.checks import Finding, Kind, Report |
| tests/test_local_reader.py | 5 | (module) | import | 2026-10-26 | import pytest |
| tests/test_local_reader.py | 6 | (module) | import | 2026-10-26 | from PIL import Image, ImageDraw, ImageFont |
| tests/test_meta_default.py | 4 | (module) | import | 2026-10-26 | import pytest |
| tests/test_meta_default.py | 5 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_meta_default.py | 7 | (module) | import | 2026-10-26 | from billradar import app as app_module |
| tests/test_meta_reading.py | 3 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_meta_reading.py | 4 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_meta_spend.py | 39 | body | code | 2026-10-26 |             "input": [{"role": "user", "content": [{"type": "input_text", "text": text}]}]} |
| tests/test_money_ceiling.py | 7 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_money_ceiling.py | 8 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_money_ceiling.py | 10 | (module) | import | 2026-10-26 | import pytest |
| tests/test_money_ceiling.py | 13 | (module) | import | 2026-10-26 | from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source |
| tests/test_money_ceiling.py | 14 | (module) | import | 2026-10-26 | from billradar.checks import Kind |
| tests/test_money_ceiling.py | 15 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_money_ceiling.py | 17 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_money_ceiling.py | 18 | (module) | code | 2026-10-26 |                                 reason="run scripts/fetch_policies.py first") |
| tests/test_money_invariant.py | 13 | (module) | import | 2026-10-26 | from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source |
| tests/test_money_invariant.py | 14 | (module) | import | 2026-10-26 | from billradar.checks import Kind |
| tests/test_money_invariant.py | 15 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_money_invariant.py | 17 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_money_invariant.py | 18 | (module) | code | 2026-10-26 |                                 reason="run scripts/fetch_policies.py first") |
| tests/test_money_invariant.py | 71 | random_case | code | 2026-10-26 |                    people=[Person(token="PATIENT_1", role=Role.MOTHER), Person(token="PATIENT_2", role=Role.NEWBORN)]) |
| tests/test_packs.py | 7 | (module) | import | 2026-10-26 | import json |
| tests/test_packs.py | 8 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_packs.py | 9 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_packs.py | 10 | (module) | import | 2026-10-26 | from pathlib import Path |
| tests/test_packs.py | 12 | (module) | import | 2026-10-26 | import pytest |
| tests/test_packs.py | 14 | (module) | import | 2026-10-26 | from billradar import checks |
| tests/test_packs.py | 15 | (module) | import | 2026-10-26 | from billradar import evaluation as ev |
| tests/test_packs.py | 17 | (module) | import | 2026-10-26 | from billradar.checks import Kind |
| tests/test_packs.py | 18 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_packs.py | 22 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_packs.py | 23 | (module) | code | 2026-10-26 |                                 reason="run scripts/fetch_policies.py first") |
| tests/test_pages.py | 4 | (module) | import | 2026-10-26 | import json |
| tests/test_pages.py | 5 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_pages.py | 6 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_pages.py | 7 | (module) | import | 2026-10-26 | from pathlib import Path |
| tests/test_pages.py | 9 | (module) | import | 2026-10-26 | import pytest |
| tests/test_pipeline.py | 2 | (module) | import | 2026-10-26 | import json |
| tests/test_pipeline.py | 4 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_pipeline.py | 5 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_pipeline.py | 6 | (module) | import | 2026-10-26 | from pathlib import Path |
| tests/test_pipeline.py | 8 | (module) | import | 2026-10-26 | import pytest |
| tests/test_pipeline.py | 10 | (module) | import | 2026-10-26 | from billradar import cli, pipeline, reader |
| tests/test_pipeline.py | 11 | (module) | import | 2026-10-26 | from billradar.case import Profile, Source |
| tests/test_pipeline.py | 12 | (module) | import | 2026-10-26 | from billradar.checks import Kind |
| tests/test_pipeline.py | 13 | (module) | import | 2026-10-26 | from billradar.meta_client import MetaAPIError, MetaClient, check_body |
| tests/test_pipeline.py | 14 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_pipeline.py | 15 | (module) | import | 2026-10-26 | from tests.synth import FakeSAM, sheet_quad, table_photo |
| tests/test_pipeline.py | 16 | (module) | import | 2026-10-26 | from tests.test_sam import QUADS, SIZE |
| tests/test_pipeline.py | 18 | (module) | code | 2026-10-26 | FIX = Path(__file__).parent / "fixtures" / "cases" / "anna-birth.json" |
| tests/test_pipeline.py | 28 | spark_payload_from_fixture | signature | 2026-10-26 | def spark_payload_from_fixture(rename: dict[str, str]) -> dict: |
| tests/test_pipeline.py | 34 | spark_payload_from_fixture.txt | code | 2026-10-26 |             return "" |
| tests/test_pipeline.py | 53 | spark_payload_from_fixture | punct | 2026-10-26 |         }) |
| tests/test_pipeline.py | 57 | FakeMeta (class) | signature | 2026-10-26 | class FakeMeta: |
| tests/test_pipeline.py | 58 | FakeMeta (class) | doc | 2026-10-26 |     """Routes by model: SAM answers from drawn quads, Spark answers with a fixed SYNTHETIC JSON.""" |
| tests/test_pipeline.py | 60 | FakeMeta.__init__ | signature | 2026-10-26 |     def __init__(self, sam_fake: FakeSAM, spark_json: dict \| str): |
| tests/test_pipeline.py | 63 | FakeMeta.__init__ | code | 2026-10-26 |         self.spark_bodies: list[dict] = [] |
| tests/test_pipeline.py | 65 | FakeMeta.events | signature | 2026-10-26 |     def events(self, body): |
| tests/test_pipeline.py | 66 | FakeMeta.events | code | 2026-10-26 |         if body["model"] == "sam-3.1": |
| tests/test_pipeline.py | 67 | FakeMeta.events | code | 2026-10-26 |             return self.sam.events(body) |
| tests/test_pipeline.py | 68 | FakeMeta.events | code | 2026-10-26 |         self.spark_bodies.append(body) |
| tests/test_pipeline.py | 69 | FakeMeta.events | code | 2026-10-26 |         text = self.spark_json if isinstance(self.spark_json, str) else json.dumps(self.spark_json) |
| tests/test_pipeline.py | 72 | FakeMeta.events | code | 2026-10-26 |         return [{"type": "response.output_text.delta", "delta": text[:half]}, |
| tests/test_pipeline.py | 73 | FakeMeta.events | code | 2026-10-26 |                 {"type": "response.output_text.delta", "delta": text[half:]}, |
| tests/test_pipeline.py | 77 | profile | signature | 2026-10-26 | def profile() -> Profile: |
| tests/test_pipeline.py | 79 | profile | code | 2026-10-26 |     return Profile.model_validate(json.loads(FIX.read_text())["profile"]) |
| tests/test_pipeline.py | 89 | test_photo_to_findings_end_to_end | signature | 2026-10-26 | @needs_text |
| tests/test_pipeline.py | 90 | test_photo_to_findings_end_to_end | signature | 2026-10-26 | def test_photo_to_findings_end_to_end(tmp_path): |
| tests/test_pipeline.py | 102 | test_photo_to_findings_end_to_end | code | 2026-10-26 |     check_body(body) |
| tests/test_pipeline.py | 103 | test_photo_to_findings_end_to_end | code | 2026-10-26 |     assert body["text"]["format"]["strict"] is True and body["store"] is False |
| tests/test_pipeline.py | 109 | test_photo_to_findings_end_to_end | code | 2026-10-26 |     assert (tmp_path / "run" / "overlay-1.jpg").stat().st_size > 10_000 |
| tests/test_pipeline.py | 113 | test_reader_refuses_to_guess | signature | 2026-10-26 | def test_reader_refuses_to_guess(): |
| tests/test_pipeline.py | 114 | test_reader_refuses_to_guess | code | 2026-10-26 |     payload = spark_payload_from_fixture({"S6": "S5"}) |
| tests/test_pipeline.py | 132 | test_spark_answer_that_is_not_json_is_an_error | code | 2026-10-26 |     fake = FakeMeta(FakeSAM(QUADS, SIZE), "Sorry, I can't read these.") |
| tests/test_pipeline.py | 134 | test_spark_answer_that_is_not_json_is_an_error | code | 2026-10-26 |     with pytest.raises(MetaAPIError, match="not JSON"): |
| tests/test_pipeline.py | 135 | test_spark_answer_that_is_not_json_is_an_error | code | 2026-10-26 |         pipeline.run(client, [table_photo(QUADS, SIZE)], [], profile(), "memorial-2026-05") |
| tests/test_pipeline.py | 138 | test_schema_fits_the_strict_subset | signature | 2026-10-26 | def test_schema_fits_the_strict_subset(): |
| tests/test_pipeline.py | 145 | test_schema_fits_the_strict_subset.walk | code | 2026-10-26 |         if node.get("type") == "object": |
| tests/test_pipeline.py | 150 | test_schema_fits_the_strict_subset.walk | code | 2026-10-26 |         if node.get("type") == "array": |
| tests/test_pipeline.py | 151 | test_schema_fits_the_strict_subset.walk | code | 2026-10-26 |             walk(node["items"], f"{path}[]") |
| tests/test_pipeline.py | 153 | test_schema_fits_the_strict_subset | code | 2026-10-26 |     walk(reader.SCHEMA) |
| tests/test_pipeline.py | 161 | test_cli_check | signature | 2026-10-26 | @needs_text |
| tests/test_pipeline.py | 162 | test_cli_check | signature | 2026-10-26 | def test_cli_check(capsys): |
| tests/test_pipeline.py | 163 | test_cli_check | code | 2026-10-26 |     assert cli.main(["check", str(FIX)]) == 0 |
| tests/test_pipeline.py | 164 | test_cli_check | code | 2026-10-26 |     out = capsys.readouterr().out |
| tests/test_pipeline.py | 180 | test_live_calls_need_a_fictional_pack | signature | 2026-10-26 | def test_live_calls_need_a_fictional_pack(monkeypatch): |
| tests/test_pipeline.py | 272 | test_an_unnamed_bill_takes_the_office_printed_on_it_and_one_debt_is_counted_once | import | 2026-10-26 |     from datetime import date |
| tests/test_pipeline.py | 273 | test_an_unnamed_bill_takes_the_office_printed_on_it_and_one_debt_is_counted_once | import | 2026-10-26 |     from decimal import Decimal |
| tests/test_policy_finder.py | 6 | (module) | import | 2026-10-26 | import json |
| tests/test_policy_finder.py | 7 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_policy_finder.py | 8 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_policy_finder.py | 10 | (module) | import | 2026-10-26 | import pytest |
| tests/test_portal_job.py | 7 | (module) | import | 2026-10-26 | import pytest |
| tests/test_portal_job.py | 8 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_portal_job.py | 10 | (module) | import | 2026-10-26 | from billradar import app as app_module |
| tests/test_prices.py | 8 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_prices.py | 9 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_prices.py | 11 | (module) | import | 2026-10-26 | import pytest |
| tests/test_reconcile.py | 9 | (module) | import | 2026-10-26 | import pytest |
| tests/test_reconcile.py | 10 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_reconcile.py | 11 | (module) | import | 2026-10-26 | from pypdf import PdfReader |
| tests/test_reconcile.py | 13 | (module) | import | 2026-10-26 | from billradar import app as app_module |
| tests/test_redact.py | 2 | (module) | doc | 2026-10-26 | before (so the check is not blind) and unreadable after. All text here is SYNTHETIC.""" |
| tests/test_redact.py | 4 | (module) | import | 2026-10-26 | import base64 |
| tests/test_redact.py | 5 | (module) | import | 2026-10-26 | import io |
| tests/test_redact.py | 6 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_redact.py | 8 | (module) | import | 2026-10-26 | import pytest |
| tests/test_redact.py | 9 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_redact.py | 12 | (module) | import | 2026-10-26 | from billradar import app as app_module |
| tests/test_redact.py | 14 | (module) | import | 2026-10-26 | from billradar.case import Profile |
| tests/test_redact.py | 15 | (module) | import | 2026-10-26 | from billradar.meta_client import MetaClient |
| tests/test_redact.py | 16 | (module) | import | 2026-10-26 | from billradar.redact import Secret, Vault, compact, leaks, ocr |
| tests/test_redact.py | 18 | (module) | import | 2026-10-26 | from tests.synth import FakeSAM |
| tests/test_redact.py | 19 | (module) | import | 2026-10-26 | from tests.test_pipeline import FakeMeta, profile, spark_payload_from_fixture |
| tests/test_redact.py | 21 | (module) | code | 2026-10-26 | pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning") |
| tests/test_redact.py | 35 | text_of | signature | 2026-10-26 | def text_of(img) -> str: |
| tests/test_redact.py | 37 | text_of | code | 2026-10-26 |     return " ".join(compact(line.text) for line in ocr(img)) |
| tests/test_redact.py | 42 | lit_name_controls | code | 2026-10-26 |     controls = [Secret("PATIENT", "Anna Sample", ""), Secret("PATIENT", "Baby Sample", "")] |
| tests/test_redact.py | 84 | _demo_module | signature | 2026-10-26 | def _demo_module(): |
| tests/test_redact.py | 89 | test_private_values_are_readable_before_and_covered_after | signature | 2026-10-26 | def test_private_values_are_readable_before_and_covered_after(): |
| tests/test_redact.py | 94 | test_private_values_are_readable_before_and_covered_after | code | 2026-10-26 |     r = redact.redact(img, Vault()) |
| tests/test_redact.py | 96 | test_private_values_are_readable_before_and_covered_after | code | 2026-10-26 |     assert leaks(r.image, controls) == [] |
| tests/test_redact.py | 97 | test_private_values_are_readable_before_and_covered_after | code | 2026-10-26 |     assert {s.kind for s in r.secrets} >= {"PATIENT", "ACCT", "MEMBER", "SSN", "DOB", "ADDR"} |
| tests/test_redact.py | 100 | test_private_values_are_readable_before_and_covered_after | code | 2026-10-26 |     after = text_of(r.image) |
| tests/test_redact.py | 105 | test_same_value_gets_the_same_token_on_every_sheet | signature | 2026-10-26 | def test_same_value_gets_the_same_token_on_every_sheet(): |
| tests/test_redact.py | 106 | test_same_value_gets_the_same_token_on_every_sheet | code | 2026-10-26 |     vault = Vault() |
| tests/test_redact.py | 117 | test_names_the_family_gave_us_are_covered_anywhere | signature | 2026-10-26 | def test_names_the_family_gave_us_are_covered_anywhere(): |
| tests/test_redact.py | 119 | test_names_the_family_gave_us_are_covered_anywhere | code | 2026-10-26 |     controls = [Secret("PATIENT", "Anna Sample", ""), Secret("PATIENT", "Mia Sample", "")] |
| tests/test_redact.py | 123 | test_names_the_family_gave_us_are_covered_anywhere | code | 2026-10-26 |     r = redact.redact(img, vault) |
| tests/test_redact.py | 125 | test_names_the_family_gave_us_are_covered_anywhere | code | 2026-10-26 |     assert leaks(r.image, controls) == [] |
| tests/test_redact.py | 129 | test_headers_without_numbers_are_left_alone | signature | 2026-10-26 | def test_headers_without_numbers_are_left_alone(): |
| tests/test_redact.py | 130 | test_headers_without_numbers_are_left_alone | code | 2026-10-26 |     img = sheet(["Account Summary", "Claim Totals", "Patient responsibility $40.00"]) |
| tests/test_redact.py | 138 | test_what_sam_gets_is_small_and_soft | code | 2026-10-26 |     small = redact.sam_copy(big, max_side=900) |
| tests/test_redact.py | 140 | test_what_sam_gets_is_small_and_soft | code | 2026-10-26 |     assert max(small.size) == 900 |
| tests/test_redact.py | 147 | test_private_pipeline_sends_nothing_readable | signature | 2026-10-26 | def test_private_pipeline_sends_nothing_readable(): |
| tests/test_redact.py | 158 | test_private_pipeline_sends_nothing_readable.images | code | 2026-10-26 |         for item in body["input"]: |
| tests/test_redact.py | 177 | test_a_labelled_name_keeps_the_persons_token | signature | 2026-10-26 | def test_a_labelled_name_keeps_the_persons_token(): |
| tests/test_redact.py | 178 | test_a_labelled_name_keeps_the_persons_token | code | 2026-10-26 |     vault = Vault(seed={("PATIENT", "Anna"): "[PATIENT_1]", ("PATIENT", "Mia"): "[PATIENT_2]"}) |
| tests/test_redact.py | 181 | test_a_labelled_name_keeps_the_persons_token | code | 2026-10-26 |     r = redact.redact(img, vault) |
| tests/test_redact.py | 187 | test_screen_can_show_what_the_models_saw | signature | 2026-10-26 | def test_screen_can_show_what_the_models_saw(tmp_path, monkeypatch): |
| tests/test_redact.py | 188 | test_screen_can_show_what_the_models_saw | code | 2026-10-26 |     monkeypatch.setattr(app_module, "RUNS", tmp_path) |
| tests/test_redact.py | 195 | test_screen_can_show_what_the_models_saw | code | 2026-10-26 |     pipeline.save(run, tmp_path / "v1") |
| tests/test_redact.py | 213 | test_a_name_printed_last_name_first_is_covered_too | code | 2026-10-26 |     r = redact.redact(img, vault) |
| tests/test_redact.py | 214 | test_a_name_printed_last_name_first_is_covered_too | code | 2026-10-26 |     assert leaks(r.image, controls) == [] |
| tests/test_redact_packs.py | 14 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_redact_packs.py | 15 | (module) | import | 2026-10-26 | from pathlib import Path |
| tests/test_redact_packs.py | 23 | (module) | import | 2026-10-26 | from billradar.case import Profile |
| tests/test_redact_packs.py | 24 | (module) | import | 2026-10-26 | from billradar.meta_client import MetaClient |
| tests/test_redact_packs.py | 27 | (module) | code | 2026-10-26 | pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning") |
| tests/test_redact_packs.py | 49 | Spy.events | code | 2026-10-26 |         for item in body["input"]: |
| tests/test_redact_packs.py | 50 | Spy.events | code | 2026-10-26 |             for part in item.get("content", []) if isinstance(item.get("content"), list) else []: |
| tests/test_redact_packs.py | 244 | test_replay_answers_pdf_pages_and_the_file_comes_back_whole | import | 2026-10-26 |     from billradar.case import Profile |
| tests/test_redact_packs.py | 245 | test_replay_answers_pdf_pages_and_the_file_comes_back_whole | import | 2026-10-26 |     from billradar.meta_client import MetaClient |
| tests/test_review_2026_10_31.py | 4 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_review_2026_10_31.py | 5 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_review_2026_10_31.py | 7 | (module) | import | 2026-10-26 | import pytest |
| tests/test_review_2026_10_31.py | 14 | (module) | import | 2026-10-26 | from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source |
| tests/test_review_2026_10_31.py | 19 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_review_2026_10_31.py | 20 | (module) | code | 2026-10-26 |                                 reason="run scripts/fetch_policies.py first") |
| tests/test_review_2026_10_31.py | 35 | L | code | 2026-10-26 |     return Line(line_no=n, service_date=kw.pop("service_date", D), code=code, charges=Decimal(charges), |
| tests/test_review_screen.py | 4 | (module) | import | 2026-10-26 | import re |
| tests/test_review_screen.py | 5 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_review_screen.py | 7 | (module) | import | 2026-10-26 | import pytest |
| tests/test_review_screen.py | 8 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_review_step.py | 32 | Spy.events | code | 2026-10-26 |         for item in body["input"]: |
| tests/test_review_step.py | 33 | Spy.events | code | 2026-10-26 |             for part in item.get("content", []) if isinstance(item.get("content"), list) else []: |
| tests/test_rw_checks.py | 8 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_rw_checks.py | 9 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_rw_checks.py | 17 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_rw_checks.py | 19 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_rw_checks.py | 20 | (module) | code | 2026-10-26 |                                 reason="run scripts/fetch_policies.py first") |
| tests/test_rw_forms.py | 11 | (module) | import | 2026-10-26 | from decimal import Decimal, InvalidOperation |
| tests/test_rw_forms.py | 20 | (module) | import | 2026-10-26 | from billradar.case import Case |
| tests/test_rw_forms.py | 21 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_rw_policy.py | 17 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_rw_sheet_checks.py | 6 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_rw_sheet_checks.py | 7 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_rw_sheet_checks.py | 9 | (module) | import | 2026-10-26 | import pytest |
| tests/test_rw_sheet_checks.py | 12 | (module) | import | 2026-10-26 | from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source |
| tests/test_rw_sheet_checks.py | 13 | (module) | import | 2026-10-26 | from billradar.checks import Evidence, Finding, Kind |
| tests/test_rw_sheet_checks.py | 285 | test_a_balance_below_zero_gives_every_field_of_the_finding | string | 2026-10-26 |         detail="The balance is in your favor. Ask for a refund instead of leaving it on the account.", |
| tests/test_rw_verifier.py | 11 | (module) | import | 2026-10-26 | from pathlib import Path |
| tests/test_sam.py | 1 | (module) | import | 2026-10-26 | import json |
| tests/test_sam.py | 3 | (module) | import | 2026-10-26 | import numpy as np |
| tests/test_sam.py | 4 | (module) | import | 2026-10-26 | import pytest |
| tests/test_sam.py | 6 | (module) | import | 2026-10-26 | from billradar import sam |
| tests/test_sam.py | 7 | (module) | import | 2026-10-26 | from billradar.meta_client import MetaAPIError, MetaClient, ReplayMissing, ReplayTransport, check_body |
| tests/test_sam.py | 12 | (module) | code | 2026-10-26 | QUADS = [ |
| tests/test_sam.py | 13 | (module) | code | 2026-10-26 |     sheet_quad(500, 470, 520, 670, -6), |
| tests/test_sam.py | 14 | (module) | code | 2026-10-26 |     sheet_quad(1180, 450, 520, 670, 4), |
| tests/test_sam.py | 15 | (module) | code | 2026-10-26 |     sheet_quad(1880, 480, 520, 670, -3), |
| tests/test_sam.py | 16 | (module) | code | 2026-10-26 |     sheet_quad(700, 1330, 520, 670, 5), |
| tests/test_sam.py | 17 | (module) | code | 2026-10-26 |     sheet_quad(1500, 1310, 520, 670, -4), |
| tests/test_sam.py | 18 | (module) | punct | 2026-10-26 | ] |
| tests/test_sam.py | 21 | client | signature | 2026-10-26 | def client(fake, tmp_path) -> MetaClient: |
| tests/test_sam.py | 33 | test_finds_every_sheet_in_reading_order | signature | 2026-10-26 | def test_finds_every_sheet_in_reading_order(tmp_path): |
| tests/test_sam.py | 35 | test_finds_every_sheet_in_reading_order | code | 2026-10-26 |     assert [s.doc_id for s in res.sheets] == ["S1", "S2", "S3", "S4", "S5"] |
| tests/test_sam.py | 45 | test_sheets_are_straightened_to_paper_shape | signature | 2026-10-26 | def test_sheets_are_straightened_to_paper_shape(tmp_path): |
| tests/test_sam.py | 54 | test_noise_is_dropped_with_a_reason | signature | 2026-10-26 | def test_noise_is_dropped_with_a_reason(tmp_path): |
| tests/test_sam.py | 63 | test_noise_is_dropped_with_a_reason | code | 2026-10-26 |     assert [s.doc_id for s in res.sheets] == ["S1", "S2", "S3", "S4", "S5"] |
| tests/test_sam.py | 68 | test_no_sheets_is_a_normal_answer | signature | 2026-10-26 | def test_no_sheets_is_a_normal_answer(tmp_path): |
| tests/test_sam.py | 70 | test_no_sheets_is_a_normal_answer | code | 2026-10-26 |     assert res.sheets == [] |
| tests/test_sam.py | 74 | test_cut_stream_is_an_error_not_a_short_answer | signature | 2026-10-26 | def test_cut_stream_is_an_error_not_a_short_answer(tmp_path): |
| tests/test_sam.py | 76 | test_cut_stream_is_an_error_not_a_short_answer | code | 2026-10-26 |     with pytest.raises(MetaAPIError, match="without a final event"): |
| tests/test_sam.py | 77 | test_cut_stream_is_an_error_not_a_short_answer | code | 2026-10-26 |         sam.find_sheets(client(fake, tmp_path), table_photo(QUADS, SIZE)) |
| tests/test_sam.py | 80 | test_request_asks_for_one_bit_masks_and_confidence | signature | 2026-10-26 | def test_request_asks_for_one_bit_masks_and_confidence(tmp_path): |
| tests/test_sam.py | 83 | test_request_asks_for_one_bit_masks_and_confidence | code | 2026-10-26 |     assert body["model"] == "sam-3.1" |
| tests/test_sam.py | 84 | test_request_asks_for_one_bit_masks_and_confidence | code | 2026-10-26 |     assert body["input"][0]["content"][0] == {"type": "input_text", "text": "sheet of paper"} |
| tests/test_sam.py | 85 | test_request_asks_for_one_bit_masks_and_confidence | code | 2026-10-26 |     assert body["metadata"] == {"mask_encoding": "one_bit", "include_confidence": "true"} |
| tests/test_sam.py | 88 | test_journal_logs_the_request_but_never_the_image | signature | 2026-10-26 | def test_journal_logs_the_request_but_never_the_image(tmp_path): |
| tests/test_sam.py | 93 | test_journal_logs_the_request_but_never_the_image | code | 2026-10-26 |     assert "base64" not in line and len(line) < 1000 |
| tests/test_sam.py | 96 | test_overlay_draws_numbers | signature | 2026-10-26 | def test_overlay_draws_numbers(tmp_path): |
| tests/test_sam.py | 104 | (module) | comment | 2026-10-26 | # --- client guards ------------------------------------------------------------------------------ |
| tests/test_sam.py | 107 | test_contributor_models_are_refused | signature | 2026-10-26 | def test_contributor_models_are_refused(): |
| tests/test_sam.py | 108 | test_contributor_models_are_refused | code | 2026-10-26 |     with pytest.raises(MetaAPIError, match="not allowed"): |
| tests/test_sam.py | 109 | test_contributor_models_are_refused | code | 2026-10-26 |         check_body({"model": "muse-spark-1.3-contributor", "store": False, "input": []}) |
| tests/test_sam.py | 112 | test_spark_must_not_store | signature | 2026-10-26 | def test_spark_must_not_store(): |
| tests/test_sam.py | 113 | test_spark_must_not_store | code | 2026-10-26 |     with pytest.raises(MetaAPIError, match="store must be false"): |
| tests/test_sam.py | 114 | test_spark_must_not_store | code | 2026-10-26 |         check_body({"model": "muse-spark-1.3", "input": []}) |
| tests/test_sam.py | 118 | test_default_is_replay_without_key_and_flag | signature | 2026-10-26 | def test_default_is_replay_without_key_and_flag(monkeypatch): |
| tests/test_sam.py | 119 | test_default_is_replay_without_key_and_flag | code | 2026-10-26 |     monkeypatch.setenv("MODEL_API_KEY", "not-a-real-key") |
| tests/test_sam.py | 120 | test_default_is_replay_without_key_and_flag | code | 2026-10-26 |     monkeypatch.delenv("BILLRADAR_LIVE", raising=False) |
| tests/test_sam.py | 122 | test_default_is_replay_without_key_and_flag | code | 2026-10-26 |     monkeypatch.delenv("MODEL_API_KEY") |
| tests/test_sam.py | 123 | test_default_is_replay_without_key_and_flag | code | 2026-10-26 |     monkeypatch.setenv("BILLRADAR_LIVE", "1") |
| tests/test_sam.py | 125 | test_default_is_replay_without_key_and_flag | code | 2026-10-26 |     monkeypatch.setenv("MODEL_API_KEY", "not-a-real-key") |
| tests/test_sam.py | 129 | test_missing_recording_is_an_error | signature | 2026-10-26 | def test_missing_recording_is_an_error(tmp_path): |
| tests/test_sam.py | 131 | test_missing_recording_is_an_error | code | 2026-10-26 |     with pytest.raises(ReplayMissing): |
| tests/test_screens_docs.py | 13 | (module) | import | 2026-10-26 | import pytest |
| tests/test_screens_docs.py | 14 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_screens_docs.py | 16 | (module) | import | 2026-10-26 | from billradar import app as app_module |
| tests/test_screens_docs.py | 20 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_screens_docs.py | 21 | (module) | code | 2026-10-26 |                                 reason="run scripts/fetch_policies.py first") |
| tests/test_screens_docs.py | 103 | test_appeal_tracker_owner_marks_sent_examples_are_read_only | code | 2026-10-26 |                     follow_redirects=False) |
| tests/test_screens_docs.py | 104 | test_appeal_tracker_owner_marks_sent_examples_are_read_only | code | 2026-10-26 |     assert r.status_code == 303 |
| tests/test_sheet_checks.py | 3 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_sheet_checks.py | 4 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_sheet_checks.py | 6 | (module) | import | 2026-10-26 | import pytest |
| tests/test_sheet_checks.py | 8 | (module) | import | 2026-10-26 | from billradar import checks, sheet_checks |
| tests/test_sheet_checks.py | 9 | (module) | import | 2026-10-26 | from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source |
| tests/test_sheet_checks.py | 10 | (module) | import | 2026-10-26 | from billradar.checks import Kind |
| tests/test_sheet_checks.py | 11 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_sheet_checks.py | 13 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_sheet_checks.py | 14 | (module) | code | 2026-10-26 |                                 reason="run scripts/fetch_policies.py first") |
| tests/test_sheet_checks.py | 18 | make | signature | 2026-10-26 | def make(*docs: Document, policy_id: str = "memorial-2026-05", income: str = "85000") -> Case: |
| tests/test_sheet_checks.py | 24 | line | signature | 2026-10-26 | def line(n, code, charges, resp, **kw) -> Line: |
| tests/test_sheet_checks.py | 26 | line | code | 2026-10-26 |     return Line(line_no=n, service_date=kw.pop("service_date", D), code=code, charges=Decimal(charges), |
| tests/test_sheet_checks.py | 30 | doc | signature | 2026-10-26 | def doc(doc_id, kind, patient="PATIENT_1", **kw) -> Document: |
| tests/test_sheet_checks.py | 31 | doc | code | 2026-10-26 |     return Document(doc_id=doc_id, source=Source.PAPER, kind=kind, patient=patient, **kw) |
| tests/test_sheet_checks.py | 34 | kinds | signature | 2026-10-26 | def kinds(findings): |
| tests/test_sheet_checks.py | 35 | kinds | code | 2026-10-26 |     return [f.kind for f in findings] |
| tests/test_sheet_checks.py | 42 | test_duplicate_anesthesia_line_counted_once_across_bill_and_eob | signature | 2026-10-26 | def test_duplicate_anesthesia_line_counted_once_across_bill_and_eob(): |
| tests/test_sheet_checks.py | 43 | test_duplicate_anesthesia_line_counted_once_across_bill_and_eob | code | 2026-10-26 |     bill = doc("S1", DocKind.HOSPITAL_STATEMENT, provider="Sample Anesthesia Group", patient_balance=Decimal("1100"), |
| tests/test_sheet_checks.py | 46 | test_duplicate_anesthesia_line_counted_once_across_bill_and_eob | code | 2026-10-26 |     found = sheet_checks.duplicates(make(bill, eob)) |
| tests/test_sheet_checks.py | 47 | test_duplicate_anesthesia_line_counted_once_across_bill_and_eob | code | 2026-10-26 |     assert kinds(found) == [Kind.E2] |
| tests/test_sheet_checks.py | 49 | test_duplicate_anesthesia_line_counted_once_across_bill_and_eob | code | 2026-10-26 |     assert {e.doc_id for e in found[0].evidence} == {"S1", "S2"} |
| tests/test_sheet_checks.py | 52 | test_same_code_on_different_days_is_not_a_duplicate | signature | 2026-10-26 | def test_same_code_on_different_days_is_not_a_duplicate(): |
| tests/test_sheet_checks.py | 61 | test_credit_in_parentheses_is_money_back | signature | 2026-10-26 | def test_credit_in_parentheses_is_money_back(): |
| tests/test_sheet_checks.py | 62 | test_credit_in_parentheses_is_money_back | code | 2026-10-26 |     bill = doc("S1", DocKind.HOSPITAL_STATEMENT, provider="Sample OB Group", patient_balance=Decimal("410.00"), |
| tests/test_sheet_checks.py | 71 | test_negative_balance_is_a_credit | signature | 2026-10-26 | def test_negative_balance_is_a_credit(): |
| tests/test_sheet_checks.py | 72 | test_negative_balance_is_a_credit | code | 2026-10-26 |     bill = doc("S1", DocKind.HOSPITAL_STATEMENT, patient_balance=Decimal("-40.00")) |
| tests/test_sheet_checks.py | 78 | test_eob_negatives_are_reversals_not_credits | signature | 2026-10-26 | def test_eob_negatives_are_reversals_not_credits(): |
| tests/test_sheet_checks.py | 80 | test_eob_negatives_are_reversals_not_credits | code | 2026-10-26 |     assert sheet_checks.credits(make(eob)) == [] |
| tests/test_sheet_checks.py | 83 | test_zero_balance_but_pay_this_amount | signature | 2026-10-26 | def test_zero_balance_but_pay_this_amount(): |
| tests/test_sheet_checks.py | 84 | test_zero_balance_but_pay_this_amount | code | 2026-10-26 |     bill = doc("S1", DocKind.HOSPITAL_STATEMENT, patient_balance=Decimal("0.00"), amount_due_coupon=Decimal("1385.00")) |
| tests/test_sheet_checks.py | 92 | test_newborn_codes_under_mothers_id | signature | 2026-10-26 | def test_newborn_codes_under_mothers_id(): |
| tests/test_sheet_checks.py | 93 | test_newborn_codes_under_mothers_id | code | 2026-10-26 |     eob = doc("S1", DocKind.EOB, member_ref="[MEMBER_1]", lines=[ |
| tests/test_sheet_checks.py | 106 | test_newborn_codes_under_babys_id_are_fine | signature | 2026-10-26 | def test_newborn_codes_under_babys_id_are_fine(): |
| tests/test_sheet_checks.py | 108 | test_newborn_codes_under_babys_id_are_fine | code | 2026-10-26 |     assert sheet_checks.baby_under_mother(make(eob)) == [] |
| tests/test_sheet_checks.py | 111 | test_missing_pages_of_one_statement | signature | 2026-10-26 | def test_missing_pages_of_one_statement(): |
| tests/test_sheet_checks.py | 120 | test_duplicate_extra_is_not_discounted_again | signature | 2026-10-26 | @needs_text |
| tests/test_sheet_checks.py | 121 | test_duplicate_extra_is_not_discounted_again | signature | 2026-10-26 | def test_duplicate_extra_is_not_discounted_again(): |
| tests/test_sheet_checks.py | 126 | test_duplicate_extra_is_not_discounted_again | code | 2026-10-26 |     assert e2.amount == Decimal("550.00") |
| tests/test_sheet_checks.py | 129 | test_duplicate_extra_is_not_discounted_again | code | 2026-10-26 |     assert r.total_may_come_off == Decimal("1017.50") |
| tests/test_sheet_checks.py | 148 | test_a_twin_line_read_without_a_date_still_makes_a_double | import | 2026-10-26 |     from datetime import date |
| tests/test_sheet_checks.py | 149 | test_a_twin_line_read_without_a_date_still_makes_a_double | import | 2026-10-26 |     from decimal import Decimal |
| tests/test_sheet_not_sent.py | 4 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_sheet_not_sent.py | 5 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_sheet_not_sent.py | 7 | (module) | import | 2026-10-26 | import pytest |
| tests/test_sheet_not_sent.py | 10 | (module) | import | 2026-10-26 | from billradar.checks import Finding, Kind, Report |
| tests/test_story.py | 6 | (module) | import | 2026-10-26 | import pytest |
| tests/test_story.py | 7 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_story.py | 9 | (module) | import | 2026-10-26 | from billradar import app as app_module |
| tests/test_table_rows.py | 4 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_table_rows.py | 5 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_trust.py | 13 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_trust.py | 14 | (module) | import | 2026-10-26 | from pathlib import Path |
| tests/test_trust.py | 16 | (module) | import | 2026-10-26 | import pytest |
| tests/test_trust.py | 17 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_trust.py | 19 | (module) | import | 2026-10-26 | from billradar import app as app_module |
| tests/test_trust.py | 22 | (module) | import | 2026-10-26 | from billradar.checks import Evidence, Finding, Kind |
| tests/test_trust.py | 123 | _make_case | code | 2026-10-26 |             "annual_income": "85000", "liquid_assets": "6000", "insured": "true", "mother_name": "Anna", |
| tests/test_verifier.py | 2 | (module) | import | 2026-10-26 | import json |
| tests/test_verifier.py | 4 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_verifier.py | 6 | (module) | import | 2026-10-26 | import pytest |
| tests/test_verifier.py | 7 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_verifier.py | 9 | (module) | import | 2026-10-26 | from billradar import app as app_module |
| tests/test_verifier.py | 10 | (module) | import | 2026-10-26 | from billradar import checks, pipeline, verifier, writer |
| tests/test_verifier.py | 11 | (module) | import | 2026-10-26 | from billradar.checks import Evidence, Kind |
| tests/test_verifier.py | 12 | (module) | import | 2026-10-26 | from billradar.meta_client import MetaClient |
| tests/test_verifier.py | 13 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_verifier.py | 14 | (module) | import | 2026-10-26 | from tests.test_writer import case |
| tests/test_verifier.py | 16 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), |
| tests/test_verifier.py | 17 | (module) | code | 2026-10-26 |                                 reason="run scripts/fetch_policies.py first") |
| tests/test_verifier.py | 20 | run_all | signature | 2026-10-26 | def run_all(c): |
| tests/test_verifier.py | 26 | test_clean_case_passes_the_checker | signature | 2026-10-26 | @needs_text |
| tests/test_verifier.py | 27 | test_clean_case_passes_the_checker | signature | 2026-10-26 | def test_clean_case_passes_the_checker(): |
| tests/test_verifier.py | 28 | test_clean_case_passes_the_checker | code | 2026-10-26 |     c = case() |
| tests/test_verifier.py | 32 | test_clean_case_passes_the_checker | code | 2026-10-26 |     assert v.ok, v.issues |
| tests/test_verifier.py | 36 | test_a_wrong_amount_is_caught_and_held_back | signature | 2026-10-26 | @needs_text |
| tests/test_verifier.py | 37 | test_a_wrong_amount_is_caught_and_held_back | signature | 2026-10-26 | def test_a_wrong_amount_is_caught_and_held_back(): |
| tests/test_verifier.py | 38 | test_a_wrong_amount_is_caught_and_held_back | code | 2026-10-26 |     c = case() |
| tests/test_verifier.py | 49 | test_a_wrong_amount_is_caught_and_held_back | code | 2026-10-26 |     assert Kind.F3 not in {f.kind for f in shown.findings} |
| tests/test_verifier.py | 55 | test_wrong_deadline_is_caught | signature | 2026-10-26 | @needs_text |
| tests/test_verifier.py | 56 | test_wrong_deadline_is_caught | signature | 2026-10-26 | def test_wrong_deadline_is_caught(): |
| tests/test_verifier.py | 57 | test_wrong_deadline_is_caught | code | 2026-10-26 |     c = case() |
| tests/test_verifier.py | 68 | test_evidence_must_exist | signature | 2026-10-26 | @needs_text |
| tests/test_verifier.py | 69 | test_evidence_must_exist | signature | 2026-10-26 | def test_evidence_must_exist(): |
| tests/test_verifier.py | 70 | test_evidence_must_exist | code | 2026-10-26 |     c = case() |
| tests/test_verifier.py | 79 | test_letters_with_made_up_amounts_tokens_or_promises_are_caught | signature | 2026-10-26 | @needs_text |
| tests/test_verifier.py | 80 | test_letters_with_made_up_amounts_tokens_or_promises_are_caught | signature | 2026-10-26 | def test_letters_with_made_up_amounts_tokens_or_promises_are_caught(): |
| tests/test_verifier.py | 81 | test_letters_with_made_up_amounts_tokens_or_promises_are_caught | code | 2026-10-26 |     c = case() |
| tests/test_verifier.py | 94 | test_wonder_review_is_read_only_and_never_sees_names | signature | 2026-10-26 | @needs_text |
| tests/test_verifier.py | 95 | test_wonder_review_is_read_only_and_never_sees_names | signature | 2026-10-26 | def test_wonder_review_is_read_only_and_never_sees_names(): |
| tests/test_verifier.py | 96 | test_wonder_review_is_read_only_and_never_sees_names | code | 2026-10-26 |     c = case() |
| tests/test_verifier.py | 99 | test_wonder_review_is_read_only_and_never_sees_names | code | 2026-10-26 |     assert body["model"] == "muse-wonder-1.0" and body["store"] is False |
| tests/test_verifier.py | 106 | test_wonder_review_is_read_only_and_never_sees_names | code | 2026-10-26 |         {"subject": "letter dispute", "verdict": "problem", "reason": "line 2 says 2,887.50"}]} |
| tests/test_verifier.py | 112 | test_wonder_review_is_read_only_and_never_sees_names.Fake.events | code | 2026-10-26 |                     {"type": "response.completed", "response": {"id": "r", "usage": {}}}] |
| tests/test_verifier.py | 115 | test_wonder_review_is_read_only_and_never_sees_names | code | 2026-10-26 |                               verifier.Verdict()) |
| tests/test_verifier.py | 124 | _saved_case | code | 2026-10-26 |     c = case() |
| tests/test_verifier.py | 129 | _saved_case | code | 2026-10-26 |     monkeypatch.setattr(app_module, "RUNS", tmp_path) |
| tests/test_verifier.py | 134 | test_reminder_calendar_file | signature | 2026-10-26 | @needs_text |
| tests/test_verifier.py | 135 | test_reminder_calendar_file | signature | 2026-10-26 | def test_reminder_calendar_file(tmp_path, monkeypatch): |
| tests/test_verifier.py | 137 | test_reminder_calendar_file | code | 2026-10-26 |     assert res.headers["content-type"].startswith("text/calendar") |
| tests/test_verifier.py | 205 | test_muse_wonder_review_runs_only_with_the_flag.Wonder.events | code | 2026-10-26 |             assert body["model"] == "muse-wonder-1.0" and body["store"] is False |
| tests/test_video.py | 115 | client_for | code | 2026-10-26 |     return MetaClient(transport=fake, record_to=None, journal=tmp_path / "requests.jsonl") |
| tests/test_voice_assist.py | 7 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_voice_assist.py | 9 | (module) | import | 2026-10-26 | import pytest |
| tests/test_voice_assist.py | 10 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_voice_assist.py | 12 | (module) | import | 2026-10-26 | from billradar import app as app_module |
| tests/test_voice_assist.py | 39 | client | signature | 2026-10-26 | @pytest.fixture |
| tests/test_voice_assist.py | 40 | client | signature | 2026-10-26 | def client(tmp_path, monkeypatch): |
| tests/test_voice_assist.py | 41 | client | code | 2026-10-26 |     monkeypatch.setattr(app_module, "RUNS", tmp_path) |
| tests/test_what_the_family_reads.py | 6 | (module) | import | 2026-10-26 | from datetime import date |
| tests/test_what_the_family_reads.py | 7 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_what_the_family_reads.py | 14 | (module) | import | 2026-10-26 | from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source |
| tests/test_what_the_family_reads.py | 15 | (module) | import | 2026-10-26 | from billradar.checks import Evidence, Finding, Kind |
| tests/test_what_the_family_reads.py | 34 | L | code | 2026-10-26 |     return Line(line_no=n, service_date=kw.pop("service_date", D), code=code, charges=Decimal(charges), |
| tests/test_what_the_family_reads.py | 45 | text_of | signature | 2026-10-26 | def text_of(letter: writer.Letter) -> str: |
| tests/test_what_the_family_reads.py | 46 | text_of | code | 2026-10-26 |     return " ".join(p.text for p in letter.paragraphs) |
| tests/test_writer.py | 1 | (module) | import | 2026-10-26 | import io |
| tests/test_writer.py | 2 | (module) | import | 2026-10-26 | import json |
| tests/test_writer.py | 3 | (module) | import | 2026-10-26 | import re |
| tests/test_writer.py | 4 | (module) | import | 2026-10-26 | from decimal import Decimal |
| tests/test_writer.py | 5 | (module) | import | 2026-10-26 | from pathlib import Path |
| tests/test_writer.py | 7 | (module) | import | 2026-10-26 | import pytest |
| tests/test_writer.py | 8 | (module) | import | 2026-10-26 | from fastapi.testclient import TestClient |
| tests/test_writer.py | 9 | (module) | import | 2026-10-26 | from pypdf import PdfReader |
| tests/test_writer.py | 11 | (module) | import | 2026-10-26 | from billradar import app as app_module |
| tests/test_writer.py | 13 | (module) | import | 2026-10-26 | from billradar.case import Case |
| tests/test_writer.py | 14 | (module) | import | 2026-10-26 | from billradar.policies import source |
| tests/test_writer.py | 16 | (module) | code | 2026-10-26 | FIX = Path(__file__).parent / "fixtures" / "cases" / "anna-birth.json" |
| tests/test_writer.py | 17 | (module) | code | 2026-10-26 | needs_text = pytest.mark.skipif( |
| tests/test_writer.py | 18 | (module) | code | 2026-10-26 |     not all(source.is_cached(p) for p in source.SOURCES) or not source.form_path("memorial-fef").exists(), |
| tests/test_writer.py | 19 | (module) | code | 2026-10-26 |     reason="run scripts/fetch_policies.py first") |
| tests/test_writer.py | 23 | (module) | code | 2026-10-26 |      "relationship": "Self", "employer": "Sample Bakery LLC"}, |
| tests/test_writer.py | 33 | case | signature | 2026-10-26 | def case(**changes) -> Case: |
| tests/test_writer.py | 35 | case | code | 2026-10-26 |     raw = json.loads(FIX.read_text()) |
| tests/test_writer.py | 37 | case | code | 2026-10-26 |     raw.update(changes) |
| tests/test_writer.py | 38 | case | code | 2026-10-26 |     return Case.model_validate(raw) |
| tests/test_writer.py | 41 | text_of | signature | 2026-10-26 | def text_of(letter: writer.Letter) -> str: |
| tests/test_writer.py | 42 | text_of | code | 2026-10-26 |     return " ".join(p.text for p in letter.paragraphs) |
| tests/test_writer.py | 47 | test_letters_for_the_demo_case | signature | 2026-10-26 | @needs_text |
| tests/test_writer.py | 48 | test_letters_for_the_demo_case | signature | 2026-10-26 | def test_letters_for_the_demo_case(): |
| tests/test_writer.py | 49 | test_letters_for_the_demo_case | code | 2026-10-26 |     c = case() |
| tests/test_writer.py | 65 | test_every_number_in_a_letter_comes_from_the_case | signature | 2026-10-26 | @needs_text |
| tests/test_writer.py | 66 | test_every_number_in_a_letter_comes_from_the_case | signature | 2026-10-26 | def test_every_number_in_a_letter_comes_from_the_case(): |
| tests/test_writer.py | 67 | test_every_number_in_a_letter_comes_from_the_case | code | 2026-10-26 |     c = case() |
| tests/test_writer.py | 80 | test_letters_cite_only_verified_quotes | signature | 2026-10-26 | @needs_text |
| tests/test_writer.py | 81 | test_letters_cite_only_verified_quotes | signature | 2026-10-26 | def test_letters_cite_only_verified_quotes(): |
| tests/test_writer.py | 82 | test_letters_cite_only_verified_quotes | code | 2026-10-26 |     c = case() |
| tests/test_writer.py | 90 | test_paragraph_with_unverified_quote_is_dropped | signature | 2026-10-26 | def test_paragraph_with_unverified_quote_is_dropped(monkeypatch): |
| tests/test_writer.py | 99 | test_account_numbers_stay_tokens_without_local_values | signature | 2026-10-26 | @needs_text |
| tests/test_writer.py | 100 | test_account_numbers_stay_tokens_without_local_values | signature | 2026-10-26 | def test_account_numbers_stay_tokens_without_local_values(): |
| tests/test_writer.py | 104 | test_account_numbers_stay_tokens_without_local_values | code | 2026-10-26 |     c = case() |
| tests/test_writer.py | 105 | test_account_numbers_stay_tokens_without_local_values | code | 2026-10-26 |     c.profile.local.tokens = {} |
| tests/test_writer.py | 110 | test_no_discount_or_dispute_letter_when_nothing_found | signature | 2026-10-26 | @needs_text |
| tests/test_writer.py | 111 | test_no_discount_or_dispute_letter_when_nothing_found | signature | 2026-10-26 | def test_no_discount_or_dispute_letter_when_nothing_found(): |
| tests/test_writer.py | 112 | test_no_discount_or_dispute_letter_when_nothing_found | code | 2026-10-26 |     c = case() |
| tests/test_writer.py | 121 | test_no_discount_or_dispute_letter_when_nothing_found | code | 2026-10-26 |     assert "apply-discount" not in kinds and "dispute" not in kinds |
| tests/test_writer.py | 124 | (module) | comment | 2026-10-26 | # --- the hospital form --------------------------------------------------------------------------- |
| tests/test_writer.py | 126 | test_memorial_form_is_filled_on_page_one_and_keeps_all_pages | signature | 2026-10-26 | @needs_text |
| tests/test_writer.py | 127 | test_memorial_form_is_filled_on_page_one_and_keeps_all_pages | signature | 2026-10-26 | def test_memorial_form_is_filled_on_page_one_and_keeps_all_pages(): |
| tests/test_writer.py | 128 | test_memorial_form_is_filled_on_page_one_and_keeps_all_pages | code | 2026-10-26 |     filled = forms.fill_memorial(case(demo=True)) |
| tests/test_writer.py | 133 | test_memorial_form_is_filled_on_page_one_and_keeps_all_pages | code | 2026-10-26 |                    "Baby Sample", "SAMPLE - FICTIONAL DATA"): |
| tests/test_writer.py | 135 | test_memorial_form_is_filled_on_page_one_and_keeps_all_pages | code | 2026-10-26 |     assert {"signature", "date", "witness", "spouse"} <= set(filled.left_for_you) |
| tests/test_writer.py | 138 | test_form_without_demo_flag_has_no_stamp | signature | 2026-10-26 | @needs_text |
| tests/test_writer.py | 139 | test_form_without_demo_flag_has_no_stamp | signature | 2026-10-26 | def test_form_without_demo_flag_has_no_stamp(): |
| tests/test_writer.py | 140 | test_form_without_demo_flag_has_no_stamp | code | 2026-10-26 |     page1 = PdfReader(io.BytesIO(forms.fill_memorial(case()).pdf)).pages[0].extract_text() |
| tests/test_writer.py | 141 | test_form_without_demo_flag_has_no_stamp | code | 2026-10-26 |     assert "FICTIONAL" not in page1 and "Anna Sample" in page1 |
| tests/test_writer.py | 154 | (module) | comment | 2026-10-26 | # --- routes -------------------------------------------------------------------------------------- |
| tests/test_writer.py | 156 | client | signature | 2026-10-26 | @pytest.fixture |
| tests/test_writer.py | 157 | client | signature | 2026-10-26 | def client(tmp_path, monkeypatch): |
| tests/test_writer.py | 159 | client | code | 2026-10-26 |     return TestClient(app_module.app), tmp_path |
| tests/test_writer.py | 162 | save | signature | 2026-10-26 | def save(tmp_path, c: Case, case_id: str = "w1"): |
| tests/test_writer.py | 170 | test_letter_and_form_routes | signature | 2026-10-26 | @needs_text |
| tests/test_writer.py | 191 | test_no_form_for_a_policy_without_one | signature | 2026-10-26 | @needs_text |
| tests/test_writer.py | 192 | test_no_form_for_a_policy_without_one | signature | 2026-10-26 | def test_no_form_for_a_policy_without_one(client): |
| billradar/web/static/brand/shield.png | 0 | (file) | binary file |  | (бинарный файл) |
| billradar/web/static/brand/wordmark.png | 0 | (file) | binary file |  | (бинарный файл) |
