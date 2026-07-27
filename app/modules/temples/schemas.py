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


class PartnerUpdate(BaseModel):
    """Edit a partner (console plan Part 5). Every field is optional; only what
    is sent is written, so a payload can end a partnership without restating
    the contact details."""

    contact_name: str | None = None
    contact_phone: str | None = None
    tier: str | None = None
    active: bool | None = None


class FestivalUpdate(BaseModel):
    name: str | None = None
    name_ml: str | None = None
    day: date | None = None


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


# ---- operator console (console plan Part 5) ----
# These are the WRITE shapes. They are deliberately separate from TempleOut /
# TempleDetailOut: those are the app's read contract, with UI-shaped names
# (`en`, `ml`, `place`, `sig`) and computed fields the console must not send.


class TempleAdminIn(BaseModel):
    """Create a directory temple. Column names, not the app's display names.

    ``extra="forbid"`` like the patch shape: a field the schema does not know
    should be an error, not a value silently dropped on the floor while the
    caller gets a 201 and assumes it landed.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    deity: str  # a remedy_map.DEITIES key
    district: str
    lat: float
    lng: float
    name_ml: str = ""
    town: str = ""
    town_ml: str | None = None
    famous_for: str = ""
    vazhipadu: list[str] = []
    story: str | None = None
    story_ml: str | None = None
    hours: list[list[int]] | None = None
    timings: dict[str, str] | None = None
    rating: str | None = None
    reviews: str | None = None
    active: bool = True
    sort_order: int = 0


class TempleAdminPatch(BaseModel):
    """Partial edit. Unset fields are left alone; an explicit ``null`` clears
    the column (which is how `hours`/`timings` fall back to the defaults), so
    the route reads ``model_dump(exclude_unset=True)`` rather than by-value."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    name_ml: str | None = None
    deity: str | None = None
    district: str | None = None
    town: str | None = None
    town_ml: str | None = None
    lat: float | None = None
    lng: float | None = None
    famous_for: str | None = None
    vazhipadu: list[str] | None = None
    story: str | None = None
    story_ml: str | None = None
    hours: list[list[int]] | None = None
    timings: dict[str, str] | None = None
    rating: str | None = None
    reviews: str | None = None
    sort_order: int | None = None


class TempleAdminOut(BaseModel):
    """A directory row as the console edits it — every stored column, including
    `active` and `reviewed`, which the public shapes never expose."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    name_ml: str
    deity: str
    district: str
    town: str
    town_ml: str | None
    lat: float
    lng: float
    famous_for: str
    vazhipadu: list[str]
    reviewed: bool
    story: str | None
    story_ml: str | None
    hours: list[list[int]] | None
    timings: dict[str, str] | None
    rating: str | None
    reviews: str | None
    active: bool
    image_key: str | None
    sort_order: int
    updated_at: datetime


class ReviewedIn(BaseModel):
    reviewed: bool


class ActiveIn(BaseModel):
    active: bool


class PoojaAdminIn(BaseModel):
    """A master offering. ``amount_paise``, not rupees: the wire contract for
    the *app* is whole rupees (PoojaCatalogueItem.amount) but that is a lossy
    rendering, and the console is where the authoritative figure is set."""

    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    amount_paise: int
    name_ml: str = ""
    description: str | None = None
    lead_days: int = 0
    active: bool = True
    sort_order: int = 0


class PoojaAdminPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    name_ml: str | None = None
    description: str | None = None
    amount_paise: int | None = None
    lead_days: int | None = None
    active: bool | None = None
    sort_order: int | None = None


class PoojaAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    name_ml: str
    description: str | None
    amount_paise: int
    lead_days: int
    active: bool
    sort_order: int


class TemplePoojaIn(BaseModel):
    """One temple's override of a master offering.

    ``null`` means *inherit*, and it is the default: changing a lead time must
    not require copying the price, or a later master repricing would silently
    skip this temple. ``active=False`` means the temple does not offer it,
    which is different from having no override at all.
    """

    amount_paise: int | None = None
    lead_days: int | None = None
    active: bool = True


class TemplePoojaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    temple_id: str
    pooja_key: str
    amount_paise: int | None
    lead_days: int | None
    active: bool


class TempleImageOut(BaseModel):
    temple_id: str
    image_key: str
    url: str


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


class CheckinOut(BaseModel):
    """Result of a darshan check-in: whether it was new + the updated count."""

    fresh: bool
    temple_id: str
    temples_visited: int


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
