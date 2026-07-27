"""Operator writes against the astrologer directory (console plan Part 6).

The module had no admin-gated route at all before this — `router.py` never
imported a guard, all six routes were public reads or user-scoped bookings. So
the first thing under test is that the new ones are shut, and the second is
that they are owner-only: a `temple_admin` runs a temple, not this directory.

As in Part 5, assertions go through the *public* API wherever they can. The
readers are synchronous and serve an in-memory snapshot, so a write that does
not rebuild it looks like a no-op until the next restart.
"""

from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.admin import operators as ops
from app.modules.astrologers import registry
from app.modules.astrologers.models import AstroBooking, Astrologer
from app.platform.db import Base, get_session

ADMIN = {"X-Admin-Token": "chargemod"}  # tests/conftest.py configures this

# 10:00–12:00 on Mondays, in 30-minute consults.
WINDOW = {"weekday": 0, "start": "10:00", "end": "12:00", "duration_min": 30}

ASTROLOGER = {
    "id": "real-astrologer",
    "name": "A Real Astrologer",
    "district": "Thrissur",
    "town": "Thrissur",
    "lat": 10.52,
    "lng": 76.21,
    "specialties": ["marriage"],
    "experience_years": 22,
    "languages": ["ml"],
    "rating": 4.6,
    "availability": [WINDOW],
}


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


@pytest_asyncio.fixture
async def api(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        main_app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clean_registry():
    """The snapshot is process-global; never leak one test's into the next."""
    registry.reset()
    yield
    registry.reset()


async def _temple_admin(session) -> dict:
    invite = await ops.invite(
        session, email="clerk@example.com", role="temple_admin", temple_id="t1"
    )
    await ops.accept(session, token=invite.token, password="temple-pass-1")
    token = await ops.login(session, identifier="clerk@example.com", password="temple-pass-1")
    await session.commit()
    return {"Authorization": f"Bearer {token}"}


async def _create(api, **over) -> httpx.Response:
    return await api.post("/astrologers", json={**ASTROLOGER, **over}, headers=ADMIN)


# ---- the gate ----


async def test_every_write_route_refuses_an_anonymous_caller(api):
    assert (await api.get("/astrologers/manage")).status_code == 401
    assert (await api.post("/astrologers", json=ASTROLOGER)).status_code == 401
    assert (await api.patch("/astrologers/x", json={"name": "n"})).status_code == 401
    assert (await api.put("/astrologers/x/availability", json={"windows": []})).status_code == 401
    assert (await api.get("/astrologers/x/bookings")).status_code == 401
    closed = await api.patch("/astrologers/bookings/1", json={"status": "completed"})
    assert closed.status_code == 401


async def test_a_temple_admin_has_no_business_here(api, session):
    headers = await _temple_admin(session)
    assert (await api.get("/astrologers/manage", headers=headers)).status_code == 403
    assert (
        await api.post("/astrologers", json=ASTROLOGER, headers=headers)
    ).status_code == 403


async def test_the_manage_path_is_not_shadowed_by_the_catch_all(api):
    """`/astrologers/manage` and `/astrologers/{astrologer_id}` overlap. If the
    catch-all is registered first this 404s as an unknown astrologer."""
    r = await api.get("/astrologers/manage", headers=ADMIN)
    assert r.status_code == 200


# ---- onboarding ----


async def test_onboarding_publishes_an_astrologer_to_the_app(api):
    assert (await _create(api)).status_code == 201
    listed = await api.get("/astrologers")
    assert [a["id"] for a in listed.json()] == ["real-astrologer"]
    assert listed.json()[0]["experience_years"] == 22


async def test_the_public_shape_still_hides_the_console_only_fields(api):
    """`AstrologerOut` declares neither price nor availability nor active. The
    directory dict carries all three, so widening it must not widen the API."""
    await _create(api)
    body = (await api.get("/astrologers")).json()[0]
    assert not {"price_paise_per_min", "availability", "active"} & set(body)


async def test_create_rejects_a_bad_id_and_a_duplicate(api):
    assert (await _create(api, id="Not A Slug")).status_code == 422
    assert (await _create(api)).status_code == 201
    assert (await _create(api)).status_code == 422


async def test_create_rejects_an_impossible_rating(api):
    assert (await _create(api, rating=9.9)).status_code == 422


async def test_an_edit_reaches_the_app_immediately(api):
    await _create(api)
    r = await api.patch(
        "/astrologers/real-astrologer", json={"bio_ml": "പുതിയ വിവരണം"}, headers=ADMIN
    )
    assert r.status_code == 200
    assert (await api.get("/astrologers/real-astrologer")).json()["bio_ml"] == "പുതിയ വിവരണം"


async def test_patch_refuses_a_field_that_is_not_editable(api):
    """`availability` and `active` have their own routes, so they must not be
    reachable through the generic edit — extra='forbid' enforces it."""
    await _create(api)
    assert (
        await api.patch(
            "/astrologers/real-astrologer", json={"active": False}, headers=ADMIN
        )
    ).status_code == 422
    assert (
        await api.patch(
            "/astrologers/real-astrologer", json={"availability": []}, headers=ADMIN
        )
    ).status_code == 422


async def test_patching_an_unknown_astrologer_is_404(api):
    r = await api.patch("/astrologers/nope", json={"name": "x"}, headers=ADMIN)
    assert r.status_code == 404


async def test_hiding_removes_an_astrologer_from_the_app_not_the_console(api):
    await _create(api)
    r = await api.post(
        "/astrologers/real-astrologer/active", json={"active": False}, headers=ADMIN
    )
    assert r.status_code == 200
    assert (await api.get("/astrologers")).json() == []
    managed = await api.get("/astrologers/manage", headers=ADMIN)
    assert [a["id"] for a in managed.json()] == ["real-astrologer"]


# ---- availability ----


async def test_replacing_the_schedule_changes_the_bookable_slots(api):
    await _create(api)
    # 2026-08-03 is a Monday, which is the seeded window's weekday.
    before = await api.get("/astrologers/real-astrologer/availability?date=2026-08-03")
    assert len(before.json()) == 4  # 10:00, 10:30, 11:00, 11:30

    r = await api.put(
        "/astrologers/real-astrologer/availability",
        json={"windows": [{**WINDOW, "end": "11:00"}]},
        headers=ADMIN,
    )
    assert r.status_code == 200
    after = await api.get("/astrologers/real-astrologer/availability?date=2026-08-03")
    assert len(after.json()) == 2


async def test_an_empty_schedule_closes_the_diary(api):
    await _create(api)
    r = await api.put(
        "/astrologers/real-astrologer/availability", json={"windows": []}, headers=ADMIN
    )
    assert r.status_code == 200
    assert (
        await api.get("/astrologers/real-astrologer/availability?date=2026-08-03")
    ).json() == []


async def test_a_backwards_window_is_rejected(api):
    await _create(api)
    r = await api.put(
        "/astrologers/real-astrologer/availability",
        json={"windows": [{**WINDOW, "start": "12:00", "end": "10:00"}]},
        headers=ADMIN,
    )
    assert r.status_code == 422


async def test_a_window_shorter_than_one_consult_is_rejected(api):
    """It would silently yield zero slots and the astrologer would look booked
    solid forever, with nothing anywhere saying why."""
    await _create(api)
    r = await api.put(
        "/astrologers/real-astrologer/availability",
        json={"windows": [{**WINDOW, "end": "10:20"}]},
        headers=ADMIN,
    )
    assert r.status_code == 422


async def test_a_nonsense_weekday_is_rejected(api):
    await _create(api)
    r = await api.put(
        "/astrologers/real-astrologer/availability",
        json={"windows": [{**WINDOW, "weekday": 9}]},
        headers=ADMIN,
    )
    assert r.status_code == 422


async def test_narrowing_the_schedule_never_cancels_a_booked_consult(api, session):
    """A booking holds an absolute instant, not a reference to a window."""
    await _create(api)
    session.add(
        AstroBooking(
            astrologer_id="real-astrologer",
            user_phone="+919999999999",
            starts_at=datetime(2026, 8, 3, 5, 30, tzinfo=UTC),  # 11:00 IST
            duration_min=30,
        )
    )
    await session.commit()

    await api.put(
        "/astrologers/real-astrologer/availability",
        json={"windows": [{**WINDOW, "end": "10:30"}]},
        headers=ADMIN,
    )
    diary = await api.get("/astrologers/real-astrologer/bookings", headers=ADMIN)
    assert [b["status"] for b in diary.json()] == ["confirmed"]


# ---- the diary ----


async def test_an_astrologer_can_finally_see_their_own_diary(api, session):
    await _create(api)
    session.add(
        AstroBooking(
            astrologer_id="real-astrologer",
            user_phone="+919999999999",
            starts_at=datetime(2026, 8, 3, 4, 30, tzinfo=UTC),
            duration_min=30,
        )
    )
    await session.commit()

    r = await api.get("/astrologers/real-astrologer/bookings", headers=ADMIN)
    assert r.status_code == 200
    # The operator running the consult needs to know who is coming.
    assert r.json()[0]["user_phone"] == "+919999999999"


async def _booking(api, session) -> int:
    await _create(api)
    row = AstroBooking(
        astrologer_id="real-astrologer",
        user_phone="+919999999999",
        starts_at=datetime(2026, 8, 3, 4, 30, tzinfo=UTC),
        duration_min=30,
    )
    session.add(row)
    await session.commit()
    return row.id


async def test_an_operator_can_record_that_a_consult_happened(api, session):
    booking_id = await _booking(api, session)
    r = await api.patch(
        f"/astrologers/bookings/{booking_id}", json={"status": "completed"}, headers=ADMIN
    )
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


async def test_a_terminal_state_may_be_corrected_but_never_revived(api, session):
    """Marking no_show by mistake must be fixable. Returning to `confirmed`
    must not be: astro_bookings is unique on (astrologer_id, starts_at) and a
    closed row still holds its slot, so reviving could re-seat a consult
    somebody else has since booked."""
    booking_id = await _booking(api, session)
    await api.patch(
        f"/astrologers/bookings/{booking_id}", json={"status": "no_show"}, headers=ADMIN
    )
    corrected = await api.patch(
        f"/astrologers/bookings/{booking_id}", json={"status": "completed"}, headers=ADMIN
    )
    assert corrected.status_code == 200

    revived = await api.patch(
        f"/astrologers/bookings/{booking_id}", json={"status": "confirmed"}, headers=ADMIN
    )
    assert revived.status_code == 422


async def test_an_unknown_status_is_rejected(api, session):
    booking_id = await _booking(api, session)
    r = await api.patch(
        f"/astrologers/bookings/{booking_id}", json={"status": "maybe"}, headers=ADMIN
    )
    assert r.status_code == 422


async def test_setting_the_same_status_twice_is_idempotent(api, session):
    booking_id = await _booking(api, session)
    first = await api.patch(
        f"/astrologers/bookings/{booking_id}", json={"status": "completed"}, headers=ADMIN
    )
    second = await api.patch(
        f"/astrologers/bookings/{booking_id}", json={"status": "completed"}, headers=ADMIN
    )
    assert first.status_code == second.status_code == 200


async def test_a_completed_consult_still_holds_its_slot(api, session):
    """Only `cancelled` frees a time. A completed consult occupied it."""
    booking_id = await _booking(api, session)
    await api.patch(
        f"/astrologers/bookings/{booking_id}", json={"status": "completed"}, headers=ADMIN
    )
    slots = (
        await api.get("/astrologers/real-astrologer/availability?date=2026-08-03")
    ).json()
    assert len(slots) == 3  # 10:00 is taken by the completed consult


async def test_a_user_cannot_cancel_a_consult_that_already_happened(api, session):
    """`cancel` used to reject only "already cancelled", because that was the
    only closed state. Widening the vocabulary would otherwise have let a user
    cancel a consult an operator recorded as completed — rewriting history and
    freeing a slot that was genuinely used."""
    from app.modules.astrologers.service import AstroBookingError, AstrologersService

    booking_id = await _booking(api, session)
    await api.patch(
        f"/astrologers/bookings/{booking_id}", json={"status": "completed"}, headers=ADMIN
    )

    # Straight at the service: the route above it only supplies the caller's
    # own phone, which is exactly what this booking already carries.
    with pytest.raises(AstroBookingError, match="already completed"):
        await AstrologersService().cancel(session, booking_id, "+919999999999")


async def test_updating_an_unknown_booking_is_404(api):
    r = await api.patch(
        "/astrologers/bookings/999", json={"status": "completed"}, headers=ADMIN
    )
    assert r.status_code == 404


# ---- photo ----

_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)


async def test_uploading_a_photo_records_the_key(api, session):
    await _create(api)
    r = await api.post("/astrologers/real-astrologer/photo", content=_PNG, headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["photo_key"] == "astrologers/real-astrologer.png"
    assert (await session.get(Astrologer, "real-astrologer")).photo_key == (
        "astrologers/real-astrologer.png"
    )


async def test_a_file_that_is_not_an_image_is_refused(api):
    await _create(api)
    r = await api.post(
        "/astrologers/real-astrologer/photo",
        content=b"not an image at all",
        headers={**ADMIN, "Content-Type": "image/png"},
    )
    assert r.status_code == 422


async def test_photographing_an_unknown_astrologer_is_404(api):
    r = await api.post("/astrologers/nope/photo", content=_PNG, headers=ADMIN)
    assert r.status_code == 404
