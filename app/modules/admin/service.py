"""Public service for the admin module — analytics for the ops dashboard.

The admin module is the app's read-only analytics surface. Per
Tara-Project-Documentation.md §2 it may READ across modules; it does so ONLY
through their public services (IdentityService, ChatService) and the platform
metrics counter — never by importing another module's internals or touching
another module's tables. It composes those reads; it owns no domain data itself.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.service import ChatService
from app.modules.identity.service import IdentityService
from app.platform import metrics
from app.platform.config import get_settings


class AdminService:
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
        chat = await self._chat_service().admin_stats()
        return {
            "generated_at": datetime.now(UTC),
            "system": self._system_status(),
            "users": users,
            "chat": chat,
            "llm": metrics.snapshot(),
        }

    async def get_users_chats(self, session: AsyncSession) -> list[dict]:
        """Fetch all unique users who have chat history, resolved with display names."""
        chat_users = await self._chat_service().get_chat_users()
        phones = [u["phone"] for u in chat_users]
        names = await self._identity.get_users_by_phones(session, phones)

        result = []
        for u in chat_users:
            phone = u["phone"]
            result.append({
                "phone": phone,
                "name": names.get(phone, "Unknown User"),
                "turns": u["turns"],
                "last_active": u["last_active"].isoformat() if u["last_active"] else None
            })
        return result

    async def get_user_chat(self, phone: str) -> list[dict]:
        """Fetch raw chat history for a specific user."""
        return await self._chat_service().get_user_chat_history(phone)
