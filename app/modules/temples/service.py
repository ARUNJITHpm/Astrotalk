"""Public service for the temples module — remedy-linked temple suggestions.

This is the ONLY surface other modules may depend on (AGENTS.md). Chat calls
``detect_concern`` / ``detect_district`` on the user's message and ``suggest``
with the chart facts it already computed; the returned suggestions are grafted
into the prompt for the LLM to narrate.

Split of responsibilities (same as the rest of the app):
  - WHICH deity fits a concern/graha/dosha: deterministic tables (remedy_map).
  - WHICH temple of that deity: this service (deity match + proximity).
  - HOW to speak about it: the LLM, bound by persona rules — a temple visit is
    an optional act of devotion, never a demand, never tied to fear or payment
    (GUARDRAILS.md §1).
"""

from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo

from app.modules.temples.remedy_map import (
    CONCERN_DEITIES,
    CONCERN_KEYWORDS,
    DEITIES,
    DISTRICTS,
    DOSHA_DEITIES,
    GRAHA_DEITIES,
)
from app.modules.temples.schemas import TempleSuggestion
from app.modules.temples.seed_data import SEED_TEMPLES

_EARTH_RADIUS_KM = 6371.0
_IST = ZoneInfo("Asia/Kolkata")

# The app draws one of these glyphs per temple. Deities without a dedicated icon
# fall back to the generic "temple" mark. Family grouping (Krishna → vishnu,
# Saraswati → devi) also lets the app's three deity chips stay meaningful.
_SIG_MAP = {
    "shiva": "shiva",
    "vishnu": "vishnu",
    "krishna": "vishnu",
    "devi": "devi",
    "saraswati": "devi",
}

# Standard Kerala darshan windows, applied when a temple seeds none. Windows are
# (open_minute, close_minute) in IST wall-clock; the display strings mirror them.
DEFAULT_HOURS: tuple[tuple[int, int], ...] = (
    (5 * 60, 12 * 60 + 30),   # morning: 5:00 AM – 12:30 PM
    (16 * 60 + 30, 20 * 60 + 30),  # evening: 4:30 – 8:30 PM
)
DEFAULT_TIMINGS = {
    "nirmalyam": "4:00 – 4:45 AM",
    "morning": "5:00 AM – 12:30 PM",
    "evening": "4:30 – 8:30 PM",
}

# A baseline offering catalogue, applied when a temple seeds none. Amounts in ₹,
# lead in days (0 = same-day bookable). Part 1 layers nakshatram lead-time locks.
DEFAULT_POOJAS: list[dict] = [
    {"key": "pushpanjali", "name": "Pushpanjali", "name_ml": "പുഷ്പാഞ്ജലി",
     "amount": 101, "lead_days": 0},
    {"key": "archana", "name": "Archana", "name_ml": "അർച്ചന",
     "amount": 51, "lead_days": 0},
    {"key": "neyvilakku", "name": "Neyvilakku", "name_ml": "നെയ്‌വിളക്ക്",
     "amount": 75, "lead_days": 1},
    {"key": "ganapathi_homam", "name": "Ganapathi Homam", "name_ml": "ഗണപതി ഹോമം",
     "amount": 1250, "lead_days": 3},
]


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km — plenty accurate at Kerala scale."""
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * asin(sqrt(a))


def _fmt_ampm(total_min: int) -> str:
    """Minutes-since-midnight → a display clock like ``12:30 PM``."""
    hour, minute = divmod(total_min, 60)
    suffix = "AM" if hour < 12 else "PM"
    return f"{hour % 12 or 12}:{minute:02d} {suffix}"


def _open_state(hours: tuple[tuple[int, int], ...], now_min: int) -> tuple[bool, str | None]:
    """Whether any darshan window covers ``now_min``; if so, when it closes."""
    for open_m, close_m in hours:
        if open_m <= now_min < close_m:
            return True, _fmt_ampm(close_m)
    return False, None


class TemplesService:
    def __init__(self) -> None:
        self._temples = SEED_TEMPLES

    def get_temple(self, temple_id: str) -> dict | None:
        """One seed-directory temple by id (public — Part 3 surfaces use it)."""
        for temple in self._temples:
            if temple["id"] == temple_id:
                return dict(temple)
        return None

    def list_temples(self) -> list[dict]:
        """The directory as light rows for the admin partner-registration picker."""
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "name_ml": t.get("name_ml", ""),
                "district": t.get("district", ""),
                "town": t.get("town", ""),
                "deity": t.get("deity", ""),
            }
            for t in self._temples
        ]

    # ---- public app surface (Nithara): list / search / nearby / detail ----

    @staticmethod
    def _sig(deity_key: str) -> str:
        return _SIG_MAP.get(deity_key, "temple")

    def _public_row(
        self, t: dict, *, now_min: int, lat: float | None, lng: float | None
    ) -> dict:
        """Map a seed temple to the app's list shape (field names match the UI)."""
        is_open, closes = _open_state(t.get("hours", DEFAULT_HOURS), now_min)
        info = DEITIES.get(t["deity"], {})
        distance = (
            round(_haversine_km(lat, lng, t["lat"], t["lng"]), 1)
            if lat is not None and lng is not None
            else None
        )
        return {
            "id": t["id"],
            "en": t["name"],
            "ml": t["name_ml"],
            "place": t["town"],
            "mplace": t.get("town_ml") or None,
            "deity": info.get("name", t["deity"].title()),
            "sig": self._sig(t["deity"]),
            "lat": t["lat"],
            "lng": t["lng"],
            "pooja": bool(t.get("poojas", DEFAULT_POOJAS)),
            "open": is_open,
            "closes": closes,
            "rating": t.get("rating"),
            "reviews": t.get("reviews"),
            "distance_km": distance,
        }

    def list_public(
        self,
        *,
        q: str | None = None,
        by: str = "name",
        deity: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        sort: str | None = None,
        limit: int | None = None,
        now: datetime | None = None,
    ) -> list[dict]:
        """List/search/nearby temples for the app.

        ``q`` matches name (``by=name``) or town+district (``by=place``).
        ``deity`` is a glyph family (shiva|devi|vishnu) or a display name.
        Sorting defaults to nearest-first when a location is given, else the
        curated order. ``now`` overrides the clock (tests pin open/closed).
        """
        ref = now or datetime.now(_IST)
        now_min = ref.hour * 60 + ref.minute

        rows = list(self._temples)
        if q:
            ql = q.strip().lower()
            if by == "place":
                rows = [t for t in rows if ql in f"{t['town']} {t['district']}".lower()]
            else:
                rows = [t for t in rows if ql in f"{t['name']} {t['name_ml']}".lower()]
        if deity:
            dl = deity.strip().lower()
            rows = [
                t
                for t in rows
                if self._sig(t["deity"]) == dl
                or t["deity"] == dl
                or DEITIES.get(t["deity"], {}).get("name", "").lower() == dl
            ]

        out = [self._public_row(t, now_min=now_min, lat=lat, lng=lng) for t in rows]
        if sort == "rating":
            out.sort(key=lambda r: (r["rating"] is None, r["rating"] or ""))
        elif sort == "near" or (sort is None and lat is not None and lng is not None):
            out.sort(key=lambda r: (r["distance_km"] is None, r["distance_km"] or 0.0))
        if limit is not None:
            out = out[: max(0, limit)]
        return out

    def pooja_catalogue(self, t: dict, *, days_until: int | None = None) -> dict:
        """The temple's offering catalogue, with each item's lead-time lock
        resolved against ``days_until`` (the wait to the target star day). When
        ``days_until`` is None the catalogue is returned unlocked."""
        poojas = [
            {**p, "locked": days_until is not None and p["lead_days"] > days_until}
            for p in t.get("poojas", DEFAULT_POOJAS)
        ]
        return {"temple_id": t["id"], "days_until": days_until, "poojas": poojas}

    def to_detail(self, t: dict, *, now: datetime | None = None) -> dict:
        """Full detail (prose + timings + catalogue) for the temple sheet."""
        ref = now or datetime.now(_IST)
        now_min = ref.hour * 60 + ref.minute
        row = self._public_row(t, now_min=now_min, lat=None, lng=None)
        row.update(
            {
                "district": t["district"],
                "story": t.get("story") or t["famous_for"],
                "story_ml": t.get("story_ml"),
                "timings": t.get("timings", DEFAULT_TIMINGS),
                "poojas": t.get("poojas", DEFAULT_POOJAS),
            }
        )
        return row

    # ---- temple visits / darshan check-in (Part 2) ----

    async def record_visit(self, session, user_id: int, temple_id: str) -> bool:
        """Record a darshan for today (idempotent per user/temple/day) and
        advance the daily streak. Returns True if this was a fresh check-in.
        The caller has already validated the temple id."""
        from datetime import date

        from sqlalchemy import select

        from app.modules.temples.models import TempleVisit

        today = date.today()
        exists = (
            await session.execute(
                select(TempleVisit.id).where(
                    TempleVisit.user_id == user_id,
                    TempleVisit.temple_id == temple_id,
                    TempleVisit.day == today,
                )
            )
        ).scalar_one_or_none()
        fresh = exists is None
        if fresh:
            session.add(
                TempleVisit(user_id=user_id, temple_id=temple_id, day=today)
            )
            await session.flush()

        # A darshan counts as a daily check-in — one streak for the whole app.
        from app.modules.community.service import CommunityService

        await CommunityService().record_checkin(session, user_id)
        return fresh

    async def visit_stats(self, session, user_id: int) -> dict:
        """Distinct temples and districts this user has checked into."""
        from sqlalchemy import select

        from app.modules.temples.models import TempleVisit

        temple_ids = set(
            (
                await session.execute(
                    select(TempleVisit.temple_id).where(TempleVisit.user_id == user_id)
                )
            ).scalars().all()
        )
        districts = {
            t["district"]
            for tid in temple_ids
            if (t := self.get_temple(tid)) is not None
        }
        return {
            "temples_visited": len(temple_ids),
            "districts_visited": len(districts),
        }

    # ---- partnership data, exposed for the notifications module (Part 3).
    # Plain dicts/strs out — other modules never touch this module's tables.

    async def partner_festivals_on(self, session, day) -> list[dict]:
        """Partner-temple festivals falling exactly on ``day``."""
        from app.modules.temples.partners import festivals_on

        return [
            {
                "id": f.id,
                "temple_id": f.temple_id,
                "name": f.name,
                "name_ml": f.name_ml,
                "day": f.day,
            }
            for f in await festivals_on(session, day)
        ]

    async def subscriber_phones(self, session, temple_id: str) -> list[str]:
        """WhatsApp subscriber phone numbers for one temple."""
        from app.modules.temples.partners import subscribers_for

        return await subscribers_for(session, temple_id)

    # ---- detection helpers (used by chat on the raw message) ----

    @staticmethod
    def detect_concern(text: str) -> str | None:
        """Map a user message to a life-concern key (career, marriage, …)."""
        lower = text.lower()
        for concern, keywords in CONCERN_KEYWORDS:
            if any(kw in lower for kw in keywords):
                return concern
        return None

    @staticmethod
    def detect_district(text: str) -> str | None:
        """Find a Kerala district mentioned in the message, if any."""
        lower = text.lower()
        for district, variants in DISTRICTS.items():
            if any(v in lower for v in variants):
                return district
        return None

    # ---- suggestion ----

    def suggest(
        self,
        *,
        concern: str | None = None,
        doshas: list[str] | tuple[str, ...] = (),
        grahas: list[str] | tuple[str, ...] = (),
        district: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        k: int = 2,
    ) -> list[TempleSuggestion]:
        """Suggest up to ``k`` temples for the given computed context.

        Deity candidates come, in priority order, from the concern, then the
        detected doshas, then the grahas (e.g. the running mahadasha lord).
        Within a deity, the nearest temple wins when a location is known;
        otherwise a temple in the given district wins, else the first curated
        entry. Deities are diversified: one temple per deity before a second
        of any deity is considered.
        """
        if k <= 0:
            return []

        # Ordered, de-duplicated deity → reason pairs.
        deity_reasons: list[tuple[str, str]] = []
        seen: set[str] = set()

        def _add(deities: list[str], reason: str) -> None:
            for d in deities:
                if d not in seen and d in DEITIES:
                    seen.add(d)
                    deity_reasons.append((d, reason))

        if concern and concern in CONCERN_DEITIES:
            deities, label = CONCERN_DEITIES[concern]
            _add(deities, f"traditionally worshipped for {label}")
        for dosha in doshas:
            if dosha in DOSHA_DEITIES:
                deities, label = DOSHA_DEITIES[dosha]
                _add(deities, f"traditionally suggested to soften {label}")
        for graha in grahas:
            if graha in GRAHA_DEITIES:
                deities, label = GRAHA_DEITIES[graha]
                _add(deities, f"traditionally worshipped for {label}")

        suggestions: list[TempleSuggestion] = []
        for deity, reason in deity_reasons:
            if len(suggestions) >= k:
                break
            temple = self._nearest_for_deity(deity, district, lat, lng)
            if temple is None:
                continue
            suggestions.append(self._to_suggestion(temple, deity, reason, lat, lng))
        return suggestions

    # ---- internals ----

    def _nearest_for_deity(
        self, deity: str, district: str | None, lat: float | None, lng: float | None
    ) -> dict | None:
        """Best temple of this deity: an explicitly given district narrows the
        field first (it states where the person IS — coordinates are only
        inferred from the birth place, possibly a placeholder), then known
        coordinates rank what remains."""
        candidates = [t for t in self._temples if t["deity"] == deity]
        if not candidates:
            return None
        if district:
            local = [t for t in candidates if t["district"] == district]
            if local:
                candidates = local
        if lat is not None and lng is not None:
            return min(
                candidates,
                key=lambda t: _haversine_km(lat, lng, t["lat"], t["lng"]),
            )
        return candidates[0]

    @staticmethod
    def _to_suggestion(
        temple: dict, deity: str, reason: str, lat: float | None, lng: float | None
    ) -> TempleSuggestion:
        info = DEITIES[deity]
        distance = (
            round(_haversine_km(lat, lng, temple["lat"], temple["lng"]), 1)
            if lat is not None and lng is not None
            else None
        )
        return TempleSuggestion(
            id=temple["id"],
            name=temple["name"],
            name_ml=temple["name_ml"],
            deity=info["name"],
            deity_ml=info["name_ml"],
            district=temple["district"],
            town=temple["town"],
            famous_for=temple["famous_for"],
            vazhipadu=temple["vazhipadu"],
            days=info["days"],
            mantra=info["mantra"],
            reason=f"{info['name']} ({info['name_ml']}) is {reason}",
            distance_km=distance,
            reviewed=temple["reviewed"],
        )
