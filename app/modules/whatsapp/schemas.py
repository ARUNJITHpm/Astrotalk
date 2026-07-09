"""Pydantic schemas (DTOs) for the whatsapp module's public boundary."""

from typing import Any

from pydantic import BaseModel


class ConsentRequest(BaseModel):
    phone: str


class ConsentResponse(BaseModel):
    phone: str
    opted_in: bool


# ---- WAHA inbound webhook payloads ----


class WAHAWebhookEvent(BaseModel):
    """Top-level envelope posted by WAHA to our webhook endpoint.

    WAHA sends different event types (``message``, ``message.ack``,
    ``session.status``, etc.). We only process ``message`` events — the rest
    are acknowledged with 200 and ignored.
    """

    event: str
    session: str = "default"
    payload: dict[str, Any] = {}


class WAHAMessagePayload(BaseModel):
    """Parsed fields we need from a WAHA ``message`` event payload.

    The raw ``payload`` dict varies by WAHA version; this model pulls the
    stable fields we route on and validates them at the boundary.
    """

    from_phone: str  # e.g. "919876543210@c.us"
    body: str
    timestamp: int | None = None
    is_group: bool = False

