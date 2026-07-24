"""Tests for the REAL Swiss Ephemeris engine (compute_* pure functions).

These call the astronomy directly — no settings, no .env, fully deterministic for
a fixed instant — so they verify the real natal chart, transits (gochara) and
panchangam that the app now serves with MOCK_EPHEMERIS=false.
"""

from datetime import date, datetime, time, timezone

import pytest

from app.modules.astrology_engine.swiss_ephemeris import (
    RASIS,
    VARGA_INFO,
    _varga_sign,
    compute_natal_chart,
    compute_panchangam,
    compute_prashna_chart,
    compute_transits,
    compute_vargas,
)

# A fixed birth event used as a known-good regression anchor. Swiss Ephemeris is
# stable, so these derived values should not drift.
_BIRTH = dict(dob=date(1990, 1, 15), birth_time=time(7, 45),
              lat=9.9312, lng=76.2673, tz="Asia/Kolkata")


def test_natal_chart_is_real_and_well_formed():
    c = compute_natal_chart(**_BIRTH)
    assert c["mock"] is False
    assert c["source"] == "swiss-ephemeris"
    assert c["system"] == "vedic" and c["ayanamsa"] == "lahiri"
    # All nine grahas, each with the full Vedic derivation.
    assert len(c["planets"]) == 9
    assert {"rasi", "rasi_index", "longitude", "house", "nakshatra", "retrograde"} <= (
        c["planets"]["chandra"].keys()
    )
    # Lahiri ayanamsa is ~23.7° around 1990.
    assert 23 < c["ayanamsa_value"] < 24
    # Vimshottari timeline is embedded and anchored on the Moon.
    assert c["dasha"]["system"] == "vimshottari"
    assert c["dasha"]["current"]["mahadasha"]["lord"]


def test_natal_chart_known_values():
    # Regression anchor for 1990-01-15 07:45 IST, Kochi (Lahiri).
    c = compute_natal_chart(**_BIRTH)
    assert c["rasi"] == "ചിങ്ങം"          # janma rasi (Moon)
    assert c["nakshatram"] == "പൂരം"       # janma nakshatram (Moon)
    assert c["lagnam"] == "മകരം"           # ascendant sign


def test_natal_chart_astronomy_is_deterministic():
    a = compute_natal_chart(**_BIRTH)
    b = compute_natal_chart(**_BIRTH)
    # The only time-varying part is the "currently running" dasha (as_of=now);
    # everything else (positions, lagna, timeline) is fixed for a birth event.
    a["dasha"].pop("current", None)
    b["dasha"].pop("current", None)
    assert a == b


def test_unknown_ayanamsa_raises():
    with pytest.raises(ValueError):
        compute_natal_chart(**_BIRTH, ayanamsa="bogus")


def test_prashna_chart_known_values():
    # Regression anchor: 2026-01-01 09:00 IST at Kochi. Prashna is the chart of
    # the question moment — the udaya lagna anchors it, Moon + tithi support.
    from zoneinfo import ZoneInfo

    c = compute_prashna_chart(
        datetime(2026, 1, 1, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata")), 9.9312, 76.2673
    )
    assert c["mock"] is False and c["source"] == "swiss-ephemeris"
    assert c["udaya_lagnam"] == "മകരം"
    assert c["moon"]["rasi"] == "ഇടവം"
    assert c["moon"]["nakshatram"] == "രോഹിണി"
    assert (c["tithi"], c["paksha"]) == ("ത്രയോദശി", "shukla")
    # Houses are whole-sign from the udaya lagna: the Moon in ഇടവം (index 1)
    # from മകരം (index 9) is house 5.
    assert c["moon"]["house"] == 5
    assert len(c["planets"]) == 9
    assert all(1 <= p["house"] <= 12 for p in c["planets"].values())


def test_prashna_lagna_is_location_and_time_sensitive():
    from zoneinfo import ZoneInfo

    kochi_9am = compute_prashna_chart(
        datetime(2026, 1, 1, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata")), 9.9312, 76.2673
    )
    kochi_3pm = compute_prashna_chart(
        datetime(2026, 1, 1, 15, 0, tzinfo=ZoneInfo("Asia/Kolkata")), 9.9312, 76.2673
    )
    # ~6 hours later the ascendant has moved several signs on.
    assert kochi_9am["udaya_lagnam"] != kochi_3pm["udaya_lagnam"]


def test_transits_real_shape():
    t = compute_transits(datetime(2026, 6, 25, 9, 0, tzinfo=timezone.utc))
    assert t["mock"] is False and t["source"] == "swiss-ephemeris"
    assert len(t["transits"]) == 9
    surya = t["transits"]["surya"]
    assert {"rasi", "rasi_index", "longitude", "nakshatra", "retrograde"} <= surya.keys()
    # No natal chart supplied → no gochara house frame.
    assert t["gochara_from"] is None
    assert "house_from_moon" not in surya


def test_transits_gochara_from_natal_moon():
    chart = compute_natal_chart(**_BIRTH)
    t = compute_transits(datetime(2026, 6, 25, 9, 0, tzinfo=timezone.utc), chart)
    assert t["gochara_from"] == "chandra"
    for body in t["transits"].values():
        assert 1 <= body["house_from_moon"] <= 12


def test_varga_sign_classical_rules():
    # D9 navamsa: first 3°20' of Aries → Aries; 0° Taurus (fixed) → 9th from it
    # (Capricorn); 0° Gemini (dual) → 5th from it (Libra).
    assert _varga_sign("D9", 0.0) == 0
    assert _varga_sign("D9", 30.0) == 9
    assert _varga_sign("D9", 60.0) == 6
    # D10 dashamsa: 15° Aries (odd sign, 6th part) → Leo; 0° Taurus (even sign)
    # → 9th from Taurus (Capricorn).
    assert _varga_sign("D10", 15.0) == 5
    assert _varga_sign("D10", 30.0) == 9
    # D12 dwadasamsa: 5° Taurus is the 3rd 2°30' part → 3rd sign from Taurus.
    assert _varga_sign("D12", 35.0) == 3
    # D3 drekkana: 25° Aries is the 3rd decanate → 9th sign from Aries.
    assert _varga_sign("D3", 25.0) == 8
    with pytest.raises(ValueError):
        _varga_sign("D60", 10.0)


def test_compute_vargas_shape():
    vargas = compute_vargas({"surya": 123.4, "chandra": 288.9}, lagna_longitude=45.0)
    assert set(vargas) == set(VARGA_INFO)
    d9 = vargas["D9"]
    assert d9["varga"] == "navamsa" and "marriage" in d9["signifies"]
    assert d9["lagnam"] in RASIS
    for body in d9["planets"].values():
        assert body["rasi"] in RASIS
        assert 1 <= body["house"] <= 12


def test_natal_chart_embeds_vargas():
    c = compute_natal_chart(**_BIRTH)
    assert set(c["vargas"]) == set(VARGA_INFO)
    # Varga positions must be consistent with the D1 longitudes they derive from.
    moon_lon = c["planets"]["chandra"]["longitude"]
    assert c["vargas"]["D9"]["planets"]["chandra"]["rasi_index"] == _varga_sign("D9", moon_lon)


def test_panchangam_real():
    p = compute_panchangam(date(2026, 6, 25))
    assert p["mock"] is False and p["source"] == "swiss-ephemeris"
    assert p["date"] == "2026-06-25"
    assert p["nakshatram"] and p["tithi"] and p["nalla_neram"]
    assert 0 <= p["tithi_index"] <= 29
    assert p["paksha"] in ("shukla", "krishna")
    # Same day -> identical panchangam.
    assert compute_panchangam(date(2026, 6, 25)) == p
