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
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import Chart, Referral, ReferralCode, Session, User
from app.modules.identity.schemas import UserCreate
from app.platform import metrics
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# Referral-code alphabet: unambiguous uppercase (no 0/O, 1/I/L) so codes
# survive being read aloud or hand-typed from a printed card.
_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_CODE_LENGTH = 8

# Password hashing — PBKDF2-HMAC-SHA256 from the stdlib, so no extra dependency.
# Stored form: ``pbkdf2_sha256$<rounds>$<salt_b64>$<hash_b64>`` (self-describing,
# so the rounds/salt travel with the hash and can be tuned without a migration).
_PBKDF2_ROUNDS = 200_000

# When True, login accepts ANY password for a registered mobile number — a
# testing-stage convenience only. OFF since 2026-07-05 (week-1 security):
# login now verifies the stored PBKDF2 hash.
_TESTING_SKIP_PASSWORD = False


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


def _norm_name(name: str) -> str:
    """Canonicalize a display name for identity comparison (reset flow).

    Case-folded with runs of whitespace collapsed, so "Arya  Menon" and
    "arya menon" match — a name typed months later shouldn't fail on spacing
    or capitalization. Not for storage; the original casing is kept on the row.
    """
    return " ".join(name.split()).casefold()

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


def _as_utc(value: datetime | None) -> datetime | None:
    """Treat a stored (SQLite-naive) datetime as UTC for safe comparison."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _is_real_chart(natal_json: Any) -> bool:
    """True when a stored chart is a real computed chart, not a mock/pending
    placeholder (mirrors identity.router._chart_is_stale's mock/pending test)."""
    if not isinstance(natal_json, dict):
        return False
    return not natal_json.get("mock") and natal_json.get("status") != "pending"


def _mask_phone(phone: str) -> str:
    """Reduce a mobile number to a non-identifying tail for admin display.

    Even in an authenticated admin view we don't render full numbers — the last
    two digits are enough to eyeball distinct accounts without exposing the key.
    """
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) <= 2:
        return "••"
    return "•••• " + digits[-2:]


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

    async def geocode_place(self, place: str) -> tuple[float, float, str]:
        """Resolve a free-text place to (lat, lng, IANA tz).

        Public wrapper over the module's geocoder so other modules (e.g. chat,
        charting a partner's birthplace for a porutham) can reuse the exact same
        resolution — Google primary, free providers fallback, Kochi placeholder
        on failure — without reaching into identity's internals (AGENTS.md).
        """
        return await _geocode(place)

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
        """Return the user when the mobile number AND password both match.

        Constant-time hash comparison; None on unknown number, wrong password,
        or an account with no stored hash (pre-auth rows must reset first).
        """
        user = await self.get_user_by_phone(session, phone)
        if user is None:
            return None
        if _TESTING_SKIP_PASSWORD:  # pragma: no cover - testing escape hatch, off
            return user
        if not verify_password(password, user.password_hash):
            return None
        return user

    async def verify_identity(
        self, session: AsyncSession, phone: str, name: str, dob: date
    ) -> User | None:
        """Return the user when mobile number + name + date of birth all match.

        The knowledge-based check behind a forgotten-password reset (no SMS/email
        channel exists yet): the account owner proves who they are with the birth
        details they gave at registration. Name is matched case-/whitespace-
        insensitively; date of birth must match exactly. None on any mismatch,
        without saying which field was wrong.
        """
        user = await self.get_user_by_phone(session, phone)
        if user is None:
            return None
        if _norm_name(user.name) != _norm_name(name):
            return None
        if user.dob != dob:
            return None
        return user

    async def reset_password(
        self, session: AsyncSession, user: User, new_password: str
    ) -> None:
        """Set a new account password and revoke every existing session.

        Revoking outstanding tokens means a reset also locks out anyone who had
        been using the old credentials — the caller mints a fresh session after.
        """
        user.password_hash = hash_password(new_password)
        await session.execute(delete(Session).where(Session.user_id == user.id))
        await session.flush()

    # ---- login sessions (bearer tokens) ----

    async def create_session(self, session: AsyncSession, user: User) -> Session:
        """Mint a login session: an opaque bearer token valid for
        ``settings.session_ttl_hours`` (47h by default)."""
        login = Session(
            token=secrets.token_urlsafe(32),
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(
                hours=get_settings().session_ttl_hours
            ),
        )
        session.add(login)
        await session.flush()
        await session.refresh(login)
        return login

    async def get_session_user(
        self, session: AsyncSession, token: str
    ) -> User | None:
        """The user a live (unexpired) session token belongs to, else None."""
        if not token:
            return None
        result = await session.execute(select(Session).where(Session.token == token))
        login = result.scalars().first()
        if login is None:
            return None
        # SQLite hands datetimes back naive; treat stored values as UTC.
        expires = login.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            await session.execute(delete(Session).where(Session.id == login.id))
            return None
        return await session.get(User, login.user_id)

    async def revoke_session(self, session: AsyncSession, token: str) -> None:
        """Delete a session token (logout) — immediate revocation, idempotent."""
        await session.execute(delete(Session).where(Session.token == token))

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

    # ---- referral loop (GROWTH_PLAN.md Part 2) ----

    async def get_or_create_referral_code(
        self, session: AsyncSession, user_id: int
    ) -> ReferralCode:
        """The user's share code, minting one on first use."""
        existing = (
            await session.execute(
                select(ReferralCode).where(ReferralCode.user_id == user_id)
            )
        ).scalars().first()
        if existing is not None:
            return existing
        for _ in range(5):  # collision retry (32^8 space — first try in practice)
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
            clash = (
                await session.execute(select(ReferralCode).where(ReferralCode.code == code))
            ).scalars().first()
            if clash is None:
                break
        row = ReferralCode(user_id=user_id, code=code)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def record_referral(
        self, session: AsyncSession, code: str, referred_user_id: int
    ) -> Referral | None:
        """Credit a signup to the code's owner (registration's ``ref`` field).

        Best-effort by design: an unknown code, a self-referral, or an already
        referred user returns None — registration NEVER fails because a shared
        link was stale. The row lands as ``activated`` because registration
        computes the birth chart in the same request (the plan's definition of
        real activation). Reaching the threshold marks the referrer's reward.
        """
        normalized = (code or "").strip().upper()
        if not normalized:
            return None
        code_row = (
            await session.execute(
                select(ReferralCode).where(ReferralCode.code == normalized)
            )
        ).scalars().first()
        if code_row is None or code_row.user_id == referred_user_id:
            return None
        already = (
            await session.execute(
                select(Referral).where(Referral.referred_user_id == referred_user_id)
            )
        ).scalars().first()
        if already is not None:
            return None
        referral = Referral(
            referrer_user_id=code_row.user_id,
            referred_user_id=referred_user_id,
            code=normalized,
            status="activated",
        )
        session.add(referral)
        await session.flush()
        metrics.increment("identity.referrals_activated")
        await self._maybe_grant_reward(session, code_row)
        return referral

    async def _maybe_grant_reward(
        self, session: AsyncSession, code_row: ReferralCode
    ) -> None:
        """Mark the one-time reward once activations reach the threshold.

        The durable grant (a premium-report entitlement in commerce) arrives
        with Part 5a; until then the flag itself is the unlock the UI reads.
        """
        if code_row.reward_granted_at is not None:
            return
        activated = (
            await session.scalar(
                select(func.count(Referral.id)).where(
                    Referral.referrer_user_id == code_row.user_id,
                    Referral.status == "activated",
                )
            )
            or 0
        )
        if activated < get_settings().referral_reward_threshold:
            return
        code_row.reward_granted_at = datetime.now(UTC)
        await session.flush()
        metrics.increment("identity.referral_rewards_granted")
        logger.info(
            "identity: referral reward unlocked for user %s (%s activations)",
            code_row.user_id, activated,
        )

    async def referral_summary(self, session: AsyncSession, user_id: int) -> dict[str, Any]:
        """What the logged-in user sees in their referral panel."""
        code_row = await self.get_or_create_referral_code(session, user_id)
        activated = (
            await session.scalar(
                select(func.count(Referral.id)).where(
                    Referral.referrer_user_id == user_id,
                    Referral.status == "activated",
                )
            )
            or 0
        )
        return {
            "code": code_row.code,
            "activated": activated,
            "threshold": get_settings().referral_reward_threshold,
            "reward_granted": code_row.reward_granted_at is not None,
        }

    async def get_referral_code_for_user(
        self, session: AsyncSession, user_id: int
    ) -> str | None:
        """The user's existing code WITHOUT minting one (for share-card CTAs)."""
        row = (
            await session.execute(
                select(ReferralCode.code).where(ReferralCode.user_id == user_id)
            )
        ).scalars().first()
        return row

    # ---- admin analytics (read-only) ----
    # The admin module is allowed cross-module READS for its dashboards
    # (Tara-Project-Documentation.md §2). It reaches these numbers only through
    # this public method — never by touching the users/charts tables directly.

    async def admin_metrics(self, session: AsyncSession) -> dict[str, Any]:
        """Aggregate user/chart/session stats for the admin dashboard.

        Read-only and privacy-aware: returns counts, growth buckets and a small
        recent-signups list with the display name and a MASKED phone — never
        birth data (dob / time / place / coordinates), which stays out of every
        analytics surface (GUARDRAILS.md §4).
        """
        now = datetime.now(UTC)

        total_users = await session.scalar(select(func.count(User.id))) or 0
        total_charts = await session.scalar(select(func.count(Chart.id))) or 0
        users_with_chart = (
            await session.scalar(select(func.count(func.distinct(Chart.user_id)))) or 0
        )

        # Active (unexpired) login sessions — a rough "currently reachable" gauge.
        active_sessions = (
            await session.scalar(
                select(func.count(Session.id)).where(Session.expires_at > now)
            )
            or 0
        )

        # Signups over time: pull just the created_at column (cheap) and bucket
        # in Python so the logic stays portable across SQLite and Postgres.
        created_ats = list(
            (await session.execute(select(User.created_at))).scalars().all()
        )
        created_ats = [_as_utc(c) for c in created_ats if c is not None]

        def _since(days: int) -> int:
            cutoff = now - timedelta(days=days)
            return sum(1 for c in created_ats if c >= cutoff)

        # Daily new-user counts for the last 14 days (oldest → newest) for a
        # small trend chart.
        daily: list[dict[str, Any]] = []
        for offset in range(13, -1, -1):
            day = (now - timedelta(days=offset)).date()
            count = sum(1 for c in created_ats if c.date() == day)
            daily.append({"date": day.isoformat(), "count": count})

        # Classify each user's LATEST chart as real vs placeholder (mock/pending).
        charts = list(
            (
                await session.execute(
                    select(Chart.user_id, Chart.natal_json, Chart.computed_at)
                )
            ).all()
        )
        latest_by_user: dict[int, tuple[datetime, Any]] = {}
        for user_id, natal_json, computed_at in charts:
            when = _as_utc(computed_at) or now
            prev = latest_by_user.get(user_id)
            if prev is None or when >= prev[0]:
                latest_by_user[user_id] = (when, natal_json)
        real_charts = sum(
            1 for _, nj in latest_by_user.values() if _is_real_chart(nj)
        )
        placeholder_charts = len(latest_by_user) - real_charts

        # Recent signups (newest first) — name + masked phone + chart status only.
        recent_rows = list(
            (
                await session.execute(
                    select(User).order_by(User.created_at.desc()).limit(12)
                )
            )
            .scalars()
            .all()
        )
        charted_user_ids = set(latest_by_user)
        recent = [
            {
                "name": u.name,
                "phone": u.phone,
                "created_at": _as_utc(u.created_at).isoformat()
                if u.created_at
                else None,
                "has_chart": u.id in charted_user_ids,
            }
            for u in recent_rows
        ]

        # Referral funnel (Part 2): codes shared → signups credited → rewards.
        referral_codes_issued = await session.scalar(select(func.count(ReferralCode.id))) or 0
        referred_signups = await session.scalar(select(func.count(Referral.id))) or 0
        referral_rewards = (
            await session.scalar(
                select(func.count(ReferralCode.id)).where(
                    ReferralCode.reward_granted_at.is_not(None)
                )
            )
            or 0
        )

        return {
            "total_users": total_users,
            "referrals": {
                "codes_issued": referral_codes_issued,
                "referred_signups": referred_signups,
                "rewards_granted": referral_rewards,
            },
            "users_with_chart": users_with_chart,
            "users_without_chart": max(total_users - users_with_chart, 0),
            "total_charts": total_charts,
            "real_charts": real_charts,
            "placeholder_charts": placeholder_charts,
            "active_sessions": active_sessions,
            "new_users_24h": _since(1),
            "new_users_7d": _since(7),
            "new_users_30d": _since(30),
            "signups_daily_14d": daily,
            "recent_users": recent,
        }

    async def get_users_by_phones(self, session: AsyncSession, phones: list[str]) -> dict[str, str]:
        """Resolve user names for a list of phone numbers (admin dashboard helper)."""
        if not phones:
            return {}
        result = await session.execute(
            select(User.phone, User.name).where(User.phone.in_(phones))
        )
        return {row[0]: row[1] for row in result.all()}
