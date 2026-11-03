"""The case model's small parsers and lookups, pinned as they behave today. SYNTHETIC values.

Dates, households and people are checked here on their own: a profile for the lookup tests is built past the household
check, so a test of one lookup fails only for that lookup.
"""

from datetime import date, datetime
from decimal import Decimal

import pydantic
import pytest

from billradar.case import Case, DocKind, Document, Person, Profile, Role, Source, parse_date


HOUSEHOLD_ERROR = "household_size must be >= 1"
BILL_KINDS = (DocKind.HOSPITAL_STATEMENT, DocKind.ITEMIZED_BILL)


def people(*persons: Person) -> Profile:
    return Profile.model_construct(household_size=2, annual_income=Decimal(1), people=list(persons))


def sheet(doc_id: str, kind: DocKind = DocKind.OTHER, tag: str = "") -> Document:
    return Document(doc_id=doc_id, source=Source.PAPER, kind=kind, provider=tag)


def case(*documents: Document) -> Case:
    return Case(case_id="c", policy_id="memorial-2026-05", today=date(2026, 3, 2), profile=people(), documents=list(documents))


def ids(documents: list[Document]) -> list[str]:
    return [d.doc_id for d in documents]


# --- parse_date ------------------------------------------------------------------------------


@pytest.mark.parametrize("text, expected", [
    ("2024-01-31", date(2024, 1, 31)),
    ("1999-12-01", date(1999, 12, 1)),
    ("08/09/2025", date(2025, 8, 9)),
    ("8/9/2025", date(2025, 8, 9)),
    ("12/1/2025", date(2025, 12, 1)),
    ("1/12/2025", date(2025, 1, 12)),
])
def test_parse_date_reads_iso_and_us_with_or_without_leading_zeros(text, expected):
    got = parse_date(text)
    assert got == expected and type(got) is date


def test_parse_date_reads_a_slashed_date_as_month_first_and_never_turns_it_around():
    assert parse_date("01/02/2025") == date(2025, 1, 2)
    assert parse_date("12/25/2025") == date(2025, 12, 25)
    assert parse_date("13/01/2025") is None
    assert parse_date("25/12/2025") is None


@pytest.mark.parametrize("text", [" 2025-03-04 ", "\t2025-03-04\n", " 2025-03-04 ", "　3/4/2025\x1c", "\r\n3/4/2025 "])
def test_parse_date_ignores_whitespace_of_any_kind_around_the_date(text):
    assert parse_date(text) == date(2025, 3, 4)


@pytest.mark.parametrize("text", ["​2025-03-04", "2025-03-04﻿", "2025 -03-04", "2025-03- 04", "3 / 4 / 2025", "3/4/ 2025"])
def test_parse_date_refuses_what_is_not_whitespace_or_sits_inside_the_date(text):
    assert parse_date(text) is None


@pytest.mark.parametrize("text", [None, "", "   ", "\t\n", " "])
def test_parse_date_gives_none_for_nothing_to_read(text):
    assert parse_date(text) is None


@pytest.mark.parametrize("value", [0, 0.0, False, [], {}, (), b""])
def test_parse_date_gives_none_for_any_empty_value_even_if_not_text(value):
    assert parse_date(value) is None


@pytest.mark.parametrize("text", [
    "2025-8-11", "2025-08-1", "25-08-11", "12025-08-11",  # ISO needs exactly 4-2-2 digits
    "8/11/25", "8/11/202", "8/11/20255", "008/11/2025", "8/011/2025",  # US needs 1-2, 1-2, 4 digits
    "2025/08/11", "08-11-2025", "2025.08.11", "11.08.2025", "2025-08/11", "8/11-2025", "20250811",
    "02/11/2025-02/13/2025", "2025-02-11 to 2025-02-13",  # a range is the reader's job: it needs None here
    "2025-08-11T00:00:00", "2025-08-11 00:00", "8/11/2025 10:00 AM", "x2025-08-11", "2025-08-11x", "2025-08-11-",
    "Aug 11, 2025", "11 August 2025", "2025-08", "8/11", "today", "/", "-",
])
def test_parse_date_refuses_every_form_it_does_not_know(text):
    assert parse_date(text) is None


@pytest.mark.parametrize("text", [
    "2025-13-01", "2025-00-10", "2025-10-00", "2025-04-31", "2025-02-29", "2100-02-29", "0000-01-01",
    "00/10/2025", "10/00/2025", "13/13/2025", "01/32/2025", "2/30/2025", "02/29/2025", "1/1/0000", "4/31/2025",
])
def test_parse_date_gives_none_for_a_day_the_calendar_does_not_have(text):
    assert parse_date(text) is None


@pytest.mark.parametrize("text, expected", [
    ("2024-02-29", date(2024, 2, 29)),
    ("02/29/2024", date(2024, 2, 29)),
    ("2000-02-29", date(2000, 2, 29)),
    ("0001-01-01", date(1, 1, 1)),
    ("1/1/0001", date(1, 1, 1)),
    ("9999-12-31", date(9999, 12, 31)),
    ("12/31/9999", date(9999, 12, 31)),
])
def test_parse_date_keeps_leap_days_and_the_first_and_last_year_of_the_calendar(text, expected):
    assert parse_date(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("٢٠٢٥-٠٨-١١", date(2025, 8, 11)),  # Arabic-Indic
    ("２０２５-０８-１１", date(2025, 8, 11)),  # fullwidth
    ("٨/١١/٢٠٢٥", date(2025, 8, 11)),
    ("२०२५-०८-११", date(2025, 8, 11)),  # Devanagari
])
def test_parse_date_takes_decimal_digits_of_any_script(text, expected):
    assert parse_date(text) == expected


def test_parse_date_refuses_superscripts_which_are_not_decimal_digits():
    assert parse_date("²025-08-11") is None


@pytest.mark.parametrize("value, error", [
    (123, AttributeError),
    (20250811, AttributeError),
    (1.5, AttributeError),
    (True, AttributeError),
    ([1], AttributeError),
    ({"a": 1}, AttributeError),
    (date(2025, 8, 11), AttributeError),
    (datetime(2025, 8, 11, 12, 0), AttributeError),
    (b"2025-08-11", TypeError),
])
def test_parse_date_raises_on_a_non_empty_value_that_is_not_text(value, error):
    with pytest.raises(error):
        parse_date(value)


# --- Profile._size ---------------------------------------------------------------------------


@pytest.mark.parametrize("size", [1, 2, 7, 20])
def test_a_household_of_one_or_more_is_kept_as_given(size):
    assert Profile(household_size=size, annual_income=1).household_size == size


@pytest.mark.parametrize("size", [0, -1, -100])
def test_a_household_below_one_is_refused_with_the_exact_message(size):
    with pytest.raises(pydantic.ValidationError) as e:
        Profile(household_size=size, annual_income=1)
    assert [(x["type"], x["loc"], x["msg"]) for x in e.value.errors()] == [
        ("value_error", ("household_size",), f"Value error, {HOUSEHOLD_ERROR}")]


@pytest.mark.parametrize("given, kept", [("3", 3), (" 2 ", 2), (2.0, 2), (True, 1), (Decimal("2"), 2)])
def test_the_household_check_sees_the_number_after_pydantic_turned_it_into_an_int(given, kept):
    got = Profile(household_size=given, annual_income=1).household_size
    assert got == kept and type(got) is int


@pytest.mark.parametrize("given", ["0", "-1", False, 0.0, Decimal("0")])
def test_a_household_below_one_is_refused_after_int_conversion_too(given):
    with pytest.raises(pydantic.ValidationError) as e:
        Profile(household_size=given, annual_income=1)
    assert e.value.errors()[0]["msg"] == f"Value error, {HOUSEHOLD_ERROR}"


def test_a_stored_profile_with_an_empty_household_is_refused_on_every_way_in():
    with pytest.raises(pydantic.ValidationError):
        Profile.model_validate({"household_size": 0, "annual_income": "1"})
    with pytest.raises(pydantic.ValidationError):
        Profile.model_validate_json('{"household_size": 0, "annual_income": "1"}')
    with pytest.raises(pydantic.ValidationError) as e:
        Case.model_validate({"case_id": "c", "policy_id": "p", "today": "2026-03-02", "documents": [],
                             "profile": {"household_size": 0, "annual_income": "1"}})
    assert e.value.errors()[0]["loc"] == ("profile", "household_size")
    assert e.value.errors()[0]["msg"] == f"Value error, {HOUSEHOLD_ERROR}"


def test_the_household_validator_called_alone_raises_a_plain_value_error_with_only_that_text():
    with pytest.raises(ValueError) as e:
        Profile._size(0)
    assert type(e.value) is ValueError and e.value.args == (HOUSEHOLD_ERROR,)


@pytest.mark.parametrize("value", [1, 3, 20, True, 1.0, 1.5, Decimal("1"), Decimal("2.5"), float("inf")])
def test_the_household_validator_returns_the_very_value_it_was_given(value):
    assert Profile._size(value) is value


def test_the_household_validator_only_refuses_what_compares_below_one():
    nan = float("nan")
    assert Profile._size(nan) is nan
    for below in (False, 0.5, 0.999, Decimal("0.5"), float("-inf")):
        with pytest.raises(ValueError):
            Profile._size(below)


@pytest.mark.parametrize("value", ["3", None, [1]])
def test_the_household_validator_raises_type_error_on_what_cannot_be_compared_with_a_number(value):
    with pytest.raises(TypeError):
        Profile._size(value)


# --- Profile.role_of -------------------------------------------------------------------------


MOTHER = Person(token="PATIENT_1", role=Role.MOTHER)
BABY = Person(token="PATIENT_2", role=Role.NEWBORN)
ADULT = Person(token="PATIENT_3", role=Role.PATIENT)


@pytest.mark.parametrize("token, role", [("PATIENT_1", Role.MOTHER), ("PATIENT_2", Role.NEWBORN), ("PATIENT_3", Role.PATIENT)])
def test_role_of_gives_the_role_of_the_person_with_that_token(token, role):
    assert people(MOTHER, BABY, ADULT).role_of(token) is role


def test_role_of_gives_a_listed_person_their_other_role_too():
    assert people(Person(token="PATIENT_9", role=Role.OTHER), MOTHER).role_of("PATIENT_9") is Role.OTHER


@pytest.mark.parametrize("token", ["PATIENT_4", "", "ACCT_1", "Anna"])
def test_role_of_gives_other_for_a_token_nobody_has(token):
    assert people(MOTHER, BABY).role_of(token) is Role.OTHER


def test_role_of_gives_other_when_the_profile_names_nobody():
    assert people().role_of("PATIENT_1") is Role.OTHER


def test_role_of_takes_the_first_person_when_two_share_a_token():
    twin = Person(token="PATIENT_1", role=Role.NEWBORN)
    assert people(MOTHER, twin).role_of("PATIENT_1") is Role.MOTHER
    assert people(twin, MOTHER).role_of("PATIENT_1") is Role.NEWBORN


@pytest.mark.parametrize("token", ["patient_1", "PATIENT_1 ", " PATIENT_1", "PATIENT 1", "[PATIENT_1]"])
def test_role_of_compares_the_token_exactly_as_it_is_written(token):
    assert people(MOTHER).role_of(token) is Role.OTHER


def test_role_of_finds_a_person_whose_token_is_empty():
    assert people(Person(token="", role=Role.NEWBORN)).role_of("") is Role.NEWBORN


@pytest.mark.parametrize("token", [None, 0, 1, [], {}])
def test_role_of_never_raises_on_something_that_is_not_a_token(token):
    assert people(MOTHER).role_of(token) is Role.OTHER


def test_role_of_sees_a_person_added_after_the_first_lookup():
    p = people(MOTHER)
    assert p.role_of("PATIENT_2") is Role.OTHER
    p.people.append(BABY)
    assert p.role_of("PATIENT_2") is Role.NEWBORN


# --- Case.doc --------------------------------------------------------------------------------


def test_doc_gives_the_document_with_that_id():
    c = case(sheet("S1"), sheet("S2"), sheet("D1"))
    assert c.doc("S2") is c.documents[1]
    assert c.doc("D1") is c.documents[2]


def test_doc_gives_the_case_s_own_document_so_a_change_on_it_stays_in_the_case():
    c = case(sheet("S1"))
    c.doc("S1").patient_balance = Decimal("12.50")
    assert c.documents[0].patient_balance == Decimal("12.50")


def test_doc_takes_the_first_of_two_documents_with_one_id():
    c = case(sheet("S1", tag="first"), sheet("S2"), sheet("S1", tag="second"))
    assert c.doc("S1").provider == "first"


@pytest.mark.parametrize("doc_id", ["S3", "s1", " S1", "S1 ", "", "1", None, 1, []])
def test_doc_raises_stop_iteration_with_no_text_for_an_id_not_in_the_case(doc_id):
    c = case(sheet("S1"), sheet("S2"))
    with pytest.raises(StopIteration) as e:
        c.doc(doc_id)
    assert type(e.value) is StopIteration and e.value.args == ()


def test_doc_raises_stop_iteration_on_an_empty_case():
    with pytest.raises(StopIteration):
        case().doc("S1")


def test_doc_finds_a_document_whose_id_is_empty():
    c = case(sheet(""))
    assert c.doc("") is c.documents[0]


def test_doc_sees_a_document_added_after_the_first_lookup():
    c = case(sheet("S1"))
    with pytest.raises(StopIteration):
        c.doc("S2")
    c.documents.append(sheet("S2"))
    assert c.doc("S2") is c.documents[1]


# --- Case.bills and Case.eobs ----------------------------------------------------------------


EVERY_KIND = case(*(sheet(f"S{i}", kind) for i, kind in enumerate(DocKind, start=1)))


def test_bills_gives_hospital_statements_and_itemized_bills_and_nothing_else():
    assert [d.kind for d in EVERY_KIND.bills()] == list(BILL_KINDS)


def test_eobs_gives_explanations_of_benefits_and_nothing_else():
    assert [d.kind for d in EVERY_KIND.eobs()] == [DocKind.EOB]


def test_bills_and_eobs_keep_the_order_of_the_pile_with_both_bill_kinds_mixed():
    c = case(sheet("S1", DocKind.ITEMIZED_BILL), sheet("S2", DocKind.EOB), sheet("S3", DocKind.HOSPITAL_STATEMENT),
             sheet("S4", DocKind.FA_LETTER), sheet("S5", DocKind.ITEMIZED_BILL), sheet("S6", DocKind.EOB))
    assert ids(c.bills()) == ["S1", "S3", "S5"]
    assert ids(c.eobs()) == ["S2", "S6"]


def test_bills_and_eobs_keep_two_documents_with_one_id():
    c = case(sheet("S1", DocKind.ITEMIZED_BILL, "a"), sheet("S1", DocKind.ITEMIZED_BILL, "b"),
             sheet("S2", DocKind.EOB, "c"), sheet("S2", DocKind.EOB, "d"))
    assert [d.provider for d in c.bills()] == ["a", "b"]
    assert [d.provider for d in c.eobs()] == ["c", "d"]


@pytest.mark.parametrize("documents", [[], [sheet("S1", DocKind.FA_LETTER), sheet("S2", DocKind.PAYMENT_RECEIPT), sheet("S3")]])
def test_bills_and_eobs_are_empty_lists_when_the_pile_has_none(documents):
    c = case(*documents)
    assert c.bills() == [] and c.eobs() == []


def test_bills_gives_the_case_s_own_documents_in_a_list_of_its_own():
    c = case(sheet("S1", DocKind.HOSPITAL_STATEMENT), sheet("S2", DocKind.EOB))
    got = c.bills()
    assert type(got) is list and got[0] is c.documents[0]
    got.clear()
    assert ids(c.bills()) == ["S1"] and len(c.documents) == 2


def test_eobs_gives_the_case_s_own_documents_in_a_list_of_its_own():
    c = case(sheet("S1", DocKind.HOSPITAL_STATEMENT), sheet("S2", DocKind.EOB))
    got = c.eobs()
    assert type(got) is list and got[0] is c.documents[1]
    got.clear()
    assert ids(c.eobs()) == ["S2"] and len(c.documents) == 2


def test_bills_and_eobs_never_hand_back_the_documents_list_itself():
    bills_only = case(sheet("S1", DocKind.ITEMIZED_BILL))
    eobs_only = case(sheet("S1", DocKind.EOB))
    assert bills_only.bills() is not bills_only.documents
    assert eobs_only.eobs() is not eobs_only.documents


def test_bills_and_eobs_see_a_document_added_or_replaced_after_the_first_call():
    c = case(sheet("S1", DocKind.ITEMIZED_BILL))
    assert ids(c.bills()) == ["S1"] and c.eobs() == []
    c.documents.append(sheet("S2", DocKind.EOB))
    c.documents.append(sheet("S3", DocKind.HOSPITAL_STATEMENT))
    assert ids(c.bills()) == ["S1", "S3"] and ids(c.eobs()) == ["S2"]
    c.documents = [sheet("S4", DocKind.EOB)]
    assert c.bills() == [] and ids(c.eobs()) == ["S4"]


def test_bills_and_eobs_follow_a_kind_changed_on_a_document():
    c = case(sheet("S1", DocKind.OTHER))
    c.documents[0].kind = DocKind.EOB
    assert c.bills() == [] and ids(c.eobs()) == ["S1"]
    c.documents[0].kind = DocKind.ITEMIZED_BILL
    assert ids(c.bills()) == ["S1"] and c.eobs() == []


def test_bills_and_eobs_count_a_kind_left_as_plain_text_by_an_unchecked_copy():
    base = sheet("S1")
    c = case(base.model_copy(update={"doc_id": "S1", "kind": "eob"}),
             base.model_copy(update={"doc_id": "S2", "kind": "itemized_bill"}),
             base.model_copy(update={"doc_id": "S3", "kind": "hospital_statement"}),
             base.model_copy(update={"doc_id": "S4", "kind": "bill"}))
    assert ids(c.bills()) == ["S2", "S3"]
    assert ids(c.eobs()) == ["S1"]
