"""Operator writes against the temple directory (console plan Part 5).

Three things are under test and they matter in this order:

  1. **Scope.** A ``temple_admin`` may only touch the temples they run. This is
     where a missing check leaks the most, so every write route is probed from
     a scoped operator, not just the happy owner path.
  2. **Publication.** The readers are synchronous and serve an in-memory
     snapshot, so a write that does not rebuild it looks like a no-op until the
     next restart. Every test asserts against the *public* API, not the row.
  3. **Route ordering.** The literal admin paths share a prefix with the
     ``/{temple_id}`` catch-all; a pin here catches a re-order that would make
     ``/temples/poojas`` resolve to a temple named "poojas".
"""

from datetime import date

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.admin import operators as ops
from app.modules.temples import registry
from app.modules.temples.models import Pooja, Temple, TempleFestival, TemplePartner
from app.platform.db import Base, get_session

ADMIN = {"X-Admin-Token": "chargemod"}  # tests/conftest.py configures this

TEMPLE = {
    "id": "test-temple",
    "name": "Test Temple",
    "name_ml": "ടെസ്റ്റ്",
    "deity": "shiva",
    "district": "Thrissur",
    "town": "Thrissur",
    "lat": 10.5,
    "lng": 76.2,
    "famous_for": "testing",
    "vazhipadu": ["archana"],
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


async def _scoped_operator(session, temple_id: str, email="clerk@example.com") -> dict:
    """Sign in a temple_admin scoped to one temple; returns its auth header."""
    invite = await ops.invite(
        session, email=email, role="temple_admin", temple_id=temple_id
    )
    await ops.accept(session, token=invite.token, password="temple-pass-1")
    token = await ops.login(session, identifier=email, password="temple-pass-1")
    await session.commit()
    return {"Authorization": f"Bearer {token}"}


async def _reviewer(session, email="reviewer@example.com") -> dict:
    invite = await ops.invite(session, email=email, role="content_reviewer")
    await ops.accept(session, token=invite.token, password="temple-pass-1")
    token = await ops.login(session, identifier=email, password="temple-pass-1")
    await session.commit()
    return {"Authorization": f"Bearer {token}"}


async def _create(api, **over) -> httpx.Response:
    return await api.post("/temples", json={**TEMPLE, **over}, headers=ADMIN)


# ---- the gate ----


async def test_every_write_route_refuses_an_anonymous_caller(api):
    assert (await api.get("/temples/manage")).status_code == 401
    assert (await api.post("/temples", json=TEMPLE)).status_code == 401
    assert (await api.patch("/temples/x", json={"name": "n"})).status_code == 401
    assert (await api.get("/temples/poojas")).status_code == 401
    assert (await api.post("/temples/x/active", json={"active": False})).status_code == 401


# ---- create / edit / retire ----


async def test_creating_a_temple_publishes_it_to_the_app(api):
    assert (await _create(api)).status_code == 201
    listed = await api.get("/temples")
    assert [t["id"] for t in listed.json()] == ["test-temple"]


async def test_create_rejects_an_unknown_deity(api):
    r = await _create(api, deity="cthulhu")
    assert r.status_code == 422
    assert "unknown deity" in r.json()["detail"]


async def test_create_rejects_a_bad_id_and_a_duplicate(api):
    assert (await _create(api, id="Not A Slug")).status_code == 422
    assert (await _create(api)).status_code == 201
    assert (await _create(api)).status_code == 422


async def test_create_rejects_impossible_coordinates(api):
    assert (await _create(api, lat=910.0)).status_code == 422


async def test_an_edit_is_visible_to_the_app_immediately(api):
    await _create(api)
    r = await api.patch(
        "/temples/test-temple", json={"name": "Renamed"}, headers=ADMIN
    )
    assert r.status_code == 200
    detail = await api.get("/temples/test-temple")
    assert detail.json()["en"] == "Renamed"


async def test_patch_refuses_a_field_that_is_not_editable(api):
    """`reviewed` has its own gate, so it must not be reachable through the
    generic edit route — extra='forbid' is what enforces that."""
    await _create(api)
    r = await api.patch(
        "/temples/test-temple", json={"reviewed": True}, headers=ADMIN
    )
    assert r.status_code == 422


async def test_patching_an_unknown_temple_is_404(api):
    r = await api.patch("/temples/nope", json={"name": "x"}, headers=ADMIN)
    assert r.status_code == 404


async def test_retiring_hides_a_temple_from_the_app_but_not_the_console(api):
    await _create(api)
    r = await api.post(
        "/temples/test-temple/active", json={"active": False}, headers=ADMIN
    )
    assert r.status_code == 200
    assert (await api.get("/temples")).json() == []
    # Still editable — retiring is a soft delete, and the row keeps its history.
    managed = await api.get("/temples/manage", headers=ADMIN)
    assert [t["id"] for t in managed.json()] == ["test-temple"]
    assert managed.json()[0]["active"] is False


async def test_hours_must_be_ordered_windows(api):
    await _create(api)
    r = await api.patch(
        "/temples/test-temple", json={"hours": [[600, 300]]}, headers=ADMIN
    )
    assert r.status_code == 422


async def test_timings_must_carry_all_three_windows(api):
    await _create(api)
    r = await api.patch(
        "/temples/test-temple", json={"timings": {"morning": "5 AM"}}, headers=ADMIN
    )
    assert r.status_code == 422


# ---- the review flag ----


async def test_a_content_reviewer_may_flip_the_review_flag(api, session):
    await _create(api)
    headers = await _reviewer(session)
    r = await api.patch(
        "/temples/test-temple/review", json={"reviewed": True}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["reviewed"] is True


async def test_a_temple_admin_cannot_certify_their_own_temple(api, session):
    """The flag asserts an astrologer checked the content. A temple's own admin
    flipping it would make it self-issued, and it is served to clients."""
    await _create(api)
    headers = await _scoped_operator(session, "test-temple")
    r = await api.patch(
        "/temples/test-temple/review", json={"reviewed": True}, headers=headers
    )
    assert r.status_code == 403


# ---- scope ----


async def test_a_temple_admin_sees_only_their_own_temples(api, session):
    await _create(api)
    await _create(api, id="other-temple", name="Other")
    headers = await _scoped_operator(session, "test-temple")

    listed = await api.get("/temples/manage", headers=headers)
    assert [t["id"] for t in listed.json()] == ["test-temple"]


async def test_a_temple_admin_may_edit_their_own_and_no_other(api, session):
    await _create(api)
    await _create(api, id="other-temple", name="Other")
    headers = await _scoped_operator(session, "test-temple")

    mine = await api.patch(
        "/temples/test-temple", json={"town": "Guruvayur"}, headers=headers
    )
    assert mine.status_code == 200
    theirs = await api.patch(
        "/temples/other-temple", json={"town": "Guruvayur"}, headers=headers
    )
    assert theirs.status_code == 403
    # And the rejected edit really did not land.
    assert (await api.get("/temples/other-temple")).json()["place"] == "Thrissur"


async def test_a_temple_admin_cannot_create_or_retire_a_temple(api, session):
    await _create(api)
    headers = await _scoped_operator(session, "test-temple")
    assert (
        await api.post("/temples", json={**TEMPLE, "id": "new-one"}, headers=headers)
    ).status_code == 403
    assert (
        await api.post(
            "/temples/test-temple/active", json={"active": False}, headers=headers
        )
    ).status_code == 403


# ---- master catalogue ----


async def test_master_offerings_reach_the_app_catalogue(api):
    await _create(api)
    created = await api.post(
        "/temples/poojas",
        json={"key": "archana", "name": "Archana", "amount_paise": 5100},
        headers=ADMIN,
    )
    assert created.status_code == 201

    catalogue = await api.get("/temples/test-temple/poojas")
    assert catalogue.json()["poojas"] == [
        {"key": "archana", "name": "Archana", "name_ml": "",
         "amount": 51, "lead_days": 0, "locked": False}
    ]


async def test_repricing_a_master_offering_republishes_it(api):
    await _create(api)
    await api.post(
        "/temples/poojas",
        json={"key": "archana", "name": "Archana", "amount_paise": 5100},
        headers=ADMIN,
    )
    r = await api.patch(
        "/temples/poojas/archana", json={"amount_paise": 7500}, headers=ADMIN
    )
    assert r.status_code == 200
    catalogue = await api.get("/temples/test-temple/poojas")
    assert catalogue.json()["poojas"][0]["amount"] == 75


async def test_a_negative_price_is_rejected(api):
    r = await api.post(
        "/temples/poojas",
        json={"key": "archana", "name": "Archana", "amount_paise": -1},
        headers=ADMIN,
    )
    assert r.status_code == 422


async def test_a_temple_admin_cannot_touch_the_master_catalogue(api, session):
    await _create(api)
    headers = await _scoped_operator(session, "test-temple")
    r = await api.post(
        "/temples/poojas",
        json={"key": "archana", "name": "Archana", "amount_paise": 5100},
        headers=headers,
    )
    assert r.status_code == 403


async def test_the_master_catalogue_path_is_not_shadowed_by_the_catch_all(api):
    """`/temples/poojas` and `/temples/{temple_id}` overlap. If the catch-all
    is ever registered first this returns 404 "Temple not found" instead."""
    r = await api.get("/temples/poojas", headers=ADMIN)
    assert r.status_code == 200
    assert r.json() == []


# ---- per-temple overrides ----


async def _with_master(api) -> None:
    await _create(api)
    await api.post(
        "/temples/poojas",
        json={"key": "archana", "name": "Archana", "amount_paise": 5100,
              "lead_days": 0},
        headers=ADMIN,
    )


async def test_a_temple_may_set_its_own_price(api):
    await _with_master(api)
    r = await api.put(
        "/temples/test-temple/poojas/archana",
        json={"amount_paise": 10150},
        headers=ADMIN,
    )
    assert r.status_code == 200
    catalogue = await api.get("/temples/test-temple/poojas")
    assert catalogue.json()["poojas"][0]["amount"] == 101


async def test_an_override_may_change_lead_time_alone_and_still_inherit_price(api):
    """Inheriting is the point: a temple that once edited its lead time must
    still pick up a later master repricing."""
    await _with_master(api)
    await api.put(
        "/temples/test-temple/poojas/archana", json={"lead_days": 3}, headers=ADMIN
    )
    await api.patch(
        "/temples/poojas/archana", json={"amount_paise": 9900}, headers=ADMIN
    )
    item = (await api.get("/temples/test-temple/poojas")).json()["poojas"][0]
    assert (item["amount"], item["lead_days"]) == (99, 3)


async def test_deactivating_an_override_removes_the_offering_here_only(api):
    await _with_master(api)
    await _create(api, id="other-temple", name="Other")
    await api.put(
        "/temples/test-temple/poojas/archana", json={"active": False}, headers=ADMIN
    )
    assert (await api.get("/temples/test-temple/poojas")).json()["poojas"] == []
    assert len((await api.get("/temples/other-temple/poojas")).json()["poojas"]) == 1


async def test_clearing_an_override_restores_the_master_entry(api):
    await _with_master(api)
    await api.put(
        "/temples/test-temple/poojas/archana",
        json={"amount_paise": 10150},
        headers=ADMIN,
    )
    r = await api.delete("/temples/test-temple/poojas/archana", headers=ADMIN)
    assert r.status_code == 204
    assert (await api.get("/temples/test-temple/poojas")).json()["poojas"][0]["amount"] == 51
    assert (
        await api.delete("/temples/test-temple/poojas/archana", headers=ADMIN)
    ).status_code == 404


async def test_an_override_needs_a_master_offering_to_override(api):
    await _create(api)
    r = await api.put(
        "/temples/test-temple/poojas/ghost", json={"amount_paise": 100}, headers=ADMIN
    )
    assert r.status_code == 404


async def test_a_temple_admin_may_price_their_own_temple_but_not_another(api, session):
    await _with_master(api)
    await _create(api, id="other-temple", name="Other")
    headers = await _scoped_operator(session, "test-temple")
    assert (
        await api.put(
            "/temples/test-temple/poojas/archana",
            json={"amount_paise": 6000},
            headers=headers,
        )
    ).status_code == 200
    assert (
        await api.put(
            "/temples/other-temple/poojas/archana",
            json={"amount_paise": 6000},
            headers=headers,
        )
    ).status_code == 403


# ---- image ----

_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)


async def test_uploading_a_photo_stores_it_and_records_the_key(api, session):
    await _create(api)
    r = await api.post("/temples/test-temple/image", content=_PNG, headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["image_key"] == "temples/test-temple.png"

    row = await session.get(Temple, "test-temple")
    assert row.image_key == "temples/test-temple.png"


async def test_a_file_that_is_not_an_image_is_refused(api):
    """The format comes from the magic bytes, never the Content-Type header —
    the header is a claim, the first bytes are evidence."""
    await _create(api)
    r = await api.post(
        "/temples/test-temple/image",
        content=b"<?php system($_GET[0]); ?>",
        headers={**ADMIN, "Content-Type": "image/png"},
    )
    assert r.status_code == 422


async def test_a_riff_container_that_is_not_webp_is_refused(api):
    """`RIFF` is the generic container magic — WAV and AVI carry it too. Matching
    on it alone would store an audio file and serve it back as image/webp."""
    await _create(api)
    wav = b"RIFF\x24\x00\x00\x00WAVEfmt "
    r = await api.post("/temples/test-temple/image", content=wav, headers=ADMIN)
    assert r.status_code == 422


async def test_uploading_to_an_unknown_temple_is_404(api):
    r = await api.post("/temples/nope/image", content=_PNG, headers=ADMIN)
    assert r.status_code == 404


# ---- partners and festivals: previously append-only ----


async def test_a_festival_date_can_finally_be_corrected(api, session):
    session.add(
        TempleFestival(temple_id="test-temple", name="Utsavam", day=date(2026, 9, 1))
    )
    await session.commit()
    festival_id = (await session.get(TempleFestival, 1)).id

    r = await api.patch(
        f"/temples/festivals/{festival_id}", json={"day": "2026-09-08"}, headers=ADMIN
    )
    assert r.status_code == 200
    assert r.json()["day"] == "2026-09-08"

    assert (
        await api.delete(f"/temples/festivals/{festival_id}", headers=ADMIN)
    ).status_code == 204
    assert (
        await api.delete(f"/temples/festivals/{festival_id}", headers=ADMIN)
    ).status_code == 404


async def test_a_partnership_can_be_ended(api, session):
    """`TemplePartner.active` had no route that could write it, so a partnership
    could be created but never ended. Ending it takes the microsite offline."""
    await _create(api)  # the microsite renders the directory row, so it must exist
    session.add(TemplePartner(temple_id="test-temple", slug="test-slug"))
    await session.commit()

    assert (await api.get("/t/test-slug")).status_code == 200
    r = await api.patch(
        "/temples/partners/test-slug", json={"active": False}, headers=ADMIN
    )
    assert r.status_code == 200
    assert (await api.get("/t/test-slug")).status_code == 404


async def test_an_unknown_partner_tier_is_rejected(api, session):
    session.add(TemplePartner(temple_id="test-temple", slug="test-slug"))
    await session.commit()
    r = await api.patch(
        "/temples/partners/test-slug", json={"tier": "platinum"}, headers=ADMIN
    )
    assert r.status_code == 422


async def test_partner_creation_is_scoped_like_partner_editing(api, session):
    """Creating a partner used to be open to any operator while editing one is
    scoped — which would have let a temple_admin register a partner for a temple
    they are then forbidden to touch."""
    await _create(api)
    await _create(api, id="other-temple", name="Other")
    headers = await _scoped_operator(session, "test-temple")

    mine = await api.post(
        "/temples/partners",
        json={"temple_id": "test-temple", "slug": "mine"},
        headers=headers,
    )
    assert mine.status_code == 201
    theirs = await api.post(
        "/temples/partners",
        json={"temple_id": "other-temple", "slug": "theirs"},
        headers=headers,
    )
    assert theirs.status_code == 403


async def test_the_partner_list_hides_other_temples_contacts(api, session):
    await _create(api)
    session.add(TemplePartner(temple_id="test-temple", slug="mine"))
    session.add(TemplePartner(temple_id="other-temple", slug="theirs"))
    await session.commit()
    headers = await _scoped_operator(session, "test-temple")

    listed = await api.get("/temples/partners", headers=headers)
    assert [p["slug"] for p in listed.json()] == ["mine"]
    # The QR poster is a partner asset too, and it is equally scoped.
    assert (await api.get("/temples/partners/theirs/qr.png", headers=headers)).status_code == 403


async def test_a_temple_admin_cannot_edit_another_temples_festival(api, session):
    session.add(
        TempleFestival(temple_id="other-temple", name="Utsavam", day=date(2026, 9, 1))
    )
    await session.commit()
    headers = await _scoped_operator(session, "test-temple")
    r = await api.patch(
        "/temples/festivals/1", json={"day": "2026-09-08"}, headers=headers
    )
    assert r.status_code == 403


# ---- the fallback trap ----


async def test_the_first_created_temple_replaces_the_seed_directory(api, session):
    """Worth pinning because it is surprising: an empty table means "never
    imported" and serves the curated seed, so creating the very first temple
    through the console on a deployment that never ran the import migration
    swaps 53 temples for 1. In production the migration has run."""
    assert len((await api.get("/temples?limit=200")).json()) == 53
    await _create(api)
    assert len((await api.get("/temples?limit=200")).json()) == 1
    assert await session.get(Pooja, "archana") is None
