"""Each photo is checked against everything the earlier ones printed, and what sticks to a token is closed the same way."""
from types import SimpleNamespace

import pytest

from billradar import local_reader, pipeline, providers, redact, sam
from billradar.case import Profile


class Stop(Exception):
    pass


def _sheet(n: int) -> sam.Sheet:
    return sam.Sheet(f"S{n}", None, 1.0, None, f"image {n}", False)


@pytest.fixture
def pile(monkeypatch):
    """Three photos with a sheet each, the finder and the drawing left out. Reports what each step saw."""
    seen = SimpleNamespace(known=[], sent=[])

    def finder(client, photo, send=None, crop_from=None):
        seen.sent.append(photo)
        return SimpleNamespace(sheets=[_sheet(1)], seconds=0.5, replayed=True, dropped=[])

    def copy_of(img, secrets):
        seen.known.append(sum(s.kind == "MAIL" for s in secrets))
        return img

    monkeypatch.setattr(providers, "sheet_finder", lambda client: finder)
    monkeypatch.setattr(sam, "load_photo", lambda raw: raw)
    monkeypatch.setattr(sam, "overlay", lambda *a: None)
    monkeypatch.setattr(pipeline, "_jpeg", lambda img: b"")
    monkeypatch.setattr(redact, "sam_copy", copy_of)
    return seen


CLIENT = SimpleNamespace(live=False, calls=[])
PROFILE = Profile(household_size=3, annual_income=50000)


def test_a_number_on_an_early_photo_guards_the_copy_of_a_later_one(pile, monkeypatch):
    def learn(img, vault):
        vault.token("MAIL", f"99000{len(vault.secrets)}{img[-1]}")

    def closing(img, vault):
        raise Stop

    monkeypatch.setattr(redact, "learn", learn)
    monkeypatch.setattr(redact, "redact", closing)
    with pytest.raises(Stop):
        pipeline.prepare(CLIENT, ["photo 1", "photo 2", "photo 3"], [], PROFILE, private=True)
    assert pile.known == [0, 1, 2]


def test_with_no_local_model_the_second_photo_never_leaves(pile, monkeypatch):
    def learn(img, vault):
        raise local_reader.NotAvailable("no model")

    monkeypatch.setattr(redact, "learn", learn)
    with pytest.raises(pipeline.RealDataGate):
        pipeline.prepare(CLIENT, ["photo 1", "photo 2", "photo 3"], [], PROFILE, private=True)
    assert pile.sent == ["photo 1"]


def test_no_photos_no_time_for_the_finder():
    assert pipeline.prepare(CLIENT, [], [], PROFILE).timings == {}


@pytest.mark.parametrize("tail, closed", [
    ("TMT237851G7", "237851G7"), ("LDH-000123", "000123"), ("LDH-000123-7.", "000123"), ("123456-789.12", "123456"),
    ("123456-789,", "123456"), ("AB-123456-7/8", "123456"), ("12-345678-9.", "12-345678"), ("Acct 1234567-8/", "1234567"),
    ("x 123456-7890.", "123456"), ("4567890-12/25", "4567890"), ("ABCDEF123456", "123456"), ("ABCDEFG123456", "G123456"),
    ("abcdefghij123456", "ghij123456"), ("CASTILLO123456", "LO123456"), ("---123456", "-123456"), ("--123456", "123456"),
])
def test_what_sticks_to_a_token_is_closed_as_a_code(tail, closed):
    vault = redact.Vault()
    assert [text for _, _, text in ((a, b, ("[CODE]" + tail)[a:b]) for a, b, _ in redact._glued_ids("[CODE]" + tail, vault))] == [closed]


@pytest.mark.parametrize("tail", ["AB123456.", "123456.78", "1,234,567", "1234567,", "99222-1234567.", "_123456", "   123456", "12345", "abcdefgh 123456"])
def test_an_amount_or_a_short_number_after_a_token_stays(tail):
    assert redact._glued_ids("[CODE]" + tail, redact.Vault()) == []


@pytest.mark.parametrize("seed", [{"Daniela Castillo": 1, "Castillo, Daniela": 2}, {"Castillo, Daniela": 1, "Daniela Castillo": 2}])
def test_one_person_keeps_one_token_whichever_way_the_names_are_listed(seed):
    vault = redact.Vault(seed={("PATIENT", name): f"[PATIENT_{n}]" for name, n in seed.items()})
    assert vault.by_value[("PATIENT", "castillodaniela")].token == vault.by_value[("PATIENT", "danielacastillo")].token
