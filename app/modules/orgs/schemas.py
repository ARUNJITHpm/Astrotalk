"""Pydantic schemas (DTOs) for the orgs module's public boundary."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrgCreate(BaseModel):
    handle: str
    name: str
    persona_overlay: str = ""
    theme_primary: str = "#e8b64c"
    theme_bg: str = "#0b0f2a"
    plan: str = "starter"
    # The astrologer's own Tara account (registered normally) — enables the
    # Part 4c owner dashboard.
    owner_phone: str | None = None


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    handle: str
    name: str
    plan: str
    active: bool
    owner_user_id: int | None
    created_at: datetime


class OrgPublic(BaseModel):
    """Branding anyone may see (the white-label pages fetch this)."""

    handle: str
    name: str
    logo_url: str | None
    theme_primary: str
    theme_bg: str


class SlotCreate(BaseModel):
    """A weekly consultation window (org owner only)."""

    weekday: int  # 0=Mon … 6=Sun
    start: str  # "HH:MM" org-local
    end: str
    duration_min: int = 30
    price_paise: int = 0


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weekday: int
    start_min: int
    end_min: int
    duration_min: int
    price_paise: int
    active: bool


class BookingCreate(BaseModel):
    """Book one open time (echo a starts_at from the availability list)."""

    starts_at: datetime


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    starts_at: datetime
    duration_min: int
    price_paise: int
    status: str
    razorpay_order_id: str | None
    created_at: datetime


class BookingCreated(BaseModel):
    """The reservation plus (for paid slots) the checkout order."""

    booking: BookingOut
    order: dict | None = None
