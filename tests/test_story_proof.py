"""What the home page's episodes prove comes from the report: real sheet numbers, the report's own titles, a real
quote of the policy. Nothing here is drawn by hand."""

from decimal import Decimal

from billradar import checks, view
from billradar.checks import Evidence, Finding, Kind
from tests.test_writer import case


def finding(kind, title, sheets, **kw):
    return Finding(kind=kind, title=title, detail="d", evidence=[Evidence(doc_id=s) for s in sheets], **kw)


def report_with(*findings, worth=()):
    r = checks.run(case())
    return r.model_copy(update={"findings": list(findings), "worth_asking": list(worth), "no_money": []})


def f1(policy_ref):
    return finding(Kind.F1, "You likely qualify", ["S4"], amount=Decimal("100"), policy_refs=[policy_ref])


def real_ref():
    r = checks.run(case())
    return next(ref for f in r.findings for ref in f.policy_refs if ref.startswith("memorial"))


def test_the_link_joins_the_two_real_sheets():
    p = view.story_proof(case(), report_with(finding(Kind.B1, "Baby billed under mom", ["S2", "S3"]),
                                             finding(Kind.B2, "No statement for the baby", ["S14"])))
    assert p["link"] == {"a": {"sheet": "S2", "box": None}, "b": {"sheet": "S14", "box": None}, "label": "Baby billed under mom"}


def test_no_letter_finding_no_link():
    assert "link" not in view.story_proof(case(), report_with(finding(Kind.B1, "Baby billed under mom", ["S2", "S3"])))


def test_no_baby_finding_no_link():
    assert "link" not in view.story_proof(case(), report_with(finding(Kind.E2, "Billed twice", ["S10"])))


def test_the_review_lists_real_findings_in_the_frames_order_then_one_worth_asking():
    p = view.story_proof(case(), report_with(f1(real_ref()), finding(Kind.E2, "Billed twice", ["S10"]),
                                             finding(Kind.B1, "Baby billed under mom", ["S2"]),
                                             worth=[finding(Kind.I1, "Ask for pages 2-4", ["D2"])]))
    assert [(x["title"], x["verdict"]) for x in p["review"]] == [
        ("Billed twice", "confirmed"), ("Baby billed under mom", "confirmed"), ("You likely qualify", "confirmed"),
        ("Ask for pages 2-4", "worth")]
    assert p["review"][0]["sheets"] == ["S10"]


def test_the_quote_is_the_policys_own_words():
    ref = "memorial-2026-05#insured-balances"
    p = view.story_proof(case(), report_with(f1(ref)))
    from billradar import writer
    src = writer.source_of(ref)
    assert p["quote"] == {"text": src["quote"], "title": src["title"], "url": src["url"]}


def test_sheet_ids_are_the_papers_of_the_case_in_order():
    c = case()
    p = view.story_proof(c, report_with())
    assert p["sheet_ids"] == [d.doc_id for d in c.documents if d.source.value == "paper"]


def test_the_quote_is_a_whole_sentence_without_the_real_hospitals_name():
    """A fictional hospital on screen: a quote naming the real one beside it would confuse."""
    refs = ["memorial-2026-05#scale-mrh", "memorial-2026-05#insured-balances"]
    p = view.story_proof(case(), report_with(finding(Kind.F1, "You likely qualify", ["D1"], amount=Decimal("100"), policy_refs=refs)))
    assert p["quote"]["text"].startswith("This means all uninsured patient responsibility amounts") and "Memorial" not in p["quote"]["text"]
