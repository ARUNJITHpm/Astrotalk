"""Pydantic schemas (DTOs) for the astrology_engine module's public boundary.

These mirror the dicts returned by AstrologyEngineService and are used as router
response models. The service returns plain dicts (JSON-serializable) so callers
like identity can persist a natal chart directly into a JSON column.
"""

from typing import Any

from pydantic import BaseModel


class NakshatramDayOut(BaseModel):
    """The next date a given nakshatram recurs — the star-day countdown source."""

    nakshatram_index: int
    nakshatram: str
    date: str
    days_until: int


class PoruthamSide(BaseModel):
    name: str
    nakshatram: str
    rasi: str


class PoruthamOut(BaseModel):
    """The ten Kerala poruthams for a (bride, groom) nakshatram pair — facts
    only; the 'should they marry' framing is the chat persona's job."""

    female: PoruthamSide
    male: PoruthamSide
    poruthams: dict[str, Any]
    score: float
    max_score: float
    rajju_dosha: bool
    favourable: list[str]
    unfavourable: list[str]


class TodayOut(BaseModel):
    """Today's panchangam, flagged for one nakshatram (the Astro tab header)."""

    date: str
    tithi: str
    nakshatram: str
    nalla_neram: str
    is_star_day: bool
    note: str


class MuhurthamOut(BaseModel):
    """Auspicious-window guidance for a date + purpose (guidance only)."""

    date: str
    tithi: str
    nakshatram: str
    nalla_neram: str
    purpose: str
    note: str


class NatalChartOut(BaseModel):
    system: str
    ayanamsa: str
    nakshatram: str
    rasi: str
    lagnam: str
    planets: dict[str, Any]
    mock: bool
    source: str


class TransitsOut(BaseModel):
    as_of: str
    transits: dict[str, Any]
    mock: bool
    source: str


class PanchangamOut(BaseModel):
    date: str
    nakshatram: str
    nalla_neram: str
    tithi: str
    mock: bool
    source: str
