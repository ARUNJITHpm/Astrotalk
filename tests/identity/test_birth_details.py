"""Setting birth details on an account that already exists.

The gap this closes: Nithara's accounts start anonymous (`POST /identity/anon`),
and the only writer of `dob`/`birth_time`/`birth_place` was the signup form,
which an anonymous account never sees. So the app could READ a chart it had no
way to create, and the profile screen said "coming soon" because there was
genuinely nothing to show.

Most of what follows is about GUARDRAILS §4 — birth data belongs in a body, in
one account's own request, and nowhere else.
"""

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.platform.config import get_settings
from app.platform.db import Base, get_session


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
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


@pytest_asyncio.fixture
async def api(session):
    main_app.dependency_overrides[get_session] = lambda: session
    try:
        transport = ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        main_app.dependency_overrides.clear()


async def _anon(api) -> tuple[dict, int]:
    """An anonymous session — how every Nithara account starts."""
    res = await api.post("/identity/anon", json={})
    body = res.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


DETAILS = {"dob": "1990-04-12", "birth_time": "06:30", "birth_place": "Thrissur"}


async def test_an_anonymous_account_can_get_a_chart(api):
    """The whole point. Before this, an anon account had no route to one."""
    auth, user_id = await _anon(api)
    assert (await api.get(f"/identity/users/{user_id}/chart", headers=auth)).status_code == 404

    res = await api.put("/identity/me/birth", json=DETAILS, headers=auth)
    assert res.status_code == 200
    chart = res.json()
    assert chart["user_id"] == user_id
    assert chart["natal_json"]["nakshatram"]

    # And it is readable afterwards, which is what the profile screen does.
    assert (await api.get(f"/identity/users/{user_id}/chart", headers=auth)).status_code == 200


async def test_the_details_are_stored_not_just_used(api):
    """A chart computed and thrown away would look identical here and break the
    moment anything recomputed — the star-day reminders, a re-geocode."""
    auth, user_id = await _anon(api)
    await api.put("/identity/me/birth", json=DETAILS, headers=auth)

    me = (await api.get(f"/identity/users/{user_id}", headers=auth)).json()
    assert me["dob"] == "1990-04-12"
    assert me["birth_place"] == "Thrissur"


async def test_a_birth_time_is_optional_and_stays_optional(api):
    """Plenty of people know the day and not the hour. Demanding a time would
    make them guess one, and a guessed hour is a confidently wrong lagna —
    worse than an honestly narrowed reading."""
    auth, _ = await _anon(api)
    res = await api.put(
        "/identity/me/birth",
        json={"dob": "1990-04-12", "birth_place": "Thrissur"},
        headers=auth,
    )
    assert res.status_code == 200


async def test_it_needs_a_session(api):
    assert (await api.put("/identity/me/birth", json=DETAILS)).status_code == 401


async def test_one_account_cannot_write_another_account_s_birth_data(api):
    """The account comes from the token, never from the payload. A `user_id` in
    the body must not move the write — this is the same rule /users/{id}
    enforces for reads, and it has to hold on the way in too."""
    victim_auth, victim_id = await _anon(api)
    await api.put("/identity/me/birth", json=DETAILS, headers=victim_auth)

    attacker_auth, attacker_id = await _anon(api)
    assert attacker_id != victim_id
    await api.put(
        "/identity/me/birth",
        json={**DETAILS, "dob": "1975-01-01", "user_id": victim_id},
        headers=attacker_auth,
    )

    victim = (await api.get(f"/identity/users/{victim_id}", headers=victim_auth)).json()
    assert victim["dob"] == "1990-04-12"  # untouched


async def test_birth_data_never_reaches_the_url(api):
    """GUARDRAILS §4. The route takes a body precisely so a date of birth is not
    written into every access log between the phone and the server."""
    auth, _ = await _anon(api)
    res = await api.put(
        "/identity/me/birth?dob=1990-04-12&birth_place=Thrissur", headers=auth
    )
    # Query params carry nothing here — the body is required, so this is a 422.
    assert res.status_code == 422


async def test_correcting_the_details_recomputes_the_chart(api):
    """Somebody mistypes a year, or finally finds their birth certificate."""
    auth, user_id = await _anon(api)
    first = (await api.put("/identity/me/birth", json=DETAILS, headers=auth)).json()

    second = (
        await api.put(
            "/identity/me/birth",
            json={**DETAILS, "dob": "1991-09-02"},
            headers=auth,
        )
    ).json()
    assert second["id"] != first["id"]

    # The read returns the corrected one, not the stale first chart.
    latest = (await api.get(f"/identity/users/{user_id}/chart", headers=auth)).json()
    assert latest["id"] == second["id"]


async def test_the_chart_is_readable_without_putting_an_id_in_the_url(api):
    """`/me/chart` exists so the client never has to know or send its own user
    id. The session already says who is asking and cannot be spoofed; an id in
    the path is an account identifier in every access log for no gain."""
    auth, _ = await _anon(api)
    assert (await api.get("/identity/me/chart", headers=auth)).status_code == 404

    await api.put("/identity/me/birth", json=DETAILS, headers=auth)
    res = await api.get("/identity/me/chart", headers=auth)
    assert res.status_code == 200
    assert res.json()["natal_json"]["nakshatram"]


async def test_an_account_can_read_back_its_own_details_to_correct_them(api):
    """Otherwise fixing a typo in the year means retyping all three fields."""
    auth, _ = await _anon(api)
    await api.put("/identity/me/birth", json=DETAILS, headers=auth)

    res = await api.get("/identity/me/birth", headers=auth)
    assert res.status_code == 200
    body = res.json()
    assert body["dob"] == "1990-04-12"
    assert body["birth_place"] == "Thrissur"
    # The three fields and nothing derived — no coordinates, no timezone.
    assert set(body) == {"dob", "birth_time", "birth_place"}


async def test_birth_reads_need_a_session_too(api):
    assert (await api.get("/identity/me/birth")).status_code == 401
    assert (await api.get("/identity/me/chart")).status_code == 401
