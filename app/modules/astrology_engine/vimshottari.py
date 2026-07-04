"""Vimshottari dasha — the 120-year planetary period system used in Kerala/Vedic
astrology, computed purely from the Moon's sidereal longitude at birth.

Why this only needs the Moon
----------------------------
Vimshottari divides a notional 120-year human span across the nine grahas in a
*fixed order and fixed proportion*. Which lord is running at birth — and how much
of it is left — is fixed entirely by where the Moon sits inside its nakshatra:
each nakshatra (13°20′) is "owned" by one dasha lord in a repeating cycle of
nine, and the fraction of the nakshatra the Moon has *not yet* traversed is the
fraction of that lord's period still remaining at birth.

So given the Moon's sidereal longitude (which :func:`compute_natal_chart` already
returns) and the birth moment, the entire mahadasha timeline — and the nested
antardasha (sub-period) timeline — is deterministic.

Conventions
-----------
* **Year length.** Fractional dasha years are converted to calendar days using
  365.25 days/year, the convention modern Vedic software uses. (Some classical
  texts use a 360-day *savana* year; swap ``DAYS_PER_YEAR`` if you prefer it.)
* **Planet ids** match the rest of the engine ("surya", "chandra", …) so the
  vocabulary stays consistent across natal chart, transits, and dashas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Sidereal span of one nakshatra (13°20′) and how far one dasha lord "owns".
_NAK_SPAN = 360.0 / 27.0

# Days per dasha year (see module docstring).
DAYS_PER_YEAR = 365.25
_DAYS_PER_MONTH = DAYS_PER_YEAR / 12  # ~30.4375, for human-readable formatting

# The nine mahadasha lords in Vimshottari order, with their period lengths in
# years. The sum is exactly 120. Ashwini (nakshatra 0) is ruled by Ketu, and the
# nine repeat every nine nakshatras, so nakshatra_index % 9 indexes into this.
DASHA_SEQUENCE: list[tuple[str, int]] = [
    ("ketu", 7),
    ("shukran", 20),   # Venus
    ("surya", 6),      # Sun
    ("chandra", 10),   # Moon
    ("chevvai", 7),    # Mars
    ("rahu", 18),
    ("guru", 16),      # Jupiter
    ("shani", 19),     # Saturn
    ("budhan", 17),    # Mercury
]

_TOTAL_YEARS = sum(years for _, years in DASHA_SEQUENCE)  # 120

# Malayalam display names for the dasha lords.
DASHA_LORD_ML: dict[str, str] = {
    "ketu": "കേതു",
    "shukran": "ശുക്രൻ",
    "surya": "സൂര്യൻ",
    "chandra": "ചന്ദ്രൻ",
    "chevvai": "ചൊവ്വ",
    "rahu": "രാഹു",
    "guru": "ഗുരു",
    "shani": "ശനി",
    "budhan": "ബുധൻ",
}

_YEARS = {lord: years for lord, years in DASHA_SEQUENCE}
_ORDER = [lord for lord, _ in DASHA_SEQUENCE]


@dataclass(frozen=True)
class DashaPeriod:
    """One dasha span (mahadasha or antardasha), with absolute calendar dates."""

    lord: str
    lord_ml: str
    start: datetime
    end: datetime
    years: float


def _add_years(anchor: datetime, years: float) -> datetime:
    return anchor + timedelta(days=years * DAYS_PER_YEAR)


def _humanize_years(years: float) -> str:
    """Format a fractional dasha-year count as ``"6y 9m 29d"``."""
    days = years * DAYS_PER_YEAR
    y = int(days // DAYS_PER_YEAR)
    days -= y * DAYS_PER_YEAR
    m = int(days // _DAYS_PER_MONTH)
    days -= m * _DAYS_PER_MONTH
    d = int(round(days))
    return f"{y}y {m}m {d}d"


def _antardashas(maha_lord: str, maha_years: float, maha_start: datetime) -> list[DashaPeriod]:
    """Sub-periods within a mahadasha.

    Antardashas run through all nine lords starting from the mahadasha lord
    itself, each lasting ``maha_years * antar_years / 120`` years.
    """
    start_i = _ORDER.index(maha_lord)
    periods: list[DashaPeriod] = []
    cursor = maha_start
    for step in range(9):
        lord = _ORDER[(start_i + step) % 9]
        years = maha_years * _YEARS[lord] / _TOTAL_YEARS
        end = _add_years(cursor, years)
        periods.append(DashaPeriod(lord, DASHA_LORD_ML[lord], cursor, end, years))
        cursor = end
    return periods


def _period_dict(p: DashaPeriod) -> dict:
    return {
        "lord": p.lord,
        "lord_ml": p.lord_ml,
        "start": p.start.isoformat(),
        "end": p.end.isoformat(),
        "years": round(p.years, 4),
        "human": _humanize_years(p.years),
    }


def compute_vimshottari_dasha(
    moon_longitude: float,
    birth_dt: datetime,
    as_of: datetime | None = None,
    antardasha: bool = True,
) -> dict:
    """Compute the full Vimshottari mahadasha (and optional antardasha) timeline.

    Args:
        moon_longitude: The Moon's **sidereal** ecliptic longitude at birth, in
            degrees (0–360). This is ``chart["planets"]["chandra"]["longitude"]``.
        birth_dt: The birth moment. Prefer a timezone-aware local datetime so the
            printed dasha dates are civil dates in the birth locale.
        as_of: The moment to report the *currently running* period for. Defaults
            to "now" (matching ``birth_dt``'s tz-awareness).
        antardasha: When True, nest each mahadasha's nine sub-periods.

    Returns:
        A dict with the starting lord, the balance remaining at birth, the running
        mahadasha/antardasha as of ``as_of``, and the ``mahadashas`` timeline.

    Note:
        The first mahadasha's ``start`` is its *notional* start — earlier than
        birth, because the lord was already partway through at birth. The portion
        actually remaining at birth is reported separately as ``balance_at_birth``.
        Every period carries true absolute dates, so ``partial_at_birth`` merely
        flags that the first one straddles the birth moment.
    """
    lon = moon_longitude % 360.0
    nak_index = int(lon // _NAK_SPAN)
    start_i = nak_index % 9
    start_lord = _ORDER[start_i]

    # Fraction of the current nakshatra the Moon has already traversed → the
    # fraction of the starting lord's period already elapsed at birth.
    elapsed_fraction = (lon % _NAK_SPAN) / _NAK_SPAN
    start_years = _YEARS[start_lord]
    balance_years = start_years * (1.0 - elapsed_fraction)

    # Anchor the whole cycle at the lord's *notional* start (before birth), so
    # every downstream date is exact.
    cycle_start = _add_years(birth_dt, -start_years * elapsed_fraction)

    mahadashas: list[DashaPeriod] = []
    cursor = cycle_start
    for step in range(9):  # one full 120-year cycle covers a lifetime
        lord = _ORDER[(start_i + step) % 9]
        years = float(_YEARS[lord])
        end = _add_years(cursor, years)
        mahadashas.append(DashaPeriod(lord, DASHA_LORD_ML[lord], cursor, end, years))
        cursor = end

    if as_of is None:
        as_of = datetime.now(birth_dt.tzinfo) if birth_dt.tzinfo else datetime.now()

    # Locate the running mahadasha and antardasha at `as_of`.
    current: dict | None = None
    for maha in mahadashas:
        if maha.start <= as_of < maha.end:
            subs = _antardashas(maha.lord, maha.years, maha.start)
            running_sub = next((s for s in subs if s.start <= as_of < s.end), None)
            current = {
                "as_of": as_of.isoformat(),
                "mahadasha": _period_dict(maha),
                "antardasha": _period_dict(running_sub) if running_sub else None,
            }
            break

    timeline: list[dict] = []
    for i, maha in enumerate(mahadashas):
        entry = _period_dict(maha)
        entry["partial_at_birth"] = i == 0
        if antardasha:
            entry["antardashas"] = [
                _period_dict(s) for s in _antardashas(maha.lord, maha.years, maha.start)
            ]
        timeline.append(entry)

    balance_end = _add_years(birth_dt, balance_years)
    return {
        "system": "vimshottari",
        "days_per_year": DAYS_PER_YEAR,
        "moon_longitude": round(lon, 6),
        "starting_lord": start_lord,
        "starting_lord_ml": DASHA_LORD_ML[start_lord],
        "balance_at_birth": {
            "lord": start_lord,
            "lord_ml": DASHA_LORD_ML[start_lord],
            "years": round(balance_years, 4),
            "human": _humanize_years(balance_years),
            "ends": balance_end.isoformat(),
        },
        "current": current,
        "mahadashas": timeline,
    }


if __name__ == "__main__":  # pragma: no cover — quick manual smoke test
    import json
    from zoneinfo import ZoneInfo

    # Moon at 5° into Ashwini (nakshatra 0, ruled by Ketu) as a worked example.
    demo = compute_vimshottari_dasha(
        moon_longitude=5.0,
        birth_dt=datetime(1990, 1, 15, 7, 45, tzinfo=ZoneInfo("Asia/Kolkata")),
        as_of=datetime(2026, 7, 3, tzinfo=timezone.utc),
        antardasha=False,
    )
    print(json.dumps(demo, ensure_ascii=False, indent=2))
