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
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

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

# Fallback when geocoding is mocked (config.mock_geocoding), fails, or finds no
# match. Kochi, Kerala / IST — keeps onboarding working offline; the chart can
# be redone later via POST /identity/recompute-chart, which re-geocodes.
_PLACEHOLDER_GEOCODE: tuple[float, float, str] = (9.9312, 76.2673, "Asia/Kolkata")

# In-process cache: place text → resolved (lat, lng, tz). Successful lookups
# only, so a transient outage never pins a wrong answer.
_GEOCODE_CACHE: dict[str, tuple[float, float, str]] = {}


async def _geocode(place: str) -> tuple[float, float, str]:
    """Resolve a birth place to (lat, lng, IANA tz).

    Mocked (config.mock_geocoding) → the Kochi placeholder, no network. Real
    mode uses Open-Meteo's free geocoding API (config.geocoding_url), which
    matches place names in Malayalam and English and returns the timezone with
    the coordinates. Any failure degrades to the placeholder — onboarding must
    never block on a third party.
    """
    if get_settings().mock_geocoding:
        return _PLACEHOLDER_GEOCODE
    key = " ".join(place.lower().split())
    cached = _GEOCODE_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        resolved = await _fetch_geocode(place)
    except Exception as exc:
        # Birth place is sensitive: log only the error type, never the place
        # (an httpx error string can echo the request URL).
        logger.warning(
            "identity: geocoding failed (%s); using placeholder.", type(exc).__name__
        )
        return _PLACEHOLDER_GEOCODE
    if resolved is None:
        logger.warning("identity: geocoder found no match; using placeholder.")
        return _PLACEHOLDER_GEOCODE
    _GEOCODE_CACHE[key] = resolved
    return resolved


# Nominatim (OpenStreetMap) — fallback that matches Malayalam-script place
# names, which Open-Meteo misses. Usage policy: identifying User-Agent, low
# volume (one call per onboarding miss) — well within limits.
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Nominatim returns no timezone, so the fallback only trusts countries with a
# single national timezone (Tara's user base: Kerala + the Gulf diaspora).
# Anything else degrades to the placeholder rather than guessing a tz — a wrong
# timezone corrupts the chart worse than a wrong place.
_COUNTRY_TZ = {
    "in": "Asia/Kolkata", "ae": "Asia/Dubai", "sa": "Asia/Riyadh",
    "qa": "Asia/Qatar", "kw": "Asia/Kuwait", "bh": "Asia/Bahrain",
    "om": "Asia/Muscat", "sg": "Asia/Singapore", "my": "Asia/Kuala_Lumpur",
    "lk": "Asia/Colombo",
}

_GEOCODE_USER_AGENT = "Tara/0.1 (Malayalam astrology companion)"


async def _fetch_geocode(place: str) -> tuple[float, float, str] | None:
    """One geocoding lookup (the network part, separated for testability).

    Google first when GEOCODING_API_KEY is set (best coverage for free-form
    and Malayalam input; timezone via the paired Time Zone API). Otherwise —
    or if Google fails — the free chain: Open-Meteo (returns the IANA timezone
    with the coordinates, but only matches bare names, so "Thrissur, Kerala"
    retries as "Thrissur"), then Nominatim for Malayalam script (+ the
    single-tz country map).
    """
    import httpx

    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=10, headers={"User-Agent": _GEOCODE_USER_AGENT}
    ) as client:
        if settings.geocoding_api_key:
            try:
                found = await _google_lookup(client, place, settings.geocoding_api_key)
            except Exception as exc:
                logger.warning(
                    "identity: google geocoding failed (%s); trying free providers.",
                    type(exc).__name__,
                )
                found = None
            if found is not None:
                return found

        head = place.split(",")[0].strip()
        for name in dict.fromkeys([place, head]):  # ordered, de-duplicated
            resp = await client.get(
                get_settings().geocoding_url,
                params={"name": name, "count": 1, "format": "json"},
            )
            resp.raise_for_status()
            results = resp.json().get("results") or []
            if results:
                top = results[0]
                tz = str(top.get("timezone") or _PLACEHOLDER_GEOCODE[2])
                return float(top["latitude"]), float(top["longitude"]), tz

        resp = await client.get(
            _NOMINATIM_URL,
            params={"q": place, "format": "jsonv2", "limit": 1, "addressdetails": 1},
        )
        resp.raise_for_status()
        hits = resp.json()
    if not hits:
        return None
    top = hits[0]
    country = ((top.get("address") or {}).get("country_code") or "").lower()
    tz = _COUNTRY_TZ.get(country)
    if tz is None:
        return None
    return float(top["lat"]), float(top["lon"]), tz


async def _google_lookup(client, place: str, key: str) -> tuple[float, float, str] | None:
    """Google Geocoding + Time Zone APIs: coords then the IANA tz for them.

    Returns None on ZERO_RESULTS or if either API declines (e.g. the key lacks
    that API), so the caller can fall through to the free providers.
    """
    import time as _time

    resp = await client.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": place, "key": key},
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        return None
    loc = data["results"][0]["geometry"]["location"]
    lat, lng = float(loc["lat"]), float(loc["lng"])

    resp = await client.get(
        "https://maps.googleapis.com/maps/api/timezone/json",
        params={
            "location": f"{lat},{lng}",
            "timestamp": int(_time.time()),
            "key": key,
        },
    )
    resp.raise_for_status()
    tzdata = resp.json()
    if tzdata.get("status") != "OK" or not tzdata.get("timeZoneId"):
        return None
    tz = str(tzdata["timeZoneId"])
    # Google says "Asia/Calcutta" (a deprecated alias); store the canonical id
    # so user rows stay consistent with the rest of the app.
    if tz == "Asia/Calcutta":
        tz = "Asia/Kolkata"
    return lat, lng, tz


class IdentityService:
    """User profile + birth-data + chart persistence for the identity domain."""

    async def create_user(self, session: AsyncSession, data: UserCreate) -> User:
        lat, lng, tz = await _geocode(data.birth_place)
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

    async def regeocode_user(self, session: AsyncSession, user: User) -> User:
        """Re-resolve the user's birth place and store fresh lat/lng/tz.

        Accounts onboarded while geocoding was mocked carry the Kochi
        placeholder; calling this before a chart recompute upgrades them to
        real coordinates (lagna is location-sensitive). No-op change when the
        geocoder returns the same values (or is still mocked).
        """
        user.lat, user.lng, user.tz = await _geocode(user.birth_place)
        await session.flush()
        await session.refresh(user)
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
