"""The WAHA operator endpoints must not answer anonymous callers.

/waha-qr returns the pairing QR and session details for the WhatsApp account —
enough for a stranger to attach their own device to it — and /waha-status leaks
the connected number. Both shipped unguarded despite "for admin" docstrings, so
these tests pin the guard in place.
"""

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.whatsapp import router as wa_router
from app.platform.db import Base, get_session

_PATHS = ("/whatsapp/waha-status", "/whatsapp/waha-qr")


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


@pytest.mark.asyncio
async def test_waha_endpoints_require_admin(session, monkeypatch):
    # Stub the upstream calls: we are testing the gate, not WAHA itself, and an
    # unauthenticated request must never reach the network in the first place.
    called: list[str] = []

    async def _status() -> dict:
        called.append("status")
        return {"connected": True}

    async def _qr() -> dict:
        called.append("qr")
        return {"qr": "data:image/png;base64,..."}

    monkeypatch.setattr(wa_router._service, "waha_status", _status)
    monkeypatch.setattr(wa_router._waha, "get_qr", _qr)

    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for path in _PATHS:
                assert (await client.get(path)).status_code == 401
                assert (
                    await client.get(path, headers={"X-Admin-Token": "wrong"})
                ).status_code == 401
            assert called == [], "upstream was called for an unauthenticated request"

            for path in _PATHS:
                ok = await client.get(path, headers={"X-Admin-Token": "chargemod"})
                assert ok.status_code == 200
            assert called == ["status", "qr"]
    finally:
        main_app.dependency_overrides.pop(get_session, None)
