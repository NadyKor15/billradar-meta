# BillRadar

BillRadar reads the whole pile of hospital bills and insurance statements from a photo or a short video of the table, and finds what a family shouldn't have to pay: billing errors and missed hospital financial assistance. Built on Meta's models for the Meta Global AI Developer Hackathon, Indie track.

All bills, statements and people in this repository are fictional. No real patient data has been sent to any model. BillRadar helps with bills and insurance statements; it is not medical or legal advice. You review and sign every letter, and only you send anything.

Before the hackathon started on October 26 at 12:24 PM ET, there was the idea, the name, the logo, research on laws and hospitals, early code drafts from that morning, and a Telegram bot that is not part of this project. During the hackathon the code was rewritten. By `git blame -w -C -C`, 2,020 of 44,972 Python lines (4.5%) still trace back to the morning drafts (11:20 AM to 12:19 PM ET), mostly imports, function signatures and field names; 755 of them (1.7%) are logic. The full list is in `docs/RESIDUE.md`. The code was written with an AI coding agent.

This repository was assembled on November 3, 2026 from our private working repository, so that it holds only the hackathon's code, without an earlier project or any private data. We can show the full history on request.

## How it works

1. Lay the paper sheets on a table and take a photo, or film the pile sheet by sheet. Add PDFs from the hospital portal.
2. **SAM 3.1** finds every sheet on the photo; on a video it follows each sheet through the clip. Before you press Send, only a heavily blurred copy with no readable text goes to Meta's SAM 3.1, to find the sheets. The sheets themselves go only when you press Send. PDF pages never go to SAM. The photo and the video stay on your computer, and the sheets are cut from them here.
3. **On your computer**, Muse Glimmer reads every printed piece of every sheet. A rule then decides what may leave: a line opens only when its shape is a date of service, a billing code, an amount or plain billing wording, and everything else is closed. Your family's names, IDs, addresses, phone numbers and account numbers become tokens (`[PATIENT_1]`, `[ACCT_1]`). The names of doctors and hospitals stay open, because matching a bill to its insurance statement and addressing a letter need them. A sheet that still shows something private, or lost a sum, stays on your computer, and the case asks you to photograph it again.
4. **Muse Spark** reads every sheet and file in one request and links them: whose bill, which claim, which line. It reads twice, in a different order. The text read on your computer settles where the two readings differ, and what stays open gets a third read of that sheet alone.
5. **Code** does the math against the hospital's own public financial assistance policy and the federal rules. Every rule is tied to a quote from its source page, and the quote is checked against that page before a finding is shown.
6. **A separate code checker** recomputes every amount and date from the sheets and holds back what it can't confirm. Then **Muse Wonder** reads the whole case again, read-only. A finding it doubts is not hidden; it moves to "worth asking about" without a dollar amount.
7. The case screen shows each finding with the sheet and line behind it, the letters to sign, the hospital's real form filled in, what the models were sent, and a receipt: which model ran each step and what it cost.

After that:

- **Questions** about the case are answered only with a quote found on a sheet, by voice in English or Spanish too. When the papers don't hold the answer, BillRadar looks on official sites and quotes them.
- **Calls:** a cheat sheet for the call, and with everyone's consent, a live helper that picks prepared answers while you talk. A voice note after the call goes into the next letter.
- **Appeals:** on a copy of an insurer's portal, Muse Spark filled in the appeal form in a recorded run and stopped before Send. Only your press of Send lets it submit; that step ran live on its own, on a form filled by code.
- **Your hospital's policy:** for a hospital not in the checked base, Tavily finds the policy on that hospital's own site. Tavily is used only as web search on hospital sites and official pages, for the hospital's policy and for answers the papers don't hold; it is not a model, and every answer it backs is a sentence copied from the page. Muse Spark copies the income tiers, and code keeps a tier only if its quote and its numbers are in the policy's text.
- **Other AI agents** can call BillRadar as a tool over MCP and A2A (`/mcp`, `/a2a`, `/.well-known/agent-card.json`; see `/agents` in the app and [docs/AGENTS.md](docs/AGENTS.md)).

## Which model does what

| Step | Model | What it does here |
|---|---|---|
| Cover the family's names, IDs, addresses and account numbers before anything leaves | Muse Glimmer, open weights, on your computer (llama.cpp) | reads every printed piece of every sheet; a rule in code decides what may open, the rest stays covered, and you can look at every covered sheet before it is sent |
| Find the sheets on a photo, follow them through a video | `sam-3.1` | sheets by text prompt, one request for a photo, the blurred copy for a video |
| Read every sheet and file | `muse-spark-1.3` | all of them in one request, strict JSON schema |
| Count money and dates | none (plain code) | a model never decides whether there is money |
| Second read of the case | `muse-wonder-1.0` | read-only; a doubt lowers a finding, code decides what is held back |
| Questions, translations of letters, the appeal form, the call helper | `muse-spark-1.3` | every number and quote is checked by code against the papers |
| Spoken questions and notes after a call | `muse-voice-transcribe-1.0` | English and Spanish |
| The case as one picture | `muse-image-1.0` | the numbers on it are written by code, and Meta's label stays in the file |
| Web search, not a model | Tavily | only on hospital sites and official pages; every answer is a sentence copied from the page, checked by code |

BillRadar marks the exact line on the photo: code finds the row on your computer and SAM 3.1 confirms it on the covered sheet.

## Proof that the models ran

Every request is written to `runs/requests.jsonl` with the model, the response id, token usage and the cost. Images are never written there. The recorded answers in `tests/fixtures/recordings/` replay the same runs without a key, and the example case replays them.

## What it finds

| Class | What |
|---|---|
| F1 | The household qualifies under the hospital's policy, but no discount is on the bill |
| F2 | The last day to apply, counted from the first bill after discharge (policy + federal rule) |
| F3 | The discount is on the mother's bill but not on the baby's, same stay |
| E1 | A bill line asks more than the insurance statement says the patient owes |
| E2 | The same service billed twice |
| E3 | A credit or overpayment left on the account |
| E4 | One sheet asks two different amounts |
| B1 | Newborn care billed under the mother's insurance ID |
| P1 | Pages missing from a statement |

It also writes honest "checked, no money here" notes, for example when a line matches the insurance statement or the income is above the policy's limit.

## Run it

```sh
uv venv --python 3.12 && uv pip install -e ".[dev]"
python scripts/fetch_policies.py        # public policies and the blank form -> .cache/ (not committed)
pytest
uvicorn billradar.app:app                # http://127.0.0.1:8000/example (replayed, no key)
```

Live calls:

```sh
MODEL_API_KEY=...              # dev.meta.ai -> API keys; never commit it
BILLRADAR_LIVE=1               # without it, recorded answers are replayed and a missing recording is an error
META_SPEND_CAP_USD=5           # hard stop for live spend: each call reserves its worst case before it is sent
BILLRADAR_SECOND_READ=1        # the second reading of every sheet
BILLRADAR_WONDER_REVIEW=1      # the second read on Muse Wonder
```

Live calls run only on packs marked fictional. Real papers stay off the models until the covering on your computer, its test and the owner's yes are all in place.

Reading a pile on your own computer needs Muse Glimmer, Meta's open-weight model, and `llama-server` from llama.cpp: about 20 GB of weights in `~/Models/Muse-Glimmer-30B-GGUF` (`BILLRADAR_GLIMMER_DIR`) and about 32 GB of free memory. On an Apple M5 Max a pile of 14 sheets took 22 to 31 minutes. Without them the private path stops and nothing is sent; the examples do not need them.

Command line: `billradar run <pack-dir>` runs the whole pipeline on a pack (photos, PDFs, `profile.json`).

## What it can't do yet

- The appeal agent works on a copy of a portal, not on a real insurer's site. Filling the form and sending it have each run live, but not yet in one go.
- The live call helper has run on a sample call, not on a real call with a microphone.
- The call helper answers only the objections prepared for the case; a deadline the office states is not checked against the policy during the call yet.
- Household income printed on an assistance letter is not covered yet.
- When the same charge is asked twice on two different sheets, the dispute letter can still name the two lines as if they were on one sheet.
- SAM 3.1 follows up to 16 sheets in one request, so a longer video goes in pieces.
- Private mode sends PDF pages as covered images; reading them is less exact than the text layer.
- A hospital whose policy can't be confirmed word for word gets a link and a request to check it yourself, not tiers.

## Sources in the repo

| Source | From |
|---|---|
| Memorial Healthcare System, Financial Assistance Policy, revised May 2026 | mhs.net (public PDF) |
| Memorial Financial Evaluation Form 2310-10040 | mhs.net (public PDF), filled only on your computer |
| Baptist Health South Florida, BHSF-355.14, revised 09/29/2026 | baptisthealth.net (public PDF) |
| 26 CFR 1.501(r)-1, application period | eCFR |
| Florida Statutes 395.301 (itemized statement, billing disputes) | leg.state.fl.us |

We store short quotes and page numbers, not the documents. Estimates follow the published policy; the hospital decides.

Licenses: this code is Apache-2.0 ([LICENSE](LICENSE)). The Noto Sans fonts are under the SIL Open Font License (`billradar/fonts/OFL.txt`).
