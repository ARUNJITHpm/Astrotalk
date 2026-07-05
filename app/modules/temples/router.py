"""HTTP routes for the temples module."""

from fastapi import APIRouter, Query

from app.modules.temples.schemas import TempleSuggestion
from app.modules.temples.service import TemplesService

router = APIRouter(prefix="/temples", tags=["temples"])

_service = TemplesService()


@router.get("/suggest", response_model=list[TempleSuggestion])
async def suggest(
    concern: str | None = Query(default=None, description="career, marriage, children, education, health, wealth, ancestors, obstacles, peace"),
    dosha: list[str] = Query(default=[]),
    graha: list[str] = Query(default=[]),
    district: str | None = Query(default=None),
    lat: float | None = Query(default=None),
    lng: float | None = Query(default=None),
    k: int = Query(default=2, ge=1, le=5),
) -> list[TempleSuggestion]:
    """Suggest temples for a concern/dosha/graha, optionally near a location.

    No birth data is accepted or returned here (GUARDRAILS.md §4) — callers pass
    already-derived keys (e.g. ``dosha=sade_sati``, ``graha=shani``).
    """
    return _service.suggest(
        concern=concern,
        doshas=dosha,
        grahas=graha,
        district=district,
        lat=lat,
        lng=lng,
        k=k,
    )
