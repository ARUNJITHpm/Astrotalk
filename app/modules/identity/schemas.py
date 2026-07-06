"""Pydantic schemas (DTOs) for the identity module's public boundary.

Birth data carried here is sensitive (GUARDRAILS.md §4): callers must never log
these payloads or place their fields in URLs.
"""

from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    """Onboarding input. lat/lng/tz are derived from birth_place, not supplied."""

    phone: str
    # Account password (plain here at the boundary only; hashed before storage).
    password: str
    name: str
    dob: date
    birth_time: time | None = None
    birth_place: str


class LoginRequest(BaseModel):
    """Login by the natural identity key (mobile number) + password."""

    phone: str
    password: str


class PhoneLookup(BaseModel):
    """Body for looking a user up by mobile number (kept out of the URL)."""

    phone: str


class PasswordResetVerify(BaseModel):
    """Identity proof for a forgotten-password reset: the birth details the
    account owner gave at registration. Sensitive (dob) — never logged/in a URL."""

    phone: str
    name: str
    dob: date


class PasswordReset(PasswordResetVerify):
    """A verified reset: the identity proof plus the new password to set."""

    new_password: str


class ProfileOut(BaseModel):
    """Minimal, non-sensitive profile — safe to show in the UI header/greeting."""

    model_config = ConfigDict(from_attributes=True)

    phone: str
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str
    name: str
    dob: date
    birth_time: time | None
    birth_place: str
    lat: float
    lng: float
    tz: str
    created_at: datetime


class AuthResponse(BaseModel):
    """Login/registration result: the profile plus the bearer session token.

    The client sends ``Authorization: Bearer <token>`` on every user-scoped
    call until ``expires_at`` (47h by default), then logs in again.
    """

    user: UserOut
    token: str
    expires_at: datetime


class ChartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    natal_json: dict[str, Any]
    computed_at: datetime
