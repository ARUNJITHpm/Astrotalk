"""Pydantic schemas (DTOs) for the temples module's public boundary."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PartnerCreate(BaseModel):
    """Register a directory temple as a distribution partner (admin console)."""

    temple_id: str
    slug: str
    contact_name: str = ""
    contact_phone: str = ""
    tier: str = "free"


class PartnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    temple_id: str
    slug: str
    contact_name: str
    tier: str
    active: bool
    created_at: datetime


class FestivalCreate(BaseModel):
    name: str
    name_ml: str = ""
    day: date


class FestivalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    temple_id: str
    name: str
    name_ml: str
    day: date


class SubscribePayload(BaseModel):
    """The microsite's subscribe action — an explicit WhatsApp opt-in."""

    phone: str


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
