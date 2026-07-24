"""Hermetic tests for the Kerala pathu-porutham engine.

Pure computation — no ephemeris, no network. Nakshatra/rasi indices follow
swiss_ephemeris.NAKSHATRAS / RASIS. These lock the reference tables and the
grading so an accidental table edit is caught.
"""

import pytest

from app.modules.astrology_engine.porutham import (
    ADHAMAM,
    UTHAMAM,
    Star,
    compute_porutham,
    star_from_chart,
)
from app.modules.astrology_engine.swiss_ephemeris import NAKSHATRAS, RASIS


def _star(nak: int, rasi: int, sex: str) -> Star:
    return Star(nakshatra=nak, rasi=rasi, sex=sex)


def test_all_ten_poruthams_present_and_scored():
    result = compute_porutham(_star(0, 0, "female"), _star(6, 2, "male"))
    assert set(result["poruthams"]) == {
        "dina", "gana", "mahendra", "stree_deergha", "yoni",
        "rasi", "rasyadhipathi", "vasya", "rajju", "vedha",
    }
    assert result["max_score"] == 10.0
    # score is the sum of the ten point values (each 0, 0.5 or 1).
    assert result["score"] == round(
        sum(p["points"] for p in result["poruthams"].values()), 1
    )
    assert 0.0 <= result["score"] <= 10.0


def test_rajju_dosha_same_group_fails():
    # Ashwini (0) and Makam (9) are both in the pada rajju -> rajju dosha.
    result = compute_porutham(_star(0, 0, "female"), _star(9, 4, "male"))
    assert result["poruthams"]["rajju"]["grade"] == ADHAMAM
    assert result["rajju_dosha"] is True


def test_rajju_different_group_passes():
    # Ashwini (0, pada) and Bharani (1, kati) are different rajjus.
    result = compute_porutham(_star(0, 0, "female"), _star(1, 1, "male"))
    assert result["poruthams"]["rajju"]["grade"] == UTHAMAM
    assert result["rajju_dosha"] is False


def test_vedha_pair_fails():
    # Ashwini (0) / Thrikketta (17) is a vedha pair.
    result = compute_porutham(_star(0, 0, "female"), _star(17, 7, "male"))
    assert result["poruthams"]["vedha"]["grade"] == ADHAMAM


def test_vedha_non_pair_passes():
    result = compute_porutham(_star(0, 0, "female"), _star(3, 1, "male"))
    assert result["poruthams"]["vedha"]["grade"] == UTHAMAM


def test_same_star_shares_rajju_and_gana():
    # Identical stars: same gana (uthamam) but same rajju (dosha).
    result = compute_porutham(_star(4, 4, "female"), _star(4, 4, "male"))
    assert result["poruthams"]["gana"]["grade"] == UTHAMAM
    assert result["poruthams"]["rajju"]["grade"] == ADHAMAM
    assert result["poruthams"]["yoni"]["grade"] == UTHAMAM  # same animal


def test_gana_deva_rakshasa_is_worst():
    # Ashwini (0, deva) vs Karthika (2, rakshasa) -> adhamam.
    result = compute_porutham(_star(0, 0, "female"), _star(2, 1, "male"))
    assert result["poruthams"]["gana"]["grade"] == ADHAMAM


def test_rasi_shashtashtaka_is_dosha():
    # Rasis 6 apart (0 -> 5): shashtashtaka 6/8 -> adhamam.
    result = compute_porutham(_star(0, 0, "female"), _star(6, 5, "male"))
    assert result["poruthams"]["rasi"]["grade"] == ADHAMAM


def test_rasyadhipathi_same_lord_is_uthamam():
    # Mesha (0) and Vrischika (7) are both ruled by Mars.
    result = compute_porutham(_star(0, 0, "female"), _star(6, 7, "male"))
    assert result["poruthams"]["rasyadhipathi"]["grade"] == UTHAMAM


def test_directional_poruthams_are_not_symmetric():
    # Dina/mahendra/stree-deergha count female -> male, so swapping the roles
    # can change the count (and thus the grade). At least the raw counts differ.
    a, b = _star(0, 0, "female"), _star(10, 2, "male")
    forward = compute_porutham(a, _star(b.nakshatra, b.rasi, "male"))
    backward = compute_porutham(_star(b.nakshatra, b.rasi, "female"), _star(a.nakshatra, a.rasi, "male"))
    assert forward["poruthams"]["mahendra"]["reason"] != backward["poruthams"]["mahendra"]["reason"]


def test_star_from_chart_resolves_names():
    chart = {"nakshatram": NAKSHATRAS[6], "rasi": RASIS[2]}
    star = star_from_chart(chart, sex="male", name="Chaithanya")
    assert star.nakshatra == 6
    assert star.rasi == 2
    assert star.name == "Chaithanya"


def test_star_from_chart_rejects_pending_chart():
    with pytest.raises(ValueError):
        star_from_chart({"status": "pending"}, sex="female")


def test_reference_tables_cover_all_27_and_12():
    # Every nakshatra/rasi index must resolve; compute a full round-robin sample
    # to exercise the tables without an index error.
    for nf in range(27):
        for nm in (0, 9, 18, 26):
            r = compute_porutham(_star(nf, nf % 12, "female"), _star(nm, nm % 12, "male"))
            assert 0.0 <= r["score"] <= 10.0
