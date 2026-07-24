"""HTTP routes for the astrology_engine module."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.modules.astrology_engine.schemas import (
    MuhurthamOut,
    NakshatramDayOut,
    PanchangamOut,
    PoruthamOut,
    TodayOut,
    TransitsOut,
)
from app.modules.astrology_engine.service import AstrologyEngineService

router = APIRouter(prefix="/astrology", tags=["astrology_engine"])

_service = AstrologyEngineService()

AtQuery = Annotated[
    datetime | None, Query(description="ISO timestamp; defaults to now.")
]
DayQuery = Annotated[date | None, Query(description="ISO date; defaults to today.")]


@router.get("/transits", response_model=TransitsOut)
async def get_transits(at: AtQuery = None) -> dict:
    return await _service.get_transits(at)


@router.get("/panchangam", response_model=PanchangamOut)
async def get_panchangam(day: DayQuery = None) -> dict:
    return await _service.get_panchangam(day)


@router.get("/today", response_model=TodayOut)
async def today(
    nak: int | None = Query(default=None, ge=0, le=26, description="flag this star's day"),
    day: DayQuery = None,
) -> dict:
    """Today's panchangam for the Astro tab, flagged when it is ``nak``'s day."""
    return await _service.today_for_nakshatram(nak, day)


@router.get("/porutham", response_model=PoruthamOut)
async def porutham(
    bride: int = Query(ge=0, le=26, description="bride's nakshatram index 0-26"),
    groom: int = Query(ge=0, le=26, description="groom's nakshatram index 0-26"),
) -> dict:
    """Nakshatram compatibility (the ten Kerala poruthams). Facts only."""
    return _service.porutham_by_nakshatra(bride, groom)


@router.get("/muhurtham", response_model=MuhurthamOut)
async def muhurtham(
    day: DayQuery = None,
    purpose: str = Query(default="", description="e.g. griha pravesham, travel"),
) -> dict:
    """Auspicious-window guidance for a date + purpose."""
    return await _service.muhurtham(day, purpose)


@router.get("/nakshatram/next", response_model=list[NakshatramDayOut])
async def nakshatram_next(
    nak: list[int] = Query(default=[], description="nakshatram index 0-26; repeatable"),
) -> list[dict]:
    """Next recurrence of each given nakshatram, soonest first — the star-day
    countdown the Poojas tab and home banners read. Pass one ``nak`` per family
    member (indices align with the app's nakshatram list, Ashwathi=0)."""
    names = _service.nakshatra_names()
    today = date.today()
    out: list[dict] = []
    for idx in dict.fromkeys(nak):  # de-dupe, keep order
        if not 0 <= idx <= 26:
            continue
        day = await _service.next_nakshatram_day(idx, from_day=today)
        if day is None:
            continue
        out.append(
            {
                "nakshatram_index": idx,
                "nakshatram": names[idx],
                "date": day.isoformat(),
                "days_until": (day - today).days,
            }
        )
    out.sort(key=lambda r: r["days_until"])
    return out
