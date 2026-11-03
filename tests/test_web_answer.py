"""When the papers do not answer: the hospital's own site and official law pages, quoted word for word, marked as
from the web, and never counted as money. What goes to the search is the question without anything personal. The
model only picks one of the sentences code found. Every answer here is SYNTHETIC: no model and no search was called."""

import json

import pytest

from billradar import ask, checks, meta_client as mc, web_answer
from tests.test_writer import case

PAGE = ("Financial assistance. You can apply for financial assistance at any time during the 240 days after your "
        "first bill. Ask the billing office for the application form. Our office is open Monday to Friday.")


class FakeTavily:
    live = False

    def __init__(self, results=None):
        self.bodies = []
        self.results = results if results is not None else [
            {"url": "https://www.mhs.net/patients/financial-assistance", "title": "Financial assistance", "raw_content": PAGE}]

    def search(self, body, label=""):
        self.bodies.append(body)
        return {"results": self.results}


class FakeSpark:
    def __init__(self, pick="W1"):
        self.pick, self.bodies = pick, []

    def events(self, body):
        self.bodies.append(body)
        return [{"type": "response.output_text.delta", "delta": json.dumps({"pick": self.pick})},
                {"type": "response.completed", "response": {"id": "r", "usage": {}}}]


def spark(pick="W1"):
    return mc.MetaClient(transport=FakeSpark(pick), record_to=None, journal=None)


def test_nothing_personal_is_in_the_question_that_leaves():
    c = case()
    name = c.profile.people[0].name
    q = (f"Can {name} at 100 Example Street, Hollywood 33021 get help with bill LDH-000123 for $1,234.56 "
         "from 03/14/2026, (555) 010-0000, and what is the deadline to apply for financial assistance?")
    cleaned = web_answer.clean_question(q, c)
    for part in name.split() + ["Hollywood", "33021", "Example", "LDH", "000123", "1,234", "555", "03/14", "2026"]:
        assert part.lower() not in cleaned.lower()
    assert "deadline to apply for financial assistance" in cleaned


def test_the_cleaning_check_is_not_blind(monkeypatch):
    """Must light: a name in small letters, as speech may give it. It goes only because the family typed it in;
    with their values taken away from the cleaner, the same check finds it."""
    c = case()
    name = c.profile.people[0].name.split()[0].lower()
    assert name not in web_answer.clean_question(f"can {name} apply for financial assistance?", c)
    monkeypatch.setattr(web_answer.i18n, "private_values", lambda _c: [])
    assert name in web_answer.clean_question(f"can {name} apply for financial assistance?", c)


def test_a_token_of_a_covered_value_does_not_leave_either():
    assert "PATIENT" not in web_answer.clean_question("what does [PATIENT_1] owe on [ACCT_1] for the deadline", case())


def test_a_name_the_family_did_not_type_does_not_leave():
    """Anyone can say a name out loud: a capitalised word in the middle of a sentence stays here."""
    cleaned = web_answer.clean_question("Can John Smith from Seaside apply for financial assistance?", case())
    assert "John" not in cleaned and "Smith" not in cleaned and "Seaside" not in cleaned
    assert cleaned == "Can from apply for financial assistance"


@pytest.mark.parametrize("said", ["dr smith said i can apply for financial assistance",
                                  "doctor jane smith said i can apply for financial assistance",
                                  "mrs jones said i can apply for financial assistance",
                                  "mr. o'neil said i can apply for financial assistance",
                                  "ms lee said i can apply for financial assistance"])
def test_a_name_in_small_letters_after_a_title_does_not_leave(said):
    """Speech and quick typing give names in small letters: the word after a title goes, and the title with it."""
    assert web_answer.clean_question(said, case()) == "said i can apply for financial assistance"


def test_a_name_from_the_case_goes_in_any_case():
    c = case()
    first = c.profile.people[0].name.split()[0]
    for form in (first.lower(), first.upper(), first):
        assert first.lower() not in web_answer.clean_question(f"did {form} miss the deadline to apply", c).lower()


def test_the_words_of_billing_keep_their_capitals():
    cleaned = web_answer.clean_question("Does the No Surprises Act cover Medicaid in Florida?", case())
    assert cleaned == "Does the No Surprises Act cover Medicaid in Florida"


def test_too_little_left_means_no_search():
    t = FakeTavily()
    assert web_answer.find(spark(), t, case(), "Anna Sample 33021") is None
    assert t.bodies == []


def test_the_search_stays_on_the_hospitals_site_and_official_pages():
    t = FakeTavily()
    web_answer.find(spark(), t, case(), "what is the deadline to apply for financial assistance")
    domains = t.bodies[0]["include_domains"]
    assert "mhs.net" in domains and "cms.gov" in domains and all(d == "mhs.net" or d.endswith(".gov") for d in domains)


def test_a_found_sentence_comes_back_word_for_word_with_its_page():
    t = FakeTavily()
    found = web_answer.find(spark("W1"), t, case(), "what is the deadline to apply for financial assistance")
    assert found.quote in PAGE and found.url == t.results[0]["url"]
    assert found.label == "from the web, check it" and found.seconds >= 0


def test_a_page_off_the_list_is_never_quoted():
    t = FakeTavily([{"url": "https://www.dollar-tips.example/blog", "title": "Tips", "raw_content": PAGE}])
    assert web_answer.find(spark(), t, case(), "what is the deadline to apply for financial assistance") is None


def test_a_lookalike_host_is_not_the_hospitals_site():
    t = FakeTavily([{"url": "https://mhs.net.evil.example/x", "title": "x", "raw_content": PAGE}])
    assert web_answer.find(spark(), t, case(), "what is the deadline to apply for financial assistance") is None


def test_the_model_cannot_write_a_quote_it_only_picks():
    assert web_answer.find(spark("none"), FakeTavily(), case(), "what is the deadline to apply for financial assistance") is None
    assert web_answer.find(spark("W99"), FakeTavily(), case(), "what is the deadline to apply for financial assistance") is None


def test_the_ladder_keeps_a_cited_answer_from_the_case(monkeypatch):
    t = FakeTavily()
    monkeypatch.setattr(ask, "answer", lambda *a: ask.Answer("Because of line 3.", [ask.Citation("sheet", "S1", "3")]))
    a = web_answer.ladder(spark(), case(), checks.run(case()), "why is this so high", t)
    assert a.source == "case" and a.text == "Because of line 3." and t.bodies == []


def test_the_ladder_goes_to_the_web_when_the_papers_do_not_answer(monkeypatch):
    monkeypatch.setattr(ask, "answer", lambda *a: ask.Answer("I could not find that.", refused=True, reason="no_citation"))
    a = web_answer.ladder(spark(), case(), checks.run(case()), "what is the deadline to apply for financial assistance", FakeTavily())
    assert a.source == "web" and a.web.quote in PAGE and a.citations == []


def test_the_ladder_ends_with_a_phrase_to_say_not_an_invented_answer(monkeypatch):
    monkeypatch.setattr(ask, "answer", lambda *a: ask.Answer("I could not find that.", refused=True, reason="no_citation"))
    a = web_answer.ladder(spark("none"), case(), checks.run(case()), "what is the deadline to apply for financial assistance", FakeTavily())
    assert a.source == "none" and a.text == web_answer.NOT_IN_CASE and "in writing" in a.say


def test_a_health_question_stays_declined_and_never_searches(monkeypatch):
    t = FakeTavily()
    monkeypatch.setattr(ask, "answer", lambda *a: ask.Answer(ask.DECLINE, refused=True, reason="health"))
    a = web_answer.ladder(spark(), case(), checks.run(case()), "is this rash dangerous", t)
    assert a.reason == "health" and t.bodies == []


def test_a_failed_search_still_ends_with_the_phrase(monkeypatch):
    class Broken(FakeTavily):
        def search(self, body, label=""):
            raise web_answer.TavilyError("HTTP 500")

    monkeypatch.setattr(ask, "answer", lambda *a: ask.Answer("I could not find that.", refused=True, reason="no_citation"))
    a = web_answer.ladder(spark(), case(), checks.run(case()), "what is the deadline to apply for financial assistance", Broken())
    assert a.source == "none"


# --- two searches: the hospital's own site through Tavily, a general question through Meta's web_search ---------

LAW = ("An employer health plan must give you at least 180 days to appeal a denied claim after you get the notice. "
       "Other rules apply to individual plans.")


class FakeMetaSearch:
    """Meta's web_search as the docs describe it: the model decides, the raw hits come with include."""

    def __init__(self, results=None, pick="W1"):
        self.bodies, self.pick = [], pick
        self.results = results if results is not None else [
            {"url": "https://www.dol.gov/agencies/ebsa/appeals", "title": "Appeals", "snippet": LAW}]

    def events(self, body):
        self.bodies.append(body)
        if "tools" in body:
            call = {"type": "web_search_call", "id": "ws_1", "status": "completed", "results": self.results}
            return [{"type": "response.output_text.delta", "delta": "some answer the app never shows"},
                    {"type": "response.completed", "response": {"id": "r", "usage": {}, "output": [call]}}]
        return [{"type": "response.output_text.delta", "delta": json.dumps({"pick": self.pick})},
                {"type": "response.completed", "response": {"id": "r2", "usage": {}}}]


def meta(**kw):
    return mc.MetaClient(transport=FakeMetaSearch(**kw), record_to=None, journal=None)


GENERAL = "how many days does a health plan give to appeal a denied claim"
HOSPITAL_SITE = "what is the deadline to apply for financial assistance at the hospital"


def test_a_general_question_goes_to_metas_search_first():
    client, t = meta(), FakeTavily()
    found = web_answer.find(client, t, case(), GENERAL)
    assert found.url.startswith("https://www.dol.gov") and found.quote in LAW and t.bodies == []
    body = client.transport.bodies[0]
    assert body["tools"] == [{"type": "web_search"}] and body["include"] == ["web_search_call.results"]


def test_a_question_about_the_hospital_goes_to_its_own_site_first():
    client, t = meta(), FakeTavily()
    found = web_answer.find(client, t, case(), HOSPITAL_SITE)
    assert found.url.startswith("https://www.mhs.net") and t.bodies
    assert not any("tools" in b for b in client.transport.bodies)


def test_no_answer_from_one_search_goes_to_the_other():
    client, t = meta(results=[]), FakeTavily()
    found = web_answer.find(client, t, case(), GENERAL.replace("health plan", "financial assistance plan"))
    assert t.bodies and found is not None and found.url.startswith("https://www.mhs.net")


def test_a_host_off_the_list_from_metas_search_is_filtered_by_code():
    client, t = meta(results=[{"url": "https://www.dollar-tips.example/x", "title": "x", "snippet": LAW}]), FakeTavily([])
    assert web_answer.find(client, t, case(), GENERAL) is None


def test_only_the_cleaned_question_goes_to_metas_search():
    c = case()
    name = next(p.name for p in c.profile.people if p.name)
    client = meta()
    web_answer.find(client, FakeTavily(), c, f"how many days does {name} have to appeal a denied claim with the plan")
    sent = json.dumps(client.transport.bodies[0]["input"])
    assert name.split()[0] not in sent and "appeal" in sent


def test_the_case_is_not_in_the_request_to_metas_search():
    client = meta()
    web_answer.find(client, FakeTavily(), case(), GENERAL)
    sent = json.dumps(client.transport.bodies[0])
    assert "documents" not in sent and "patient_balance" not in sent


def test_a_search_failure_on_one_side_does_not_stop_the_other():
    class Down(FakeMetaSearch):
        def events(self, body):
            if "tools" in body:
                raise mc.MetaAPIError("search down")
            return super().events(body)

    client = mc.MetaClient(transport=Down(), record_to=None, journal=None)
    found = web_answer.find(client, FakeTavily(), case(), GENERAL.replace("health plan", "financial assistance plan"))
    assert found is not None and found.url.startswith("https://www.mhs.net")


def test_the_quote_from_metas_search_is_checked_against_its_snippet():
    class Sneaky(FakeMetaSearch):
        def events(self, body):
            return super().events(body)

    client = mc.MetaClient(transport=Sneaky(pick="W7"), record_to=None, journal=None)
    assert web_answer.find(client, FakeTavily([]), case(), GENERAL) is None


def test_a_search_is_priced_on_the_call():
    client = meta()
    web_answer.find(client, FakeTavily(), case(), GENERAL)
    assert client.calls[0]["searches"] == 1 and client.calls[0]["usd"] == pytest.approx(0.0025)
