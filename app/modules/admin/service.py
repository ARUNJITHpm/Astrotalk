"""Public service for the admin module — analytics for the ops dashboard.

The admin module is the app's read-only analytics surface. Per
Tara-Project-Documentation.md §2 it may READ across modules; it does so ONLY
through their public services (IdentityService, ChatService) and the platform
metrics counter — never by importing another module's internals or touching
another module's tables. It composes those reads; it owns no domain data itself.
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.service import ChatService
from app.modules.identity.service import IdentityService
from app.platform import metrics
from app.platform.config import get_settings


class AdminService:
    # The engagement page folds every counted user in memory. Bounded because
    # an unbounded scan of a growing register eventually takes the process with
    # it, and a page that quietly got slower is worse than one that says it is
    # showing a sample.
    _MAX_ENGAGEMENT_USERS = 5000

    def __init__(
        self,
        identity: IdentityService | None = None,
        chat: ChatService | None = None,
    ) -> None:
        self._identity = identity or IdentityService()
        # ChatService builds a retrieval index on construction, so build it
        # lazily and reuse it across requests (see _chat).
        self._chat = chat

    def _chat_service(self) -> ChatService:
        if self._chat is None:
            self._chat = ChatService()
        return self._chat

    def _system_status(self) -> dict[str, Any]:
        """Non-secret snapshot of how the app is wired — which integrations are
        live vs mocked, the active LLM provider, and the key operational knobs.
        Reports only booleans/names, never any credential."""
        s = get_settings()
        return {
            "app_env": s.app_env,
            "chat_provider": s.chat_provider,
            "session_ttl_hours": s.session_ttl_hours,
            "chat_rate_limit_per_hour": s.chat_rate_limit_per_hour,
            "integrations": {
                # True = talking to the real service; False = mocked/offline.
                "llm": not s.mock_openai,
                "ephemeris": not s.mock_ephemeris,
                "mongo": not s.mock_mongo,
                "geocoding": not s.mock_geocoding,
                "whatsapp": not s.mock_whatsapp,
                "razorpay": not s.mock_razorpay,
                "chroma": not s.mock_chroma,
            },
            "api_keys_present": {
                "openai": bool(s.openai_api_key),
                "sarvam": bool(s.sarvam_api_key),
                "geocoding": bool(s.geocoding_api_key),
            },
        }

    async def overview(self, session: AsyncSession) -> dict[str, Any]:
        """Assemble the whole dashboard payload from the module reads."""
        users = await self._identity.admin_metrics(session)
        chat = await self._chat_service().admin_stats(session)
        return {
            "generated_at": datetime.now(UTC),
            "system": self._system_status(),
            "users": users,
            "chat": chat,
            "llm": metrics.snapshot(),
        }

    async def engagement(
        self, session: AsyncSession, *, limit: int = 25, today: date | None = None
    ) -> dict[str, Any]:
        """Check-ins, streaks and milestones across the register.

        Console plan Part 12. Every engagement figure the product had was
        per-caller — ``/community/streak``, ``/identity/me/milestones`` — so a
        person could see their own streak and nobody could see whether the
        feature was working at all.

        Four queries, not four per devotee. Each module hands over its own table
        in one aggregate call and the folding happens here; a loop over users
        would be fine on a laptop and would take the process down on a real
        register. The one instant (`today`) is passed into every streak so a run
        straddling midnight does not credit some users a day the rest miss.

        Nothing here is invented. A user with no check-ins is absent from the
        counters rather than reported as a zero-streak participant, and the
        milestone thresholds come from identity so the console cannot grow its
        own copy that drifts.
        """
        from app.modules.bookings.service import BookingsService
        from app.modules.community.service import CommunityService
        from app.modules.temples.service import TemplesService

        community = CommunityService()
        day = today or date.today()

        checkins = await community.checkin_days_by_user(session)
        visits = await TemplesService().visit_stats_by_user(session)
        poojas = await BookingsService().counts_by_user(session)
        total_users, names = await self._identity.user_index(
            session, limit=self._MAX_ENGAGEMENT_USERS
        )

        rows: list[dict[str, Any]] = []
        badge_counts: dict[str, int] = {}
        checkin_total = 0
        for user_id, (name, phone) in names.items():
            days = checkins.get(user_id, set())
            checkin_total += len(days)
            counters = {
                "temples_visited": visits.get(user_id, {}).get("temples_visited", 0),
                "districts_visited": visits.get(user_id, {}).get("districts_visited", 0),
                "poojas": poojas.get(user_id, 0),
                "streak": community.streak_from_days(days, day),
            }
            badges = self._identity.milestones_from_counters(counters)
            for badge in badges:
                badge_counts.setdefault(badge["key"], 0)
                if badge["got"]:
                    badge_counts[badge["key"]] += 1
            rows.append(
                {
                    "user_id": user_id,
                    "name": name,
                    "phone": phone,
                    "checkins": len(days),
                    "badges": sum(1 for b in badges if b["got"]),
                    **counters,
                }
            )

        # Most engaged first: streak, then check-ins, then temples. A person on
        # a long streak is the one worth talking to today.
        rows.sort(key=lambda r: (r["streak"], r["checkins"], r["temples_visited"]), reverse=True)
        active = [r for r in rows if r["streak"] > 0]
        targets = {b["key"]: b["target"] for b in self._identity.milestones_from_counters(
            {"temples_visited": 0, "districts_visited": 0, "poojas": 0, "streak": 0}
        )}

        return {
            "generated_at": datetime.now(UTC),
            "day": day,
            # Reported so the console can say when it is looking at a sample
            # rather than the whole register, instead of implying totality.
            "users_counted": len(rows),
            "users_total": total_users,
            "truncated": total_users > len(rows),
            "checkins": {
                "total": checkin_total,
                "users_ever": sum(1 for r in rows if r["checkins"]),
                "users_on_a_streak": len(active),
                "checked_in_today": sum(
                    1 for uid in names if day in checkins.get(uid, set())
                ),
            },
            "milestones": [
                {"key": key, "target": targets.get(key, 0), "unlocked": count}
                for key, count in badge_counts.items()
            ],
            "most_engaged": rows[:limit],
        }

    async def get_users_chats(self, session: AsyncSession) -> list[dict]:
        """Fetch all unique users who have chat history, resolved with display names."""
        chat_users = await self._chat_service().get_chat_users(session)
        phones = [u["phone"] for u in chat_users]
        names = await self._identity.get_users_by_phones(session, phones)

        result = []
        for u in chat_users:
            phone = u["phone"]
            result.append(
                {
                    "phone": phone,
                    "name": names.get(phone, "Unknown User"),
                    "turns": u["turns"],
                    "last_active": (
                        u["last_active"].isoformat() if u["last_active"] else None
                    ),
                }
            )
        return result

    async def get_user_chat(self, session: AsyncSession, phone: str) -> list[dict]:
        """Fetch raw chat history for a specific user."""
        return await self._chat_service().get_user_chat_history(session, phone)
