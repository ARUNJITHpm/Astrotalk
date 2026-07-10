"""Tests for deterministic dosha detection (astrology_engine.doshas).

Doshas are pure functions over positions — no ephemeris, no network — so these
are fully hermetic. Framing/tone of doshas is the knowledge corpus's job and is
covered by the knowledge tests.
"""

from app.modules.astrology_engine.doshas import (
    detect_natal_doshas,
    detect_sade_sati,
)


def _planet(house: int, rasi_index: int, longitude: float) -> dict:
    return {"house": house, "rasi_index": rasi_index, "longitude": longitude}


def _chart_planets(mars_house: int, mars_rasi: int, moon_rasi: int) -> dict:
    """Minimal planets mapping; longitudes spread so kala sarpa is NOT triggered."""
    return {
        "surya": _planet(3, 2, 10.0),
        "chandra": _planet(1, moon_rasi, 200.0),
        "chevvai": _planet(mars_house, mars_rasi, 100.0),
        "budhan": _planet(4, 3, 350.0),
        "guru": _planet(5, 4, 170.0),
        "shukran": _planet(2, 1, 190.0),
        "shani": _planet(9, 8, 300.0),
        "rahu": _planet(6, 5, 0.0),
        "ketu": _planet(12, 11, 180.0),
    }


def test_chovva_dosha_from_lagna():
    # Mars in the 7th from lagna in Thula (rasi 6, not exempt/dignified) → an
    # uncancelled dosha. Moon count lands on the 4th (also a chovva house), so
    # both frames fire → strong.
    planets = _chart_planets(mars_house=7, mars_rasi=6, moon_rasi=3)
    doshas = detect_natal_doshas(planets)
    chovva = doshas["chovva_dosha"]
    assert chovva["present"] is True
    assert chovva["effective"] is True
    assert chovva["cancelled"] is False
    assert chovva["severity"] == "strong"
    assert chovva["from_lagna"] is True
    assert chovva["mars_house_from_lagna"] == 7


def test_chovva_dosha_from_moon_only():
    # Mars in the 5th from lagna (clean) but 2nd from the Moon → dosha (Kerala
    # convention counts both frames). Mars in Simha (rasi 4) is not exempt for
    # the 2nd house, so the single frame is uncancelled → mild.
    planets = _chart_planets(mars_house=5, mars_rasi=4, moon_rasi=3)
    doshas = detect_natal_doshas(planets)
    chovva = doshas["chovva_dosha"]
    assert chovva["present"] is True
    assert chovva["effective"] is True
    assert chovva["severity"] == "mild"
    assert chovva["from_lagna"] is False
    assert chovva["from_moon"] is True
    assert chovva["mars_house_from_moon"] == 2


def test_no_chovva_dosha():
    # Mars 5th from lagna and 5th from Moon → no dosha.
    planets = _chart_planets(mars_house=5, mars_rasi=4, moon_rasi=0)
    chovva = detect_natal_doshas(planets)["chovva_dosha"]
    assert chovva["present"] is False
    assert chovva["effective"] is False
    assert chovva["severity"] == "none"


def test_chovva_cancelled_by_own_sign():
    # Mars in the 1st in its own sign Mesha (rasi 0) → present but cancelled from
    # every frame (own-sign parihara).
    planets = _chart_planets(mars_house=1, mars_rasi=0, moon_rasi=0)
    chovva = detect_natal_doshas(planets)["chovva_dosha"]
    assert chovva["present"] is True
    assert chovva["cancelled"] is True
    assert chovva["effective"] is False
    assert chovva["severity"] == "cancelled"
    assert "mars_in_own_or_exalted_sign" in chovva["cancellation_reasons"]


def test_chovva_cancelled_by_exaltation_in_seventh():
    # Mars exalted in Makara (rasi 9) in the 7th → cancelled.
    planets = _chart_planets(mars_house=7, mars_rasi=9, moon_rasi=9)
    chovva = detect_natal_doshas(planets)["chovva_dosha"]
    assert chovva["present"] is True
    assert chovva["cancelled"] is True
    assert chovva["severity"] == "cancelled"


def test_chovva_cancelled_by_house_sign_exemption():
    # Mars in the 2nd in Mithuna (rasi 2), which is exempt for the 2nd house.
    # Moon count also lands on the 2nd → both frames exempt → cancelled.
    planets = _chart_planets(mars_house=2, mars_rasi=2, moon_rasi=0)
    chovva = detect_natal_doshas(planets)["chovva_dosha"]
    assert chovva["present"] is True
    assert chovva["cancelled"] is True
    assert "house2_sign_exempt" in chovva["cancellation_reasons"]


def test_chovva_mild_when_one_frame_cancelled():
    # Lagna frame: 2nd house in Mithuna (rasi 2) → exempt/cancelled.
    # Moon frame: mars rasi 2 counted from moon rasi 7 → house 8 (chovva), and
    # rasi 2 is not exempt for the 8th → uncancelled. One uncancelled → mild.
    planets = _chart_planets(mars_house=2, mars_rasi=2, moon_rasi=7)
    chovva = detect_natal_doshas(planets)["chovva_dosha"]
    assert chovva["from_lagna"] is True
    assert chovva["from_moon"] is True
    assert chovva["mars_house_from_moon"] == 8
    assert chovva["cancelled"] is False
    assert chovva["effective"] is True
    assert chovva["severity"] == "mild"


def test_kala_sarpa_present_when_all_grahas_on_one_side():
    # Rahu at 0°, Ketu at 180°; every classical graha between 10° and 170°.
    planets = {
        "rahu": _planet(1, 0, 0.0),
        "ketu": _planet(7, 6, 180.0),
        "surya": _planet(1, 0, 10.0),
        "chandra": _planet(2, 1, 40.0),
        "chevvai": _planet(3, 2, 70.0),
        "budhan": _planet(4, 3, 100.0),
        "guru": _planet(5, 4, 130.0),
        "shukran": _planet(6, 5, 150.0),
        "shani": _planet(6, 5, 170.0),
    }
    kala = detect_natal_doshas(planets)["kala_sarpa_dosha"]
    assert kala["present"] is True
    assert kala["hemmed_side"] == "rahu-to-ketu"


def test_kala_sarpa_absent_when_axis_straddled():
    planets = _chart_planets(mars_house=3, mars_rasi=2, moon_rasi=0)
    assert detect_natal_doshas(planets)["kala_sarpa_dosha"]["present"] is False


def test_missing_positions_degrade_to_not_computed():
    doshas = detect_natal_doshas({})
    assert doshas["chovva_dosha"] == {"present": False, "computed": False}
    assert doshas["kala_sarpa_dosha"] == {"present": False, "computed": False}


def test_sade_sati_phases():
    assert detect_sade_sati(12) == {
        "active": True, "computed": True, "phase": "rising",
        "saturn_house_from_moon": 12,
    }
    assert detect_sade_sati(1)["phase"] == "peak"
    assert detect_sade_sati(2)["phase"] == "setting"
    assert detect_sade_sati(5)["active"] is False
    assert detect_sade_sati(None) == {"active": False, "computed": False}
