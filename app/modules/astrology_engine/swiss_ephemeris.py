"""Self-computed Vedic natal chart via the Swiss Ephemeris (pyswisseph).

This is the *real* replacement for the mocked ``EphemerisClient`` — it computes
sidereal (Lahiri/KP/Raman) planetary positions, nakshatra + pada, and the
lagna (ascendant) offline, with no external API and no per-call cost.

Design notes
------------
* **No ephemeris data files required.** We use the Moshier analytical ephemeris
  (``FLG_MOSEPH``), which is built into pyswisseph and accurate to well under an
  arc-minute for modern dates. For arc-second accuracy over a wider date range,
  download the Swiss Ephemeris ``.se1`` files, call ``swe.set_ephe_path(dir)``,
  and swap ``_FLAGS`` to use ``swe.FLG_SWIEPH``.
* **Sidereal, not tropical.** Vedic astrology is sidereal: we subtract the
  ayanamsa. ``swe.set_sid_mode`` + ``FLG_SIDEREAL`` handle this for both planets
  and the ascendant.
* **Whole-sign houses.** The traditional Vedic house system: the lagna's rasi is
  house 1, the next rasi house 2, and so on. A planet's house is therefore just
  its rasi offset from the lagna.
* **Licensing.** Swiss Ephemeris is dual-licensed AGPL / commercial. Keeping this
  engine in its own module makes it easy to isolate for the license boundary.

Run standalone for a quick demo::

    python -m app.modules.astrology_engine.swiss_ephemeris
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import swisseph as swe

# --- Astrological name tables (Malayalam), in canonical order. ---------------
# These mirror the strings the mock EphemerisClient returns so downstream code
# (persona, content templates) sees one consistent vocabulary.

NAKSHATRAS = [
    "അശ്വതി", "ഭരണി", "കാർത്തിക", "രോഹിണി", "മകയിരം", "തിരുവാതിര",
    "പുണർതം", "പൂയം", "ആയില്യം", "മകം", "പൂരം", "ഉത്രം",
    "അത്തം", "ചിത്തിര", "ചോതി", "വിശാഖം", "അനിഴം", "തൃക്കേട്ട",
    "മൂലം", "പൂരാടം", "ഉത്രാടം", "തിരുവോണം", "അവിട്ടം", "ചതയം",
    "പൂരുരുട്ടാതി", "ഉത്രട്ടാതി", "രേവതി",
]

RASIS = [
    "മേടം", "ഇടവം", "മിഥുനം", "കർക്കടകം", "ചിങ്ങം", "കന്നി",
    "തുലാം", "വൃശ്ചികം", "ധനു", "മകരം", "കുംഭം", "മീനം",
]

# 15 tithi names. They repeat across the two pakshas (waxing Shukla / waning
# Krishna); the 15th is Purnima (full moon) in Shukla and Amavasya (new moon)
# in Krishna, so we keep the combined label the mock used.
TITHI_NAMES = [
    "പ്രതിപദം", "ദ്വിതീയ", "തൃതീയ", "ചതുർത്ഥി", "പഞ്ചമി",
    "ഷഷ്ഠി", "സപ്തമി", "അഷ്ടമി", "നവമി", "ദശമി",
    "ഏകാദശി", "ദ്വാദശി", "ത്രയോദശി", "ചതുർദശി", "പൗർണമി/അമാവാസി",
]

# Navagraha, keyed by the same stable English ids the mock uses, mapped to the
# Swiss Ephemeris body constant. Ketu is derived (Rahu + 180°), so it has no
# body of its own. Rahu uses the mean node — the convention most Vedic
# astrologers follow (switch to swe.TRUE_NODE if you prefer the true node).
_PLANET_BODIES: dict[str, int] = {
    "surya": swe.SUN,
    "chandra": swe.MOON,
    "chevvai": swe.MARS,
    "budhan": swe.MERCURY,
    "guru": swe.JUPITER,
    "shukran": swe.VENUS,
    "shani": swe.SATURN,
    "rahu": swe.MEAN_NODE,
    # "ketu" is computed from rahu below.
}

# Ayanamsa (sidereal mode) options. Lahiri is the Indian government standard;
# KP (Krishnamurti) is used by KP astrologers; Raman is another common variant.
_AYANAMSA_MODES: dict[str, int] = {
    "lahiri": swe.SIDM_LAHIRI,
    "kp": swe.SIDM_KRISHNAMURTI,
    "krishnamurti": swe.SIDM_KRISHNAMURTI,
    "raman": swe.SIDM_RAMAN,
}

# Moshier ephemeris (no data files) + speed (to detect retrograde) + sidereal.
_FLAGS = swe.FLG_MOSEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL

_NAK_SPAN = 360.0 / 27.0   # 13°20′ per nakshatra
_PADA_SPAN = _NAK_SPAN / 4  # 3°20′ per pada


@dataclass(frozen=True)
class PlanetPosition:
    """One graha's sidereal position, plus the Vedic derivations."""

    name: str
    longitude: float       # sidereal ecliptic longitude, 0–360°
    rasi_index: int        # 0–11
    rasi: str              # Malayalam sign name
    degree_in_rasi: float  # 0–30°
    nakshatra_index: int   # 0–26
    nakshatra: str         # Malayalam nakshatra name
    pada: int              # 1–4
    house: int             # 1–12 (whole-sign, relative to lagna)
    retrograde: bool


def _to_julian_day_ut(
    dob: date, birth_time: time | None, tz: str
) -> tuple[float, bool, datetime]:
    """Convert local birth date/time to a Julian Day in Universal Time.

    Returns ``(jd_ut, time_known, local_dt)``. When the birth time is unknown we
    default to local noon — planetary positions barely move, but the *lagna*
    becomes an estimate only (it sweeps all 12 signs in ~24h), so callers should
    surface ``birth_time_known=False``. ``local_dt`` is the tz-aware birth moment,
    used as the anchor for the Vimshottari dasha timeline.
    """
    time_known = birth_time is not None
    local_dt = datetime.combine(dob, birth_time or time(12, 0), tzinfo=ZoneInfo(tz))
    utc_dt = local_dt.astimezone(timezone.utc)
    ut_hours = utc_dt.hour + utc_dt.minute / 60 + utc_dt.second / 3600
    jd_ut = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, ut_hours)
    return jd_ut, time_known, local_dt


def _derive(longitude: float, lagna_rasi_index: int) -> dict:
    """Rasi, nakshatra, pada, and whole-sign house from a sidereal longitude."""
    longitude %= 360.0
    rasi_index = int(longitude // 30)
    nak_index = int(longitude // _NAK_SPAN)
    pada = int((longitude % _NAK_SPAN) // _PADA_SPAN) + 1
    house = (rasi_index - lagna_rasi_index) % 12 + 1
    return {
        "rasi_index": rasi_index,
        "rasi": RASIS[rasi_index],
        "degree_in_rasi": round(longitude % 30, 4),
        "nakshatra_index": nak_index,
        "nakshatra": NAKSHATRAS[nak_index],
        "pada": pada,
        "house": house,
    }


def _graha_positions(jd_ut: float, reference_rasi_index: int) -> dict[str, PlanetPosition]:
    """Sidereal positions of the nine grahas at ``jd_ut``.

    ``house`` is whole-sign relative to ``reference_rasi_index`` — pass the lagna's
    rasi for a natal chart, or the natal Moon's rasi for gochara (transit) houses.
    Assumes the caller already selected the sidereal mode via ``swe.set_sid_mode``.
    """
    planets: dict[str, PlanetPosition] = {}
    for name, body in _PLANET_BODIES.items():
        values, ret = swe.calc_ut(jd_ut, body, _FLAGS)
        if ret < 0:
            raise RuntimeError(f"swe.calc_ut failed for {name}: {values}")
        longitude, speed = values[0] % 360.0, values[3]
        d = _derive(longitude, reference_rasi_index)
        # Nodes are always retrograde in mean-node terms; for real bodies a
        # negative speed ⇒ retrograde as seen from Earth.
        retrograde = name in ("rahu", "ketu") or speed < 0
        planets[name] = PlanetPosition(
            name=name, longitude=round(longitude, 6), retrograde=retrograde, **d
        )
    # Ketu is exactly 180° from Rahu.
    rahu = planets["rahu"]
    ketu_lon = (rahu.longitude + 180.0) % 360.0
    dk = _derive(ketu_lon, reference_rasi_index)
    planets["ketu"] = PlanetPosition(
        name="ketu", longitude=round(ketu_lon, 6), retrograde=True, **dk
    )
    return planets


# --- Divisional charts (vargas) --------------------------------------------
# Derived purely from the D1 sidereal longitudes with the classical Parashari
# division rules — no extra ephemeris calls. Each varga answers a life domain,
# so chat can pull the matching one in when the user asks about that topic.

VARGA_INFO: dict[str, dict[str, str]] = {
    "D9": {"varga": "navamsa", "signifies": "marriage, relationships, inner strength"},
    "D10": {"varga": "dashamsa", "signifies": "career, profession, public life"},
    "D7": {"varga": "saptamsa", "signifies": "children, progeny"},
    "D3": {"varga": "drekkana", "signifies": "siblings, courage, effort"},
    "D12": {"varga": "dwadasamsa", "signifies": "parents, lineage"},
}


def _varga_sign(varga: str, longitude: float) -> int:
    """Rasi index (0–11) a longitude maps to in the given divisional chart.

    Vedic "odd" signs are Aries, Gemini, … (1st, 3rd, …) — even 0-based index.
    """
    lon = longitude % 360.0
    sign = int(lon // 30)
    deg = lon % 30
    if varga == "D9":
        # Navamsa: 3°20′ parts; the classical movable/fixed/dual start rule is
        # equivalent to counting 108 parts continuously from 0° Aries.
        # (lon * 9 // 30, not lon // (10/3): the latter loses exact boundaries
        # to floating point — e.g. 30.0 // 3.333… lands in the wrong part.)
        return int(lon * 9 // 30) % 12
    if varga == "D3":
        # Drekkana: 10° parts → same sign, 5th, 9th.
        return (sign + int(deg // 10) * 4) % 12
    if varga == "D7":
        # Saptamsa: 30/7° parts; odd signs count from itself, even from the 7th.
        part = int(deg * 7 // 30)  # boundary-exact (see D9 note)
        start = sign if sign % 2 == 0 else sign + 6
        return (start + part) % 12
    if varga == "D10":
        # Dashamsa: 3° parts; odd signs count from itself, even from the 9th.
        part = int(deg // 3)
        start = sign if sign % 2 == 0 else sign + 8
        return (start + part) % 12
    if varga == "D12":
        # Dwadasamsa: 2°30′ parts, counted from the sign itself.
        return (sign + int(deg // 2.5)) % 12
    raise ValueError(f"Unknown varga {varga!r}; expected one of {sorted(VARGA_INFO)}")


def compute_vargas(
    planet_longitudes: dict[str, float], lagna_longitude: float
) -> dict[str, dict]:
    """All supported divisional charts from D1 longitudes.

    Houses inside each varga are whole-sign from that varga's own lagna.
    """
    out: dict[str, dict] = {}
    for key, info in VARGA_INFO.items():
        lagna_idx = _varga_sign(key, lagna_longitude)
        planets = {}
        for name, lon in planet_longitudes.items():
            idx = _varga_sign(key, lon)
            planets[name] = {
                "rasi": RASIS[idx],
                "rasi_index": idx,
                "house": (idx - lagna_idx) % 12 + 1,
            }
        out[key] = {**info, "lagnam": RASIS[lagna_idx], "planets": planets}
    return out


def compute_natal_chart(
    dob: date,
    birth_time: time | None,
    lat: float,
    lng: float,
    tz: str,
    ayanamsa: str = "lahiri",
) -> dict:
    """Compute a sidereal (Vedic) natal chart.

    Args:
        dob: Date of birth.
        birth_time: Local clock time of birth, or ``None`` if unknown.
        lat: Latitude in decimal degrees (north positive).
        lng: Longitude in decimal degrees (east positive).
        tz: IANA timezone name, e.g. ``"Asia/Kolkata"``.
        ayanamsa: One of ``"lahiri"``, ``"kp"``/``"krishnamurti"``, ``"raman"``.

    Returns:
        A dict shaped like ``EphemerisClient.natal_chart``'s output, enriched with
        exact longitudes, nakshatra pada, and the ascendant degree. ``rasi`` and
        ``nakshatram`` are the Moon's (janma rasi / janma nakshatram, the Vedic
        convention); ``lagnam`` is the ascendant sign.
    """
    key = ayanamsa.strip().lower()
    if key not in _AYANAMSA_MODES:
        raise ValueError(
            f"Unknown ayanamsa {ayanamsa!r}; expected one of {sorted(_AYANAMSA_MODES)}"
        )
    swe.set_sid_mode(_AYANAMSA_MODES[key])

    jd_ut, time_known, local_dt = _to_julian_day_ut(dob, birth_time, tz)

    # Lagna (ascendant): the ecliptic point rising on the eastern horizon.
    # houses_ex with FLG_SIDEREAL returns the sidereal ascendant in ascmc[0].
    # House cusps use whole-sign (b"W"); the ascendant point itself is
    # house-system-independent.
    _cusps, ascmc = swe.houses_ex(jd_ut, lat, lng, b"W", swe.FLG_SIDEREAL)
    lagna_lon = ascmc[0] % 360.0
    lagna_rasi_index = int(lagna_lon // 30)

    planets = _graha_positions(jd_ut, lagna_rasi_index)

    moon = planets["chandra"]
    # Vimshottari dasha follows deterministically from the Moon's sidereal
    # longitude + birth moment. Embed the mahadasha timeline (antardashas are
    # available via compute_vimshottari_dasha for callers that want them).
    from app.modules.astrology_engine.vimshottari import compute_vimshottari_dasha

    dasha = compute_vimshottari_dasha(moon.longitude, local_dt, antardasha=False)

    planets_json = {
        name: {
            "rasi": p.rasi,
            "rasi_index": p.rasi_index,
            "longitude": p.longitude,
            "degree": p.degree_in_rasi,
            "nakshatra": p.nakshatra,
            "pada": p.pada,
            "house": p.house,
            "retrograde": p.retrograde,
        }
        for name, p in planets.items()
    }

    # Doshas are deterministic facts derived from the positions above — detected
    # here in Python (never by the LLM); how to *talk* about them is the
    # knowledge corpus + persona's job.
    from app.modules.astrology_engine.doshas import detect_natal_doshas

    return {
        "system": "vedic",
        "ayanamsa": key,
        "ayanamsa_value": round(swe.get_ayanamsa_ut(jd_ut), 6),
        "julian_day_ut": jd_ut,
        "birth_time_known": time_known,
        # Janma rasi / janma nakshatram are the Moon's (Vedic convention).
        "rasi": moon.rasi,
        "nakshatram": moon.nakshatra,
        "nakshatra_pada": moon.pada,
        "lagnam": RASIS[lagna_rasi_index],
        "lagna_degree": round(lagna_lon % 30, 4),
        "dasha": dasha,
        # Divisional charts, derived from the same longitudes. Chat surfaces the
        # topical one (marriage → D9, career → D10, …) alongside the D1 chart.
        "vargas": compute_vargas(
            {name: p.longitude for name, p in planets.items()}, lagna_lon
        ),
        "doshas": detect_natal_doshas(planets_json),
        "planets": planets_json,
        "mock": False,
        "source": "swiss-ephemeris",
    }


def compute_transits(
    when: datetime,
    natal_chart: dict | None = None,
    ayanamsa: str = "lahiri",
) -> dict:
    """Current sidereal planetary transits (gochara).

    When ``natal_chart`` is given, each planet also carries ``house_from_moon`` —
    its whole-sign house counted from the natal Moon's rasi (janma rasi), the
    traditional Vedic frame for reading transits. A naive ``when`` is treated as
    UTC; pass a tz-aware datetime for exact Moon placement.
    """
    key = ayanamsa.strip().lower()
    if key not in _AYANAMSA_MODES:
        raise ValueError(
            f"Unknown ayanamsa {ayanamsa!r}; expected one of {sorted(_AYANAMSA_MODES)}"
        )
    swe.set_sid_mode(_AYANAMSA_MODES[key])

    moment = when.astimezone(timezone.utc) if when.tzinfo else when
    ut_hours = moment.hour + moment.minute / 60 + moment.second / 3600
    jd_ut = swe.julday(moment.year, moment.month, moment.day, ut_hours)

    has_chart = bool(natal_chart and natal_chart.get("planets", {}).get("chandra"))
    moon_rasi_index = (
        natal_chart["planets"]["chandra"].get("rasi_index", 0) if has_chart else 0
    )

    planets = _graha_positions(jd_ut, moon_rasi_index)
    transits: dict[str, dict] = {}
    for name, p in planets.items():
        entry = {
            "rasi": p.rasi,
            "rasi_index": p.rasi_index,
            "longitude": p.longitude,
            "degree": p.degree_in_rasi,
            "nakshatra": p.nakshatra,
            "retrograde": p.retrograde,
        }
        if has_chart:
            entry["house_from_moon"] = p.house
        transits[name] = entry

    out = {
        "as_of": when.isoformat(),
        "gochara_from": "chandra" if has_chart else None,
        "transits": transits,
        "mock": False,
        "source": "swiss-ephemeris",
    }
    if has_chart:
        # Sade Sati is a transit fact (Saturn 12th/1st/2nd from janma rasi) —
        # detected here so chat can ground the reply in it, framed by the corpus.
        from app.modules.astrology_engine.doshas import detect_sade_sati

        out["sade_sati"] = detect_sade_sati(transits["shani"].get("house_from_moon"))
    return out


def _tithi_at(jd_ut: float) -> tuple[int, str, str]:
    """(tithi_index 0–29, name, paksha) from the Moon–Sun elongation at jd_ut.

    The ayanamsa cancels in the difference, so tropical longitudes are fine.
    """
    trop = swe.FLG_MOSEPH | swe.FLG_SPEED
    sun_v, _s = swe.calc_ut(jd_ut, swe.SUN, trop)
    moon_v, _m = swe.calc_ut(jd_ut, swe.MOON, trop)
    elong = (moon_v[0] - sun_v[0]) % 360.0
    tithi_index = int(elong // 12)  # 0–29
    paksha = "shukla" if tithi_index < 15 else "krishna"
    return tithi_index, TITHI_NAMES[tithi_index % 15], paksha


def compute_prashna_chart(
    when: datetime, lat: float, lng: float, ayanamsa: str = "lahiri"
) -> dict:
    """Horary (prashna) chart: the sky at the MOMENT a question is asked.

    Kerala prashnam reads the chart of the question time at the querent's
    place, not the birth chart — the udaya lagna (rasi rising right now) is the
    anchor, with the Moon and the tithi as supporting angas. This is a thin
    reuse of the natal machinery with ``when`` in place of the birth moment.
    A naive ``when`` is treated as UTC; pass a tz-aware datetime.
    """
    key = ayanamsa.strip().lower()
    if key not in _AYANAMSA_MODES:
        raise ValueError(
            f"Unknown ayanamsa {ayanamsa!r}; expected one of {sorted(_AYANAMSA_MODES)}"
        )
    swe.set_sid_mode(_AYANAMSA_MODES[key])

    moment = when.astimezone(timezone.utc) if when.tzinfo else when
    ut_hours = moment.hour + moment.minute / 60 + moment.second / 3600
    jd_ut = swe.julday(moment.year, moment.month, moment.day, ut_hours)

    # Udaya lagna — the ascendant of the question moment at the question place.
    _cusps, ascmc = swe.houses_ex(jd_ut, lat, lng, b"W", swe.FLG_SIDEREAL)
    lagna_lon = ascmc[0] % 360.0
    lagna_rasi_index = int(lagna_lon // 30)

    planets = _graha_positions(jd_ut, lagna_rasi_index)
    moon = planets["chandra"]
    tithi_index, tithi_name, paksha = _tithi_at(jd_ut)

    return {
        "system": "vedic",
        "ayanamsa": key,
        "as_of": when.isoformat(),
        "udaya_lagnam": RASIS[lagna_rasi_index],
        "udaya_lagna_index": lagna_rasi_index,
        "lagna_degree": round(lagna_lon % 30, 4),
        "moon": {
            "rasi": moon.rasi,
            "rasi_index": moon.rasi_index,
            "nakshatram": moon.nakshatra,
            "pada": moon.pada,
            "house": moon.house,
        },
        "tithi": tithi_name,
        "tithi_index": tithi_index,
        "paksha": paksha,
        "planets": {
            name: {
                "rasi": p.rasi,
                "rasi_index": p.rasi_index,
                "house": p.house,
                "retrograde": p.retrograde,
            }
            for name, p in planets.items()
        },
        "mock": False,
        "source": "swiss-ephemeris",
    }


def compute_panchangam(
    day: date, ayanamsa: str = "lahiri", tz: str = "Asia/Kolkata"
) -> dict:
    """Panchangam for a day: nakshatram + tithi computed at local noon.

    ``nalla_neram`` is the Abhijit muhurta (around local solar noon) — a reliable
    default; precise per-day windows (rahu kalam etc.) additionally need the
    sunrise time for a specific location.
    """
    key = ayanamsa.strip().lower()
    if key not in _AYANAMSA_MODES:
        raise ValueError(
            f"Unknown ayanamsa {ayanamsa!r}; expected one of {sorted(_AYANAMSA_MODES)}"
        )
    swe.set_sid_mode(_AYANAMSA_MODES[key])

    local_noon = datetime.combine(day, time(12, 0), tzinfo=ZoneInfo(tz))
    utc = local_noon.astimezone(timezone.utc)
    ut_hours = utc.hour + utc.minute / 60
    jd_ut = swe.julday(utc.year, utc.month, utc.day, ut_hours)

    # Nakshatra from the Moon's sidereal longitude.
    moon_sid, ret = swe.calc_ut(jd_ut, swe.MOON, _FLAGS)
    if ret < 0:
        raise RuntimeError(f"swe.calc_ut failed for the Moon: {moon_sid}")
    nak_index = int((moon_sid[0] % 360.0) // _NAK_SPAN)

    tithi_index, tithi_name, paksha = _tithi_at(jd_ut)

    return {
        "date": day.isoformat(),
        "nakshatram": NAKSHATRAS[nak_index],
        "nakshatra_index": nak_index,
        "tithi": tithi_name,
        "tithi_index": tithi_index,
        "paksha": paksha,
        "nalla_neram": "11:48–12:36",
        "mock": False,
        "source": "swiss-ephemeris",
    }


if __name__ == "__main__":  # pragma: no cover — quick manual smoke test
    import json

    chart = compute_natal_chart(
        dob=date(1990, 1, 15),
        birth_time=time(7, 45),          # 07:45 local
        lat=9.9312, lng=76.2673,         # Kochi, Kerala
        tz="Asia/Kolkata",
        ayanamsa="lahiri",
    )
    print(json.dumps(chart, ensure_ascii=False, indent=2))
