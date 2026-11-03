"""Record the example on Meta's models: every request of the example pack that has no recording goes out live, once.

  MODEL_API_KEY=... BILLRADAR_LIVE=1 python scripts/record_example.py run             # sheets, reading, second read
  ... python scripts/record_example.py extras                                         # picture, translations, voice
  ... python scripts/record_example.py call                                           # the sample call, live, once

Live calls count against META_SPEND_CAP_USD like any other; the pack is fictional and goes out in private mode.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from billradar import (app, ask, bill_picture, call_assist, callprep, example, highlight, i18n, meta_client as mc, pipeline, voice,  # noqa: E402
                       web_answer, writer)
from billradar.case import Profile  # noqa: E402


class Fill(mc.MetaClient):
    """Replays what is recorded; only what is missing goes out."""

    def __init__(self):
        super().__init__()
        self.live_transport, self.replay = self.transport, mc.ReplayTransport()
        assert isinstance(self.live_transport, mc.LiveTransport), "needs MODEL_API_KEY and BILLRADAR_LIVE=1"

    def respond(self, body, label=""):
        self.transport = self.replay
        try:
            return super().respond(body, label)
        except mc.ReplayMissing:
            print("LIVE:", label)
            self.transport = self.live_transport
            return super().respond(body, label)

    def transcribe(self, request, audio, label=""):
        self.transport = self.replay
        try:
            return super().transcribe(request, audio, label)
        except mc.ReplayMissing:
            print("LIVE:", label)
            self.transport = self.live_transport
            return super().transcribe(request, audio, label)

    def image(self, request, label=""):
        self.transport = self.replay
        try:
            return super().image(request, label)
        except mc.ReplayMissing:
            print("LIVE:", label)
            self.transport = self.live_transport
            return super().image(request, label)


def run(client: Fill) -> pipeline.CaseRun:
    pack = example.PACK
    meta = json.loads((pack / "profile.json").read_text())
    photos = sorted(p for p in pack.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    return pipeline.run(client, [p.read_bytes() for p in photos], [(p.name, p.read_bytes()) for p in sorted(pack.glob("*.pdf"))],
                        Profile.model_validate(meta["profile"]), meta["policy_id"], meta.get("letterhead", ""),
                        date.fromisoformat(meta["today"]), example.EXAMPLE_ID, fictional=True, private=True)


QUESTIONS = ["Why was the anesthesia billed twice, and how much of it do I have to pay?",
             "What is the last day to apply for financial assistance?"]


def extras(client: Fill, r: pipeline.CaseRun) -> None:
    case, report = r.case, r.report
    case.demo = True
    bill_picture.render(client, case, report, "en")
    for letter in writer.all_letters(case, report):
        for lang in ("ru", "es"):
            i18n.letter(client, case, letter, lang)
    for lang in ("ru", "es"):
        i18n.findings(client, case, report, lang)
    samples = Path(app.VOICE_SAMPLES)
    tx = voice.transcribe_audio(client, (samples / "intake.wav").read_bytes(), "en")
    print("intake:", tx.text, voice.pick_chips(client, tx))
    for q in QUESTIONS:
        a = ask.answer(client, case, report, q)
        print("Q:", q, "| A:", a.text[:120], "| cites:", len(a.citations), "| refused:", a.refused)
    voiced(client, case, report, "hospital")
    appeal = example.run_appeal_example()
    voiced(client, appeal.case, appeal.report, "insurer")


def voiced(client: Fill, case, report, to: str) -> None:
    """What the sample buttons replay: the spoken question with its answer, the note after a call."""
    samples = Path(app.VOICE_SAMPLES)
    case.demo = True
    heard = voice.transcribe(client, case, (samples / "ask.wav").read_bytes(), "en")
    a = web_answer.ladder(client, case, report, heard.text[:500])
    print("ask:", heard.text, "| A:", a.text[:120], "| cites:", len(a.citations), "| refused:", a.refused)
    said = voice.transcribe(client, case, (samples / "note.wav").read_bytes(), "en")
    note = voice.read_note(client, case, said, who=callprep.build(case, report, to).who)
    print("note:", said.text, "|", note.rep_name, note.reference, note.promises)


def call(client: Fill, r: pipeline.CaseRun) -> None:
    """The synthetic call through the real stream: what the sample button replays afterwards."""
    from billradar import tavily_client
    r.case.demo = True
    key = os.environ["MODEL_API_KEY"]
    sheet = callprep.build(r.case, r.report, "hospital")
    pcm = app._sample_pcm()
    s = call_assist.CallSession(call_assist.LiveRealtime(key), client, r.case, sheet, "en", tavily=tavily_client.TavilyClient())
    s.they_agreed()
    started = time.monotonic()
    for u in s.run(call_assist.pcm_frames(pcm), key):
        if u.kind != "partial":
            print(f"{time.monotonic() - started:6.1f} s", u.kind, json.dumps(u.data)[:220])
    app._charge_call(mc.SpendLedger(), len(pcm))


def marks(client: Fill, r: pipeline.CaseRun) -> None:
    """One SAM call per finding with a sum on a sheet: what the example's marked sheets replay."""
    with tempfile.TemporaryDirectory() as tmp:
        pipeline.save(r, Path(tmp))
        for m in highlight.marks(client, r.case, r.report, Path(tmp) / "sheets", Path(tmp) / "sent-sheets"):
            print(m.index, m.kind, m.doc_id, m.line_no, m.value, m.box, len(m.outline), m.by)


def main(argv: list[str]) -> int:
    client = Fill()
    r = run(client)
    print("sheets", len(r.sheets), "findings", [(f.kind.value, str(f.amount)) for f in r.report.findings],
          "total", r.report.total_may_come_off, "apply_by", r.report.apply_by)
    if argv[:1] == ["extras"]:
        extras(client, r)
    if argv[:1] == ["call"]:
        call(client, r)
    if argv[:1] == ["marks"]:
        marks(client, r)
    print("calls", len(client.calls), "spent $%.4f" % mc.SpendLedger().spent())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
