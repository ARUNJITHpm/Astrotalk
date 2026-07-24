"""HTTP routes for the astrology_engine module."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.modules.astrology_engine.schemas import (
    NakshatramDayOut,
    PanchangamOut,
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
