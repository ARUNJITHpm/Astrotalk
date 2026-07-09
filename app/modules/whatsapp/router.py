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
    WAHAWebhookEvent,
)
from app.modules.whatsapp.service import WhatsappService
from app.modules.whatsapp.waha_client import WAHAClient, _chat_id_to_phone
from app.platform.config import get_settings
from app.platform.db import get_session
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_service = WhatsappService()
_waha = WAHAClient()


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

    # Normalize the phone number.
    from app.modules.identity.service import normalize_phone

    phone = normalize_phone(_chat_id_to_phone(from_field))

    logger.info("waha-webhook: inbound from phone ending ••%s", phone[-2:])

    try:
        # Route through the service orchestrator.
        reply = await _service.handle_inbound_message(session, phone, body_text)
        await session.commit()

        # Send the reply back.
        await _service.send_reply(phone, reply)

        return {"status": "ok"}

    except Exception as exc:
        logger.error("waha-webhook: processing failed (%s)", exc)
        # Best-effort error reply to the user.
        try:
            await _service.send_reply(
                phone,
                "❌ ക്ഷമിക്കണം, ഒരു പിശക് സംഭവിച്ചു. ദയവായി വീണ്ടും ശ്രമിക്കൂ.",
            )
        except Exception:
            pass
        return {"status": "error"}


# ---- WAHA admin endpoints (new) ----


@router.get("/waha-status")
async def waha_status() -> dict:
    """Check WAHA connection status (for admin dashboard / health probes)."""
    return await _service.waha_status()


@router.get("/waha-qr")
async def waha_qr() -> dict:
    """Get the WAHA QR code / session info (for admin pairing setup)."""
    return await _waha.get_qr()
