import dataclasses
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from billradar import checks, fpl, policy
from billradar.case import Case, parse_date, parse_money
from billradar.checks import Kind
from billradar.policies import source

FIX = Path(__file__).parent / "fixtures" / "cases"
needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES),
                                reason="run scripts/fetch_policies.py first")


def _key(part: str):
    return int(part) if part.isdigit() else part


def load(name: str, **changes) -> Case:
    """A fixture case with dotted-path edits ("documents.1.lines.0.patient_responsibility"), applied before validation.

    A None value removes the field. Amounts are passed as strings, as they are printed in the fixture."""
    raw = json.loads((FIX / f"{name}.json").read_text())
    for path, value in changes.items():
        *parents, last = path.split(".")
        node = raw
        for part in parents:
            node = node[_key(part)]
        if value is None:
            del node[_key(last)]
        else:
            node[_key(last)] = value
    return Case.model_validate(raw)


def by_kind(report, kind):
    """The findings shown to the family (not worth-asking, no-money or held-back) of one kind, in report order."""
    return [f for f in report.findings if f.kind == kind]



@pytest.mark.parametrize("text,expected", [
    ("$3,215.40", Decimal("3215.40")),
    ("(312.40)", Decimal("-312.40")),
    ("-$12", Decimal("-12.00")),
    ("1,240.00 CR", Decimal("-1240.00")),
    ("", None),
    ("N/A", None),
    ("1.2.3", None),
])
def test_parse_money(text, expected):
    assert parse_money(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("2025-08-11", date(2025, 8, 11)),
    ("8/11/2025", date(2025, 8, 11)),  # month first, as printed in the US
    ("May 19", None),  # no year
    ("2026-02-30", None),  # no such day
])
def test_parse_date_never_guesses(text, expected):
    assert parse_date(text) == expected


def test_fpl_2026():
    assert fpl.guideline(4) == Decimal(33000)
    assert fpl.guideline(8) == Decimal(55720)
    assert fpl.guideline(10) == Decimal(67080)  # 55720 + 2 x 5680
    assert fpl.percent_of_guideline(Decimal(85000), 4) == Decimal("257.6")  # 85000 / 33000 = 257.57...



# --- policy quotes ----------------------------------------------------------------------------


def test_policy_list_has_both_hospitals():
    assert {"memorial-2026-05", "baptist-2026-09"} <= set(policy.available())


@needs_text
@pytest.mark.parametrize("policy_id", policy.available())
def test_every_policy_quote_is_on_its_page(policy_id):
    fragments = policy.load(policy_id).fragments
    assert fragments
    results = [policy.verify_fragment(frag) for frag in fragments.values()]
    wrong = [f"{r.ref}: {r.detail}" for r in results if not r.found]
    assert not wrong, wrong


@pytest.mark.parametrize("pct,discount", [("200.0", 100), ("250.9", 90), ("257.6", 85), ("400.0", 83), ("401.0", None)])
def test_memorial_tiers(pct, discount):
    tier = policy.load("memorial-2026-05").tier_for(Decimal(pct))
    assert (tier.discount_pct if tier else None) == discount


@needs_text
def test_quote_check_catches_wrong_page():
    window = policy.load("memorial-2026-05").fragment("window")
    assert policy.verify_fragment(window).found  # the real page is 5
    check = policy.verify_fragment(dataclasses.replace(window, page=2))
    assert not check.found
    assert check.found_on_page == 5
    assert check.detail == "quote is on page 5, not 2"


@needs_text
def test_quote_check_rejects_a_made_up_quote():
    fake = policy.Fragment("memorial-2026-05", "fake", 5, "Patients get free ice cream every Tuesday.")
    check = policy.verify_fragment(fake)
    assert not check.found
    assert check.found_on_page is None


# --- the demo case ----------------------------------------------------------------------------


@needs_text
def test_anna_birth_case():
    r = checks.run(load("anna-birth"))
    assert r.fpl_pct == Decimal("257.6")
    assert sorted(f.kind for f in r.findings) == [Kind.E1, Kind.F2, Kind.F3]

    (e1,) = by_kind(r, Kind.E1)
    assert e1.math["difference"] == "312.40"
    assert e1.amount == Decimal("46.86")  # 312.40 x 676.80 / 4512.00: S1 already has the 85% discount

    (f3,) = by_kind(r, Kind.F3)
    assert f3.amount == Decimal("1054.00")  # 85% of the baby's 1,240.00
    assert {e.doc_id for e in f3.evidence} == {"S1", "S2"}

    (f2,) = by_kind(r, Kind.F2)
    assert f2.deadline == date(2026, 9, 2)  # 12 months after the insurance payment of 2025-09-02
    assert f2.math[checks.FEDERAL_RULE] == "2026-04-08"

    assert r.total_may_come_off == Decimal("1100.86")  # 46.86 + 1054.00
    assert r.held_back == []
    assert [n.title for n in r.no_money] == ["Sheet 1 line 1 matches your insurance statement",
                                             "Sheet 2 line 1 matches your insurance statement"]
    assert [[(e.doc_id, e.line_no) for e in n.evidence] for n in r.no_money] == [[("S1", 1), ("S4", 1)], [("S2", 1), ("S6", 1)]]


@needs_text
def test_baptist_does_not_cover_insured_balances():
    r = checks.run(load("anna-birth", policy_id="baptist-2026-09"))
    for kind in (Kind.F1, Kind.F3, Kind.F2):
        assert by_kind(r, kind) == []
    (e1,) = by_kind(r, Kind.E1)  # the mismatch with the insurer is real under any policy
    assert e1.math["difference"] == "312.40"
    stops = [n for n in r.no_money if n.policy_refs == ["baptist-2026-09#uninsured-only"]]
    assert len(stops) == 1


@needs_text
def test_free_care_level_asks_about_savings():
    r = checks.run(load("anna-birth", **{"profile.annual_income": "60000", "profile.liquid_assets": "25000"}))
    assert r.fpl_pct == Decimal("181.8")  # the 100% level
    assert by_kind(r, Kind.F3) == []
    assert any("savings" in n.title for n in r.no_money)


@needs_text
def test_income_above_policy_limit():
    r = checks.run(load("anna-birth", **{"profile.annual_income": "200000"}))
    assert r.fpl_pct == Decimal("606.1")  # above the 400% top tier
    assert by_kind(r, Kind.F3) == []
    assert any("above this policy's limit" in n.title for n in r.no_money)


@needs_text
def test_income_cap_adds_a_finding():
    big = "80000.00"
    r = checks.run(load("anna-birth", **{
        "profile.annual_income": "129000",
        "documents.1.patient_balance": big,
        "documents.1.lines.0.patient_responsibility": big,
        "documents.4.lines.0.patient_responsibility": big,
    }))
    assert r.fpl_pct == Decimal("390.9")  # the 83% tier
    (capped,) = [f for f in r.findings if "Capped" in f.title]
    assert capped.math["cap"] == "12900.00"  # 10% of 129000


@needs_text
def test_no_discount_anywhere_is_f1_on_each_bill():
    r = checks.run(load("anna-birth", **{"documents.0.fa_discount": None, "documents.0.patient_balance": "4512.00"}))
    f1 = by_kind(r, Kind.F1)
    assert [f.evidence[0].doc_id for f in f1] == ["S1", "S2"]
    assert by_kind(r, Kind.F3) == []
    (e1,) = by_kind(r, Kind.E1)
    assert e1.amount == Decimal("312.40")  # no discount to take its share first
    assert f1[0].amount == Decimal("3569.66")  # 85% of 4512.00 - 312.40 = 4199.60


@needs_text
def test_small_balances_under_memorial_minimum():
    r = checks.run(load("anna-birth", **{
        "documents.0.patient_balance": "120.00",
        "documents.1.patient_balance": "170.00",
        "documents.1.lines.0.patient_responsibility": "170.00",
        "documents.4.lines.0.patient_responsibility": "170.00",
    }))
    assert by_kind(r, Kind.F3) == []
    assert any("minimum" in n.title for n in r.no_money)


def test_unverified_quote_is_held_back(monkeypatch):
    monkeypatch.setattr(policy, "verified", lambda ref: not ref.startswith("memorial"))
    r = checks.run(load("anna-birth"))
    assert {f.kind for f in r.findings} == {Kind.E1}
    assert {f.kind for f in r.held_back} == {Kind.F3, Kind.F2}
    assert all("[held back: unverified memorial-2026-05#" in f.detail for f in r.held_back)
    assert r.total_may_come_off == Decimal("46.86")  # only the E1 sum is shown


@needs_text
def test_guideline_year_comes_from_the_policy_not_from_today():
    r = checks.run(load("anna-birth", today="2025-04-21"))  # no 2025 table: the policy says 2026
    assert r.fpl_pct == Decimal("257.6")


def test_finding_and_profile_contract_defaults():
    from billradar.case import Profile
    from billradar.checks import Finding, Kind

    f = Finding(kind=Kind.E1, title="t", detail="d")
    assert (f.severity, f.confidence, f.laws, f.explain) == (None, None, [], None)
    g = Finding(kind=Kind.E1, title="t", detail="d", severity="borderline", confidence=0.4,
                laws=["federal-501r#application-period"], explain="plain words")
    assert Profile(household_size=1, annual_income=1).context == []


def test_an_account_billed_by_a_doctors_office_is_not_the_hospitals():
    """S12 prints the hospital as the place of service, S13 of the same account is the OB/GYN office's coupon."""
    from billradar.case import Document, DocKind, Source
    from billradar.checks import one_office_per_account
    Document = __import__("functools").partial(Document, source=Source.PAPER)
    a = Document(doc_id="S12", kind=DocKind.HOSPITAL_STATEMENT, provider="Seaside Regional Hospital (IP) 300", account_ref="[ACCT_9]")
    b = Document(doc_id="S13", kind=DocKind.HOSPITAL_STATEMENT, provider="300_Women First OB/GYN Care, LLC", account_ref="[ACCT_9]")
    c = Document(doc_id="D1", kind=DocKind.HOSPITAL_STATEMENT, provider="Seaside Regional Hospital", account_ref="[ACCT_1]")
    out = one_office_per_account([a, b, c], "Seaside Regional Hospital")
    assert [d.provider for d in out] == [b.provider, b.provider, c.provider]  # the hospital's own account stays
