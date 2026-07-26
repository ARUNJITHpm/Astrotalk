"""The role-aware operator guard (console plan Part 4).

Covers the three credentials, the role and scope checks, and two regressions
worth pinning permanently:

  1. an unset ``admin_token`` must authenticate NOBODY — it used to fall back to
     the hardcoded literal "chargemod";
  2. ``require_cron_or_admin`` must actually verify the caller. It used to pass
     the admin token into ``require_admin``'s *session* parameter, so it could
     never authorise anyone; when ``require_admin`` became a pure dependency the
     very same call began returning None for everyone, opening the cron
     endpoints to the public.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.modules.identity.models  # noqa: F401  — registers `sessions` on Base.metadata
from app.modules.admin.models import Operator as OperatorRow
from app.modules.admin.models import OperatorRole, OperatorSession
from app.platform.admin_auth import Operator, require_operator
from app.platform.config import get_settings
from app.platform.cron_auth import CronOrAdminGuard
from app.platform.db import Base, get_session

ADMIN = {"X-Admin-Token": "chargemod"}

# Hoisted out of the signatures below: ruff B008 forbids calling Depends() in an
# argument default, and FastAPI is happy with a module-level singleton.
AnyOperator = Depends(require_operator())
OwnerOnly = Depends(require_operator("owner"))
TempleOrOwner = Depends(require_operator("owner", "temple_admin"))


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
    app = FastAPI()

    @app.get("/any")
    async def any_operator(op=AnyOperator) -> dict:
        return {"roles": sorted(op.roles), "temples": sorted(op.temple_ids)}

    @app.get("/owner-only")
    async def owner_only(op=OwnerOnly) -> dict:
        return {"ok": True}

    @app.get("/temples-or-owner")
    async def temples(op=TempleOrOwner) -> dict:
        return {"visible": None if op.visible_temple_ids() is None else sorted(op.temple_ids)}

    @app.post("/cron-thing", dependencies=[CronOrAdminGuard])
    async def cron_thing() -> dict:
        return {"ran": True}

    app.dependency_overrides[get_session] = lambda: session
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _operator(session, *grants, active=True) -> str:
    """Create an operator with the given (role, temple_id) grants → token."""
    row = OperatorRow(email="staff@example.com", name="Staff", active=active)
    session.add(row)
    await session.flush()
    for role, temple_id in grants:
        session.add(OperatorRole(operator_id=row.id, role=role, temple_id=temple_id))
    token = f"tok-{row.id}"
    session.add(OperatorSession(
        token=token, operator_id=row.id,
        expires_at=datetime.now(UTC) + timedelta(hours=8),
    ))
    await session.commit()
    return token


# ---- credentials ----


async def test_no_credential_is_401(api):
    assert (await api.get("/any")).status_code == 401


async def test_admin_token_is_a_full_owner(api):
    r = await api.get("/owner-only", headers=ADMIN)
    assert r.status_code == 200


async def test_unset_admin_token_authenticates_nobody(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_token", "")
    for header in ({"X-Admin-Token": "chargemod"}, {"X-Admin-Token": ""}, {}):
        assert (await api.get("/any", headers=header)).status_code == 401


async def test_operator_session_carries_its_roles(api, session):
    token = await _operator(session, ("temple_admin", "t1"), ("temple_admin", "t2"))
    r = await api.get("/any", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"roles": ["temple_admin"], "temples": ["t1", "t2"]}


async def test_deactivated_operator_is_rejected(api, session):
    token = await _operator(session, ("owner", None), active=False)
    auth = {"Authorization": f"Bearer {token}"}
    assert (await api.get("/any", headers=auth)).status_code == 401


async def test_expired_session_is_rejected(api, session):
    row = OperatorRow(email="x@example.com")
    session.add(row)
    await session.flush()
    session.add(OperatorSession(
        token="stale", operator_id=row.id,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    ))
    await session.commit()
    assert (await api.get("/any", headers={"Authorization": "Bearer stale"})).status_code == 401


# ---- roles and scope ----


async def test_wrong_role_is_403_not_401(api, session):
    """401 means "we do not know you", 403 means "we do and the answer is no".
    A console needs the difference to tell a re-login from a permission wall."""
    token = await _operator(session, ("temple_admin", "t1"))
    auth = {"Authorization": f"Bearer {token}"}
    assert (await api.get("/owner-only", headers=auth)).status_code == 403


async def test_owner_satisfies_every_role(api, session):
    token = await _operator(session, ("owner", None))
    for path in ("/any", "/owner-only", "/temples-or-owner"):
        r = await api.get(path, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, path


async def test_scope_limits_a_temple_admin(api, session):
    token = await _operator(session, ("temple_admin", "t1"))
    r = await api.get("/temples-or-owner", headers={"Authorization": f"Bearer {token}"})
    assert r.json() == {"visible": ["t1"]}


async def test_owner_visibility_is_unrestricted_not_empty(api):
    """None means "all temples", an empty set means "none". Confusing the two
    turns a scoped operator into an unscoped one, or hides everything."""
    r = await api.get("/temples-or-owner", headers=ADMIN)
    assert r.json() == {"visible": None}


def test_can_edit_temple_honours_scope():
    scoped = Operator(
        operator_id=1, roles=frozenset({"temple_admin"}), temple_ids=frozenset({"t1"})
    )
    assert scoped.can_edit_temple("t1") is True
    assert scoped.can_edit_temple("t2") is False
    assert scoped.visible_temple_ids() == frozenset({"t1"})

    owner = Operator(operator_id=None, roles=frozenset({"owner"}), temple_ids=frozenset())
    assert owner.can_edit_temple("anything") is True
    assert owner.visible_temple_ids() is None


def test_require_temple_raises_403():
    from fastapi import HTTPException

    scoped = Operator(
        operator_id=1, roles=frozenset({"temple_admin"}), temple_ids=frozenset({"t1"})
    )
    scoped.require_temple("t1")  # no raise
    with pytest.raises(HTTPException) as exc:
        scoped.require_temple("t2")
    assert exc.value.status_code == 403


# ---- the cron-or-admin regression ----


async def test_cron_or_admin_rejects_anonymous(api, monkeypatch):
    """This is the regression. It must never return 200 without a credential."""
    monkeypatch.setattr(get_settings(), "cron_token", "cron-secret")
    assert (await api.post("/cron-thing")).status_code == 401
    bad = {"X-Cron-Token": "wrong"}
    assert (await api.post("/cron-thing", headers=bad)).status_code == 401


async def test_cron_or_admin_accepts_either_credential(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "cron_token", "cron-secret")
    cron = {"X-Cron-Token": "cron-secret"}
    assert (await api.post("/cron-thing", headers=cron)).status_code == 200
    # The admin token path is the one that never actually worked before.
    assert (await api.post("/cron-thing", headers=ADMIN)).status_code == 200
