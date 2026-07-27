"""Pydantic schemas (DTOs) for the astrologers module's public boundary."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AstrologerOut(BaseModel):
    """A directory entry (dummy data) — everything the booking page renders."""

    id: str
    name: str
    district: str
    town: str
    lat: float
    lng: float
    specialties: list[str]
    experience_years: int
    languages: list[str]
    rating: float
    bio_ml: str


# ---- operator console (console plan Part 6) ----
# Write shapes, kept apart from AstrologerOut: that is the app's read contract
# and deliberately hides `active`, `price_paise_per_min` and `availability`.


class AstrologerAdminIn(BaseModel):
    """Onboard an astrologer. Every seeded entry is a generated placeholder, so
    this is how the first real practitioner gets into the directory.

    ``extra="forbid"`` like the patch shape: an unknown field should be an
    error, not a value silently dropped while the caller gets a 201 back.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    district: str
    lat: float
    lng: float
    name_ml: str = ""
    town: str = ""
    specialties: list[str] = []
    experience_years: int = 0
    languages: list[str] = []
    rating: float = 0.0
    bio_ml: str = ""
    availability: list[dict] = []
    active: bool = True
    price_paise_per_min: int = 0
    sort_order: int = 0


class AstrologerAdminPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    name_ml: str | None = None
    district: str | None = None
    town: str | None = None
    lat: float | None = None
    lng: float | None = None
    specialties: list[str] | None = None
    experience_years: int | None = None
    languages: list[str] | None = None
    rating: float | None = None
    bio_ml: str | None = None
    price_paise_per_min: int | None = None
    sort_order: int | None = None


class AstrologerAdminOut(BaseModel):
    """A directory row as the console edits it — including the fields the
    public shape hides."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    name_ml: str
    district: str
    town: str
    lat: float
    lng: float
    specialties: list[str]
    experience_years: int
    languages: list[str]
    rating: float
    bio_ml: str
    availability: list[dict]
    active: bool
    price_paise_per_min: int
    photo_key: str | None
    sort_order: int
    updated_at: datetime


class AvailabilityWindow(BaseModel):
    """One weekly consult window. ``weekday`` is 0 (Mon) … 6 (Sun), matching
    ``date.weekday()``; ``start``/``end`` are IST wall-clock ``HH:MM``."""

    weekday: int
    start: str
    end: str
    duration_min: int


class AvailabilityIn(BaseModel):
    """A full replacement of the weekly schedule, not a merge — a PUT, because
    'these are my hours' is how a person thinks about it, and a partial update
    makes removing a window awkward."""

    windows: list[AvailabilityWindow]


class AstrologerActiveIn(BaseModel):
    active: bool


class BookingStatusIn(BaseModel):
    """One of ``cancelled``, ``completed`` or ``no_show``."""

    status: str


class AstrologerPhotoOut(BaseModel):
    astrologer_id: str
    photo_key: str
    url: str


class OperatorBookingOut(BaseModel):
    """A diary entry. Carries ``user_phone``, which ``BookingOut`` does not:
    the operator running the consult needs to know who is coming, and the user
    reading their own bookings already knows."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    astrologer_id: str
    user_phone: str
    starts_at: datetime
    duration_min: int
    status: str
    note: str | None
    created_at: datetime


class OpenSlot(BaseModel):
    starts_at: datetime
    duration_min: int


class BookingCreate(BaseModel):
    """Book one open time (echo a starts_at from the availability list)."""

    starts_at: datetime
    note: str | None = None


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    astrologer_id: str
    starts_at: datetime
    duration_min: int
    status: str
    note: str | None
    created_at: datetime
