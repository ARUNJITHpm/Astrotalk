"""HTTP adapter for WAHA (WhatsApp HTTP API) — the ONLY code that talks to WAHA.

All outbound WhatsApp communication goes through this client. The adapter pattern
means swapping to the official Meta Cloud API later requires changing only this file.

GUARDRAILS.md §3 (enforced here):
  - Every outbound message carries the AI disclosure.
  - ``mock_whatsapp`` mode logs instead of calling WAHA (zero network in dev).
"""

import httpx

from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# AI disclosure appended to EVERY outbound message. Malayalam.
_AI_DISCLOSURE = "🤖 ഈ സന്ദേശം AI സഹായത്തോടെ തയ്യാറാക്കിയതാണ്."


def _with_disclosure(text: str) -> str:
    """Append the AI disclosure to an outbound message."""
    return f"{text}\n\n{_AI_DISCLOSURE}"


def _phone_to_chat_id(phone: str) -> str:
    """Convert a normalized phone (e.g. +919876543210 or 919876543210) to
    WAHA's chat ID format: ``919876543210@c.us``.

    Strips the leading ``+`` if present and appends ``@c.us``.
    """
    digits = phone.lstrip("+")
    if "@" in digits:
        return digits  # already a chat ID
    return f"{digits}@c.us"


def _chat_id_to_phone(chat_id: str) -> str:
    """Convert a WAHA chat ID (``919876543210@c.us``) back to a normalized
    phone number (``919876543210``) matching ``identity.service.normalize_phone``.

    We do NOT add a ``+`` prefix here because normalize_phone only adds it when
    the original input had one — and WhatsApp chat IDs don't carry one. Callers
    that need the ``+`` form should use ``normalize_phone`` on the result.
    """
    return chat_id.split("@")[0]


class WAHAClient:
    """Thin HTTP adapter over WAHA's REST API.

    Every method respects ``mock_whatsapp``: True = log only (dev default),
    False = call the live WAHA container. The first live send requires human
    approval (AGENTS.md / GUARDRAILS.md §3).
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.waha_api_url.strip().rstrip("/")
        self._session = settings.waha_session
        self._api_key = settings.waha_api_key
        self._mock = settings.mock_whatsapp

    def _headers(self) -> dict[str, str]:
        # WAHA authenticates with the ``X-Api-Key`` header — NOT
        # ``Authorization: Bearer`` (that form returns 401 on every endpoint,
        # which silently broke the reply path / two-way sends).
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-Api-Key"] = self._api_key
        return headers

    async def send_text(self, phone: str, text: str) -> dict:
        """Send a text message with the AI disclosure footer appended.

        This is the standard send — used for chat replies and onboarding
        prompts. The disclosure is appended IN CODE so it cannot be skipped.

        Returns the WAHA response dict, or a mock placeholder.
        """
        return await self._send(phone, _with_disclosure(text))

    async def send_text_raw(self, phone: str, text: str) -> dict:
        """Send a text message WITHOUT the AI disclosure footer.

        Reserved for system messages where the disclosure would be confusing
        (e.g. the opt-out confirmation: "You've been unsubscribed"). Use
        sparingly — the default ``send_text`` is correct for 99% of cases.
        """
        return await self._send(phone, text)

    async def _send(self, phone: str, text: str) -> dict:
        """Internal send — mock or live."""
        chat_id = _phone_to_chat_id(phone)

        if self._mock:
            logger.info(
                "waha(mock): would send to %s:\n%s",
                chat_id,
                text[:200] + ("…" if len(text) > 200 else ""),
            )
            return {"mock": True, "chatId": chat_id}

        payload = {
            "session": self._session,
            "chatId": chat_id,
            "text": text,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self._base_url}/sendText",
                    json=payload,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("waha: send failed for %s (%s)", chat_id, exc)
            return {"error": str(exc), "chatId": chat_id}

    async def is_healthy(self) -> dict:
        """Check WAHA session status (for admin dashboard / health probes).

        Returns a dict with at least ``{"healthy": bool}``. In mock mode,
        always returns healthy.
        """
        if self._mock:
            return {"healthy": True, "mock": True}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._base_url}/sessions/{self._session}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "healthy": True,
                    "status": data.get("status"),
                    "name": data.get("name"),
                }
        except Exception as exc:
            logger.warning("waha: health check failed (%s)", exc)
            return {"healthy": False, "error": str(exc)}

    async def get_qr(self) -> dict:
        """Get the QR code for pairing (admin use only).

        Returns the WAHA response which includes a base64 QR image when the
        session is in ``SCAN_QR`` status.
        """
        if self._mock:
            return {"mock": True, "message": "WAHA is mocked; no QR available."}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._base_url}/sessions/{self._session}/me",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning("waha: QR fetch failed (%s)", exc)
            return {"error": str(exc)}
