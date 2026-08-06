"""Pydantic schemas (DTOs) for the identity module's public boundary.

Birth data carried here is sensitive (GUARDRAILS.md §4): callers must never log
these payloads or place their fields in URLs.
"""

from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


def compute_age(dob: date, today: date | None = None) -> int:
    """Age in whole years from date of birth. Derived, never stored — a stored
    age column would silently drift out of date every birthday."""
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class MemberCreate(BaseModel):
    """Add someone to the family board (a relative a pooja can be booked for)."""

    name: str = ""
    rel: str = "rMother"  # relation key from the app (rMother, rSpouse, …)
    nak: int | None = Field(default=None, ge=0, le=26)
    # A birth DATE, never an age: an age is right for one year and wrong after.
    # Optional because it is usually not known, and inventing one to record an
    # approximate age would corrupt the field a star day is computed from.
    dob: date | None = None


class MemberUpdate(BaseModel):
    """Edit a family member. Only the fields present are changed."""

    name: str | None = None
    rel: str | None = None
    nak: int | None = Field(default=None, ge=0, le=26)
    dob: date | None = None


class MemberOut(BaseModel):
    """A family-board row. ``self`` marks the account holder's own row.

    ``dob`` is birth data (GUARDRAILS §4), so this shape belongs only in one
    person's own response or one user's operator detail — never in a list of
    users, and never reachable from a URL that names it.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str
    rel: str
    nak: int | None
    dob: date | None = None
    is_self: bool = Field(serialization_alias="self")


class StatsOut(BaseModel):
    """The profile header counters."""

    temples_visited: int
    poojas: int
    streak: int
    badges: int


class MilestoneOut(BaseModel):
    """One badge: progress toward a target, and whether it's unlocked."""

    key: str
    current: int
    target: int
    got: bool


class UserCreate(BaseModel):
    """Onboarding input. lat/lng/tz are derived from birth_place, not supplied."""

    phone: str
    # Account password (plain here at the boundary only; hashed before storage).
    password: str
    name: str
    dob: date
    birth_time: time | None = None
    birth_place: str
    # Referral code the signup arrived with (?ref= on the login page). Optional
    # and best-effort — a stale/unknown code never fails registration.
    ref: str | None = None
    # White-label org handle when registering from /a/{handle}/login (Part 4a).
    # Best-effort like ref: an unknown handle registers a Tara-direct account.
    org: str | None = None


class BirthDetailsIn(BaseModel):
    """The three facts a natal chart needs, set after the account exists.

    Nithara's accounts start anonymous (`POST /identity/anon`), so birth details
    arrive later — or never. Until this existed the only way to record them was
    the signup form, which an anonymous account never sees: the app could read a
    chart and had no way to create one.

    A body, never a query string. GUARDRAILS §4 puts dob, birth time and birth
    place in the same class as the chart they produce, and a URL is written to
    every access log between here and the browser.

    ``birth_time`` is optional and stays optional. A great many people know the
    day and not the hour, and the engine says so — ``birth_time_known`` rides on
    the chart, the lagna is computed from noon, and the reading is narrowed
    rather than invented. Demanding a time would make people guess one, which is
    worse than not knowing: a guessed hour produces a confidently wrong lagna.
    """

    dob: date
    birth_time: time | None = None
    birth_place: str


class BirthDetailsOut(BaseModel):
    """What this account previously entered, read back to itself.

    Deliberately the same three fields and nothing derived — no coordinates, no
    timezone, no chart. Enough to correct a typo, and no more.
    """

    dob: date | None = None
    birth_time: time | None = None
    birth_place: str = ""


class HomeTempleIn(BaseModel):
    """The temple a devotee picks during onboarding."""

    temple_id: str


class HomeTempleOut(BaseModel):
    """The chosen temple, or null for an account that has not chosen one.

    Null is a normal answer, not an error: onboarding is skippable and the app
    offers it again whenever this is empty.
    """

    temple_id: str | None = None


class ReferralSummary(BaseModel):
    """The logged-in user's referral panel (GROWTH_PLAN.md Part 2)."""

    code: str
    share_link: str
    activated: int
    threshold: int
    reward_granted: bool


class AnonRequest(BaseModel):
    """No-signup device session.

    ``anon_id`` is the SERVER-MINTED key returned by a previous call, sent back
    to resume the same anonymous account. Omit it on first run. An unknown or
    malformed value simply mints a fresh account — the id is never trusted as
    an identity claim beyond looking up an existing anonymous row.
    """

    anon_id: str | None = None


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
    # Whether this account is an app administrator (config.admin_phones).
    is_admin: bool = False


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

    @computed_field  # derived from dob so the profile can show age without a column
    @property
    def age(self) -> int:
        return compute_age(self.dob)


class AuthResponse(BaseModel):
    """Login/registration result: the profile plus the bearer session token.

    The client sends ``Authorization: Bearer <token>`` on every user-scoped
    call until ``expires_at`` (47h by default), then logs in again.
    """

    user: UserOut
    token: str
    expires_at: datetime
    # True when the account is an app administrator (see config.admin_phones).
    # Lets the web app reveal the admin/console nav right after login.
    is_admin: bool = False


class AnonResponse(AuthResponse):
    """Auth payload plus the server-minted anon key the client stores to resume."""

    anon_id: str


class ChartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    natal_json: dict[str, Any]
    computed_at: datetime
