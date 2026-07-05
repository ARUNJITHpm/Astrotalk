"""Tests for the prashnam (Kerala horary) rules: thamboola + swarna.

The rules are pure functions over a prashna chart dict, so these are fully
deterministic — no ephemeris, no settings. The service-level test exercises the
mocked client path (hermetic, like the other astrology_engine tests).
"""

import pytest

from app.modules.astrology_engine.prashnam import (
    _house_class,
    sankhya_prashnam,
    swarna_prashnam,
    thamboola_prashnam,
)
from app.platform.config import get_settings

# A minimal prashna chart: udaya lagna മകരം (index 9), Moon in ഇടവം (index 1),
# which is house 5 from the lagna. Matches the real-engine regression anchor.
_CHART = {
    "udaya_lagnam": "മകരം",
    "udaya_lagna_index": 9,
    "moon": {"rasi": "ഇടവം", "rasi_index": 1, "house": 5},
}


def test_house_classes_follow_precedence():
    assert _house_class(1) == "kendra"
    assert _house_class(10) == "kendra"      # kendra wins over upachaya
    assert _house_class(9) == "trikona"
    assert _house_class(6) == "dusthana"     # dusthana wins over upachaya
    assert _house_class(11) == "upachaya"
    assert _house_class(2) == "sama"
    with pytest.raises(ValueError):
        _house_class(13)


def test_swarna_reads_arudha_against_udaya_lagna():
    # Arudha മേടം (index 0) from lagna മകരം (index 9) → house 4 (kendra).
    r = swarna_prashnam(0, _CHART)
    assert r["mode"] == "swarna"
    assert r["arudha_rasi"] == "മേടം"
    assert r["arudha_house_from_lagna"] == 4
    assert r["arudha_lagna_relation"] == "kendra"
    # Moon in index 1 from arudha index 0 → house 2.
    assert r["moon_house_from_arudha"] == 2
    # Cues carry the exact tokens the corpus chunks are written around.
    assert "prashnam arudha മേടം" in r["cues"]
    assert "prashnam lagna house 4 kendra" in r["cues"]


def test_swarna_same_rasi_as_lagna_is_house_1():
    r = swarna_prashnam(9, _CHART)  # arudha == udaya lagna
    assert r["arudha_house_from_lagna"] == 1
    assert r["arudha_lagna_relation"] == "kendra"


def test_swarna_rejects_bad_square():
    with pytest.raises(ValueError):
        swarna_prashnam(12, _CHART)


def test_thamboola_parity_and_remainder():
    r = thamboola_prashnam(21, _CHART)
    assert r["mode"] == "thamboola"
    assert (r["parity"], r["remainder"]) == ("odd", 5)
    assert r["moon_house_from_lagna"] == 5
    assert r["moon_house_relation"] == "trikona"
    assert "prashnam thamboola odd leaves" in r["cues"]
    assert "prashnam thamboola remainder 5" in r["cues"]

    even = thamboola_prashnam(16, _CHART)
    assert (even["parity"], even["remainder"]) == ("even", 0)

    with pytest.raises(ValueError):
        thamboola_prashnam(0, _CHART)


def test_sankhya_maps_number_to_rasi_and_nakshatra():
    # 108 splits evenly: 9 numbers per rasi, 4 per nakshatra (navamsa padas).
    r1 = sankhya_prashnam(1, _CHART)
    assert r1["number_rasi"] == "മേടം"
    assert r1["number_nakshatram"] == "അശ്വതി"
    assert r1["number_pada"] == 1

    r54 = sankhya_prashnam(54, _CHART)
    assert r54["number_rasi"] == "കന്നി"          # (54-1)*12//108 = 5
    assert r54["number_nakshatram"] == "ചിത്തിര"   # (54-1)*27//108 = 13
    assert r54["number_pada"] == 2

    r108 = sankhya_prashnam(108, _CHART)
    assert r108["number_rasi"] == "മീനം"
    assert r108["number_nakshatram"] == "രേവതി"
    assert r108["number_pada"] == 4

    # The number's rasi reads against the udaya lagna like an arudha:
    # കന്നി (5) from മകരം (9) → house 9 (trikona).
    assert r54["number_house_from_lagna"] == 9
    assert r54["number_lagna_relation"] == "trikona"
    assert "prashnam lagna house 9 trikona" in r54["cues"]
    assert "ചിത്തിര" in r54["cues"]  # pulls the nakshatra profile chunk

    with pytest.raises(ValueError):
        sankhya_prashnam(0, _CHART)
    with pytest.raises(ValueError):
        sankhya_prashnam(109, _CHART)


async def test_service_prashnam_reading_via_mock_client(monkeypatch):
    # Hermetic: pin the mock ephemeris so no pyswisseph work runs.
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    from app.modules.astrology_engine.service import AstrologyEngineService

    svc = AstrologyEngineService()
    r = await svc.get_prashnam_reading("swarna", arudha_rasi_index=3)
    assert r["mode"] == "swarna"
    assert r["prashna_chart"]["mock"] is True
    assert 1 <= r["arudha_house_from_lagna"] <= 12
    assert r["cues"]

    t = await svc.get_prashnam_reading("thamboola", leaf_count=13)
    assert t["parity"] == "odd" and t["remainder"] == 5

    with pytest.raises(ValueError):
        await svc.get_prashnam_reading("thamboola")  # missing leaf_count
    with pytest.raises(ValueError):
        await svc.get_prashnam_reading("ashtamangala")  # not offered as a mode
