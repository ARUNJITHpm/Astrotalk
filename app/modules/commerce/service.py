"""Public service for the commerce module (GROWTH_PLAN.md Part 5a).

This is the ONLY surface other modules may depend on (AGENTS.md). Two jobs:

  - **Payments** (Razorpay Orders API): ``create_order`` → checkout happens
    client-side → Razorpay calls ``POST /commerce/webhook/razorpay`` →
    ``handle_webhook`` verifies the signature and marks the payment paid.
    ``mock_razorpay=True`` (default) keeps everything in-process: orders get
    ``order_mock_*`` ids and the dev-only ``mock-pay`` endpoint simulates the
    capture, so the full unlock flow runs with zero keys.
  - **Entitlements**: the single source of truth for "may this user use X".
    Purchases, referral rewards (Part 2), and admin grants all land here;
    feature code calls ``has_entitlement`` and never looks at payments.

Razorpay is called over plain HTTPS (httpx, Basic auth) — no SDK dependency.
Amounts are integer paise throughout.
"""

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commerce.models import Entitlement, Payment
from app.platform import metrics
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# Product catalog: key → (display name, price in paise). Prices are the
# server's truth — the client never sends an amount.
PRODUCTS: dict[str, dict[str, Any]] = {
    "premium_report": {"name": "Premium ജാതക റിപ്പോർട്ട്", "amount_paise": 19900},
}

_RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders"


class UnknownProduct(ValueError):
    pass


class PaymentNotFound(LookupError):
    pass


class SignatureMismatch(ValueError):
    """The webhook body was not signed with our webhook secret."""


def _mock_mode() -> bool:
    s = get_settings()
    return s.mock_razorpay or not (s.razorpay_key_id and s.razorpay_key_secret)


class CommerceService:
    # ---- orders ----

    async def create_order(
        self, session: AsyncSession, user_id: int, product: str
    ) -> dict[str, Any]:
        """Create a Razorpay order for one catalog product.

        Returns what the checkout needs: order id, amount, currency, and the
        public key id (empty when mocked).
        """
        spec = PRODUCTS.get(product)
        if spec is None:
            raise UnknownProduct(product)
        amount = int(spec["amount_paise"])

        if _mock_mode():
            order_id = f"order_mock_{secrets.token_hex(8)}"
        else:
            order_id = await self._razorpay_create_order(amount, product)

        payment = Payment(
            user_id=user_id,
            product=product,
            amount_paise=amount,
            razorpay_order_id=order_id,
        )
        session.add(payment)
        await session.flush()
        metrics.increment("commerce.orders_created")
        return {
            "order_id": order_id,
            "product": product,
            "amount_paise": amount,
            "currency": "INR",
            "razorpay_key_id": "" if _mock_mode() else get_settings().razorpay_key_id,
            "mock": _mock_mode(),
        }

    async def _razorpay_create_order(self, amount_paise: int, product: str) -> str:
        import httpx

        s = get_settings()
        async with httpx.AsyncClient(
            timeout=15, auth=(s.razorpay_key_id, s.razorpay_key_secret)
        ) as client:
            resp = await client.post(
                _RAZORPAY_ORDERS_URL,
                json={"amount": amount_paise, "currency": "INR", "notes": {"product": product}},
            )
            resp.raise_for_status()
            return str(resp.json()["id"])

    # ---- webhook ----

    def verify_webhook_signature(self, body: bytes, signature: str | None) -> None:
        """Razorpay signs the raw body with HMAC-SHA256(webhook_secret).

        No secret configured + mock mode → accepted (dev convenience).
        No secret + live mode → always rejected (fail closed).
        """
        secret = get_settings().razorpay_webhook_secret
        if not secret:
            if _mock_mode():
                return
            raise SignatureMismatch("webhook secret not configured")
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(expected, signature):
            raise SignatureMismatch("bad webhook signature")

    async def handle_webhook(
        self, session: AsyncSession, body: bytes, signature: str | None
    ) -> dict[str, str]:
        """Process a (verified) Razorpay event. Idempotent per payment.

        Handles ``payment.captured`` (paid + entitlement) and
        ``payment.failed``. Unknown events are acknowledged and ignored —
        Razorpay retries on non-2xx, and we only care about these two.
        """
        self.verify_webhook_signature(body, signature)
        event = json.loads(body.decode("utf-8"))
        kind = event.get("event", "")
        entity = (
            event.get("payload", {}).get("payment", {}).get("entity", {})
            if isinstance(event.get("payload"), dict)
            else {}
        )
        order_id = entity.get("order_id", "")
        if kind not in ("payment.captured", "payment.failed") or not order_id:
            return {"status": "ignored"}

        payment = (
            await session.execute(
                select(Payment).where(Payment.razorpay_order_id == order_id)
            )
        ).scalars().first()
        if payment is None:
            raise PaymentNotFound(order_id)
        if payment.status == "paid":  # replayed webhook — already done
            return {"status": "ok"}

        if kind == "payment.captured":
            await self._mark_paid(session, payment, entity.get("id"))
        else:
            payment.status = "failed"
            metrics.increment("commerce.payments_failed")
        await session.flush()
        return {"status": "ok"}

    async def _mark_paid(
        self, session: AsyncSession, payment: Payment, razorpay_payment_id: str | None
    ) -> None:
        payment.status = "paid"
        payment.razorpay_payment_id = razorpay_payment_id
        payment.paid_at = datetime.now(UTC)
        metrics.increment("commerce.payments_captured")
        await self.grant_entitlement(
            session,
            user_id=payment.user_id,
            org_id=payment.org_id,
            product_key=payment.product,
            granted_by="purchase",
            source=payment.razorpay_order_id,
        )
        logger.info(
            "commerce: payment captured for user %s product %s",
            payment.user_id, payment.product,
        )

    async def mock_capture(self, session: AsyncSession, order_id: str) -> None:
        """Simulate a capture in mock mode (dev/test only; router gates it)."""
        payment = (
            await session.execute(
                select(Payment).where(Payment.razorpay_order_id == order_id)
            )
        ).scalars().first()
        if payment is None:
            raise PaymentNotFound(order_id)
        if payment.status != "paid":
            await self._mark_paid(session, payment, f"pay_mock_{secrets.token_hex(6)}")
            await session.flush()

    # ---- entitlements ----

    async def grant_entitlement(
        self,
        session: AsyncSession,
        *,
        user_id: int | None,
        product_key: str,
        granted_by: str,
        source: str | None = None,
        org_id: int | None = None,
        expires_at: datetime | None = None,
    ) -> Entitlement:
        """Record a grant. Idempotent per (user, product, granted_by) for
        non-expiring grants, so a replayed webhook or a re-checked referral
        threshold never double-grants."""
        if user_id is not None and expires_at is None:
            existing = (
                await session.execute(
                    select(Entitlement).where(
                        Entitlement.user_id == user_id,
                        Entitlement.product_key == product_key,
                        Entitlement.granted_by == granted_by,
                        Entitlement.expires_at.is_(None),
                    )
                )
            ).scalars().first()
            if existing is not None:
                return existing
        row = Entitlement(
            user_id=user_id,
            org_id=org_id,
            product_key=product_key,
            granted_by=granted_by,
            source=source,
            expires_at=expires_at,
        )
        session.add(row)
        await session.flush()
        metrics.increment("commerce.entitlements_granted")
        return row

    async def has_entitlement(
        self, session: AsyncSession, user_id: int, product_key: str
    ) -> bool:
        """The ONE check feature code uses to unlock anything."""
        rows = (
            await session.execute(
                select(Entitlement).where(
                    Entitlement.user_id == user_id,
                    Entitlement.product_key == product_key,
                )
            )
        ).scalars().all()
        now = datetime.now(UTC)
        for row in rows:
            expires = row.expires_at
            if expires is None:
                return True
            if expires.tzinfo is None:  # SQLite returns naive datetimes
                expires = expires.replace(tzinfo=UTC)
            if expires > now:
                return True
        return False

    async def list_entitlements(
        self, session: AsyncSession, user_id: int
    ) -> list[Entitlement]:
        return list(
            (
                await session.execute(
                    select(Entitlement)
                    .where(Entitlement.user_id == user_id)
                    .order_by(Entitlement.created_at.desc())
                )
            ).scalars().all()
        )
