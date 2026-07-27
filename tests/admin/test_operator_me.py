"""GET /admin/operators/me — the console's first call (console plan Part 9).

Part 4 issued a session token but nothing told the holder what it was *for*, so
a console had no way to render a role-aware sidebar. This endpoint returns the
already-resolved ``Operator``: no new authorisation logic, just the answer
``require_operator`` computes, made readable.

The contract these tests defend is that ``is_owner`` — not an empty
``temple_ids`` — is what distinguishes an unscoped owner from a scoped
operator. A client that reads "no temple ids" as "no temples" turns an owner
into someone who can see nothing, or worse, reads a scoped clerk as unscoped.
"""

import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.admin import operators as ops
from app.platform.db import Base, get_session

ADMIN = {"X-Admin-Token": "chargemod"}  # tests/conftest.py configures this


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


async def _signed_in(session, *, role: str, temple_id: str | None = None) -> dict:
    email = f"{role}@example.com"
    invite = await ops.invite(session, email=email, role=role, temple_id=temple_id)
    await ops.accept(session, token=invite.token, password="a-real-password")
    token = await ops.login(session, identifier=email, password="a-real-password")
    await session.commit()
    return {"Authorization": f"Bearer {token}"}


async def test_it_needs_a_credential(api):
    assert (await api.get("/admin/operators/me")).status_code == 401


async def test_any_role_may_ask_who_they_are(api, session):
    """Not owner-gated: a temple_admin needs this to render their own sidebar."""
    headers = await _signed_in(session, role="temple_admin", temple_id="tsr-guruvayur")
    r = await api.get("/admin/operators/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["roles"] == ["temple_admin"]
    assert body["temple_ids"] == ["tsr-guruvayur"]
    assert body["is_owner"] is False
    assert body["operator_id"] is not None


async def test_the_admin_token_is_an_owner_without_a_row(api):
    """An X-Admin-Token caller is a credential, not a row in `operators`, so
    `operator_id` is null while the role is still owner."""
    body = (await api.get("/admin/operators/me", headers=ADMIN)).json()
    assert body["is_owner"] is True
    assert body["roles"] == ["owner"]
    assert body["operator_id"] is None


async def test_an_owners_empty_temple_list_does_not_mean_no_temples(api):
    """The distinction a console must not collapse: an owner is UNSCOPED, and
    `temple_ids: []` alongside `is_owner: true` is what says so."""
    body = (await api.get("/admin/operators/me", headers=ADMIN)).json()
    assert body["temple_ids"] == []
    assert body["is_owner"] is True


async def test_a_content_reviewer_gets_no_temple_scope(api, session):
    headers = await _signed_in(session, role="content_reviewer")
    body = (await api.get("/admin/operators/me", headers=headers)).json()
    assert body["roles"] == ["content_reviewer"]
    assert body["temple_ids"] == []
    assert body["is_owner"] is False


async def test_a_revoked_session_stops_describing_itself(api, session):
    headers = await _signed_in(session, role="support")
    assert (await api.get("/admin/operators/me", headers=headers)).status_code == 200
    await api.post("/admin/operators/logout", headers=headers)
    assert (await api.get("/admin/operators/me", headers=headers)).status_code == 401


async def test_a_disabled_operator_stops_describing_itself(api, session):
    """Matches admin_auth._operator_from_session, which refuses an inactive
    operator — the console must not keep rendering a sidebar for someone whose
    access was withdrawn mid-session."""
    headers = await _signed_in(session, role="temple_admin", temple_id="tsr-guruvayur")
    operator_id = (await api.get("/admin/operators/me", headers=headers)).json()[
        "operator_id"
    ]
    r = await api.post(
        f"/admin/operators/{operator_id}/active", json={"active": False}, headers=ADMIN
    )
    assert r.status_code == 200
    assert (await api.get("/admin/operators/me", headers=headers)).status_code == 401


async def test_roles_and_temples_come_back_sorted(api, session):
    """Stable ordering so a console can compare without sorting first."""
    invite = await ops.invite(
        session, email="multi@example.com", role="temple_admin", temple_id="tsr-vadakkun"
    )
    created = await ops.accept(session, token=invite.token, password="a-real-password")
    await ops.grant(session, operator_id=created.id, role="temple_admin",
                    temple_id="tsr-guruvayur")
    await ops.grant(session, operator_id=created.id, role="content_reviewer")
    token = await ops.login(
        session, identifier="multi@example.com", password="a-real-password"
    )
    await session.commit()

    body = (
        await api.get(
            "/admin/operators/me", headers={"Authorization": f"Bearer {token}"}
        )
    ).json()
    assert body["roles"] == ["content_reviewer", "temple_admin"]
    assert body["temple_ids"] == ["tsr-guruvayur", "tsr-vadakkun"]
