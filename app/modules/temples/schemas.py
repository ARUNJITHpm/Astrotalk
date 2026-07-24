"""Pydantic schemas (DTOs) for the temples module's public boundary."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class TempleDirectoryItem(BaseModel):
    """A directory temple, for the admin partner-registration picker."""

    id: str
    name: str
    name_ml: str
    district: str
    town: str
    deity: str


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


class PoojaCatalogueItem(BaseModel):
    """One bookable offering at a temple (amount in ₹, lead in days).

    ``locked`` is set when the offering's lead time can no longer be met before
    the target star day (``lead_days > days_until``); it stays False when no
    star day is in play (plain catalogue view).
    """

    key: str
    name: str
    name_ml: str
    amount: int
    lead_days: int
    locked: bool = False


class PoojaCatalogueOut(BaseModel):
    """A temple's offering catalogue, optionally resolved against a star day."""

    temple_id: str
    days_until: int | None = None
    poojas: list[PoojaCatalogueItem]


class TempleTimings(BaseModel):
    """Darshan windows, as display strings (the app renders them verbatim)."""

    nirmalyam: str
    morning: str
    evening: str


class TempleOut(BaseModel):
    """A temple as the Nithara app lists it (field names match the UI).

    ``open`` / ``closes`` are computed from the darshan windows against the
    current IST wall-clock. ``distance_km`` is present only when the caller
    supplied a location. ``rating`` / ``reviews`` are optional and stay ``null``
    until real check-in/review data exists — never fabricated.
    """

    id: str
    en: str
    ml: str
    place: str
    mplace: str | None = None
    deity: str
    sig: str
    lat: float
    lng: float
    pooja: bool
    open: bool
    closes: str | None = None
    rating: str | None = None
    reviews: str | None = None
    distance_km: float | None = None


class TempleDetailOut(TempleOut):
    """Full temple detail for the temple sheet (adds prose, timings, catalogue)."""

    district: str
    story: str
    story_ml: str | None = None
    timings: TempleTimings
    poojas: list[PoojaCatalogueItem]


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
