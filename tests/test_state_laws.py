"""state_laws: a state's own law site only, the law's words checked by code, a date, and one fixed cautious line."""

import json

from billradar import state_laws as sl
from billradar import tavily_client as tc
from tests.test_policy_finder import FakeModel, FakeTransport, client, reads

STATUTE = """HEALTH AND SAFETY CODE - HSC
127405. (a) (1) (A) Each hospital shall maintain an understandable written policy regarding discount payments for
financially qualified patients as well as an understandable written charity care policy.
(B) A hospital shall not charge a patient more than $1,500 for a test case of this file.
(Amended by Stats. 2024, Ch. 770, Sec. 3. (AB 2297) Effective January 1, 2025.)
"""
URL = "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=127405.&lawCode=HSC"
TRUE = {"section": "127405", "date_quote": "Amended by Stats. 2024, Ch. 770, Sec. 3. (AB 2297) Effective January 1, 2025.",
        "quote": "Each hospital shall maintain an understandable written policy regarding discount payments for "
                 "financially qualified patients as well as an understandable written charity care policy."}


def law(sections, url=URL, text=STATUTE, state="CA"):
    t = FakeTransport(search=lambda b: {"results": [{"url": url, "title": "Health and Safety Code 127405",
                                                     "raw_content": text, "score": 0.9}]})
    n = FakeModel({"sections": sections})
    return sl.for_state(state, client(t), n), t, n


def test_a_quote_from_the_law_with_its_date_is_shown_with_the_cautious_line():
    out, t, _ = law([TRUE])
    assert out.status == "shown" and out.sections[0]["section"] == "127405"
    assert out.sections[0]["label"] == "May apply to you; check." and "Effective January 1, 2025" in out.sections[0]["date_quote"]
    assert t.bodies[0][1]["include_domains"] == ["leginfo.legislature.ca.gov"]


def test_a_changed_quote_goes_dark_while_the_true_one_still_lights():
    changed = dict(TRUE, quote=TRUE["quote"].replace("shall maintain", "may skip"))
    out, _, _ = law([changed, TRUE])
    assert len(out.sections) == 1 and out.dropped[0]["why"] == "quote not found in the law's text"


def test_a_dollar_amount_is_never_shown():
    out, _, _ = law([dict(TRUE, quote="A hospital shall not charge a patient more than $1,500 for a test case of this file.")])
    assert out.status == "link_only" and out.dropped[0]["why"] == "the quote carries a dollar amount"


def test_without_a_printed_date_the_section_is_not_shown():
    out, _, _ = law([dict(TRUE, date_quote="")], text=STATUTE.replace("(Amended by Stats. 2024", "(Note"))
    assert out.status == "link_only" and "no revision or effective date" in out.dropped[0]["why"]


def test_only_the_states_own_law_host_over_https_is_read():
    page = "/faces/codes_displaySection.xhtml?sectionNum=127405.&lawCode=HSC"  # the path of a real statute page
    for url in ("https://law.justia.com" + page, "https://www.ca.gov" + page, "http://leginfo.legislature.ca.gov" + page,
                "https://leginfo.legislature.ca.gov.evil.com" + page, "https://leginfo.legislature.ca.gov:443@evil.com" + page):
        out, _, n = law([TRUE], url=url)
        assert out.status == "not_found" and not reads(n), url


def test_florida_and_unlisted_states_are_skipped_without_a_call():
    for state in ("FL", "OH", ""):
        t = FakeTransport()
        out = sl.for_state(state, client(t), FakeModel({"sections": [TRUE]}))
        assert out.status == "skipped" and t.bodies == []
        assert ("Florida's protections" in out.message) == (state == "FL")


def test_nothing_says_you_are_protected_or_promises_money():
    out, _, _ = law([TRUE])
    shown = json.dumps(out.to_dict()).lower() + sl.LABEL.lower() + sl.NOTE.lower()
    for word in ("you are protected", "you have the right", "entitled", "guarantee", "you will get", "you qualify"):
        assert word not in shown


def test_a_failed_search_is_a_visible_error():
    class Broken(FakeTransport):
        def answer(self, endpoint, body):
            raise tc.TavilyError("HTTP 500")
    out = sl.for_state("TX", client(Broken()), FakeModel({"sections": []}))
    assert out.status == "error" and "HTTP 500" in out.message


def test_a_one_section_page_lends_its_only_history_line_but_two_lines_do_not():
    out, _, _ = law([dict(TRUE, date_quote="")])
    assert out.status == "shown" and "Effective January 1, 2025" in out.sections[0]["date_quote"]
    two = STATUTE + "(Added by Stats. 2006, Ch. 755, Sec. 2. Effective January 1, 2007.)\n"
    out, _, _ = law([dict(TRUE, date_quote="")], text=two)
    assert out.status == "link_only" and "no revision or effective date" in out.dropped[0]["why"]


# --- which search answers: a question about a law goes to Meta's search first, Tavily takes the next turn ---------

class SearchingModel(FakeModel):
    """Meta's search answers with `found`; the sections come from the same model. `broken`: the search call fails."""

    def __init__(self, sections, found=(), broken=False):
        super().__init__({"sections": sections})
        self.found, self.broken = list(found), broken

    def respond(self, body, label=""):
        if label != "spark:law-search":
            return super().respond(body, label)
        self.bodies.append(body)
        if self.broken:
            raise sl.MetaAPIError("HTTP 500")
        results = [{"url": u, "title": "Health and Safety Code 127405", "snippet": "a snippet"} for u in self.found]
        return type("R", (), {"text": "", "events": [{"type": "response.completed", "response": {"output": [
            {"type": "web_search_call", "results": results}]}}]})()


def extracting(text=STATUTE, url=URL):
    return FakeTransport(search=lambda b: {"results": []},
                         extract=lambda b: {"results": [{"url": u, "raw_content": text} for u in b["urls"]]})


def test_meta_search_goes_first_and_the_page_text_comes_from_extract():
    t = extracting()
    n = SearchingModel([TRUE], found=[URL])
    out = sl.for_state("CA", client(t), n)
    assert out.status == "shown" and out.sections[0]["url"] == URL
    assert [e for e, _ in t.bodies] == ["extract"]  # must light for the next test: Tavily's search was never needed
    assert "site:leginfo.legislature.ca.gov" in json.dumps(n.bodies[0])


def test_a_page_off_the_law_site_from_meta_search_is_dropped_and_tavily_takes_its_turn():
    t = FakeTransport(search=lambda b: {"results": [{"url": URL, "title": "Code", "raw_content": STATUTE, "score": 0.9}]})
    n = SearchingModel([TRUE], found=["https://www.lawfirm-example.com/california-hospital-law",
                                      "http://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"])
    out = sl.for_state("CA", client(t), n)
    assert out.status == "shown" and out.sections[0]["url"] == URL
    assert [e for e, _ in t.bodies] == ["search"]


def test_meta_search_down_leaves_tavily_its_turn():
    t = FakeTransport(search=lambda b: {"results": [{"url": URL, "title": "Code", "raw_content": STATUTE, "score": 0.9}]})
    out = sl.for_state("CA", client(t), SearchingModel([TRUE], broken=True))
    assert out.status == "shown"


def test_a_law_page_without_text_from_meta_search_is_not_the_end():
    t = FakeTransport(search=lambda b: {"results": [{"url": URL, "title": "Code", "raw_content": STATUTE, "score": 0.9}]},
                      extract=lambda b: {"results": []})
    out = sl.for_state("CA", client(t), SearchingModel([TRUE], found=[URL]))
    assert out.status == "shown" and [e for e, _ in t.bodies] == ["extract", "search"]


def test_no_page_from_either_search_says_so():
    out = sl.for_state("CA", client(extracting()), SearchingModel([TRUE]))
    assert out.status == "not_found" and "official law site" in out.message
