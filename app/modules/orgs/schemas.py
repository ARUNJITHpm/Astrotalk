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
