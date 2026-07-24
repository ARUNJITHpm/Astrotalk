"""Tests for the astrologers module: dummy directory, suggestion rule, and the
free consult booking flow (availability slicing, book, double-book, revive on
cancel, auth). Hermetic — in-memory SQLite, no network.
"""

import re
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.astrologers.service import (
    IST,
    AstroBookingError,
    AstroBookingNotFound,
    AstrologersService,
)
from app.modules.astrologers.seed_data import SEED_ASTROLOGERS
from app.modules.temples.remedy_map import CONCERN_DEITIES, DISTRICTS
from app.platform.config import get_settings
from app.platform.db import Base, get_session

# A Tuesday (weekday 1) in the future → astro-1 morning windows apply.
_TUESDAY = date(2026, 7, 14)
assert _TUESDAY.weekday() == 1


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    monkeypatch.setattr(get_settings(), "mock_geocoding", True)


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


# ---- seed directory integrity ----

def test_seed_has_two_per_district():
    assert len(SEED_ASTROLOGERS) == 28
    per_district: dict[str, int] = {}
    for a in SEED_ASTROLOGERS:
        per_district[a["district"]] = per_district.get(a["district"], 0) + 1
    assert set(per_district) == set(DISTRICTS)
    assert all(count == 2 for count in per_district.values())


def test_seed_ids_and_specialties_are_valid():
    valid_concerns = set(CONCERN_DEITIES)
    ids = set()
    for a in SEED_ASTROLOGERS:
        assert re.fullmatch(r"[a-z]+-astro-[12]", a["id"]), a["id"]
        assert a["name"] == a["id"]
        assert a["specialties"], a["id"]
        assert set(a["specialties"]) <= valid_concerns
        assert 4.2 <= a["rating"] <= 4.9
        ids.add(a["id"])
    assert len(ids) == 28  # ids unique


def test_every_concern_covered_by_multiple_astrologers():
    for concern in CONCERN_DEITIES:
        covering = [a for a in SEED_ASTROLOGERS if concern in a["specialties"]]
        # Not every concern is a specialty; those that are must be shared.
        if covering:
            assert len(covering) >= 2, concern


# ---- suggest_for precedence ----

def test_suggest_for_district_beats_distance():
    svc = AstrologersService()
    # Coordinates near Thiruvananthapuram, but district pins Kannur.
    got = svc.suggest_for(district="Kannur", lat=8.5, lng=76.9)
    assert got is not None
    assert got["district"] == "Kannur"


def test_suggest_for_specialty_filter():
    svc = AstrologersService()
    got = svc.suggest_for(concern="marriage")
    assert got is not None
    assert "marriage" in got["specialties"]


def test_suggest_for_rating_fallback_when_no_location():
    svc = AstrologersService()
    got = svc.suggest_for(district="Thrissur")
    assert got is not None
    thrissur = [a for a in SEED_ASTROLOGERS if a["district"] == "Thrissur"]
    assert got["rating"] == max(a["rating"] for a in thrissur)


# ---- availability + booking at the service level ----

async def test_availability_slices_and_excludes_bookings(session):
    svc = AstrologersService()
    astro = next(a["id"] for a in SEED_ASTROLOGERS if a["id"].endswith("-astro-1"))
    slots = await svc.availability(session, astro, _TUESDAY)
    # 09:30–12:30, 30-min → 6 slots.
    assert len(slots) == 6
    first = slots[0]["starts_at"]
    assert first.endswith("+05:30")

    booking = await svc.book(
        session, astrologer_id=astro, user_phone="+919000000001",
        starts_at=datetime.fromisoformat(first),
    )
    assert booking.status == "confirmed"

    slots2 = await svc.availability(session, astro, _TUESDAY)
    assert first not in [s["starts_at"] for s in slots2]
    assert len(slots2) == 5

    # Double-book the same instant → conflict.
    with pytest.raises(AstroBookingError):
        await svc.book(
            session, astrologer_id=astro, user_phone="+919000000002",
            starts_at=datetime.fromisoformat(first),
        )

    # Cancel frees the slot; re-booking revives the same row.
    await svc.cancel(session, booking.id, "+919000000001")
    slots3 = await svc.availability(session, astro, _TUESDAY)
    assert first in [s["starts_at"] for s in slots3]
    revived = await svc.book(
        session, astrologer_id=astro, user_phone="+919000000002",
        starts_at=datetime.fromisoformat(first),
    )
    assert revived.id == booking.id
    assert revived.user_phone == "+919000000002"


async def test_book_unknown_astrologer_not_found(session):
    svc = AstrologersService()
    with pytest.raises(AstroBookingNotFound):
        await svc.book(
            session, astrologer_id="nowhere-astro-9", user_phone="+91900",
            starts_at=datetime(2026, 7, 14, 10, 0, tzinfo=IST),
        )


async def test_cancel_not_owner_not_found(session):
    svc = AstrologersService()
    astro = next(a["id"] for a in SEED_ASTROLOGERS if a["id"].endswith("-astro-1"))
    slots = await svc.availability(session, astro, _TUESDAY)
    booking = await svc.book(
        session, astrologer_id=astro, user_phone="+919000000001",
        starts_at=datetime.fromisoformat(slots[0]["starts_at"]),
    )
    with pytest.raises(AstroBookingNotFound):
        await svc.cancel(session, booking.id, "+919999999999")


# ---- HTTP: public browse, auth-gated booking ----

@pytest.mark.asyncio
async def test_directory_and_booking_over_http(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Directory is public.
            listing = await client.get("/astrologers")
            assert listing.status_code == 200
            assert len(listing.json()) == 28
            kozhikode = (await client.get("/astrologers?district=Kozhikode")).json()
            assert len(kozhikode) == 2

            astro_id = "kozhikode-astro-1"
            assert (await client.get(f"/astrologers/{astro_id}")).status_code == 200
            assert (await client.get("/astrologers/no-such-astro")).status_code == 404

            avail = (
                await client.get(f"/astrologers/{astro_id}/availability?date={_TUESDAY}")
            ).json()
            assert len(avail) == 6
            slot = avail[0]["starts_at"]

            # Booking requires a login.
            assert (
                await client.post(f"/astrologers/{astro_id}/book", json={"starts_at": slot})
            ).status_code in (401, 403)
            assert (await client.get("/astrologers/bookings/me")).status_code in (401, 403)

            reg = await client.post("/identity/users", json={
                "phone": "+919000000010", "password": "p", "name": "Seeker",
                "dob": "1995-01-01", "birth_time": None, "birth_place": "Kozhikode",
            })
            auth = {"Authorization": f"Bearer {reg.json()['token']}"}

            booked = await client.post(
                f"/astrologers/{astro_id}/book",
                json={"starts_at": slot, "note": "first time"}, headers=auth,
            )
            assert booked.status_code == 201
            assert booked.json()["status"] == "confirmed"

            mine = (await client.get("/astrologers/bookings/me", headers=auth)).json()
            assert len(mine) == 1
            booking_id = mine[0]["id"]

            # Double-book → 409.
            dup = await client.post(
                f"/astrologers/{astro_id}/book", json={"starts_at": slot}, headers=auth,
            )
            assert dup.status_code == 409

            cancelled = await client.post(
                f"/astrologers/bookings/{booking_id}/cancel", headers=auth
            )
            assert cancelled.status_code == 200
            assert cancelled.json()["status"] == "cancelled"
    finally:
        main_app.dependency_overrides.pop(get_session, None)
