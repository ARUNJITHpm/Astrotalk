"""Public service for the identity module.

This is the ONLY surface other modules may depend on (AGENTS.md), and the ONLY
code allowed to read or write the `users` / `charts` tables (GUARDRAILS.md §4).
Never import another module's internal files or query its tables directly —
cross-module side effects go through the event bus in app/platform/events.

Birth data is sensitive: it is never logged here, and never placed in URLs.
"""

import base64
import hashlib
import hmac
import os
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import Chart, User
from app.modules.identity.schemas import UserCreate

# Password hashing — PBKDF2-HMAC-SHA256 from the stdlib, so no extra dependency.
# Stored form: ``pbkdf2_sha256$<rounds>$<salt_b64>$<hash_b64>`` (self-describing,
# so the rounds/salt travel with the hash and can be tuned without a migration).
_PBKDF2_ROUNDS = 200_000

# ⚠️ TESTING STAGE ONLY: when True, login accepts ANY password for a registered
# mobile number (see IdentityService.authenticate). Set back to False to enforce
# real password checks before shipping.
_TESTING_SKIP_PASSWORD = True


def hash_password(password: str) -> str:
    """Return a self-describing salted PBKDF2 hash for storage."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return (
        f"pbkdf2_sha256${_PBKDF2_ROUNDS}"
        f"${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"
    )


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time check of a plaintext password against a stored hash."""
    if not stored:
        return False
    try:
        algo, rounds, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk, expected)


def normalize_phone(phone: str) -> str:
    """Canonicalize a mobile number so the same person maps to one key.

    Keeps a leading ``+`` (country code) and digits only; drops spaces, dashes,
    parentheses. Public so callers (e.g. whatsapp) key on the same form.
    """
    stripped = phone.strip()
    digits = re.sub(r"\D", "", stripped)
    return f"+{digits}" if stripped.startswith("+") else digits

# Placeholder used until a real geocoding provider is wired in (config.mock_geocoding
# defaults True). Kochi, Kerala / IST — keeps onboarding working with no API key.
_PLACEHOLDER_GEOCODE: tuple[float, float, str] = (9.9312, 76.2673, "Asia/Kolkata")


def _geocode(place: str) -> tuple[float, float, str]:
    """Resolve a birth place to (lat, lng, tz).

    Stub: returns a fixed placeholder so onboarding works without a geocoding
    API key. The real implementation (OpenCage/Google + IANA tz) lands when
    config.mock_geocoding is turned off.
    """
    return _PLACEHOLDER_GEOCODE


class IdentityService:
    """User profile + birth-data + chart persistence for the identity domain."""

    async def create_user(self, session: AsyncSession, data: UserCreate) -> User:
        lat, lng, tz = _geocode(data.birth_place)
        user = User(
            phone=normalize_phone(data.phone),
            password_hash=hash_password(data.password),
            name=data.name,
            dob=data.dob,
            birth_time=data.birth_time,
            birth_place=data.birth_place,
            lat=lat,
            lng=lng,
            tz=tz,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user

    async def get_user(self, session: AsyncSession, user_id: int) -> User | None:
        return await session.get(User, user_id)

    async def get_user_by_phone(
        self, session: AsyncSession, phone: str
    ) -> User | None:
        """Look up a user by mobile number — the natural identity key."""
        result = await session.execute(
            select(User).where(User.phone == normalize_phone(phone))
        )
        return result.scalars().first()

    async def authenticate(
        self, session: AsyncSession, phone: str, password: str
    ) -> User | None:
        """Return the user for a registered mobile number, if it exists.

        ⚠️ TESTING STAGE: the password is NOT checked — any password is accepted
        as long as the mobile number is already registered. To restore real
        password verification, drop `_TESTING_SKIP_PASSWORD` and re-enable the
        `verify_password` check below.
        """
        user = await self.get_user_by_phone(session, phone)
        if user is None:
            return None
        if _TESTING_SKIP_PASSWORD:
            return user
        if not verify_password(password, user.password_hash):
            return None
        return user

    async def save_chart(
        self, session: AsyncSession, user_id: int, natal_json: dict[str, Any]
    ) -> Chart:
        chart = Chart(user_id=user_id, natal_json=natal_json)
        session.add(chart)
        await session.flush()
        await session.refresh(chart)
        return chart

    async def get_chart(self, session: AsyncSession, user_id: int) -> Chart | None:
        """Return the user's most recently computed chart, if any."""
        result = await session.execute(
            select(Chart)
            .where(Chart.user_id == user_id)
            .order_by(Chart.computed_at.desc(), Chart.id.desc())
        )
        return result.scalars().first()

    async def get_chart_by_phone(
        self, session: AsyncSession, phone: str
    ) -> Chart | None:
        """Return the newest chart for the user with this mobile number, if any."""
        user = await self.get_user_by_phone(session, phone)
        if user is None:
            return None
        return await self.get_chart(session, user.id)
