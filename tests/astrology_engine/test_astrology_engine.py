"""Tests for astrology_engine's mock (MOCK_EPHEMERIS) path.

Hermetic: `_force_mock` pins the ephemeris mock ON regardless of the local `.env`
(which now runs the real Swiss Ephemeris), so these mock-shape tests are stable.
The real engine is covered separately in test_swiss_ephemeris.py.
"""

from datetime import date, datetime, time

import httpx
import pytest
from httpx import ASGITransport

from app.modules.astrology_engine.service import AstrologyEngineService
from app.platform.config import get_settings

_DOB = date(1995, 4, 12)


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch):
    # Fresh services built inside a test read this patched setting.
    monkeypatch.setattr(get_settings(), "mock_ephemeris", True)
    # The router holds a module-level service built at import from the real .env,
    # so flip its already-constructed client to mock too.
    import app.modules.astrology_engine.router as r

    monkeypatch.setattr(r._service._client, "_mock", True)


async def test_compute_natal_chart_shape_and_mock_flag():
    chart = await AstrologyEngineService().compute_natal_chart(
        dob=_DOB, birth_time=time(6, 30), lat=10.5, lng=76.2, tz="Asia/Kolkata"
    )

    assert chart["mock"] is True
    assert chart["source"] == "mock-ephemeris"
    assert chart["nakshatram"]
    assert chart["rasi"] and chart["lagnam"]
    # All nine grahas present, each with a rasi and house.
    assert len(chart["planets"]) == 9
    assert {"rasi", "house", "retrograde"} <= chart["planets"]["chandra"].keys()


async def test_natal_chart_is_deterministic():
    svc = AstrologyEngineService()
    args = dict(dob=_DOB, birth_time=time(6, 30), lat=10.5, lng=76.2, tz="Asia/Kolkata")
    first = await svc.compute_natal_chart(**args)
    second = await svc.compute_natal_chart(**args)
    assert first == second


async def test_panchangam_has_required_fields():
    p = await AstrologyEngineService().get_panchangam(date(2026, 6, 25))

    assert p["date"] == "2026-06-25"
    assert p["nakshatram"]
    assert p["nalla_neram"]
    assert p["tithi"]
    assert p["mock"] is True
    # Same day -> identical panchangam.
    again = await AstrologyEngineService().get_panchangam(date(2026, 6, 25))
    assert p == again


async def test_get_transits_shape():
    t = await AstrologyEngineService().get_transits(datetime(2026, 6, 25, 9, 0))

    assert t["mock"] is True
    assert len(t["transits"]) == 9
    assert "rasi" in next(iter(t["transits"].values()))


@pytest.fixture
def client():
    from app.main import app

    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_router_transits_and_panchangam(client):
    async with client:
        transits = await client.get("/astrology/transits", params={"at": "2026-06-25T09:00:00"})
        assert transits.status_code == 200, transits.text
        assert transits.json()["mock"] is True

        panchangam = await client.get("/astrology/panchangam", params={"day": "2026-06-25"})
        assert panchangam.status_code == 200, panchangam.text
        body = panchangam.json()
        assert body["date"] == "2026-06-25"
        assert body["nakshatram"] and body["nalla_neram"] and body["tithi"]
