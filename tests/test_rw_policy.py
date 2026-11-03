"""Current behaviour of billradar/policy.py: tiers, fragments, loading, the policy list and the quote check.

Temporary policies and page text are made up for the test; the real files are only read.
"""

import decimal
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from billradar import policy
from billradar.policies import source
from billradar.policy import Fragment, Policy, QuoteCheck, Tier

needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES),
                                reason="policy text not downloaded: run scripts/fetch_policies.py")

MEMORIAL = "memorial-2026-05"
BAPTIST = "baptist-2026-09"
STATUTE = "fl-95-11"
ALL_POLICIES = [BAPTIST, "erisa-2560-503-1", "federal-501r", "federal-501r-4", "federal-501r-5", "federal-501r-6",
                "fl-395-301", STATUTE, MEMORIAL, "nsa-149-410", "nsa-149-420", "nsa-149-610", "nsa-149-620"]

MADE_UP = "test-policy"
URL = "https://example.org/policy.pdf"
RULE = "Patients may apply."


def ladder(*tiers: Tier) -> Policy:
    return Policy("p", "Hospital", "Policy", URL, {}, tiers=list(tiers))


def fragment(quote: str = RULE, page: int = 2) -> Fragment:
    return Fragment(MADE_UP, "rule", page, quote)


@pytest.fixture
def clean_caches():
    policy.load.cache_clear()
    policy.verified.cache_clear()
    yield
    policy.load.cache_clear()
    policy.verified.cache_clear()


@pytest.fixture
def policy_dir(tmp_path, monkeypatch, clean_caches):
    folder = tmp_path / "policies"
    folder.mkdir()
    monkeypatch.setattr(policy, "POLICY_DIR", folder)
    return folder


def write_policy(folder, name: str = MADE_UP, **fields) -> None:
    raw = {"policy_id": name, "hospital": "Hospital", "title": "Policy", "url": URL,
           "fragments": {"rule": {"page": 2, "quote": RULE}}} | fields
    (folder / f"{name}.json").write_text(json.dumps(raw), encoding="utf-8")


@pytest.fixture
def downloaded(tmp_path, monkeypatch, clean_caches):
    """`downloaded("page one", "page two")`: the made-up policy's text is on disk with these pages."""
    cache = tmp_path / "text"
    cache.mkdir()
    monkeypatch.setattr(source, "CACHE", cache)
    monkeypatch.setitem(source.SOURCES, MADE_UP, source.PolicySource(MADE_UP, "Hospital", URL))

    def put(*sheets: str) -> None:
        (cache / f"{MADE_UP}.pdf").write_bytes(b"")
        reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda t=t: t) for t in sheets])
        monkeypatch.setattr(source, "PdfReader", lambda path: reader)
    return put


# --- Policy.tier_for ------------------------------------------------------------------------

@pytest.mark.parametrize("percent, tier", [
    ("-5", Tier(200, 100, "tier-200")),
    ("0", Tier(200, 100, "tier-200")),
    ("200.9", Tier(200, 100, "tier-200")),
    ("201", Tier(250, 90, "scale-mrh")),
    ("250.4", Tier(250, 90, "scale-mrh")),
    ("251", Tier(300, 85, "scale-mrh")),
    ("300.9", Tier(300, 85, "scale-mrh")),
    ("301", Tier(350, 83, "scale-mrh")),
    ("350.9", Tier(350, 83, "scale-mrh")),
    ("351", Tier(400, 83, "scale-mrh")),
    ("400.9", Tier(400, 83, "scale-mrh")),
])
def test_memorial_tier_is_the_first_ceiling_at_or_above_the_whole_percent(percent, tier):
    assert policy.load(MEMORIAL).tier_for(Decimal(percent)) == tier


@pytest.mark.parametrize("percent", ["401.9", "402", "100000", "1E+3"])
def test_memorial_has_no_tier_above_its_last_ceiling(percent):
    assert policy.load(MEMORIAL).tier_for(Decimal(percent)) is None


@pytest.mark.parametrize("percent, tier", [
    ("200.9", Tier(200, 100, "levels")),
    ("201", Tier(300, 100, "levels")),
    ("300.9", Tier(300, 100, "levels")),
    ("301", None),
])
def test_baptist_tiers_end_at_300_percent(percent, tier):
    assert policy.load(BAPTIST).tier_for(Decimal(percent)) == tier


def test_a_law_without_tiers_gives_no_tier():
    assert policy.load(STATUTE).tier_for(Decimal("100")) is None


def test_a_policy_with_no_tiers_gives_no_tier():
    assert ladder().tier_for(Decimal("0")) is None


def test_listed_order_decides_even_when_the_ceilings_are_not_sorted():
    high, low = Tier(400, 50, "high"), Tier(200, 100, "low")
    assert ladder(high, low).tier_for(Decimal("100")) is high


def test_of_two_tiers_with_one_ceiling_the_first_listed_wins():
    first, second = Tier(300, 85, "first"), Tier(300, 80, "second")
    assert ladder(first, second).tier_for(Decimal("300")) is first


def test_the_returned_tier_is_the_policys_own_object():
    pol = policy.load(MEMORIAL)
    assert pol.tier_for(Decimal("225")) is pol.tiers[1]


def test_a_negative_percent_loses_its_fraction_toward_zero():
    pol = ladder(Tier(-1, 10, "minus-one"), Tier(0, 20, "zero"))
    assert pol.tier_for(Decimal("-1.5")).fragment == "minus-one"
    assert pol.tier_for(Decimal("-0.9")).fragment == "zero"


@pytest.mark.parametrize("percent, name", [(250, "b"), (250.9, "b"), ("250", "b"), (True, "a"), (Decimal("2.5E+2"), "b")])
def test_anything_int_can_read_is_accepted_as_a_percent(percent, name):
    pol = ladder(Tier(200, 100, "a"), Tier(250, 90, "b"))
    assert pol.tier_for(percent).fragment == name


@pytest.mark.parametrize("percent, error", [
    (Decimal("NaN"), ValueError),
    (Decimal("sNaN"), ValueError),
    (Decimal("Infinity"), OverflowError),
    (Decimal("-Infinity"), OverflowError),
    (float("nan"), ValueError),
    (float("inf"), OverflowError),
    ("250.4", ValueError),
    ("", ValueError),
    (None, TypeError),
    ([], TypeError),
])
@pytest.mark.parametrize("tiers", [[], [Tier(400, 100, "a")]])
def test_a_percent_that_is_no_number_raises_even_without_tiers(percent, error, tiers):
    with pytest.raises(error):
        ladder(*tiers).tier_for(percent)


# --- Policy.fragment ------------------------------------------------------------------------

def test_fragment_returns_the_stored_fragment():
    window = policy.load(MEMORIAL).fragment("window")
    assert window == Fragment(MEMORIAL, "window", 5, "Patients or responsible parties can apply for financial assistance "
                              "for up to one year after the date of service or twelve months after last insurance payment.")
    assert window is policy.load(MEMORIAL).fragments["window"]


def test_fragment_works_on_a_policy_built_by_hand():
    stored = fragment()
    pol = Policy("p", "Hospital", "Policy", URL, {"rule": stored})
    assert pol.fragment("rule") is stored


@pytest.mark.parametrize("missing", ["nope", "Window", "window ", "", f"{MEMORIAL}#window", None, 5])
def test_an_unknown_fragment_is_a_key_error_naming_it(missing):
    with pytest.raises(KeyError) as caught:
        policy.load(MEMORIAL).fragment(missing)
    assert caught.value.args == (missing,)


def test_a_list_as_fragment_id_is_a_type_error():
    with pytest.raises(TypeError):
        policy.load(MEMORIAL).fragment(["window"])


# --- load -----------------------------------------------------------------------------------

def test_memorial_loads_with_everything_it_prints():
    pol = policy.load(MEMORIAL)
    assert pol.policy_id == MEMORIAL
    assert pol.hospital == "Memorial Healthcare System (Memorial Regional Hospital, Hollywood FL)"
    assert pol.title == "Financial Assistance Policy, Revised May 2026"
    assert pol.url == "https://www.mhs.net/-/media/mhs/files/patients-and-visitors/financial-assistance/en/full-policy.pdf"
    assert pol.covers_insured_balances is True
    assert isinstance(pol.min_request_total, Decimal) and str(pol.min_request_total) == "500.00"
    assert isinstance(pol.liquid_assets_limit_for_free_care, Decimal)
    assert str(pol.liquid_assets_limit_for_free_care) == "10000.00"
    assert pol.income_cap_pct == 10
    assert pol.fpg_year == 2026
    assert pol.tiers == [Tier(200, 100, "tier-200"), Tier(250, 90, "scale-mrh"), Tier(300, 85, "scale-mrh"),
                         Tier(350, 83, "scale-mrh"), Tier(400, 83, "scale-mrh")]
    assert pol.window == {"after_service_days": 365, "after_last_insurance_payment_months": 12, "fragment": "window"}
    assert list(pol.fragments) == ["insured-balances", "min-request", "tier-200", "liquid-assets", "scale", "income-cap",
                                   "prior-accounts", "window", "facilities-only", "scale-mrh"]


def test_baptist_loads_as_a_policy_without_amount_limits():
    pol = policy.load(BAPTIST)
    assert pol.hospital == "Baptist Health South Florida (Baptist Hospital of Miami)"
    assert pol.covers_insured_balances is False
    assert pol.min_request_total is None
    assert pol.liquid_assets_limit_for_free_care is None
    assert pol.income_cap_pct is None
    assert pol.fpg_year == 2026
    assert pol.tiers == [Tier(200, 100, "levels"), Tier(300, 100, "levels")]
    assert pol.window == {"after_first_statement_days": 240, "after_ecas_notice_days": 30, "fragment": "window"}


def test_a_law_file_loads_with_the_defaults_for_what_it_does_not_say():
    pol = policy.load(STATUTE)
    assert pol.title == "Florida Statutes 95.11(4), 2026"
    assert pol.covers_insured_balances is True
    assert (pol.min_request_total, pol.liquid_assets_limit_for_free_care, pol.income_cap_pct, pol.fpg_year) == (None,) * 4
    assert pol.tiers == []
    assert pol.window == {}


@pytest.mark.parametrize("policy_id", ALL_POLICIES)
def test_fragments_keep_file_order_and_the_quote_byte_for_byte(policy_id):
    raw = json.loads((policy.POLICY_DIR / f"{policy_id}.json").read_text(encoding="utf-8"))
    loaded = policy.load(policy_id).fragments
    assert list(loaded) == list(raw["fragments"])
    for fragment_id, stored in raw["fragments"].items():
        assert loaded[fragment_id] == Fragment(policy_id, fragment_id, stored["page"], stored["quote"])


def test_loading_twice_gives_the_same_object():
    assert policy.load(MEMORIAL) is policy.load(MEMORIAL)


def test_an_unknown_policy_is_a_missing_file_and_a_later_file_is_picked_up(policy_dir):
    with pytest.raises(FileNotFoundError):
        policy.load(MADE_UP)
    write_policy(policy_dir)
    assert policy.load(MADE_UP).policy_id == MADE_UP


def test_the_folder_is_read_when_load_is_called(policy_dir):
    write_policy(policy_dir, title="From the folder of the moment")
    assert policy.load(MADE_UP).title == "From the folder of the moment"


def test_a_minimal_file_fills_in_the_defaults(policy_dir):
    write_policy(policy_dir)
    assert policy.load(MADE_UP) == Policy(MADE_UP, "Hospital", "Policy", URL, {"rule": Fragment(MADE_UP, "rule", 2, RULE)})


def test_every_field_of_a_full_file_is_taken_as_written(policy_dir):
    window = {"after_service_days": 90, "nested": {"fragment": "rule", "days": [1, 2]}}
    write_policy(policy_dir, covers_insured_balances=False, min_request_total="12.50",
                 liquid_assets_limit_for_free_care="0.00", income_cap_pct=7, fpg_year=2025,
                 tiers=[{"max_fpl_pct": 300, "discount_pct": 50, "fragment": "rule"},
                        {"max_fpl_pct": 100, "discount_pct": 90, "fragment": "rule"}], window=window)
    pol = policy.load(MADE_UP)
    assert pol.covers_insured_balances is False
    assert str(pol.min_request_total) == "12.50"
    assert str(pol.liquid_assets_limit_for_free_care) == "0.00"
    assert (pol.income_cap_pct, pol.fpg_year) == (7, 2025)
    assert pol.tiers == [Tier(300, 50, "rule"), Tier(100, 90, "rule")]
    assert pol.window == window


def test_zero_values_stay_zero_and_nulls_stay_none(policy_dir):
    write_policy(policy_dir, min_request_total="0", liquid_assets_limit_for_free_care=None, income_cap_pct=0, fpg_year=None,
                 tiers=[], window={})
    pol = policy.load(MADE_UP)
    assert isinstance(pol.min_request_total, Decimal) and pol.min_request_total == 0
    assert pol.liquid_assets_limit_for_free_care is None
    assert pol.income_cap_pct == 0
    assert pol.fpg_year is None


@pytest.mark.parametrize("number, expected", [(500, Decimal("500")), (0.1, Decimal(0.1)), (0, Decimal("0"))])
def test_an_amount_written_as_a_json_number_becomes_decimal_of_that_number(policy_dir, number, expected):
    write_policy(policy_dir, min_request_total=number)
    amount = policy.load(MADE_UP).min_request_total
    assert isinstance(amount, Decimal) and amount == expected


def test_policy_id_comes_from_the_file_and_fragment_policy_id_from_the_request(policy_dir):
    write_policy(policy_dir, "the-file-name", policy_id="the-id-inside")
    pol = policy.load("the-file-name")
    assert pol.policy_id == "the-id-inside"
    assert pol.fragment("rule").policy_id == "the-file-name"
    assert pol.fragment("rule").ref == "the-file-name#rule"


def test_keys_the_policy_does_not_know_are_ignored(policy_dir):
    write_policy(policy_dir, note="ignored", fragments={"rule": {"page": 2, "quote": RULE, "note": "ignored"}})
    assert policy.load(MADE_UP).fragment("rule") == Fragment(MADE_UP, "rule", 2, RULE)


@pytest.mark.parametrize("key", ["policy_id", "hospital", "title", "url", "fragments"])
def test_a_missing_required_key_is_a_key_error_naming_it(policy_dir, key):
    write_policy(policy_dir)
    path = policy_dir / f"{MADE_UP}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw[key]
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(KeyError) as caught:
        policy.load(MADE_UP)
    assert caught.value.args == (key,)


@pytest.mark.parametrize("key", ["page", "quote"])
def test_a_fragment_without_page_or_quote_is_a_key_error(policy_dir, key):
    stored = {"page": 2, "quote": RULE}
    del stored[key]
    write_policy(policy_dir, fragments={"rule": stored})
    with pytest.raises(KeyError) as caught:
        policy.load(MADE_UP)
    assert caught.value.args == (key,)


@pytest.mark.parametrize("tier", [
    {"max_fpl_pct": 200, "discount_pct": 100},
    {"max_fpl_pct": 200, "discount_pct": 100, "fragment": "rule", "extra": 1},
])
def test_a_tier_with_missing_or_extra_keys_is_a_type_error(policy_dir, tier):
    write_policy(policy_dir, tiers=[tier])
    with pytest.raises(TypeError):
        policy.load(MADE_UP)


@pytest.mark.parametrize("amount", ["five hundred", ""])
def test_an_amount_that_is_no_number_is_invalid_operation(policy_dir, amount):
    write_policy(policy_dir, min_request_total=amount)
    with pytest.raises(decimal.InvalidOperation):
        policy.load(MADE_UP)


def test_a_broken_file_is_a_json_error(policy_dir):
    (policy_dir / f"{MADE_UP}.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        policy.load(MADE_UP)


# --- available ------------------------------------------------------------------------------

def test_available_lists_the_thirteen_policy_files_sorted():
    assert policy.available() == ALL_POLICIES


def test_available_sorts_file_names_and_ignores_the_rest(policy_dir):
    for name in ("b", "Z", "a.b", "a"):
        (policy_dir / f"{name}.json").write_text("not read", encoding="utf-8")
    (policy_dir / "notes.txt").write_text("skip", encoding="utf-8")
    (policy_dir / "source.py").write_text("skip", encoding="utf-8")
    (policy_dir / "nested").mkdir()
    (policy_dir / "nested" / "deep.json").write_text("skip", encoding="utf-8")
    assert policy.available() == ["Z", "a", "a.b", "b"]


def test_available_sees_a_new_file_and_hands_out_a_new_list(policy_dir):
    write_policy(policy_dir, "first")
    listed = policy.available()
    assert listed == ["first"]
    listed.append("scribble")
    write_policy(policy_dir, "second")
    assert policy.available() == ["first", "second"]


def test_available_is_empty_for_an_empty_folder(policy_dir):
    assert policy.available() == []


def test_available_is_empty_when_the_folder_does_not_exist(policy_dir, monkeypatch):
    monkeypatch.setattr(policy, "POLICY_DIR", policy_dir / "missing")
    assert policy.available() == []


# --- verify_fragment ------------------------------------------------------------------------

def test_a_quote_on_its_page_is_ok(downloaded):
    downloaded("Other words.", RULE, "More words.")
    assert policy.verify_fragment(fragment()) == QuoteCheck(f"{MADE_UP}#rule", True, 2, 2, "ok")


def test_a_quote_on_another_page_names_that_page(downloaded):
    downloaded("Other words.", "More words.", RULE)
    assert policy.verify_fragment(fragment()) == QuoteCheck(f"{MADE_UP}#rule", False, 2, 3, "quote is on page 3, not 2")


def test_a_quote_that_is_nowhere_says_so(downloaded):
    downloaded("Other words.", "More words.")
    assert policy.verify_fragment(fragment()) == QuoteCheck(f"{MADE_UP}#rule", False, 2, None,
                                                            "quote not found in policy text")


def test_text_not_on_disk_is_reported_before_anything_else(downloaded):
    assert policy.verify_fragment(fragment("", page=0)) == QuoteCheck(f"{MADE_UP}#rule", False, 0, None,
                                                                      "policy text not downloaded")


def test_the_stated_page_wins_over_an_earlier_copy_of_the_quote(downloaded):
    downloaded(RULE, RULE, "More words.")
    assert policy.verify_fragment(fragment()) == QuoteCheck(f"{MADE_UP}#rule", True, 2, 2, "ok")


def test_of_two_other_pages_the_first_is_named(downloaded):
    downloaded("Other words.", "More words.", RULE, RULE)
    check = policy.verify_fragment(fragment())
    assert (check.found, check.found_on_page) == (False, 3)
    assert check.detail == "quote is on page 3, not 2"


@pytest.mark.parametrize("page, detail", [(0, "quote is on page 3, not 0"), (-1, "quote is on page 3, not -1"),
                                          (4, "quote is on page 3, not 4"), (99, "quote is on page 3, not 99")])
def test_a_page_outside_the_document_is_not_a_page_of_it(downloaded, page, detail):
    downloaded("Other words.", "More words.", RULE)
    assert policy.verify_fragment(fragment(page=page)) == QuoteCheck(f"{MADE_UP}#rule", False, page, 3, detail)


def test_a_page_outside_the_document_with_the_quote_nowhere(downloaded):
    downloaded("Other words.")
    assert policy.verify_fragment(fragment(page=9)) == QuoteCheck(f"{MADE_UP}#rule", False, 9, None,
                                                                  "quote not found in policy text")


def test_the_last_page_counts_as_inside_the_document(downloaded):
    downloaded("Other words.", RULE)
    assert policy.verify_fragment(fragment()).found is True


def test_a_quote_split_across_two_pages_is_not_found(downloaded):
    downloaded("Patients may", "apply.")
    assert policy.verify_fragment(fragment()).found_on_page is None


@pytest.mark.parametrize("sheet, quote", [
    ("Balan ces   after\nINSURANCE", "balances after insurance"),
    ("balances after insurance", "BALANCES  after\n insurance"),
    ("the patient’s “balance” – up to — one", "THE PATIENT'S \"BALANCE\" - UP TO - ONE"),
    ("the patient's \"balance\" - up to - one", "the patient’s “balance” – up to — one"),
])
def test_case_spaces_quote_marks_and_dashes_do_not_matter(downloaded, sheet, quote):
    downloaded(sheet)
    assert policy.verify_fragment(fragment(quote, page=1)).found is True


@pytest.mark.parametrize("quote", ["", " \n\t "])
def test_an_empty_quote_is_found_on_any_real_page(downloaded, quote):
    downloaded("Other words.", "More words.")
    assert policy.verify_fragment(fragment(quote)) == QuoteCheck(f"{MADE_UP}#rule", True, 2, 2, "ok")
    assert policy.verify_fragment(fragment(quote, page=9)) == QuoteCheck(f"{MADE_UP}#rule", False, 9, 1,
                                                                         "quote is on page 1, not 9")


def test_a_document_without_pages_has_no_quotes(downloaded):
    downloaded()
    assert policy.verify_fragment(fragment("")) == QuoteCheck(f"{MADE_UP}#rule", False, 2, None,
                                                              "quote not found in policy text")


def test_each_check_reads_the_text_of_the_moment(downloaded):
    downloaded("Other words.", RULE)
    assert policy.verify_fragment(fragment()).found is True
    downloaded("Other words.", "New revision.")
    assert policy.verify_fragment(fragment()).found is False


def test_a_policy_that_has_no_source_is_a_key_error():
    with pytest.raises(KeyError) as caught:
        policy.verify_fragment(Fragment("no-such-source", "rule", 1, RULE))
    assert caught.value.args == ("no-such-source",)


def test_a_fragment_needs_no_policy_file(downloaded, policy_dir):
    downloaded("Other words.", RULE)
    assert policy.verify_fragment(fragment()).found is True


@needs_text
def test_a_real_quote_on_a_late_pdf_page():
    frag = policy.load(MEMORIAL).fragment("scale-mrh")
    assert policy.verify_fragment(frag) == QuoteCheck(f"{MEMORIAL}#scale-mrh", True, 11, 11, "ok")


@needs_text
def test_a_real_quote_on_page_zero_is_reported_on_its_true_page():
    real = policy.load(MEMORIAL).fragment("window")
    check = policy.verify_fragment(Fragment(MEMORIAL, "window", 0, real.quote))
    assert check == QuoteCheck(f"{MEMORIAL}#window", False, 0, 5, "quote is on page 5, not 0")


@needs_text
def test_a_statute_page_is_one_page():
    real = policy.load(STATUTE).fragment("medical-debt-3-years")
    assert policy.verify_fragment(real).found is True
    check = policy.verify_fragment(Fragment(STATUTE, real.fragment_id, 2, real.quote))
    assert check == QuoteCheck(f"{STATUTE}#medical-debt-3-years", False, 2, 1, "quote is on page 1, not 2")


# --- verified -------------------------------------------------------------------------------

@needs_text
def test_a_real_ref_is_verified(clean_caches):
    assert policy.verified(f"{BAPTIST}#levels") is True


def test_a_quote_on_the_stated_page_is_verified(policy_dir, downloaded):
    write_policy(policy_dir)
    downloaded("Other words.", RULE)
    assert policy.verified(f"{MADE_UP}#rule") is True


def test_a_quote_on_another_page_is_not_verified(policy_dir, downloaded):
    write_policy(policy_dir)
    downloaded(RULE, "Other words.")
    assert policy.verified(f"{MADE_UP}#rule") is False


def test_text_not_downloaded_is_not_verified(policy_dir, downloaded):
    write_policy(policy_dir)
    assert policy.verified(f"{MADE_UP}#rule") is False


def test_the_fragment_id_runs_to_the_end_of_the_ref(policy_dir, downloaded):
    write_policy(policy_dir, fragments={"rule#2": {"page": 1, "quote": RULE}})
    downloaded(RULE)
    assert policy.verified(f"{MADE_UP}#rule#2") is True


def test_the_answer_for_a_ref_is_remembered_until_the_cache_is_cleared(policy_dir, downloaded):
    write_policy(policy_dir)
    downloaded("Other words.", RULE)
    assert policy.verified(f"{MADE_UP}#rule") is True
    downloaded("Other words.", "New revision.")
    assert policy.verified(f"{MADE_UP}#rule") is True
    policy.verified.cache_clear()
    assert policy.verified(f"{MADE_UP}#rule") is False


@pytest.mark.parametrize("ref", ["", MEMORIAL])
def test_a_ref_without_a_hash_is_a_value_error(ref, clean_caches):
    with pytest.raises(ValueError):
        policy.verified(ref)


@pytest.mark.parametrize("ref", ["no-such-policy#rule", "#", "#window"])
def test_a_ref_to_an_unknown_policy_is_a_missing_file(ref, clean_caches):
    with pytest.raises(FileNotFoundError):
        policy.verified(ref)


@pytest.mark.parametrize("ref, name", [(f"{MEMORIAL}#no-such-fragment", "no-such-fragment"), (f"{MEMORIAL}#", ""),
                                       (f"{MEMORIAL}#window#2", "window#2")])
def test_a_ref_to_an_unknown_fragment_is_a_key_error(ref, name, clean_caches):
    with pytest.raises(KeyError) as caught:
        policy.verified(ref)
    assert caught.value.args == (name,)


def test_a_policy_file_with_no_source_is_a_key_error(policy_dir):
    write_policy(policy_dir, "no-such-source")
    with pytest.raises(KeyError) as caught:
        policy.verified("no-such-source#rule")
    assert caught.value.args == ("no-such-source",)
