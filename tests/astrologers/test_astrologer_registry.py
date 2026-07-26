"""The astrologer directory now lives in the database, not in seed_data.py.

Mirrors tests/temples/test_temple_registry.py. The properties that matter:
an empty table falls back to the seed (so every other test's fresh database
behaves as it always did), a populated table replaces it, and deactivating
every astrologer does NOT resurrect the placeholders — which is the whole point
here, since all 28 seeded entries are generated dummies.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.modules.astrologers import registry
from app.modules.astrologers.models import Astrologer
from app.modules.astrologers.seed_data import SEED_ASTROLOGERS
from app.modules.astrologers.service import AstrologersService
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


def _astrologer(**over) -> Astrologer:
    base = dict(
        id="test-astro-1", name="Test Astrologer", name_ml="ടെസ്റ്റ്",
        district="Thrissur", town="Thrissur", lat=10.5276, lng=76.2144,
        specialties=["career"], experience_years=12, languages=["ml"],
        rating=4.5, bio_ml="ടെസ്റ്റ്",
        availability=[{"weekday": 0, "start": "09:00", "end": "11:00", "duration_min": 30}],
    )
    return Astrologer(**{**base, **over})


async def test_empty_table_falls_back_to_the_seed(session):
    assert await registry.load(session) == 0
    assert len(AstrologersService().list_astrologers()) == len(SEED_ASTROLOGERS)


async def test_populated_table_replaces_the_seed(session):
    session.add(_astrologer())
    await session.commit()

    assert await registry.load(session) == 1
    svc = AstrologersService()
    assert [a["id"] for a in svc.list_astrologers()] == ["test-astro-1"]
    assert svc.get_astrologer("kozhikode-astro-1") is None


async def test_deactivating_every_astrologer_empties_the_directory(session):
    """The point of the module: hide the 28 generated placeholders without the
    seed reappearing underneath."""
    session.add(_astrologer(active=False))
    await session.commit()

    assert await registry.load(session) == 0
    assert registry.current() == []
    assert AstrologersService().list_astrologers() == []
    assert AstrologersService().suggest_for(concern="career") is None


async def test_filters_and_suggest_read_the_database(session):
    session.add(_astrologer(id="a", district="Thrissur", specialties=["career"], rating=4.1))
    session.add(_astrologer(id="b", district="Kollam", specialties=["marriage"], rating=4.9))
    await session.commit()
    await registry.load(session)

    svc = AstrologersService()
    assert [a["id"] for a in svc.list_astrologers(district="Kollam")] == ["b"]
    assert [a["id"] for a in svc.list_astrologers(specialty="career")] == ["a"]
    # No coords → highest rating wins.
    assert svc.suggest_for()["id"] == "b"
    # A specialty match narrows before rating does.
    assert svc.suggest_for(concern="career")["id"] == "a"


async def test_availability_reads_windows_from_the_database(session):
    """`availability` stays a JSON array so _open_slots_utc is unchanged."""
    from datetime import date

    session.add(_astrologer())
    await session.commit()
    await registry.load(session)

    # 2026-07-27 is a Monday (weekday 0), matching the seeded window.
    slots = await AstrologersService().availability(session, "test-astro-1", date(2026, 7, 27))
    assert len(slots) == 4  # 09:00–11:00 in 30-minute slots
    assert slots[0]["duration_min"] == 30

    # Tuesday has no window.
    assert await AstrologersService().availability(session, "test-astro-1", date(2026, 7, 28)) == []


async def test_new_columns_do_not_leak_onto_the_wire(session):
    """The DB rows carry fields the seed never had (name_ml, price_paise_per_min).

    They are for the operator console. AstrologerOut does not declare them, so
    the public response shape is unchanged — this pins that, because widening
    the directory's dict is exactly how an unintended API change would sneak in.
    """
    from app.modules.astrologers.schemas import AstrologerOut

    session.add(_astrologer(name_ml="ജ്യോതിഷി", price_paise_per_min=5000))
    await session.commit()
    await registry.load(session)

    row = registry.current()[0]
    assert row["name_ml"] == "ജ്യോതിഷി" and row["price_paise_per_min"] == 5000

    served = AstrologerOut(**row).model_dump()
    assert "name_ml" not in served
    assert "price_paise_per_min" not in served
    assert set(served) == set(AstrologerOut.model_fields)


async def test_seed_round_trips_through_the_model(session):
    seed = dict(SEED_ASTROLOGERS[0])
    session.add(_astrologer(
        id=seed["id"], name=seed["name"], district=seed["district"], town=seed["town"],
        lat=seed["lat"], lng=seed["lng"], specialties=list(seed["specialties"]),
        experience_years=seed["experience_years"], languages=list(seed["languages"]),
        rating=seed["rating"], bio_ml=seed["bio_ml"],
        availability=[dict(w) for w in seed["availability"]],
    ))
    await session.commit()
    await registry.load(session)

    row = registry.current()[0]
    for key in ("id", "name", "district", "town", "lat", "lng", "specialties",
                "experience_years", "languages", "rating", "bio_ml", "availability"):
        assert row[key] == seed[key], key
