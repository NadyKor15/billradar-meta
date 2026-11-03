"""Hospital assistance policies and laws, stored as data, and the check that keeps them honest.

Every rule in a `policies/*.json` file points at a verbatim quote and a page. A rule reaches a finding
or a letter only once its quote is confirmed on that page of the downloaded text, so a typo in our file
or a new revision of the hospital's PDF surfaces as an unconfirmed fragment, not as a quiet wrong finding.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from functools import cache
from pathlib import Path

from billradar.policies import source

POLICY_DIR = Path(__file__).parent / "policies"

_REQUIRED_KEYS = ("policy_id", "hospital", "title", "url")
_OPTIONAL_KEYS = ("covers_insured_balances", "income_cap_pct", "fpg_year", "window")
_AMOUNT_KEYS = ("min_request_total", "liquid_assets_limit_for_free_care")


@dataclass(frozen=True)
class Fragment:
    policy_id: str
    fragment_id: str
    page: int
    quote: str

    @property
    def ref(self) -> str:
        return f"{self.policy_id}#{self.fragment_id}"


@dataclass(frozen=True)
class Tier:
    max_fpl_pct: int
    discount_pct: int
    fragment: str


@dataclass
class Policy:
    policy_id: str
    hospital: str
    title: str
    url: str
    fragments: dict[str, Fragment]
    covers_insured_balances: bool = True
    min_request_total: Decimal | None = None
    liquid_assets_limit_for_free_care: Decimal | None = None
    income_cap_pct: int | None = None
    fpg_year: int | None = None  # the poverty-guideline year the policy's tiers are written against
    tiers: list[Tier] = field(default_factory=list)
    window: dict = field(default_factory=dict)

    def tier_for(self, fpl_pct: Decimal) -> Tier | None:
        """First listed tier whose ceiling covers the percent; policies print whole percents, so the fraction is cut."""
        whole_percent = int(fpl_pct)
        return next((tier for tier in self.tiers if whole_percent <= tier.max_fpl_pct), None)

    def fragment(self, fragment_id: str) -> Fragment:
        return self.fragments[fragment_id]


@cache
def load(policy_id: str) -> Policy:
    with (POLICY_DIR / f"{policy_id}.json").open(encoding="utf-8") as file:
        raw = json.load(file)

    # A key missing from the file stays out of `fields`, so the defaults of `Policy` apply.
    fields = {key: raw[key] for key in _REQUIRED_KEYS}
    fields["fragments"] = {
        fragment_id: Fragment(policy_id, fragment_id, entry["page"], entry["quote"])
        for fragment_id, entry in raw["fragments"].items()
    }
    fields.update({key: raw[key] for key in _OPTIONAL_KEYS if key in raw})
    for key in _AMOUNT_KEYS:
        if raw.get(key) is not None:
            fields[key] = Decimal(raw[key])
    fields["tiers"] = [Tier(**entry) for entry in raw.get("tiers", ())]
    return Policy(**fields)


def available() -> list[str]:
    return sorted(path.stem for path in POLICY_DIR.glob("*.json"))


@dataclass(frozen=True)
class QuoteCheck:
    ref: str
    found: bool
    page: int
    found_on_page: int | None
    detail: str


def verify_fragment(frag: Fragment) -> QuoteCheck:
    """Say whether the quote stands on its stated page; pages are compared one by one, never joined."""
    def outcome(found: bool, found_on_page: int | None, detail: str) -> QuoteCheck:
        return QuoteCheck(frag.ref, found, frag.page, found_on_page, detail)

    if not source.is_cached(frag.policy_id):
        return outcome(False, None, "policy text not downloaded")

    key = source.compact(frag.quote)
    pages_with_quote = [number for number, text in enumerate(source.page_texts(frag.policy_id), start=1)
                        if key in source.compact(text)]
    if frag.page in pages_with_quote:
        return outcome(True, frag.page, "ok")
    if pages_with_quote:
        first = pages_with_quote[0]
        return outcome(False, first, f"quote is on page {first}, not {frag.page}")
    return outcome(False, None, "quote not found in policy text")


@cache
def verified(ref: str) -> bool:
    policy_id, fragment_id = ref.split("#", 1)
    return verify_fragment(load(policy_id).fragment(fragment_id)).found
