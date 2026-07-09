"""HTTP routes for the whatsapp module — BSP webhooks, consent ledger, WAHA webhook.

Opt-in is required before any PROACTIVE send (GUARDRAILS.md §3). The first live
send needs human approval (AGENTS.md).

Two-way AI chat via WAHA is enabled per owner approval (2026-07-09). Inbound
user-initiated messages are processed by ``WhatsappService.handle_inbound_message``
and replied to via the ``WAHAClient`` adapter.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.whatsapp import consent
from app.modules.whatsapp.models import (
    WASession,  # noqa: F401 — ensures init_db creates wa_sessions
)
from app.modules.whatsapp.schemas import (
    ConsentRequest,
    ConsentResponse,
    SimulateRequest,
    SimulateResponse,
    WAHAWebhookEvent,
)
from app.modules.whatsapp.service import WhatsappService
from app.modules.whatsapp.waha_client import WAHAClient, _chat_id_to_phone, _with_disclosure
from app.platform.admin_auth import AdminGuard
from app.platform.config import get_settings
from app.platform.db import get_session
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_service = WhatsappService()
_waha = WAHAClient()


import time as _time

# Recently-processed webhook event ids → monotonic timestamp. WAHA occasionally
# delivers the same message event twice (e.g. multiple linked-device sessions on
# the number); we reply only to the first. In-memory is fine — the HF Space is a
# single process, and a missed dedup after a restart is harmless (at worst one
# duplicate reply). Check+insert is synchronous so concurrent duplicate requests
# can't both pass (asyncio won't interleave a function with no await).
_SEEN_EVENTS: dict[str, float] = {}
_SEEN_TTL = 300.0  # seconds


def _already_processed(event_id: str, msg_id: str) -> bool:
    key = event_id or msg_id
    if not key:
        return False
    now = _time.monotonic()
    if len(_SEEN_EVENTS) > 2000:  # bounded cleanup
        for k, t in list(_SEEN_EVENTS.items()):
            if now - t > _SEEN_TTL:
                del _SEEN_EVENTS[k]
    if key in _SEEN_EVENTS and now - _SEEN_EVENTS[key] < _SEEN_TTL:
        return True
    _SEEN_EVENTS[key] = now
    return False


def _reply_chat_id(payload: dict, from_field: str) -> str:
    """The chat id to reply to, resolving WhatsApp's LID addressing.

    GOWS delivers some messages with ``from="<lid>@lid"`` — a privacy alias, not
    a phone number. Replying to a LID is slow/unreliable (and identity lookup on
    it never matches a real user), but the sender's REAL phone is carried in
    ``_data.Info.SenderAlt`` as ``"<phone>@s.whatsapp.net"``. Prefer it so the
    reply routes to a normal ``"<phone>@c.us"`` chat and the phone key matches
    the web-registered user. Normal ``@c.us`` senders pass straight through.
    """
    if from_field.endswith("@lid"):
        info = (payload.get("_data") or {}).get("Info") or {}
        alt = info.get("SenderAlt") or ""
        if alt.endswith("@s.whatsapp.net"):
            digits = alt.split("@", 1)[0].split(":", 1)[0]  # drop device suffix
            if digits.isdigit():
                return f"{digits}@c.us"
    return from_field


# ---- Existing BSP webhook (unchanged) ----


@router.post("/webhook")
async def webhook() -> dict[str, str]:
    # Opt-in only; first live send needs human approval (AGENTS.md / GUARDRAILS.md).
    # TODO(whatsapp): handle delivery/consent callbacks.
    return {"status": "ok"}


# ---- Consent endpoints (unchanged) ----


@router.post("/opt-in", response_model=ConsentResponse)
async def opt_in(payload: ConsentRequest, session: SessionDep) -> ConsentResponse:
    record = await consent.opt_in(session, payload.phone)
    await session.commit()
    return ConsentResponse(phone=record.phone, opted_in=record.opted_in)


@router.post("/opt-out", response_model=ConsentResponse)
async def opt_out(payload: ConsentRequest, session: SessionDep) -> ConsentResponse:
    record = await consent.opt_out(session, payload.phone)
    await session.commit()
    return ConsentResponse(phone=record.phone, opted_in=record.opted_in)


# ---- WAHA webhook (new: real WhatsApp integration) ----


@router.post("/waha-webhook")
async def waha_webhook(request: Request, session: SessionDep) -> dict[str, str]:
    """Receive inbound WhatsApp messages from the WAHA container.

    WAHA posts JSON events here for every incoming message. We:
      1. Parse the event envelope (WAHAWebhookEvent).
      2. Ignore non-message events (acks, status changes, etc.).
      3. Ignore group messages (GUARDRAILS.md §3: no bots in groups).
      4. Extract sender phone + message text.
      5. Route through WhatsappService.handle_inbound_message().
      6. Send the reply back via WAHAClient.

    The endpoint always returns 200 to WAHA (even on internal errors) so WAHA
    doesn't retry and flood us. Errors are logged, not surfaced.
    """
    try:
        body = await request.json()
    except Exception:
        logger.warning("waha-webhook: invalid JSON body")
        return {"status": "ignored", "reason": "invalid json"}

    # Optional webhook secret verification.
    secret = get_settings().waha_webhook_secret
    if secret:
        header_secret = request.headers.get("X-Webhook-Secret", "")
        if header_secret != secret:
            logger.warning("waha-webhook: invalid webhook secret")
            return {"status": "ignored", "reason": "invalid secret"}

    try:
        event = WAHAWebhookEvent(**body)
    except Exception as exc:
        logger.warning("waha-webhook: payload parse error (%s)", exc)
        return {"status": "ignored", "reason": "parse error"}

    # Only process "message" events.
    if event.event != "message":
        return {"status": "ignored", "reason": f"event type: {event.event}"}

    # Extract the message fields from the payload.
    payload = event.payload
    # WAHA payload structure: payload.from (sender), payload.body (text).
    # The "from" field is a chat ID like "919876543210@c.us".
    from_field = payload.get("from", "")
    body_text = payload.get("body", "")

    # Ignore messages from ourselves (the bot number).
    if payload.get("fromMe", False):
        return {"status": "ignored", "reason": "own message"}

    # Ignore group messages (GUARDRAILS.md §3).
    if "@g.us" in from_field:
        return {"status": "ignored", "reason": "group message"}

    if not from_field or not body_text:
        return {"status": "ignored", "reason": "empty message"}

    # Drop duplicate deliveries of the same event so we don't reply twice.
    if _already_processed(event.id, str(payload.get("id", ""))):
        logger.info("waha-webhook: duplicate event %s ignored", event.id or payload.get("id"))
        return {"status": "ignored", "reason": "duplicate"}

    # Resolve LID-addressed senders to their real "<phone>@c.us" chat id, then
    # derive the phone key from THAT (not the raw LID) so identity matches the
    # web-registered user and the reply routes to a real phone.
    from app.modules.identity.service import normalize_phone

    reply_chat = _reply_chat_id(payload, from_field)
    phone = normalize_phone(_chat_id_to_phone(reply_chat))

    logger.info("waha-webhook: inbound from phone ending ••%s", phone[-2:])

    try:
        # Route through the service orchestrator.
        reply = await _service.handle_inbound_message(session, phone, body_text)
        await session.commit()

        # Send the reply back to the resolved chat id.
        await _service.send_reply(reply_chat, reply)

        return {"status": "ok"}

    except Exception as exc:
        logger.error("waha-webhook: processing failed (%s)", exc)
        # Best-effort error reply to the user.
        try:
            await _service.send_reply(
                reply_chat,
                "❌ ക്ഷമിക്കണം, ഒരു പിശക് സംഭവിച്ചു. ദയവായി വീണ്ടും ശ്രമിക്കൂ.",
            )
        except Exception:
            pass
        return {"status": "error"}


# ---- WhatsApp simulator (the /whatsapp demo page) ----


@router.post("/simulate", response_model=SimulateResponse, dependencies=[AdminGuard])
async def simulate_message(
    payload: SimulateRequest, session: SessionDep
) -> SimulateResponse:
    """Route a message through the SAME brain as real WhatsApp — onboarding FSM,
    registration, chat — for an arbitrary phone, and return the reply instead of
    sending it via WAHA. Used by the /whatsapp demo page to test the exact flow
    a real WhatsApp user would get.

    Admin-gated (X-Admin-Token): the caller can act as ANY phone number, which
    would otherwise expose other users' personalised readings.
    """
    from app.modules.identity.service import normalize_phone

    phone = normalize_phone(payload.phone.strip())
    if not phone or len(phone.lstrip("+")) < 8:
        return SimulateResponse(reply="❌ Invalid phone number.")

    reply = await _service.handle_inbound_message(session, phone, payload.text)
    await session.commit()
    # Mirror the real path: WAHAClient.send_text appends the AI disclosure.
    return SimulateResponse(reply=_with_disclosure(reply))


# ---- WAHA admin endpoints (new) ----


@router.get("/waha-status")
async def waha_status() -> dict:
    """Check WAHA connection status (for admin dashboard / health probes)."""
    return await _service.waha_status()


@router.get("/waha-qr")
async def waha_qr() -> dict:
    """Get the WAHA QR code / session info (for admin pairing setup)."""
    return await _waha.get_qr()
