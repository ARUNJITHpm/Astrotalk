"""Deterministic dosha detection (internal to astrology_engine).

Doshas are FACTS computed from planetary positions — pure if-statements over the
chart, never an LLM call and never retrieval. The *framing* of a dosha (what it
means, how to talk about it without fear) lives in the knowledge corpus and the
persona rules (GUARDRAILS.md §1: guidance and agency, never doom).

Detected here:
  - Chovva (Mangal/Kuja) dosha — Mars in houses 1, 2, 4, 7, 8 or 12. Kerala
    convention checks the placement both from the lagna and from the Moon.
  - Kala Sarpa dosha — all seven classical grahas confined to one side of the
    Rahu–Ketu axis.
  - Sade Sati — transit Saturn in the 12th, 1st or 2nd house from the natal
    Moon (janma rasi); computed from transits, so it lives in its own function.
"""

from __future__ import annotations

# Houses that place Mars in chovva dosha, counted from lagna or Moon.
_CHOVVA_HOUSES = frozenset({1, 2, 4, 7, 8, 12})

# The seven classical grahas checked against the Rahu–Ketu axis.
_CLASSICAL_GRAHAS = ("surya", "chandra", "chevvai", "budhan", "guru", "shukran", "shani")

# Sade Sati phase by Saturn's whole-sign house from the natal Moon.
_SADE_SATI_PHASES = {12: "rising", 1: "peak", 2: "setting"}


def _house_from(rasi_index: int, reference_rasi_index: int) -> int:
    """Whole-sign house (1–12) of a rasi counted from a reference rasi."""
    return (rasi_index - reference_rasi_index) % 12 + 1


def detect_natal_doshas(planets: dict[str, dict]) -> dict:
    """Detect natal doshas from the chart's ``planets`` mapping.

    Expects each entry to carry ``house`` (from lagna), ``rasi_index`` and
    ``longitude`` — the shape ``compute_natal_chart`` builds. Returns plain
    JSON-serializable facts; interpretation is the knowledge module's job.
    """
    return {
        "chovva_dosha": _detect_chovva(planets),
        "kala_sarpa_dosha": _detect_kala_sarpa(planets),
    }


def _detect_chovva(planets: dict[str, dict]) -> dict:
    mars = planets.get("chevvai")
    moon = planets.get("chandra")
    if not mars or not moon:
        return {"present": False, "computed": False}

    from_lagna = int(mars["house"])
    from_moon = _house_from(int(mars["rasi_index"]), int(moon["rasi_index"]))
    lagna_hit = from_lagna in _CHOVVA_HOUSES
    moon_hit = from_moon in _CHOVVA_HOUSES
    return {
        "present": lagna_hit or moon_hit,
        "computed": True,
        "from_lagna": lagna_hit,
        "from_moon": moon_hit,
        "mars_house_from_lagna": from_lagna,
        "mars_house_from_moon": from_moon,
    }


def _detect_kala_sarpa(planets: dict[str, dict]) -> dict:
    rahu = planets.get("rahu")
    if rahu is None or "longitude" not in rahu:
        return {"present": False, "computed": False}
    missing = [g for g in _CLASSICAL_GRAHAS if "longitude" not in planets.get(g, {})]
    if missing:
        return {"present": False, "computed": False}

    rahu_lon = float(rahu["longitude"]) % 360.0
    # Arc position of each graha measured forward from Rahu; Ketu sits at 180°.
    offsets = [
        (float(planets[g]["longitude"]) - rahu_lon) % 360.0 for g in _CLASSICAL_GRAHAS
    ]
    all_rahu_to_ketu = all(0.0 < off < 180.0 for off in offsets)
    all_ketu_to_rahu = all(180.0 < off < 360.0 for off in offsets)
    present = all_rahu_to_ketu or all_ketu_to_rahu
    return {
        "present": present,
        "computed": True,
        "hemmed_side": (
            "rahu-to-ketu" if all_rahu_to_ketu
            else "ketu-to-rahu" if all_ketu_to_rahu
            else None
        ),
    }


def detect_sade_sati(saturn_house_from_moon: int | None) -> dict:
    """Sade Sati status from transit Saturn's whole-sign house from the natal Moon."""
    if saturn_house_from_moon is None:
        return {"active": False, "computed": False}
    phase = _SADE_SATI_PHASES.get(int(saturn_house_from_moon))
    return {
        "active": phase is not None,
        "computed": True,
        "phase": phase,
        "saturn_house_from_moon": int(saturn_house_from_moon),
    }
