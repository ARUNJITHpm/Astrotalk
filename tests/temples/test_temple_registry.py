"""The temple directory now lives in the database, not in seed_data.py.

These tests pin the two properties the whole move depends on:
  1. an empty table falls back to the curated seed, so a fresh database (every
     other test builds one) behaves exactly as it did before the move; and
  2. a populated table replaces it, and the service — which is synchronous and
     was reading a module-level literal — sees the change.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.modules.temples import registry
from app.modules.temples.models import Temple
from app.modules.temples.seed_data import SEED_TEMPLES
from app.modules.temples.service import DEFAULT_POOJAS, DEFAULT_TIMINGS, TemplesService
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
    """The snapshot is process-global; never leak one test's into the next."""
    registry.reset()
    yield
    registry.reset()


def _temple(**over) -> Temple:
    base = dict(
        id="test-temple", name="Test Temple", name_ml="ടെസ്റ്റ്", deity="shiva",
        district="Thrissur", town="Thrissur", lat=10.5, lng=76.2,
        famous_for="testing", vazhipadu=["archana"], reviewed=False,
    )
    return Temple(**{**base, **over})


async def test_empty_table_falls_back_to_the_seed(session):
    assert await registry.load(session) == 0
    assert registry.current() == list(SEED_TEMPLES)
    # And the service, which is what actually matters, is unchanged.
    assert len(TemplesService().list_temples()) == len(SEED_TEMPLES)


async def test_populated_table_replaces_the_seed(session):
    session.add(_temple())
    await session.commit()

    assert await registry.load(session) == 1
    svc = TemplesService()
    assert [t["id"] for t in svc.list_temples()] == ["test-temple"]
    assert svc.get_temple("test-temple")["name"] == "Test Temple"
    # A seed temple is genuinely gone, not merged in.
    assert svc.get_temple("tvm-padmanabhaswamy") is None


async def test_inactive_temples_are_not_served(session):
    session.add(_temple(id="live"))
    session.add(_temple(id="retired", active=False))
    await session.commit()

    assert await registry.load(session) == 1
    assert [t["id"] for t in registry.current()] == ["live"]


async def test_retiring_every_temple_does_not_resurrect_the_seed(session):
    """The fallback keys on the table being EMPTY, not on there being no active
    rows — an operator who retires everything meant it."""
    session.add(_temple(active=False))
    await session.commit()

    assert await registry.load(session) == 0
    assert registry.current() == []
    assert TemplesService().list_temples() == []


async def test_unset_optional_columns_keep_their_service_defaults(session):
    """`t.get("hours", DEFAULT_HOURS)` only defaults when the key is ABSENT.

    A row carrying NULL must therefore be omitted from the dict, not passed
    through as None — otherwise every temple silently loses its fallback
    darshan hours and its offering catalogue.
    """
    session.add(_temple())
    await session.commit()
    await registry.load(session)

    row = registry.current()[0]
    assert "hours" not in row and "timings" not in row and "poojas" not in row

    detail = TemplesService().to_detail(row)
    assert detail["timings"] == DEFAULT_TIMINGS
    assert detail["poojas"] == DEFAULT_POOJAS
    assert detail["pooja"] is True


async def test_overrides_win_when_set(session):
    session.add(_temple(
        timings={"morning": "6 AM – 11 AM"},
        poojas=[{"key": "archana", "name": "Archana", "name_ml": "അർച്ചന",
                 "amount": 51, "lead_days": 0}],
        hours=[[6 * 60, 11 * 60]],
    ))
    await session.commit()
    await registry.load(session)

    detail = TemplesService().to_detail(registry.current()[0])
    assert detail["timings"] == {"morning": "6 AM – 11 AM"}
    assert [p["key"] for p in detail["poojas"]] == ["archana"]


async def test_sort_order_preserves_the_curated_ordering(session):
    session.add(_temple(id="b", sort_order=1))
    session.add(_temple(id="a", sort_order=0))
    await session.commit()
    await registry.load(session)

    assert [t["id"] for t in registry.current()] == ["a", "b"]


async def test_seed_round_trips_through_the_model(session):
    """Every seed temple must survive model → registry unchanged; this is what
    the migration's bulk import relies on."""
    seed = dict(SEED_TEMPLES[0])
    session.add(_temple(
        id=seed["id"], name=seed["name"], name_ml=seed["name_ml"],
        deity=seed["deity"], district=seed["district"], town=seed["town"],
        lat=seed["lat"], lng=seed["lng"], famous_for=seed["famous_for"],
        vazhipadu=list(seed["vazhipadu"]), reviewed=seed["reviewed"],
        story=seed.get("story"), story_ml=seed.get("story_ml"),
    ))
    await session.commit()
    await registry.load(session)

    row = registry.current()[0]
    for key in ("id", "name", "name_ml", "deity", "district", "town",
                "lat", "lng", "famous_for", "vazhipadu", "reviewed"):
        assert row[key] == seed[key], key
