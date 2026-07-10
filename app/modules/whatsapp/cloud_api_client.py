"""HTTP adapter for the official Meta WhatsApp Cloud API.

The durable alternative to WAHA. Same public surface as ``WAHAClient``
(``send_text`` / ``send_text_raw`` / ``is_healthy``) so ``WhatsappService`` can
hold either one interchangeably — the transport is chosen by
``settings.whatsapp_transport`` ("waha" | "cloud").

Why this exists: the WAHA/GOWS/whatsmeow stack links a real device via QR/pairing
code, which Meta's anti-abuse repeatedly unlinks or bans. The Cloud API is the
official channel — no device linking, no unlink/ban risk. Migrating is contained
to this file + the inbound webhook (Cloud API's payload shape differs from WAHA's).

GUARDRAILS.md §3 (enforced here, identical to WAHAClient):
  - Every outbound message carries the AI disclosure.
  - ``mock_whatsapp`` mode logs instead of calling Meta (zero network in dev).

Cloud API notes:
  - Endpoint: POST https://graph.facebook.com/{version}/{phone_number_id}/messages
  - Auth: ``Authorization: Bearer {access_token}``.
  - Recipient (``to``) is BARE international digits — no ``+``, no ``@c.us``
    (e.g. ``919400621156``).
  - Free-form text replies are allowed only inside the 24h customer-service
    window (since the user's last message). Every reply here is reactive
    (user-initiated), so we're always in-window — no template needed. Proactive
    sends outside 24h would require an approved template (separate path).
"""

import httpx

from app.modules.whatsapp.waha_client import _with_disclosure
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)


def _phone_to_wa_id(phone: str) -> str:
    """Convert a normalized phone (``+919876543210`` or ``919876543210`` or a
    ``…@c.us`` chat id) to the Cloud API recipient form: bare digits
    ``919876543210``."""
    digits = phone.lstrip("+")
    if "@" in digits:
        digits = digits.split("@", 1)[0]
    return digits.split(":", 1)[0]  # drop any device suffix


class CloudAPIClient:
    """Thin HTTP adapter over Meta's WhatsApp Cloud API.

    Mirrors ``WAHAClient``'s method surface so the two are drop-in swappable.
    Respects ``mock_whatsapp``: True = log only (dev default, no network),
    False = call the live Graph API.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._token = settings.meta_access_token
        self._phone_number_id = settings.meta_phone_number_id
        self._version = (settings.meta_api_version or "v21.0").strip("/")
        self._mock = settings.mock_whatsapp

    @property
    def _url(self) -> str:
        return (
            f"https://graph.facebook.com/{self._version}"
            f"/{self._phone_number_id}/messages"
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def send_text(self, phone: str, text: str) -> dict:
        """Send a text message with the AI disclosure footer appended (in code,
        so it cannot be skipped). The standard send for chat replies / prompts."""
        return await self._send(phone, _with_disclosure(text))

    async def send_text_raw(self, phone: str, text: str) -> dict:
        """Send a text message WITHOUT the AI disclosure footer. Reserved for
        system messages where the disclosure would be confusing (e.g. the
        opt-out confirmation). Use sparingly."""
        return await self._send(phone, text)

    async def _send(self, phone: str, text: str) -> dict:
        """Internal send — mock or live."""
        to = _phone_to_wa_id(phone)

        if self._mock:
            logger.info(
                "cloud-api(mock): would send to %s:\n%s",
                to,
                text[:200] + ("…" if len(text) > 200 else ""),
            )
            return {"mock": True, "to": to}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self._url, json=payload, headers=self._headers()
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            # Log the response body when present — Meta returns a JSON error with
            # a diagnostic ``code``/``message`` (e.g. 131047 = outside 24h window,
            # 190 = bad token) that is essential for triage. Never log the token.
            detail = ""
            if isinstance(exc, httpx.HTTPStatusError):
                detail = f" — {exc.response.text[:300]}"
            logger.error("cloud-api: send failed for %s (%s)%s", to, exc, detail)
            return {"error": str(exc), "to": to}

    async def is_healthy(self) -> dict:
        """Check that the configured phone number id is reachable with the token
        (for the admin dashboard / health probes). In mock mode, always healthy.

        Hits the phone-number node (a cheap GET). A 200 means token + id are
        valid and the number is registered on the Cloud API.
        """
        if self._mock:
            return {"healthy": True, "mock": True, "transport": "cloud"}
        if not self._token or not self._phone_number_id:
            return {
                "healthy": False,
                "transport": "cloud",
                "error": "meta_access_token / meta_phone_number_id not set",
            }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://graph.facebook.com/{self._version}"
                    f"/{self._phone_number_id}",
                    params={"fields": "verified_name,display_phone_number,quality_rating"},
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "healthy": True,
                    "transport": "cloud",
                    "status": "WORKING",
                    "display_phone_number": data.get("display_phone_number"),
                    "verified_name": data.get("verified_name"),
                    "quality_rating": data.get("quality_rating"),
                }
        except Exception as exc:
            logger.warning("cloud-api: health check failed (%s)", exc)
            return {"healthy": False, "transport": "cloud", "error": str(exc)}
