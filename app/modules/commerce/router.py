"""HTTP routes for the commerce module (GROWTH_PLAN.md Part 5a).

  - POST /commerce/orders             — logged-in user starts a purchase.
  - POST /commerce/webhook/razorpay   — Razorpay's server calls back here;
    auth is the HMAC signature over the raw body, nothing else.
  - GET  /commerce/entitlements       — what the logged-in user has unlocked.
  - POST /commerce/orders/{id}/mock-pay — dev/test only (404 in live mode):
    simulates the capture so the whole unlock flow works with zero keys.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commerce.schemas import EntitlementOut, OrderCreate, OrderOut
from app.modules.commerce.service import (
    CommerceService,
    PaymentNotFound,
    SignatureMismatch,
    UnknownProduct,
    _mock_mode,
)
from app.modules.identity.auth import CurrentUser
from app.platform.db import get_session

router = APIRouter(prefix="/commerce", tags=["commerce"])

_service = CommerceService()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate, user: CurrentUser, session: SessionDep
) -> OrderOut:
    try:
        order = await _service.create_order(session, user.id, payload.product)
    except UnknownProduct:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown product")
    await session.commit()
    return OrderOut(**order)


@router.post("/webhook/razorpay", summary="Razorpay event callback (signature-verified)")
async def razorpay_webhook(
    request: Request,
    session: SessionDep,
    x_razorpay_signature: Annotated[str | None, Header()] = None,
) -> dict:
    body = await request.body()
    try:
        result = await _service.handle_webhook(session, body, x_razorpay_signature)
    except SignatureMismatch:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Bad signature")
    except PaymentNotFound:
        # 2xx anyway: this deployment doesn't know the order (another env's
        # webhook) and a 4xx would just make Razorpay retry forever.
        await session.commit()
        return {"status": "unknown-order"}
    await session.commit()
    return result


@router.get("/entitlements", response_model=list[EntitlementOut])
async def my_entitlements(user: CurrentUser, session: SessionDep) -> list[EntitlementOut]:
    rows = await _service.list_entitlements(session, user.id)
    return [EntitlementOut.model_validate(r) for r in rows]


@router.post(
    "/reports/premium",
    summary="Generate the premium ജാതക PDF (requires the entitlement)",
)
async def premium_report(user: CurrentUser, session: SessionDep) -> dict:
    """402 without an entitlement (buy or earn via referrals); otherwise the
    PDF is rendered (once per day) and returned as a download URL."""
    from app.platform.storage import get_storage

    try:
        key = await _service.generate_premium_report(session, user)
    except CommerceService.NotEntitled:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail="Premium report is locked — purchase it or earn it by inviting friends",
        )
    except CommerceService.NoChart:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="No chart computed yet")
    await session.commit()
    return {"download_url": get_storage().url(key)}


@router.post(
    "/orders/{order_id}/mock-pay",
    summary="Simulate a capture (mock mode only — 404 when live)",
)
async def mock_pay(order_id: str, user: CurrentUser, session: SessionDep) -> dict:
    if not _mock_mode():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        await _service.mock_capture(session, order_id)
    except PaymentNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    await session.commit()
    return {"status": "paid"}
