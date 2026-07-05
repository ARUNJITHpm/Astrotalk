"""Pydantic schemas (DTOs) for the temples module's public boundary."""

from pydantic import BaseModel


class TempleSuggestion(BaseModel):
    """One temple suggestion, ready for the LLM to narrate (or the app to render).

    ``reason`` says WHY this temple matches (which concern/dosha/graha) so the
    reply can tie the suggestion to the person's actual chart — never generic.
    ``distance_km`` is present only when the caller supplied a location.
    """

    id: str
    name: str
    name_ml: str
    deity: str
    deity_ml: str
    district: str
    town: str
    famous_for: str
    vazhipadu: list[str]
    days: str
    mantra: str
    reason: str
    distance_km: float | None = None
    reviewed: bool
