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
