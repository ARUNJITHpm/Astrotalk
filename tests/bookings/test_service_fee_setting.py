"""The ₹15 service fee is operator-settable, not a Python constant.

Pricing stays server-side truth either way: the client never sends an amount,
and the fee is read from the database at booking time.
"""

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.modules.bookings.models import BookingSettings
from app.modules.bookings.service import SERVICE_FEE_PAISE, service_fee_paise
from app.platform.db import Base


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_missing_row_falls_back_to_the_built_in_default(session):
    """A database predating the table — and every test's fresh one — must price
    exactly as it always did."""
    assert await service_fee_paise(session) == SERVICE_FEE_PAISE == 1500


async def test_operator_set_fee_is_used(session):
    session.add(BookingSettings(id=1, service_fee_paise=2500))
    await session.commit()

    assert await service_fee_paise(session) == 2500


async def test_a_zero_fee_is_honoured_not_treated_as_unset(session):
    """Waiving the fee is a legitimate operator choice; `or` would swallow it."""
    session.add(BookingSettings(id=1, service_fee_paise=0))
    await session.commit()

    assert await service_fee_paise(session) == 0
