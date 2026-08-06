"""HTTP routes for the whatsapp module — the Cloud API webhook, consent, simulator.

Opt-in is required before any PROACTIVE send (GUARDRAILS.md §3). The first live
send needs human approval (AGENTS.md).

Two-way AI chat is enabled per owner approval (2026-07-09). Inbound
user-initiated messages are processed by ``WhatsappService.handle_inbound_message``
and replied to through the Cloud API client.

Console plan Part 15 removed the self-hosted WAHA transport and its three
routes. ``/cloud-webhook`` is the only inbound path now; a WAHA container still
POSTing to the old ``/waha-webhook`` gets a 404, which is the correct answer.
"""

import asyncio
import hashlib
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.whatsapp import consent
from app.modules.whatsapp.disclosure import with_disclosure
from app.modules.whatsapp.models import (
    WASession,  # noqa: F401 — ensures init_db creates wa_sessions
)
from app.modules.whatsapp.schemas import (
    ConsentRequest,
    ConsentResponse,
    SimulateRequest,
    SimulateResponse,
)
from app.modules.whatsapp.service import WhatsappService
from app.platform.admin_auth import require_operator
from app.platform.config import get_settings
from app.platform.db import get_session
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# The simulator lets the caller act as ANY phone number and get that person's
# personalised reading back. `AdminGuard` — any authenticated operator — was
# therefore a way for a temple_admin or a support account to read a devotee's
# private conversation by typing their mobile. Owner only.
OwnerGuard = Depends(require_operator("owner"))

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_service = WhatsappService()


import time as _time

# Recently-processed webhook message ids → monotonic timestamp. Meta redelivers
# a message when our 200 is slow or lost, so without this a delayed reply earns
# a second one. In-memory is fine — the HF Space is a single process, and a
# missed dedup after a restart is harmless (at worst one duplicate reply).
# Check+insert is synchronous so concurrent duplicate requests can't both pass
# (asyncio won't interleave a function with no await).
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


# Detached background sends kept alive here so asyncio doesn't GC a running task.
_BG_SENDS: set[asyncio.Task] = set()

# Extra send attempts AFTER the client's own quick retries, spaced out to outlast
# an egress window. graph.facebook.com is periodically unreachable from the HF
# Space for a minute or more (ConnectTimeout); since the request never leaves the
# box, re-sending can't duplicate. ~6 min of coverage total.
_BG_RETRY_DELAYS = (15, 30, 60, 120, 120)


async def _resilient_send(label: str, send) -> None:
    """Deliver a reply across transient egress outages.

    ``send`` is a zero-arg coroutine factory (a fresh send per attempt). Runs
    detached from the webhook so Meta still gets its 200 immediately. Retries
    only while the send keeps failing; stops the instant one succeeds.
    """
    attempt = 0
    while True:
        try:
            result = await send()
            if not (isinstance(result, dict) and result.get("error")):
                if attempt:
                    logger.info("cloud-webhook: %s delivered on retry %d", label, attempt)
                return
        except Exception as exc:  # never let a background task die loudly
            logger.warning("cloud-webhook: %s send raised (%s)", label, exc)
        if attempt >= len(_BG_RETRY_DELAYS):
            logger.error("cloud-webhook: %s gave up after %d attempts", label, attempt + 1)
            return
        await asyncio.sleep(_BG_RETRY_DELAYS[attempt])
        attempt += 1


def _schedule_send(label: str, send) -> None:
    """Fire-and-forget a resilient send, holding a task ref so it isn't GC'd."""
    task = asyncio.create_task(_resilient_send(label, send))
    _BG_SENDS.add(task)
    task.add_done_callback(_BG_SENDS.discard)


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


def _verify_meta_signature(raw_body: bytes, header: str, app_secret: str) -> bool:
    """Verify Meta's ``X-Hub-Signature-256`` HMAC over the raw request body.

    Meta signs every webhook POST with the app secret. When ``meta_app_secret``
    is configured we reject any body whose signature doesn't match, so a forged
    caller can't inject fake inbound messages. Empty secret = check skipped.
    """
    if not app_secret:
        return True  # not configured → skip (dev / setup)
    if not header.startswith("sha256="):
        return False
    expected = header.split("=", 1)[1]
    digest = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest)


@router.get("/cloud-webhook")
async def cloud_webhook_verify(request: Request) -> Response:
    """Meta webhook verification handshake (GET).

    When you save the webhook URL in the Meta app dashboard, Meta calls this with
    ``hub.mode=subscribe``, ``hub.verify_token=<your token>`` and a
    ``hub.challenge``. We echo the challenge back verbatim IFF the verify token
    matches ``meta_webhook_verify_token`` — that's how Meta confirms the endpoint
    is ours. Returns 403 on mismatch.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    expected = get_settings().meta_webhook_verify_token
    if mode == "subscribe" and expected and token == expected:
        # Meta expects the raw challenge string, 200, text/plain.
        return PlainTextResponse(challenge)
    logger.warning("cloud-webhook: verification failed (mode=%s)", mode)
    return PlainTextResponse("forbidden", status_code=403)


@router.post("/cloud-webhook")
async def cloud_webhook(request: Request, session: SessionDep) -> dict[str, str]:
    """Receive inbound WhatsApp messages from the Meta Cloud API.

    Payload shape (nested):
      entry[].changes[].value.messages[]  → inbound messages
      entry[].changes[].value.statuses[]  → delivery/read receipts (ignored)

    A message carries ``from`` (bare international digits, e.g. ``919400621156``)
    and, for text, ``text.body``. We route each text message through the SAME
    same brain as the simulator (``handle_inbound_message``) and reply via the
    Cloud API client.

    Always returns 200 so Meta doesn't retry-flood us; errors are logged.
    """
    raw = await request.body()

    # Verify Meta's HMAC signature when an app secret is configured.
    secret = get_settings().meta_app_secret
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_meta_signature(raw, sig, secret):
        logger.warning("cloud-webhook: bad X-Hub-Signature-256")
        return {"status": "ignored", "reason": "bad signature"}

    try:
        body = await request.json()
    except Exception:
        logger.warning("cloud-webhook: invalid JSON body")
        return {"status": "ignored", "reason": "invalid json"}

    from app.modules.identity.service import normalize_phone

    handled = 0
    for entry in body.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            messages = value.get("messages") or []
            for msg in messages:
                from_digits = msg.get("from", "")
                msg_id = msg.get("id", "")
                msg_type = msg.get("type", "")

                if not from_digits:
                    continue
                if _already_processed(msg_id, msg_id):
                    logger.info("cloud-webhook: duplicate message %s ignored", msg_id)
                    continue

                phone = normalize_phone(from_digits)
                logger.info(
                    "cloud-webhook: inbound %s from phone ending ••%s",
                    msg_type,
                    phone[-2:] if len(phone) >= 2 else phone,
                )

                if msg_type == "text":
                    text = (msg.get("text") or {}).get("body", "")
                else:
                    # Images/audio/stickers/etc. — we only do text. Nudge politely
                    # instead of dropping silently so the user isn't left hanging.
                    text = ""

                label = f"reply to ••{phone[-2:] if len(phone) >= 2 else phone}"
                try:
                    if text:
                        reply = await _service.handle_inbound_message(
                            session, phone, text
                        )
                        await session.commit()
                        # Send in the background with extended retries so an egress
                        # window to Meta delays the reply instead of dropping it.
                        _schedule_send(label, lambda r=reply, f=from_digits: _service.send_reply(f, r))
                    else:
                        _schedule_send(
                            label,
                            lambda f=from_digits: _service.send_reply_raw(
                                f,
                                "ക്ഷമിക്കണം, എനിക്ക് ഇപ്പോൾ ടെക്‌സ്റ്റ് സന്ദേശങ്ങൾ "
                                "മാത്രമേ വായിക്കാൻ കഴിയൂ. നിങ്ങളുടെ ചോദ്യം ടൈപ്പ് "
                                "ചെയ്‌ത് അയക്കൂ 🙏",
                            ),
                        )
                    handled += 1
                except Exception as exc:
                    logger.error("cloud-webhook: processing failed (%s)", exc)
                    _schedule_send(
                        label,
                        lambda f=from_digits: _service.send_reply(
                            f,
                            "❌ ക്ഷമിക്കണം, ഒരു പിശക് സംഭവിച്ചു. ദയവായി വീണ്ടും ശ്രമിക്കൂ.",
                        ),
                    )

    return {"status": "ok", "handled": str(handled)}


# ---- WhatsApp simulator (the /whatsapp demo page) ----


@router.post("/simulate", response_model=SimulateResponse, dependencies=[OwnerGuard])
async def simulate_message(
    payload: SimulateRequest, session: SessionDep
) -> SimulateResponse:
    """Route a message through the SAME brain as real WhatsApp — onboarding FSM,
    registration, chat — for an arbitrary phone, and return the reply instead of
    sending it. Used by the console's Channels → WhatsApp sim to test the flow
    a real WhatsApp user would get.

    Owner-gated: the caller can act as ANY phone number, which would otherwise
    expose other users' personalised readings.
    """
    from app.modules.identity.service import normalize_phone

    phone = normalize_phone(payload.phone.strip())
    if not phone or len(phone.lstrip("+")) < 8:
        return SimulateResponse(reply="❌ Invalid phone number.")

    reply = await _service.handle_inbound_message(session, phone, payload.text)
    await session.commit()
    # Mirror the real path: the transport's send_text appends the AI disclosure.
    return SimulateResponse(reply=with_disclosure(reply))


# ---- transport health ----


@router.get("/status", dependencies=[OwnerGuard])
async def transport_status() -> dict:
    """Is the WhatsApp transport actually usable?

    Replaces ``/waha-status``, which Part 15 removed with the transport it
    probed. Owner-gated: the reply carries the sending number's display name and
    Meta quality rating, and a failure carries whichever credential is missing.

    "Live" on the console's Integrations page only means "not mocked". An
    expired token or a wrong phone-number id looks exactly the same from there
    until a devotee's reply does not arrive.
    """
    return await _service.transport_status()
