"""Pydantic schemas (DTOs) for the astrology_engine module's public boundary.

These mirror the dicts returned by AstrologyEngineService and are used as router
response models. The service returns plain dicts (JSON-serializable) so callers
like identity can persist a natal chart directly into a JSON column.
"""

from typing import Any

from pydantic import BaseModel


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
