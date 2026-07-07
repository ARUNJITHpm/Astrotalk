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

from math import asin, cos, radians, sin, sqrt

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


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km — plenty accurate at Kerala scale."""
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * asin(sqrt(a))


class TemplesService:
    def __init__(self) -> None:
        self._temples = SEED_TEMPLES

    def get_temple(self, temple_id: str) -> dict | None:
        """One seed-directory temple by id (public — Part 3 surfaces use it)."""
        for temple in self._temples:
            if temple["id"] == temple_id:
                return dict(temple)
        return None

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
