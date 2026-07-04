"""HTTP routes for the astrology_engine module."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.modules.astrology_engine.schemas import PanchangamOut, TransitsOut
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
