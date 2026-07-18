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

import asyncio

import httpx

from app.modules.whatsapp.waha_client import _with_disclosure
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# Network transients we retry (as opposed to an API rejection, which is
# deterministic and must not be retried). ConnectTimeout dominates from the Space.
_RETRYABLE = (
    httpx.ConnectTimeout,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)


def _client(timeout: float) -> httpx.AsyncClient:
    """An httpx client pinned to IPv4, with connect retries at the transport.

    Some container networks (observed on the HF Space) advertise an IPv6 default
    route with no working IPv6 connectivity. ``graph.facebook.com`` is dual-stack,
    so httpx picks its AAAA (IPv6) address and the connection hangs until the
    timeout — silently failing every Meta call while IPv4-only hosts (e.g. Sarvam)
    keep working. Binding the source socket to ``0.0.0.0`` forces httpx onto the
    A (IPv4) record, which is reachable.

    Even on IPv4 the Space's outbound path to Meta is intermittently slow to
    complete the TCP handshake (ConnectTimeout). Retrying is handled by the
    caller's app-level loop (``_send``), NOT here — stacking transport ``retries``
    inside that loop meant up to 12 connect attempts and ~2 min hung per failure.
    A dedicated 8s ``connect`` timeout makes each attempt fail fast.
    """
    transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=8.0),
        transport=transport,
    )


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
        # Retry transient network failures (esp. ConnectTimeout from the Space)
        # with linear backoff. An API rejection (HTTPStatusError) is deterministic,
        # so it's logged and returned immediately — retrying would only repeat it.
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            try:
                async with _client(timeout=20) as client:
                    resp = await client.post(
                        self._url, json=payload, headers=self._headers()
                    )
                    resp.raise_for_status()
                    if attempt > 1:
                        logger.info("cloud-api: send to %s succeeded on attempt %d", to, attempt)
                    return resp.json()
            except httpx.HTTPStatusError as exc:
                # Meta returns a JSON error with a diagnostic ``code``/``message``
                # (131047 = outside 24h window, 190 = bad token) — essential for
                # triage. Never log the token. Deterministic → do not retry.
                logger.error(
                    "cloud-api: send failed for %s (HTTP %s) — %s",
                    to, exc.response.status_code, exc.response.text[:300],
                )
                return {"error": exc.response.text[:300], "to": to}
            except _RETRYABLE as exc:
                last_exc = exc
                logger.warning(
                    "cloud-api: send attempt %d/3 to %s failed (%s), retrying",
                    attempt, to, type(exc).__name__,
                )
                if attempt < 3:
                    await asyncio.sleep(attempt)  # 1s, then 2s
            except Exception as exc:
                # Unexpected — log with type and stop (don't hammer on an unknown).
                logger.error(
                    "cloud-api: send failed for %s (%s: %s)", to, type(exc).__name__, exc
                )
                return {"error": f"{type(exc).__name__}: {exc}", "to": to}

        logger.error(
            "cloud-api: send failed for %s after 3 attempts (%s: %s)",
            to, type(last_exc).__name__, last_exc,
        )
        return {"error": f"{type(last_exc).__name__}: {last_exc}", "to": to}

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
            async with _client(timeout=10) as client:
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
