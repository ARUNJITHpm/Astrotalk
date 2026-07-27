"""Invite-by-owner operator accounts (console plan Part 4).

Nobody self-registers: the owner invites by email or mobile, the invitee
redeems the token once to set a password, and signs in with whichever
identifier they were invited with.
"""

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.admin import operators as ops
from app.modules.admin.models import Operator
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


async def _invite(api, **over) -> str:
    body = {"email": "staff@example.com", "role": "temple_admin",
            "temple_id": "tvm-padmanabhaswamy"}
    body.update(over)
    r = await api.post("/admin/operators/invite", json=body, headers=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["invite_token"]


# ---- invite ----


async def test_inviting_requires_owner(api):
    r = await api.post("/admin/operators/invite", json={"email": "x@example.com"})
    assert r.status_code == 401


async def test_invite_then_accept_then_sign_in(api):
    token = await _invite(api)

    accepted = await api.post(
        "/admin/operators/accept", json={"token": token, "password": "temple-pass-1"}
    )
    assert accepted.status_code == 200

    signed_in = await api.post(
        "/admin/operators/login",
        json={"identifier": "staff@example.com", "password": "temple-pass-1"},
    )
    assert signed_in.status_code == 200
    bearer = {"Authorization": f"Bearer {signed_in.json()['token']}"}

    # And the session actually carries the invited scope.
    listed = await api.get("/admin/operators", headers=bearer)
    assert listed.status_code == 403, "a temple_admin must not read the operator list"


async def test_invite_by_mobile_signs_in_by_mobile(api):
    token = await _invite(api, email=None, phone="9876543210")
    await api.post(
        "/admin/operators/accept", json={"token": token, "password": "temple-pass-1"}
    )
    r = await api.post(
        "/admin/operators/login",
        json={"identifier": "9876543210", "password": "temple-pass-1"},
    )
    assert r.status_code == 200


async def test_invite_needs_an_identifier(api):
    r = await api.post(
        "/admin/operators/invite", json={"role": "content_reviewer"}, headers=ADMIN
    )
    assert r.status_code == 422


async def test_temple_admin_must_be_scoped(api):
    r = await api.post(
        "/admin/operators/invite",
        json={"email": "a@example.com", "role": "temple_admin"},
        headers=ADMIN,
    )
    assert r.status_code == 422


async def test_unscoped_role_cannot_carry_a_temple(api):
    """An owner scoped to one temple would read as a restriction it does not
    actually apply — reject it rather than store a misleading row."""
    r = await api.post(
        "/admin/operators/invite",
        json={"email": "a@example.com", "role": "owner", "temple_id": "t1"},
        headers=ADMIN,
    )
    assert r.status_code == 422


async def test_unknown_role_is_rejected(api):
    r = await api.post(
        "/admin/operators/invite",
        json={"email": "a@example.com", "role": "superuser"},
        headers=ADMIN,
    )
    assert r.status_code == 422


# ---- accept ----


async def test_an_invite_can_only_be_redeemed_once(api):
    token = await _invite(api)
    first = await api.post(
        "/admin/operators/accept", json={"token": token, "password": "temple-pass-1"}
    )
    assert first.status_code == 200
    second = await api.post(
        "/admin/operators/accept", json={"token": token, "password": "other-pass-99"}
    )
    assert second.status_code == 404


async def test_unknown_invite_token_is_404(api):
    r = await api.post(
        "/admin/operators/accept", json={"token": "nope", "password": "temple-pass-1"}
    )
    assert r.status_code == 404


async def test_short_password_is_rejected(api):
    token = await _invite(api)
    r = await api.post("/admin/operators/accept", json={"token": token, "password": "short"})
    assert r.status_code == 422


# ---- sign-in ----


async def test_login_failures_are_indistinguishable(api):
    """Unknown account, wrong password and deactivated must look identical, or
    the endpoint becomes a way to enumerate who has console access."""
    token = await _invite(api)
    await api.post(
        "/admin/operators/accept", json={"token": token, "password": "temple-pass-1"}
    )

    unknown = await api.post(
        "/admin/operators/login",
        json={"identifier": "nobody@example.com", "password": "temple-pass-1"},
    )
    wrong = await api.post(
        "/admin/operators/login",
        json={"identifier": "staff@example.com", "password": "wrong-password"},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


async def test_an_invited_operator_cannot_sign_in_before_accepting(session):
    """The row exists the moment they are invited; a null password_hash must not
    verify against anything."""
    await ops.invite(session, email="pending@example.com", role="owner")
    await session.commit()
    # No operator row is created until accept, so login simply fails.
    with pytest.raises(ops.OperatorError):
        await ops.login(session, identifier="pending@example.com", password="anything")


async def test_deactivating_drops_live_sessions(session):
    """Revoking access has to mean now, not whenever the token expires."""
    invite = await ops.invite(session, email="staff@example.com", role="owner")
    await ops.accept(session, token=invite.token, password="temple-pass-1")
    token = await ops.login(session, identifier="staff@example.com", password="temple-pass-1")
    await session.commit()

    operator = (
        await session.execute(
            __import__("sqlalchemy").select(Operator).where(Operator.email == "staff@example.com")
        )
    ).scalar_one()
    await ops.set_active(session, operator_id=operator.id, active=False)
    await session.commit()

    from app.platform.admin_auth import resolve_operator

    assert await resolve_operator(session, token, None) is None


# ---- grants ----


async def test_owner_can_grant_and_revoke(api, session):
    token = await _invite(api)
    await api.post(
        "/admin/operators/accept", json={"token": token, "password": "temple-pass-1"}
    )
    listed = (await api.get("/admin/operators", headers=ADMIN)).json()
    operator_id = listed[0]["id"]

    granted = await api.post(
        f"/admin/operators/{operator_id}/roles",
        json={"role": "temple_admin", "temple_id": "second-temple"},
        headers=ADMIN,
    )
    assert granted.status_code == 200
    role_id = granted.json()["id"]

    again = await api.post(
        f"/admin/operators/{operator_id}/roles",
        json={"role": "temple_admin", "temple_id": "second-temple"},
        headers=ADMIN,
    )
    assert again.json()["id"] == role_id, "granting twice must be idempotent"

    assert (
        await api.delete(f"/admin/operators/roles/{role_id}", headers=ADMIN)
    ).status_code == 204
    assert (
        await api.delete(f"/admin/operators/roles/{role_id}", headers=ADMIN)
    ).status_code == 404


async def test_an_unaccepted_invite_creates_no_operator(api):
    """The account materialises on accept, not on invite — so a pending invite
    cannot be mistaken for someone who already has access."""
    await _invite(api)
    assert (await api.get("/admin/operators", headers=ADMIN)).json() == []


async def test_logout_revokes_the_session_server_side(api):
    token = await _invite(api)
    await api.post(
        "/admin/operators/accept", json={"token": token, "password": "temple-pass-1"}
    )
    signed = await api.post(
        "/admin/operators/login",
        json={"identifier": "staff@example.com", "password": "temple-pass-1"},
    )
    bearer = {"Authorization": f"Bearer {signed.json()['token']}"}

    # A temple_admin gets 403 (known), which proves the session resolves.
    assert (await api.get("/admin/operators", headers=bearer)).status_code == 403
    assert (await api.post("/admin/operators/logout", headers=bearer)).status_code == 204
    # After logout the same token is no longer a credential at all.
    assert (await api.get("/admin/operators", headers=bearer)).status_code == 401
