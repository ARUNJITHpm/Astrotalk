"""The pooja catalogue is a table now, not DEFAULT_POOJAS in service.py.

The catalogue is resolved during the registry load and materialised into each
temple's ``poojas`` key, so ``TemplesService.pooja_catalogue`` and
``BookingsService._find_pooja`` — both of which read
``t.get("poojas", DEFAULT_POOJAS)`` — keep working untouched. These tests cover
that resolution: inheritance, per-temple override, opting out, and the
paise→rupee boundary.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.modules.temples import registry
from app.modules.temples.models import Pooja, Temple, TemplePooja
from app.modules.temples.service import DEFAULT_POOJAS, TemplesService
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


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.reset()
    yield
    registry.reset()


async def _setup(session, *, overrides=(), masters=None):
    session.add(Temple(
        id="t1", name="T", name_ml="ടി", deity="shiva", district="Thrissur",
        town="Thrissur", lat=10.5, lng=76.2, famous_for="x", vazhipadu=[],
        reviewed=False,
    ))
    for i, m in enumerate(masters if masters is not None else [
        dict(key="pushpanjali", name="Pushpanjali", name_ml="പുഷ്പാഞ്ജലി",
             amount_paise=10100, lead_days=0),
        dict(key="ganapathi_homam", name="Ganapathi Homam", name_ml="ഗണപതി ഹോമം",
             amount_paise=125000, lead_days=3),
    ]):
        session.add(Pooja(sort_order=i, **m))
    for o in overrides:
        session.add(TemplePooja(temple_id="t1", **o))
    await session.commit()
    await registry.load(session)


async def test_catalogue_comes_from_the_master_table(session):
    await _setup(session)

    poojas = TemplesService().pooja_catalogue(registry.current()[0])["poojas"]
    assert [p["key"] for p in poojas] == ["pushpanjali", "ganapathi_homam"]
    # Stored in paise, served in whole rupees — the existing API contract.
    assert poojas[0]["amount"] == 101
    assert poojas[1]["amount"] == 1250
    assert poojas[1]["lead_days"] == 3


async def test_override_changes_price_and_lead_for_one_temple(session):
    await _setup(session, overrides=[
        dict(pooja_key="pushpanjali", amount_paise=25000, lead_days=2),
    ])

    poojas = TemplesService().pooja_catalogue(registry.current()[0])["poojas"]
    got = {p["key"]: p for p in poojas}
    assert got["pushpanjali"]["amount"] == 250
    assert got["pushpanjali"]["lead_days"] == 2
    # The un-overridden one still inherits.
    assert got["ganapathi_homam"]["amount"] == 1250


async def test_null_override_columns_inherit_the_master(session):
    """Inheriting is the common case; an override row must not require copying
    the price just to change the lead time."""
    await _setup(session, overrides=[
        dict(pooja_key="pushpanjali", amount_paise=None, lead_days=5),
    ])

    got = {p["key"]: p for p in TemplesService().pooja_catalogue(registry.current()[0])["poojas"]}
    assert got["pushpanjali"]["amount"] == 101  # inherited
    assert got["pushpanjali"]["lead_days"] == 5  # overridden


async def test_a_temple_can_opt_out_of_an_offering(session):
    await _setup(session, overrides=[dict(pooja_key="ganapathi_homam", active=False)])

    keys = [p["key"] for p in TemplesService().pooja_catalogue(registry.current()[0])["poojas"]]
    assert keys == ["pushpanjali"]


async def test_inactive_master_pooja_disappears_everywhere(session):
    await _setup(session, masters=[
        dict(key="pushpanjali", name="Pushpanjali", name_ml="പുഷ്പാഞ്ജലി",
             amount_paise=10100, lead_days=0),
        dict(key="retired", name="Retired", name_ml="—",
             amount_paise=5000, lead_days=0, active=False),
    ])

    keys = [p["key"] for p in TemplesService().pooja_catalogue(registry.current()[0])["poojas"]]
    assert keys == ["pushpanjali"]


async def test_lead_time_locks_still_work_against_the_resolved_catalogue(session):
    await _setup(session)

    # 1 day until the star day: the 3-day-lead homam is locked, same-day is not.
    got = {
        p["key"]: p
        for p in TemplesService().pooja_catalogue(registry.current()[0], days_until=1)["poojas"]
    }
    assert got["pushpanjali"]["locked"] is False
    assert got["ganapathi_homam"]["locked"] is True


async def test_paise_is_carried_through_so_pricing_cannot_truncate(session):
    """`amount` is a whole-rupee rendering for the client. Booking must price
    from `amount_paise`, or a ₹101.50 offering would charge ₹101."""
    from app.modules.temples.schemas import PoojaCatalogueItem

    await _setup(session, masters=[
        dict(key="odd", name="Odd", name_ml="—", amount_paise=10150, lead_days=0),
    ])

    p = TemplesService().pooja_catalogue(registry.current()[0])["poojas"][0]
    assert p["amount"] == 101  # lossy, for display
    assert p["amount_paise"] == 10150  # authoritative

    # And it must not leak onto the wire.
    assert "amount_paise" not in PoojaCatalogueItem(**p).model_dump()


async def test_empty_master_table_leaves_the_service_default(session):
    """No catalogue rows → temples fall through to DEFAULT_POOJAS, so a
    database predating this table prices exactly as it always did."""
    session.add(Temple(
        id="t1", name="T", name_ml="ടി", deity="shiva", district="Thrissur",
        town="Thrissur", lat=10.5, lng=76.2, famous_for="x", vazhipadu=[],
        reviewed=False,
    ))
    await session.commit()
    await registry.load(session)

    row = registry.current()[0]
    assert "poojas" not in row
    assert TemplesService().pooja_catalogue(row)["poojas"] == [
        {**p, "locked": False} for p in DEFAULT_POOJAS
    ]
