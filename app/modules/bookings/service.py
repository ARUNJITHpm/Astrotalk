"""Public service for the bookings module (NITHARA-BUILD-PLAN Part 1).

Books a temple pooja and tracks its confirmation:

  1. price the offering from the temple's catalogue (server-side truth);
  2. open a Razorpay custom order via the commerce module (the ₹15 service fee
     is added here, exactly as the app shows it);
  3. record a ``pooja_bookings`` row linked to that order, state ``wait``.

On capture (Razorpay webhook or the dev ``mock-pay`` endpoint) the payment turns
``paid``; ``list_for_user`` reconciles each booking's state against commerce and
promotes it to ``ok``. No cross-module tables are touched — commerce and temples
are reached only through their public services (AGENTS.md).
"""

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.models import PoojaBooking
from app.modules.bookings.schemas import BookingCreate
from app.modules.commerce.service import CommerceService
from app.modules.temples.service import DEFAULT_POOJAS, TemplesService
from app.platform import metrics

SERVICE_FEE_PAISE = 1500  # ₹15, matching the app's review screen


class UnknownTemple(LookupError):
    pass


class UnknownPooja(LookupError):
    pass


class BookingsService:
    def __init__(self) -> None:
        self._commerce = CommerceService()
        self._temples = TemplesService()

    def _find_pooja(self, temple: dict, pooja_key: str) -> dict | None:
        for p in temple.get("poojas", DEFAULT_POOJAS):
            if p["key"] == pooja_key:
                return p
        return None

    async def create(
        self, session: AsyncSession, *, user_id: int, payload: BookingCreate
    ) -> dict:
        temple = self._temples.get_temple(payload.temple_id)
        if temple is None:
            raise UnknownTemple(payload.temple_id)
        pooja = self._find_pooja(temple, payload.pooja_key)
        if pooja is None:
            raise UnknownPooja(payload.pooja_key)

        amount_paise = int(pooja["amount"]) * 100
        total_paise = amount_paise + SERVICE_FEE_PAISE
        order = await self._commerce.create_custom_order(
            session,
            user_id=user_id,
            product=f"pooja:{payload.pooja_key}",
            amount_paise=total_paise,
        )
        booking = PoojaBooking(
            user_id=user_id,
            ref="NT" + "".join(secrets.choice("0123456789") for _ in range(6)),
            temple_id=payload.temple_id,
            pooja_key=payload.pooja_key,
            pooja_name=pooja["name"],
            amount_paise=amount_paise,
            service_fee_paise=SERVICE_FEE_PAISE,
            member_id=payload.member_id,
            member_name=payload.member_name,
            member_nak=payload.member_nak,
            when_label=payload.when,
            razorpay_order_id=order["order_id"],
            state="wait",
        )
        session.add(booking)
        await session.flush()
        metrics.increment("bookings.created")
        return self._to_out(booking, razorpay_key_id=order["razorpay_key_id"])

    async def count_for_user(self, session: AsyncSession, user_id: int) -> int:
        """How many CONFIRMED poojas this user has (PUBLIC — the profile stat).

        Only paid bookings count; an unpaid/abandoned 'wait' order must not
        inflate the stat or unlock a badge. Goes through the same reconcile as
        the listing so a just-captured payment is reflected."""
        rows = await self.list_for_user(session, user_id)
        return sum(1 for b in rows if b["state"] == "ok")

    async def list_for_user(self, session: AsyncSession, user_id: int) -> list[dict]:
        rows = list(
            (
                await session.execute(
                    select(PoojaBooking)
                    .where(PoojaBooking.user_id == user_id)
                    .order_by(PoojaBooking.created_at.desc())
                )
            ).scalars().all()
        )
        for b in rows:
            if b.state != "ok" and b.razorpay_order_id:
                status = await self._commerce.get_payment_status(
                    session, b.razorpay_order_id
                )
                if status == "paid":
                    b.state = "ok"
        await session.flush()
        return [self._to_out(b) for b in rows]

    @staticmethod
    def _to_out(b: PoojaBooking, *, razorpay_key_id: str = "") -> dict:
        return {
            "id": b.id,
            "ref": b.ref,
            "temple_id": b.temple_id,
            "pooja_key": b.pooja_key,
            "pooja_name": b.pooja_name,
            "amount_paise": b.amount_paise,
            "service_fee_paise": b.service_fee_paise,
            "total_paise": b.amount_paise + b.service_fee_paise,
            "member_id": b.member_id,
            "member_name": b.member_name,
            "member_nak": b.member_nak,
            "when": b.when_label,
            "state": b.state,
            "order_id": b.razorpay_order_id,
            "mock": CommerceService.mock_mode(),
            "razorpay_key_id": "" if CommerceService.mock_mode() else razorpay_key_id,
            "created_at": b.created_at,
        }
