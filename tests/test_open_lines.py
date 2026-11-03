"""A line opens by its shape, not by its words. The names and addresses here are ordinary words on purpose, and none is the family's."""
import random

import pytest

from billradar import open_lines as d

NAME_LINES = ["Grace Hunter", "Rose Baker", "GRACE HUNTER", "Mark Stone", "Hunter, Grace", "Baker , Rose", "Faith Rivers", "Hope Field", "Bill Price",
              "Joy Summer", "Dawn Marsh", "Dale Woods", "Grace R. Hunter", "Rose Marie Baker", "Mrs. Rose Baker", "Mark Stone Jr.",
              "Ember Sparrow", "Clover Meadows", "Willow Brook", "Sage Rivers", "Rose Baker and Mark Hill", "Mary of the Oak Hill", "Ann Lee"]
ADDRESS_LINES = ["12 Oak Street", "12 OAK ST", "9 Hill Park Road", "450 Long Lane", "Oak Street", "Hill, Park", "Park Hill", "Apt 12", "Unit 7", "Suite 200", "PO Box 77",
                 "Orlando, FL 32801", "FL 32801", "Winter Park, FL 32789-1234", "77 Maple Ave Apt 3", "1 Sunset Way"]
LABELLED = ["To: Grace Hunter", "From: Rose Baker", "Patient: Grace Hunter", "Guarantor: Rose Baker", "PATIENT NAME: Rose Baker", "Member: Mark Stone", "Subscriber: Faith Rivers",
            "Insured: Hope Field", "Bill To: Grace Hunter", "Attn: Rose Baker", "Patient Grace Hunter", "Guarantor Hill Park", "To Grace Hunter", "From Rose Baker",
            "Address: 12 Oak Street", "DOB: 01/02/1985", "Phone: 407-555-0100", "Member ID: 39132817396", "Claim #: 731393143800", "Account No. 4788416", "Group Number: HHNX"]


def tag(text, n=1, box=(100, 100, 400, 120)):
    return d.Tag(n, text, box)


def verdict(text, known=()):
    return d.decide([tag(text)], 20, set(known))[1]


def shows(v, text):
    """What stays open of a line."""
    if v.how == "closed":
        return ""
    kept = list(text)
    for a, b, _ in v.hide:
        kept[a:b] = " " * (b - a)
    return "".join(kept)


@pytest.mark.parametrize("line", NAME_LINES + ADDRESS_LINES)
def test_ordinary_words_do_not_open_a_name_or_an_address(line):
    assert verdict(line).how == "closed"


@pytest.mark.parametrize("line", ["Grace Hunter", "Rose Baker", "Hill Park", "12 Oak Street", "Orlando, FL 32801", "Oak Street", "Ember Sparrow", "Clover Meadows", "Willow Brook", "Sage Rivers"])
def test_a_money_line_beside_them_does_not_open_them_either(line):
    tags = [tag(line, 1, (100, 100, 300, 120)), tag("$719.03", 2, (500, 100, 580, 120))]
    v = d.decide(tags, 20, set())
    assert v[1].how == "closed" and v[2].how == "open"


@pytest.mark.parametrize("line", LABELLED)
def test_the_value_after_a_person_label_stays_closed(line):
    value = line.split(":")[-1].split()[-1] if ":" in line else line.split()[-1]
    assert value.lower() not in shows(verdict(line), line).lower()


def test_the_lines_are_ordinary_words_to_the_old_rule():
    """Control: a rule of ordinary words alone would open them, so the tests above measure the hole itself."""
    words = d.english()
    for line in ["rose baker", "hill park", "oak street", "hope field"]:
        assert all(w in words for w in line.split())


def test_every_common_name_pair_stays_closed():
    rng = random.Random(7)
    first, sur = sorted(d._words("first_names.txt")), sorted(d._words("surnames.txt"))
    for _ in range(3000):
        a, b = rng.choice(first).title(), rng.choice(sur).title()
        for line in (f"{a} {b}", f"{b}, {a}", f"{a} {b}".upper()):
            assert verdict(line).how == "closed", line
            row = [tag(line, 1, (100, 100, 300, 120)), tag("$12.00", 2, (500, 100, 580, 120))]
            assert d.decide(row, 20, set())[1].how == "closed", line


@pytest.mark.parametrize("line", ["$88.00", "$1,574.58", "($40.00)", "27.00"])
def test_a_sum_opens_on_its_own(line):
    assert verdict(line).how == "open"


@pytest.mark.parametrize("line", ["Amount Due", "Total Charges", "Date of Service", "Patient Responsibility", "Deductible Amount", "Your Responsibility: $4.49",
                                  "Patient Responsibility: $4.49 Other Carrier Adjustments: $0.00", "Total Payment Amount: $40.43", "Page 1 of 4", "THIS IS NOT A BILL",
                                  "Explanation of Benefits", "RETAIN FOR TAX PURPOSES", "Claim Totals $302.00 $257.08", "Insurance Adjustment", "Patient Copay"])
def test_a_billing_label_stays_open(line):
    assert verdict(line).how == "open", line


@pytest.mark.parametrize("line", ["Nov 25, 2024 99213 Office Visit, Est Pt., Level 3 $240.00", "02/11/2025- 85610 $88.00 $77.03", "99213 Office Visit", "Primary Insurance Payment $53.12"])
def test_a_service_line_stays_open(line):
    tags = [tag(line, 1, (100, 100, 600, 120)), tag("$9.00", 2, (700, 100, 760, 120))]
    assert d.decide(tags, 20, set())[1].how == "open", line


def test_a_family_value_closes_even_a_service_line():
    line = "Grace 99213 Office Visit $240.00"
    assert "Grace" not in shows(verdict(line, {"grace"}), line)


def test_a_five_digit_number_opens_only_on_a_service_line():
    assert d.decide([tag("32801")], 20, set())[1].how == "closed"
    row = [tag("02/11/2025", 3, (10, 100, 90, 120)), tag("85610", 1, (100, 100, 170, 120)), tag("$88.00", 2, (300, 100, 380, 120))]
    assert d.decide(row, 20, set())[1].how == "open"


def test_a_number_under_an_account_header_stays_closed_on_a_money_line():
    tags = [tag("ACCOUNT NO.", 1, (300, 60, 400, 80)), tag("PAY THIS", 2, (500, 60, 590, 80)),
            tag("30955", 3, (300, 100, 370, 120)), tag("$719.03", 4, (500, 100, 580, 120))]
    v = d.decide(tags, 20, set())
    assert v[3].how == "closed" and v[4].how == "open"


def test_a_birth_date_stays_closed_and_a_statement_date_opens():
    v = d.decide([tag("DOB", 1, (100, 100, 150, 120)), tag("02/11/2025", 2, (300, 100, 400, 120))], 20, set())
    assert v[2].how == "closed"
    v = d.decide([tag("Statement Date", 1, (100, 100, 250, 120)), tag("07/06/2025", 2, (300, 100, 400, 120))], 20, set())
    assert v[2].how == "open" and v[2].why == "date:statement date"


def test_a_date_alone_stays_closed():
    assert verdict("01/02/1985").how == "closed"


def test_a_provider_stays_open_a_family_member_does_not():
    assert "QUILLFORD" in shows(verdict("Provider: QUILLFORD, AUGUSTINE P."), "Provider: QUILLFORD, AUGUSTINE P.")
    line = "Provider: Grace Hunter"
    assert "Hunter" not in shows(verdict(line, {"gracehunter"}), line)


def test_the_claim_number_closes_and_the_doctor_stays_on_one_line():
    line = "Claim:3270189, Provider: Greta I. V Vanterpool, MD"
    seen = shows(verdict(line), line)
    assert "3270189" not in seen and "Vanterpool" in seen


@pytest.mark.parametrize("line", ["Seaside Regional Hospital", "Harborlight Health", "Little Harbor Pediatrics - PA", "Women First OB/GYN Care, LLC"])
def test_an_organization_stays_open(line):
    assert verdict(line).how == "open", line


@pytest.mark.parametrize("line", ["H2PX375M007494 HLNX", "292006-143-69524025", "4744 500976", "PXVEVrdx", "954-555-0177", "https://payclinic24.example"])
def test_codes_and_addresses_on_the_web_stay_closed(line):
    assert verdict(line).how == "closed", line


@pytest.mark.parametrize("line,sum_", [("Mar 18, 2025 Castillo , Daniela 30955 AMOUNT $719.03", "$719.03"), ("Grace Hunter 30955 $12.00", "$12.00")])
def test_a_sum_beside_a_name_stays_and_the_rest_closes(line, sum_):
    seen = shows(verdict(line, {"castillo", "daniela"}), line)
    assert sum_ in seen and "Castillo" not in seen and "Grace" not in seen and "30955" not in seen


@pytest.mark.parametrize("line", ["Please note, this letter is not a bill.", "A27 Service is not consistent with the age of the member on file.",
                                  "You have one bill that is ready to pay. The total amount is", "CDA Allowed amount reflects the provider's contract with the plan",
                                  "If we do not receive updated coverage, or the plan does not pay, within 30 days"])
def test_a_plain_sentence_stays_open(line):
    assert verdict(line).how == "open", line


@pytest.mark.parametrize("line", ["0302 Lab, Immunology Hosp IP", "86880 Antihuman Globulin Test, Direct Med IP", "59410 Delivery and Postpartum Care Med IP",
                                  "Feb 11, 2025 59410 VAG DELIV & PP CARE (02/11/2025) $5,346.00", "Mar 18, 2025 Balance Transferred To Payment Plan ($712.31)", "COMMERCIAL -$1,574.58"])
def test_a_line_of_a_bill_stays_open(line):
    assert verdict(line).how == "open" and not verdict(line).hide, line


def test_location_and_clinician_stay_open():
    line = "Location: Seaside Regional Hosp | Clinician: Oswin Tremayne MD"
    assert "Tremayne" in shows(verdict(line), line)


BIRTH_WITH_LABEL = ["DOB: 01/02/1985", "DOB 01/02/1985", "D.O.B. 01/02/1985", "D0B 01/02/1985", "Date of Birth: 01/02/1985", "Date Of Birth 01/02/1985", "Date of Brith 01/02/1985",
                    "Birthdate 01/02/1985", "Brithdate: 01/02/1985", "Birth Date 01/02/1985", "Born 01/02/1985", "Birthday: Jan 2, 1985", "DOB: 02/11/2025", "Date of Birth 02/11/2025"]


@pytest.mark.parametrize("line", BIRTH_WITH_LABEL)
def test_a_birth_date_with_its_label_stays_closed(line):
    seen = shows(verdict(line), line)
    assert "1985" not in seen and "2025" not in seen


@pytest.mark.parametrize("label", ["DOB", "Date of Birth", "D0B", "Birthdate", "Birth Date"])
def test_a_birth_date_in_the_next_cell_or_under_its_label_stays_closed(label):
    beside = [tag(label, 1, (100, 100, 200, 120)), tag("02/11/2025", 2, (300, 100, 400, 120)), tag("$20.00", 3, (500, 100, 580, 120))]
    v = d.decide(beside, 20, set())
    assert v[2].how == "closed" and v[3].how == "open"
    under = [tag(label, 1, (100, 60, 200, 80)), tag("Amount", 2, (300, 60, 380, 80)), tag("02/11/2025", 3, (100, 100, 200, 120)), tag("$20.00", 4, (300, 100, 380, 120))]
    assert d.decide(under, 20, set())[3].how == "closed"


@pytest.mark.parametrize("date", ["01/02/1985", "Jan 2, 1985"])
def test_a_birth_date_without_a_label_stays_closed(date):
    assert verdict(date).how == "closed"
    v = d.decide([tag(date, 1, (100, 100, 200, 120)), tag("$20.00", 2, (300, 100, 380, 120))], 20, set())
    assert v[1].how == "closed"
    v = d.decide([tag(date, 1, (100, 100, 200, 120)), tag("Grace Hunter", 2, (220, 100, 300, 120)), tag("$20.00", 3, (500, 100, 580, 120))], 20, set())
    assert v[1].how == "closed"


def test_a_service_line_does_not_open_a_date_decades_older_than_the_sheet():
    row = [tag("03/11/2025", 5, (100, 60, 200, 80)), tag("99213", 6, (220, 60, 280, 80)), tag("Office Visit", 7, (300, 60, 400, 80)), tag("$90.00", 8, (500, 60, 580, 80)),
           tag("01/02/1985", 1, (100, 100, 200, 120)), tag("99213", 2, (220, 100, 280, 120)), tag("Office Visit", 3, (300, 100, 400, 120)), tag("$20.00", 4, (500, 100, 580, 120))]
    v = d.decide(row, 20, set())
    assert v[1].how == "closed" and v[5].how == "open"
    line = "01/02/1985 99213 Office Visit $20.00"
    assert "1985" not in shows(verdict(line), line)


def test_a_recent_date_beside_only_a_sum_stays_closed():
    assert d.decide([tag("02/11/2025", 1, (100, 100, 200, 120)), tag("$20.00", 2, (300, 100, 380, 120))], 20, set())[1].how == "closed"


@pytest.mark.parametrize("line", ["Effective Date 01/01/2025", "Renewal Date 03/03/2026", "Issued 03/03/2026", "Expires 03/03/2026"])
def test_a_date_under_a_label_outside_the_list_stays_closed(line):
    assert verdict(line).how == "closed"


@pytest.mark.parametrize("line,label", [("Date of Service 03/11/2025", "date of service"), ("Statement Date: 07/06/2025", "statement date"), ("Due Date 04/01/2026", "due date"),
                                        ("Admission Date 02/10/2025", "admission date"), ("Discharge Date: 02/12/2025", "discharge date"), ("Appeal deadline: 08/01/2025", "appeal deadline")])
def test_a_date_under_a_listed_label_opens_and_names_it(line, label):
    v = verdict(line)
    assert v.how == "open" and v.why == f"date:{label}"


def test_a_long_date_column_opens_by_its_header():
    tags = [tag("Dates of Service", 1, (100, 20, 220, 40))] + [tag("02/11/2025", n, (100, 40 + 40 * n, 200, 60 + 40 * n)) for n in range(2, 9)]
    v = d.decide(tags, 20, set())
    assert all(v[n].how == "open" and v[n].why == "date:dates of service" for n in range(2, 9))


CLOSED_VALUES = ["Account 30955", "Account No. 30955", "Account # 30955", "Acct 30955", "ACCT#30955", "Accounl No 30955", "Acount # 30955", "Polcy 30955", "Policy 30955",
                 "Policy No. 30955", "Policy # 30955", "Group 30955", "Grp 30955", "Group No: 30955", "Gruop 30955", "MRN 30955", "M.R.N. 30955", "SSN 123-45-6789", "S5N 123-45-6789",
                 "Phone 407 555 0100", "Phne: 407-555-0100", "Tel 4075550100", "Email anna@mail.example", "E-mail: anna@mail.example", "Emial: anna@mail.example",
                 "Adress: 12 Oak Street", "Addr 12 Oak Street", "Address 9 Sunset Way"]


@pytest.mark.parametrize("line", CLOSED_VALUES)
def test_a_value_after_a_number_label_stays_closed_in_any_spelling(line):
    seen = shows(verdict(line), line)
    for value in ("30955", "6789", "0100", "anna", "Oak", "Sunset"):
        assert value not in seen, seen


@pytest.mark.parametrize("label", ["Account No.", "Account", "Acct #", "Policy #", "Policy", "Polcy No", "Group", "MRN"])
def test_a_five_digit_number_beside_its_label_stays_closed_on_a_money_line(label):
    row = [tag(label, 1, (100, 100, 200, 120)), tag("30955", 2, (220, 100, 290, 120)), tag("$719.03", 3, (500, 100, 580, 120))]
    v = d.decide(row, 20, set())
    assert v[2].how == "closed" and v[3].how == "open"
    line = f"{label} 30955 $719.03"
    seen = shows(verdict(line), line)
    assert "30955" not in seen and "$719.03" in seen


@pytest.mark.parametrize("label", ["ACCOUNT NO.", "Policy Number", "Group #", "Member ID"])
def test_a_five_digit_number_under_its_label_stays_closed_on_a_service_line(label):
    tags = [tag(label, 1, (100, 60, 200, 80)), tag("30955", 2, (100, 100, 170, 120)), tag("03/11/2025", 3, (200, 100, 280, 120)), tag("Office Visit", 4, (300, 100, 400, 120)),
            tag("$719.03", 5, (500, 100, 580, 120))]
    assert d.decide(tags, 20, set())[2].how == "closed"


def test_a_bare_five_digit_number_beside_a_sum_stays_closed():
    row = [tag("30955", 1, (100, 100, 170, 120)), tag("$719.03", 2, (300, 100, 380, 120))]
    assert d.decide(row, 20, set())[1].how == "closed"


@pytest.mark.parametrize("line", ["Account Balance $5.00", "Group Health Plan", "Policy Year", "Phone calls are recorded for quality"])
def test_ordinary_words_near_a_number_label_stay_open(line):
    assert verdict(line).how == "open", line


FOOT = (100, 1500, 300, 1520)  # the foot of the sheet: the head is counted from it


def sheet(*tags):
    return d.decide(list(tags) + [tag("Page 1 of 1", 99, FOOT)], 20, set())


def test_a_bare_date_opens_once_at_the_head_of_the_sheet():
    v = sheet(tag("Date: 03/21/2025", 1, (100, 100, 300, 120)), tag("Date: 03/22/2025", 2, (100, 200, 300, 220)))
    assert (v[1].how, v[1].why) == ("open", "date:date") and v[2].how == "closed"


def test_a_bare_date_low_on_the_sheet_stays_closed():
    assert sheet(tag("Date: 03/21/2025", 1, (100, 900, 300, 920)))[1].how == "closed"


@pytest.mark.parametrize("label", ["Patient: Grace Hunter", "Name: Rose Baker", "Guarantor: Rose Baker", "Member: Mark Stone", "Address: 12 Oak Street", "PATIENT NAME"])
@pytest.mark.parametrize("date", ["Date: 03/14/1991", "Date: 03/14/2025"])
def test_a_bare_date_in_a_person_block_stays_closed(label, date):
    assert sheet(tag(label, 1, (100, 100, 300, 120)), tag(date, 2, (100, 130, 300, 150)))[2].how == "closed"


def test_a_bare_date_beside_a_person_label_in_its_own_cell_stays_closed():
    v = sheet(tag("Patient: Grace Hunter", 1, (100, 100, 300, 120)), tag("Date:", 2, (100, 130, 150, 150)), tag("03/14/1991", 3, (160, 130, 260, 150)))
    assert v[3].how == "closed"


def test_a_bare_date_decades_older_stays_closed_at_the_head():
    assert sheet(tag("Date: 03/14/1991", 1, (100, 100, 300, 120)))[1].how == "closed"
    assert sheet(tag("Date: 03/14/2020", 1, (100, 100, 300, 120)), tag("Date of Service 03/11/2025", 2, (100, 400, 400, 420)),
                 tag("Date of Service 03/12/2025", 3, (100, 440, 400, 460)))[1].how == "closed"


def test_a_column_called_date_opens_only_on_service_lines():
    tags = [tag("Date", 1, (100, 60, 200, 80)), tag("03/11/2025", 2, (100, 100, 200, 120)), tag("Office Visit", 3, (300, 100, 400, 120)), tag("$20.00", 4, (500, 100, 580, 120)),
            tag("03/14/2025", 5, (100, 140, 200, 160)), tag("$20.00", 6, (500, 140, 580, 160)), tag("03/15/2025", 7, (100, 180, 200, 200))]
    v = sheet(*tags)
    assert v[2].how == "open" and v[5].how == "closed" and v[7].how == "closed"


def test_a_code_and_its_description_open_without_a_sum():
    v = d.decide([tag("86880", 1, (100, 100, 170, 120)), tag("Antihuman Globulin Test, Direct Med IP", 2, (200, 100, 600, 120))], 20, set())
    assert v[1].how == "open" and v[2].how == "open"


@pytest.mark.parametrize("name", ["Grace Hunter", "Ember Sparrow", "Rose Baker"])
def test_a_number_beside_a_name_is_no_code_and_description(name):
    v = d.decide([tag("30955", 1, (100, 100, 170, 120)), tag(name, 2, (200, 100, 400, 120))], 20, set())
    assert v[1].how == "closed" and v[2].how == "closed"


@pytest.mark.parametrize("line", ["30955 Grace Hunter $12.00", "30955 Rose Baker $12.00", "30955 Ember Sparrow $12.00"])
def test_a_number_at_the_start_of_a_name_line_stays_closed(line):
    seen = shows(verdict(line), line)
    assert "30955" not in seen and "Hunter" not in seen and "Baker" not in seen and "Sparrow" not in seen and "$12.00" in seen


def test_a_cut_service_line_keeps_its_code_and_sum_and_closes_the_cut_word():
    tags = [tag("02/11/2025", 1, (10, 100, 90, 120)), tag("59410 Delivery and Po", 2, (100, 100, 300, 120)), tag("$5,346.00", 3, (500, 100, 590, 120))]
    v = d.decide(tags, 20, set())
    assert "59410" in shows(v[2], tags[1].text) and "Po" not in shows(v[2], tags[1].text) and v[3].how == "open"


SERVICES = [tag("Dates of Service", 10, (100, 700, 260, 720)), tag("02/11/2025", 11, (100, 740, 200, 760)), tag("99213", 12, (220, 740, 290, 760)), tag("Office Visit", 13, (300, 740, 400, 760)),
            tag("$20.00", 14, (500, 740, 580, 760))]
BLOCK = [tag("Member: Mark Stone", 1, (100, 100, 300, 120))]


def block_date(line, services=True):
    return sheet(*BLOCK, tag(line, 2, (100, 130, 300, 150)), *(SERVICES if services else []))[2]


def test_a_document_date_beside_a_person_opens_after_every_service():
    v = block_date("Date: 03/21/2025")
    assert (v.how, v.why) == ("open", "date:date")


def test_a_birth_date_in_a_patient_block_stays_closed_with_services_on_the_sheet():
    assert block_date("Date: 03/14/1991").how == "closed"


def test_a_date_beside_a_person_stays_closed_on_a_sheet_without_service_dates():
    assert block_date("Date: 03/21/2025", services=False).how == "closed"
    assert block_date("Date: 03/14/1991", services=False).how == "closed"


def test_a_date_equal_to_a_service_stays_closed():
    assert block_date("Date: 02/11/2025").how == "closed"


def test_a_date_before_a_service_stays_closed():
    assert block_date("Date: 02/10/2025").how == "closed"


def test_a_date_twelve_months_after_opens_and_the_thirteenth_month_does_not():
    assert block_date("Date: 02/11/2026").how == "open"
    assert block_date("Date: 02/12/2026").how == "closed"
    assert block_date("Date: 03/15/2026").how == "closed"


def test_the_same_holds_when_the_label_and_the_date_sit_apart():
    def apart(date_):
        return sheet(*BLOCK, tag("Date:", 2, (100, 130, 150, 150)), tag(date_, 3, (160, 130, 260, 150)), *SERVICES)[3]
    assert apart("03/21/2025").how == "open"
    for bad in ("03/14/1991", "02/11/2025", "03/15/2026"):
        assert apart(bad).how == "closed"


def test_a_date_inside_a_birth_row_is_no_service_date():
    v = sheet(*BLOCK, tag("Date: 03/21/2025", 2, (100, 130, 300, 150)), tag("DOB 03/25/2025 Dates of Service", 3, (100, 300, 400, 320)), *SERVICES)
    assert v[2].how == "open"


@pytest.mark.parametrize("line", ["02/12/2025 0251 025813185 ACETAMINOPHEN 500 MG TAB", "02/11/2025 0251 025594594 CEFAZOLIN 2 G/50 ML IN DEXTROSE IV",
                                  "02/12/2025 0251 025513813 SIMETHICONE 80 MG CHEW TAB", "02/13/2025 0272 027462297 HC ICE PACK PERINEAL"])
def test_a_charge_line_of_an_itemized_bill_stays_open(line):
    assert verdict(line).how == "open" and not verdict(line).hide, line


@pytest.mark.parametrize("line", ["02/12/2025 4788416 Grace Hunter", "0251 025813185 Grace Hunter", "025813185 ACETAMINOPHEN 500 MG TAB", "02/12/2025 0251 025813185 Grace Hunter",
                                  "02/12/2025 0251 025813185 Ember Sparrow"])
def test_a_long_number_without_the_shape_of_a_charge_line_stays_closed(line):
    seen = shows(verdict(line), line)
    assert "4788416" not in seen and "025813185" not in seen


def test_a_negative_sum_with_the_sign_after_the_dollar_opens():
    assert verdict("$-10,973.77").how == "open"


@pytest.mark.parametrize("line", ["of the date of this letter, the balance shown above becomes your", "Please see the date of the notice"])
def test_a_sentence_with_date_of_is_no_birth_label(line):
    v = verdict(line)
    assert v.how == "open" and not v.hide, line


@pytest.mark.parametrize("line", ["|02/11/2025-", "| 02/11/2025", "02/11/2025 |"])
def test_a_table_rule_read_as_a_bar_does_not_spoil_a_date(line):
    tags = [tag("Dates of Service", 1, (100, 20, 220, 40)), tag(line, 2, (100, 60, 200, 80))]
    assert d.decide(tags, 20, set())[2].how == "open"


def test_a_family_name_inside_a_line_closes_alone_and_the_line_stays():
    line = "Daniela's visit on February 11, 2025 Insurance applied"
    v = verdict(line, {"daniela", "castillo"})
    seen = shows(v, line)
    assert "Daniela" not in seen and "February 11, 2025" in seen and "Insurance" in seen


@pytest.mark.parametrize("line", ["Daniela Castillo 123 Oak Street", "Daniela lives at 12 Oak Street", "Daniela Hunter", "Daniela 407-555-0100"])
def test_what_is_left_after_a_family_name_must_pass_by_itself(line):
    v = verdict(line, {"daniela", "castillo"})
    seen = shows(v, line)
    for bad in ("Oak", "Hunter", "0100"):
        assert bad not in seen, seen


def test_an_organization_word_opens_on_the_next_sheet_only_with_that_name():
    v = d.decide([tag("Meridian Physician Services")], 20, set())
    orgs = d.org_words([tag("Meridian Physician Services")], v)
    assert "meridian" in orgs
    assert d.decide([tag("Meridian")], 20, set(), orgs)[1].how == "open"
    assert d.decide([tag("Meridian")], 20, set())[1].how == "closed"
    assert d.decide([tag("Grace Meridian")], 20, set(), orgs)[1].how == "closed"


@pytest.mark.parametrize("box,text", [((6, 688, 15, 707), "0081"), ((6, 601, 15, 619), "001"), ((6, 793, 15, 808), "NX"), ((6, 646, 15, 659), "8")])
def test_a_scrap_of_a_line_printed_sideways_stays_closed_beside_a_sum(box, text):
    tags = [tag(text, 1, box), tag("$12.00", 2, (300, box[1], 380, box[3])), tag("Office Visit", 3, (100, box[1], 280, box[3])), tag("edge", 4, (1200, 100, 1290, 120))]
    assert d.decide(tags, 20, set())[1].how == "closed"


def test_a_tall_piece_of_several_characters_is_sideways_anywhere_on_the_sheet():
    tags = [tag("007494", 1, (600, 300, 612, 380)), tag("$12.00", 2, (700, 330, 780, 350)), tag("edge", 4, (1200, 100, 1290, 120))]
    assert d.decide(tags, 20, set())[1].how == "closed"


def test_a_single_digit_of_a_table_stays_a_quantity():
    tags = [tag("1", 1, (600, 300, 609, 313)), tag("$12.00", 2, (700, 300, 780, 313)), tag("Office Visit", 3, (100, 300, 280, 313)), tag("02/11/2025", 5, (10, 300, 90, 313)), tag("edge", 4, (1200, 100, 1290, 120))]
    assert d.decide(tags, 20, set())[1].how == "open"


def test_a_bar_read_beside_a_sum_is_not_hidden_with_it():
    line = "Patient | $1,913.43"
    v = verdict(line)
    assert "$1,913.43" in shows(v, line) and all("$" not in line[a:b] for a, b, _ in v.hide)


def test_a_row_of_a_tilted_sheet_stays_one_row():
    """A photograph leans: the right end of a row can stand at the height of the next row's left end."""
    tags = [tag("Dates of Service", 1, (100, 20, 220, 34))]
    for row in range(3):
        y = 80 + 38 * row
        tags += [tag("02/11/2025-", 10 + row * 10, (100, y, 170, y + 11)), tag("85610", 11 + row * 10, (205, y - 1, 240, y + 10)),
                 tag("$64.00", 12 + row * 10, (270, y - 2, 310, y + 9)), tag("$7.06", 13 + row * 10, (470, y - 5, 500, y + 6)), tag("FS1", 14 + row * 10, (1220, y - 14, 1240, y - 3))]
    v = d.decide(tags, 11, set())
    assert all(v[10 + r * 10].how == "open" and v[11 + r * 10].how == "open" for r in range(3))


def test_a_web_address_is_no_description_of_a_service():
    tags = [tag("online or on your statement details. Visit pay.meridianhealth.example for more", 1, (100, 100, 600, 120)), tag("$12.00", 2, (700, 100, 780, 120))]
    assert d.decide(tags, 20, set())[1].how == "closed"


def test_a_box_cut_through_a_name_is_closed_with_the_name():
    tags = [tag("| More", 1, (274, 1255, 437, 1270)), tag("Moreno , Daniela", 2, (401, 1255, 533, 1272)), tag("$683.02", 3, (1041, 1259, 1108, 1277))]
    v = d.decide(tags, 14, set())
    assert v[2].how == "closed" and v[1].how == "closed"


def test_a_date_cut_in_two_is_closed_with_the_part_that_has_no_label():
    tags = [tag("| May 27,", 1, (70, 1254, 167, 1272)), tag("May 27, 2025", 2, (107, 1254, 212, 1272))]
    v = d._parts_of_closed(tags, {1: d.Verdict("open", "service"), 2: d.Verdict("closed", "date without a label")})
    assert v[1].how == "closed"


def test_a_piece_of_a_family_value_is_closed_with_no_neighbour_to_show_it():
    tags = [tag("| More", 1, (274, 1255, 400, 1270)), tag("$683.02", 3, (1041, 1259, 1108, 1277))]
    assert d.decide(tags, 14, {"moreno"})[1].how == "closed"


def test_a_sum_beside_a_closed_piece_that_reads_a_part_of_it_stays_open():
    tags = [tag("AMOUNT | $683.0", 1, (882, 1257, 1094, 1276)), tag("$683.02", 2, (1041, 1259, 1108, 1277))]
    v = d.decide(tags, 14, set())
    assert v[1].how == "closed" and v[2].how == "open"


def test_a_label_keeps_its_ink_when_a_closed_scrap_of_it_overlaps():
    tags = [tag("Reason Code Description", 1, (604, 975, 795, 985)), tag("ription", 2, (750, 975, 795, 985))]
    assert d.decide(tags, 14, set())[1].how == "open"
