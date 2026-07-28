"""One user's family board and chart, and the engagement aggregate (Part 12).

Three surfaces that did not exist for an operator at all:

  - **The family board was write-only from the app.** An operator taking a
    booking over the phone is told "book it for my mother, her star is Pooram",
    and had nowhere to put it until the devotee opened their own app.
  - **The chart had no operator door.** Answering a question about a reading
    meant reading the database.
  - **Every engagement figure was per-caller.** A devotee could see their own
    streak; nobody could see whether the feature worked at all.

Two of the three carry birth data, so the tests weight GUARDRAILS §4 as heavily
as the CRUD: a birth date may appear in one named user's detail and must never
reach a URL, a query string, a search result or any list of users. Asserting the
*absence* of a field is the only way that gets caught before it ships.
"""

from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.admin import operators as ops
from app.modules.admin.service import AdminService
from app.modules.bookings.models import PoojaBooking
from app.modules.community.models import UserCheckin
from app.modules.identity.models import Chart
from app.modules.identity.schemas import UserCreate
from app.modules.identity.service import IdentityService
from app.modules.temples.models import TempleVisit
from app.platform.db import Base, get_session

ADMIN = {"X-Admin-Token": "chargemod"}  # tests/conftest.py configures this
TODAY = date(2026, 7, 28)


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


async def _user(session, phone="+919812345678", name="Ananya Nair"):
    user = await IdentityService().create_user(
        session,
        UserCreate(
            name=name, phone=phone, password="a-real-password", dob=date(1990, 1, 1),
            tob="06:00", birth_place="Thrissur", lat=10.5, lng=76.2, tz="Asia/Kolkata",
        ),
    )
    await session.commit()
    return user


async def _temple_admin(session, email="clerk@example.com") -> dict:
    invite = await ops.invite(
        session, email=email, role="temple_admin", temple_id="tsr-guruvayur"
    )
    await ops.accept(session, token=invite.token, password="temple-pass-1")
    token = await ops.login(session, identifier=email, password="temple-pass-1")
    await session.commit()
    return {"Authorization": f"Bearer {token}"}


# ---- the gate ----


async def test_family_and_chart_are_owner_only(api, session):
    user = await _user(session)
    headers = await _temple_admin(session)
    for path in (f"/admin/users/{user.id}/family", f"/admin/users/{user.id}/chart"):
        assert (await api.get(path)).status_code == 401
        assert (await api.get(path, headers=headers)).status_code == 403
    assert (await api.get("/admin/engagement")).status_code == 401
    assert (await api.get("/admin/engagement", headers=headers)).status_code == 403


# ---- the family board ----


async def test_the_board_starts_with_the_account_holders_own_row(api, session):
    user = await _user(session)
    rows = (await api.get(f"/admin/users/{user.id}/family", headers=ADMIN)).json()
    assert [(m["name"], m["rel"], m["self"]) for m in rows] == [
        ("Ananya Nair", "rSelf", True)
    ]


async def test_an_operator_can_add_a_relative_mid_call(api, session):
    """The whole point of the write half: this is what someone is told on the
    phone, and the devotee's own app is no use at that moment."""
    user = await _user(session)
    added = await api.post(
        f"/admin/users/{user.id}/family",
        json={"name": "Sarada", "rel": "rMother", "nak": 10, "dob": "1961-04-12"},
        headers=ADMIN,
    )
    assert added.status_code == 201
    assert added.json()["nak"] == 10
    assert added.json()["dob"] == "1961-04-12"

    rows = (await api.get(f"/admin/users/{user.id}/family", headers=ADMIN)).json()
    assert [m["name"] for m in rows] == ["Ananya Nair", "Sarada"]


async def test_a_birth_date_is_stored_as_a_date_not_an_age(api, session):
    """An age is right for one year and silently wrong after it, and this is the
    field a star-day reminder would be computed from."""
    user = await _user(session)
    added = await api.post(
        f"/admin/users/{user.id}/family",
        json={"name": "Sarada", "rel": "rMother", "age": 65},
        headers=ADMIN,
    )
    assert added.status_code == 201
    assert "age" not in added.json()
    assert added.json()["dob"] is None


async def test_a_star_or_a_birth_date_can_be_corrected_to_unknown(api, session):
    """`null` is a real answer — "we asked and they do not know" — and it must be
    distinguishable from leaving the field out of the payload."""
    user = await _user(session)
    member = (
        await api.post(
            f"/admin/users/{user.id}/family",
            json={"name": "Sarada", "rel": "rMother", "nak": 10, "dob": "1961-04-12"},
            headers=ADMIN,
        )
    ).json()

    # Changing only the name leaves both alone.
    renamed = await api.patch(
        f"/admin/users/{user.id}/family/{member['id']}",
        json={"name": "Sarada Amma"},
        headers=ADMIN,
    )
    assert (renamed.json()["nak"], renamed.json()["dob"]) == (10, "1961-04-12")

    cleared = await api.patch(
        f"/admin/users/{user.id}/family/{member['id']}",
        json={"nak": None, "dob": None},
        headers=ADMIN,
    )
    assert (cleared.json()["nak"], cleared.json()["dob"]) == (None, None)


async def test_the_account_holders_own_row_cannot_be_removed(api, session):
    """It is the row a booking defaults to; deleting it would leave the account
    unable to book for itself."""
    user = await _user(session)
    rows = (await api.get(f"/admin/users/{user.id}/family", headers=ADMIN)).json()
    self_row = next(m for m in rows if m["self"])
    r = await api.delete(
        f"/admin/users/{user.id}/family/{self_row['id']}", headers=ADMIN
    )
    assert r.status_code == 422


async def test_a_relative_can_be_removed(api, session):
    user = await _user(session)
    member = (
        await api.post(
            f"/admin/users/{user.id}/family",
            json={"name": "Sarada", "rel": "rMother"},
            headers=ADMIN,
        )
    ).json()
    assert (
        await api.delete(f"/admin/users/{user.id}/family/{member['id']}", headers=ADMIN)
    ).status_code == 204
    assert (
        await api.delete(f"/admin/users/{user.id}/family/{member['id']}", headers=ADMIN)
    ).status_code == 404


async def test_one_users_board_is_not_reachable_through_another(api, session):
    """The member id is a global sequence, so the user id in the path has to be
    part of the lookup and not decoration."""
    mine = await _user(session)
    theirs = await _user(session, phone="+919812345679", name="Other")
    member = (
        await api.post(
            f"/admin/users/{theirs.id}/family",
            json={"name": "Their mother", "rel": "rMother"},
            headers=ADMIN,
        )
    ).json()

    r = await api.patch(
        f"/admin/users/{mine.id}/family/{member['id']}",
        json={"name": "Hijacked"},
        headers=ADMIN,
    )
    assert r.status_code == 404


async def test_the_board_is_full_at_the_limit(api, session):
    user = await _user(session)
    for i in range(IdentityService.MEMBER_LIMIT):
        await api.post(
            f"/admin/users/{user.id}/family",
            json={"name": f"Relative {i}", "rel": "rOther"},
            headers=ADMIN,
        )
    r = await api.post(
        f"/admin/users/{user.id}/family",
        json={"name": "One too many", "rel": "rOther"},
        headers=ADMIN,
    )
    assert r.status_code == 422


async def test_adding_to_an_unknown_user_is_404_not_a_stray_row(api, session):
    r = await api.post(
        "/admin/users/9999/family", json={"name": "Nobody"}, headers=ADMIN
    )
    assert r.status_code == 404


# ---- GUARDRAILS §4 ----


async def test_a_family_birth_date_never_reaches_a_list_of_users(api, session):
    """The board may be read for one named user. It must not turn up in the
    register, which is a search result and therefore a much wider surface."""
    user = await _user(session)
    await api.post(
        f"/admin/users/{user.id}/family",
        json={"name": "Sarada", "rel": "rMother", "dob": "1961-04-12"},
        headers=ADMIN,
    )
    listing = (await api.get("/admin/users", headers=ADMIN)).text
    assert "1961-04-12" not in listing
    assert "family" not in listing


async def test_no_route_takes_a_birth_date_as_a_query_string(api, session):
    """§4's other half. Searching by birth detail is not offered anywhere, and
    a filter that looked harmless would put a date of birth in an access log."""
    await _user(session)
    body = (await api.get("/admin/users?q=1990-01-01", headers=ADMIN)).json()
    assert body["total"] == 0  # matched against name and phone only


async def test_the_engagement_page_carries_no_birth_data(api, session):
    user = await _user(session)
    session.add(UserCheckin(user_id=user.id, day=TODAY))
    await session.commit()
    text = (await api.get("/admin/engagement", headers=ADMIN)).text
    assert "1990-01-01" not in text
    assert "Thrissur" not in text


# ---- the chart ----


async def test_the_chart_is_served_for_one_named_user_only(api, session):
    user = await _user(session)
    session.add(
        Chart(user_id=user.id, natal_json={"lagna": "Simha"}, computed_at=datetime.now(UTC))
    )
    await session.commit()

    r = await api.get(f"/admin/users/{user.id}/chart", headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["natal"] == {"lagna": "Simha"}


async def test_a_user_with_no_chart_says_so_rather_than_returning_nothing(api, session):
    user = await _user(session)
    r = await api.get(f"/admin/users/{user.id}/chart", headers=ADMIN)
    assert r.status_code == 404
    assert "No chart" in r.json()["detail"]


async def test_a_chart_for_an_unknown_user_is_404(api):
    assert (await api.get("/admin/users/9999/chart", headers=ADMIN)).status_code == 404


# ---- engagement ----


async def test_engagement_counts_checkins_streaks_and_badges(api, session):
    keen = await _user(session, phone="+919000000001", name="Keen")
    lapsed = await _user(session, phone="+919000000002", name="Lapsed")

    # Three consecutive days ending today: a live streak of 3.
    for back in range(3):
        session.add(UserCheckin(user_id=keen.id, day=TODAY - timedelta(days=back)))
    # A check-in a fortnight ago: counted, but the streak is broken.
    session.add(UserCheckin(user_id=lapsed.id, day=TODAY - timedelta(days=14)))
    session.add(TempleVisit(user_id=keen.id, temple_id="tsr-guruvayur", day=TODAY))
    session.add(
        PoojaBooking(
            user_id=keen.id, ref="NT000001", temple_id="tsr-guruvayur",
            pooja_key="archana", pooja_name="Archana", amount_paise=5100,
            service_fee_paise=1500, member_name="Keen", when_label="today", state="ok",
        )
    )
    await session.commit()

    body = await AdminService().engagement(session, today=TODAY)

    assert body["checkins"]["total"] == 4
    assert body["checkins"]["users_ever"] == 2
    assert body["checkins"]["users_on_a_streak"] == 1
    assert body["checkins"]["checked_in_today"] == 1

    top = body["most_engaged"][0]
    assert (top["name"], top["streak"], top["checkins"]) == ("Keen", 3, 3)
    assert (top["temples_visited"], top["poojas"]) == (1, 1)

    unlocked = {m["key"]: m["unlocked"] for m in body["milestones"]}
    assert unlocked["first_temple"] == 1
    assert unlocked["first_pooja"] == 1
    assert unlocked["ten_temples"] == 0


async def test_a_user_with_no_activity_is_a_zero_not_an_omission(api, session):
    """A quiet devotee is still a devotee. Dropping them would make
    "users_ever" and the register disagree with no way to tell why."""
    await _user(session, phone="+919000000003", name="Quiet")
    body = await AdminService().engagement(session, today=TODAY)
    assert body["users_counted"] == 1
    assert body["checkins"]["users_ever"] == 0
    assert body["most_engaged"][0]["streak"] == 0


async def test_engagement_says_when_it_is_showing_a_sample(api, session):
    await _user(session, phone="+919000000004")
    body = await AdminService().engagement(session, today=TODAY)
    assert body["truncated"] is False
    assert body["users_total"] == body["users_counted"] == 1


async def test_every_streak_is_measured_against_one_instant(api, session):
    """A run that straddled midnight would otherwise credit some users a day the
    rest did not get, and the leaderboard would reorder for no reason."""
    a = await _user(session, phone="+919000000005", name="A")
    b = await _user(session, phone="+919000000006", name="B")
    for user in (a, b):
        session.add(UserCheckin(user_id=user.id, day=TODAY))
    await session.commit()

    body = await AdminService().engagement(session, today=TODAY)
    assert {r["streak"] for r in body["most_engaged"]} == {1}
    # The day after, with nobody checking in, both have lapsed together.
    later = await AdminService().engagement(session, today=TODAY + timedelta(days=2))
    assert {r["streak"] for r in later["most_engaged"]} == {0}


async def test_the_leaderboard_is_bounded(api, session):
    for i in range(5):
        await _user(session, phone=f"+91900000010{i}", name=f"User {i}")
    body = await AdminService().engagement(session, limit=2, today=TODAY)
    assert len(body["most_engaged"]) == 2
    assert body["users_counted"] == 5


@pytest.mark.parametrize("limit", [0, 500])
async def test_the_engagement_route_bounds_its_own_limit(api, limit):
    r = await api.get(f"/admin/engagement?limit={limit}", headers=ADMIN)
    assert r.status_code == 422
