"""Users, payments, entitlements and the app feed (console plan Part 8).

Three surfaces, one theme: things that existed as data but had no operator
route. A user who never chatted was invisible. `granted_by="admin"` was a
declared value nothing could produce. The feed was a Python literal whose own
docstring said the CRUD would come later.

Two rules get more attention than the CRUD itself, because they are the ones
that quietly rot:

  - **GUARDRAILS §4** — birth data never reaches a URL, a query string or a
    list response. Tests assert the *absence* of fields, which is the only way
    a leak gets caught before it ships.
  - **GUARDRAILS §1/§4 for the feed** — a card must say whose words it carries,
    and nobody may type in an engagement count.
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
from app.modules.commerce.models import Entitlement, Payment
from app.modules.content import feed
from app.modules.identity.schemas import UserCreate
from app.modules.identity.service import IdentityService
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


@pytest.fixture(autouse=True)
def _clean_feed():
    feed.reset()
    yield
    feed.reset()


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


async def _reviewer(session, email="reviewer@example.com") -> dict:
    invite = await ops.invite(session, email=email, role="content_reviewer")
    await ops.accept(session, token=invite.token, password="temple-pass-1")
    token = await ops.login(session, identifier=email, password="temple-pass-1")
    await session.commit()
    return {"Authorization": f"Bearer {token}"}


async def _temple_admin(session, email="clerk@example.com") -> dict:
    invite = await ops.invite(
        session, email=email, role="temple_admin", temple_id="tsr-guruvayur"
    )
    await ops.accept(session, token=invite.token, password="temple-pass-1")
    token = await ops.login(session, identifier=email, password="temple-pass-1")
    await session.commit()
    return {"Authorization": f"Bearer {token}"}


# ---- users ----


async def test_the_user_register_refuses_anyone_but_an_owner(api, session):
    assert (await api.get("/admin/users")).status_code == 401
    headers = await _temple_admin(session)
    assert (await api.get("/admin/users", headers=headers)).status_code == 403


async def test_a_user_who_never_chatted_is_still_visible(api, session):
    """The only operator view was /admin/users-chats, which lists people with
    chat history — someone who signed up and never chatted did not exist."""
    await _user(session)
    body = (await api.get("/admin/users", headers=ADMIN)).json()
    assert body["total"] == 1
    assert body["items"][0]["phone"] == "+919812345678"


async def test_the_user_list_carries_no_birth_data(api, session):
    """GUARDRAILS §4. Asserting absence is the only way a leak is caught before
    it ships — a new field added to the row shape would otherwise sail through."""
    await _user(session)
    row = (await api.get("/admin/users", headers=ADMIN)).json()["items"][0]
    assert not {"dob", "birth_time", "birth_place", "lat", "lng"} & set(row)


async def test_search_matches_name_or_mobile(api, session):
    await _user(session, phone="+919812345678", name="Ananya Nair")
    await _user(session, phone="+919800000001", name="Rajesh Menon")

    async def total(q: str) -> int:
        return (await api.get(f"/admin/users?q={q}", headers=ADMIN)).json()["total"]

    assert await total("Rajesh") == 1
    assert await total("9812345678") == 1
    assert await total("nobody") == 0


async def test_user_detail_shows_activity_but_not_the_birth_chart(api, session):
    user = await _user(session)
    session.add(
        Payment(
            user_id=user.id, product="premium_report", amount_paise=29900,
            razorpay_order_id="order_x", status="paid",
        )
    )
    session.add(
        Entitlement(user_id=user.id, product_key="premium_report", granted_by="purchase")
    )
    await session.commit()

    body = (await api.get(f"/admin/users/{user.id}", headers=ADMIN)).json()
    assert [p["status"] for p in body["payments"]] == ["paid"]
    assert [e["granted_by"] for e in body["entitlements"]] == ["purchase"]
    # Birth PLACE is here (an operator handling "my chart looks wrong" needs it);
    # the date and time of birth are not.
    assert body["birth_place"] == "Thrissur"
    assert not {"dob", "birth_time", "lat", "lng"} & set(body)


async def test_an_unknown_user_is_404(api):
    assert (await api.get("/admin/users/9999", headers=ADMIN)).status_code == 404


async def test_disabling_blocks_the_next_login(api, session):
    user = await _user(session)
    assert (
        await api.post(
            "/identity/login",
            json={"phone": "+919812345678", "password": "a-real-password"},
        )
    ).status_code == 200

    r = await api.post(
        f"/admin/users/{user.id}/active", json={"active": False}, headers=ADMIN
    )
    assert r.status_code == 200
    assert r.json()["active"] is False

    blocked = await api.post(
        "/identity/login",
        json={"phone": "+919812345678", "password": "a-real-password"},
    )
    assert blocked.status_code == 401


async def test_disabling_drops_a_live_session_immediately(api, session):
    """Otherwise a disabled account keeps working for up to the session TTL,
    which is not what anyone means by "disable"."""
    user = await _user(session)
    login = await api.post(
        "/identity/login",
        json={"phone": "+919812345678", "password": "a-real-password"},
    )
    bearer = {"Authorization": f"Bearer {login.json()['token']}"}
    assert (await api.get("/identity/me", headers=bearer)).status_code == 200

    await api.post(f"/admin/users/{user.id}/active", json={"active": False}, headers=ADMIN)
    assert (await api.get("/identity/me", headers=bearer)).status_code == 401


async def test_a_disabled_account_can_be_restored(api, session):
    user = await _user(session)
    await api.post(f"/admin/users/{user.id}/active", json={"active": False}, headers=ADMIN)
    await api.post(f"/admin/users/{user.id}/active", json={"active": True}, headers=ADMIN)
    r = await api.post(
        "/identity/login",
        json={"phone": "+919812345678", "password": "a-real-password"},
    )
    assert r.status_code == 200


async def test_the_active_filter_separates_the_two(api, session):
    first = await _user(session, phone="+919812345678")
    await _user(session, phone="+919800000001", name="Rajesh")
    await api.post(f"/admin/users/{first.id}/active", json={"active": False}, headers=ADMIN)

    disabled = (await api.get("/admin/users?active=false", headers=ADMIN)).json()
    assert [u["id"] for u in disabled["items"]] == [first.id]
    assert (await api.get("/admin/users?active=true", headers=ADMIN)).json()["total"] == 1


# ---- payments and entitlements ----


async def test_the_payment_ledger_is_owner_only(api, session):
    headers = await _temple_admin(session)
    assert (await api.get("/admin/payments")).status_code == 401
    assert (await api.get("/admin/payments", headers=headers)).status_code == 403


async def test_payments_filter_by_status_and_user(api, session):
    user = await _user(session)
    session.add(
        Payment(user_id=user.id, product="premium_report", amount_paise=29900,
                razorpay_order_id="order_a", status="paid")
    )
    session.add(
        Payment(user_id=user.id, product="premium_report", amount_paise=29900,
                razorpay_order_id="order_b", status="created")
    )
    session.add(
        Payment(user_id=999, product="premium_report", amount_paise=29900,
                razorpay_order_id="order_c", status="paid")
    )
    await session.commit()

    async def total(query: str) -> int:
        return (await api.get(f"/admin/payments?{query}", headers=ADMIN)).json()["total"]

    assert await total("") == 3
    assert await total("status=paid") == 2
    assert await total(f"user_id={user.id}") == 2
    assert await total(f"status=paid&user_id={user.id}") == 1


async def test_an_unknown_payment_status_is_rejected(api):
    r = await api.get("/admin/payments?status=refunded", headers=ADMIN)
    assert r.status_code == 422


async def test_an_operator_can_finally_grant_an_entitlement(api, session):
    """`granted_by="admin"` was a declared value with no route that could
    produce one, so a goodwill unlock meant editing the database."""
    user = await _user(session)
    r = await api.post(
        "/admin/entitlements",
        json={"user_id": user.id, "product_key": "premium_report",
              "reason": "payment failed at the gateway, honoured by hand"},
        headers=ADMIN,
    )
    assert r.status_code == 200
    assert r.json()["granted_by"] == "admin"
    assert "honoured by hand" in r.json()["source"]

    from app.modules.commerce.service import CommerceService

    assert await CommerceService().has_entitlement(session, user.id, "premium_report")


async def test_a_grant_cannot_claim_it_came_from_a_purchase(api, session):
    """The console always records `admin`. Letting it name `purchase` would
    forge the audit trail that tells a real payment from a comp."""
    user = await _user(session)
    r = await api.post(
        "/admin/entitlements",
        json={"user_id": user.id, "product_key": "premium_report",
              "granted_by": "purchase"},
        headers=ADMIN,
    )
    assert r.status_code == 200
    assert r.json()["granted_by"] == "admin"


async def test_granting_to_an_unknown_user_is_404(api):
    r = await api.post(
        "/admin/entitlements",
        json={"user_id": 9999, "product_key": "premium_report"},
        headers=ADMIN,
    )
    assert r.status_code == 404


async def test_revoking_actually_closes_the_feature(api, session):
    """A soft delete would leave `has_entitlement` returning True, which is the
    opposite of revoking."""
    from app.modules.commerce.service import CommerceService

    user = await _user(session)
    granted = await api.post(
        "/admin/entitlements",
        json={"user_id": user.id, "product_key": "premium_report"},
        headers=ADMIN,
    )
    entitlement_id = granted.json()["id"]

    r = await api.delete(f"/admin/entitlements/{entitlement_id}", headers=ADMIN)
    assert r.status_code == 204
    assert not await CommerceService().has_entitlement(session, user.id, "premium_report")
    assert (
        await api.delete(f"/admin/entitlements/{entitlement_id}", headers=ADMIN)
    ).status_code == 404


async def test_an_expiring_grant_is_honoured_then_lapses(api, session):
    from app.modules.commerce.service import CommerceService

    user = await _user(session)
    await api.post(
        "/admin/entitlements",
        json={
            "user_id": user.id,
            "product_key": "premium_report",
            "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        },
        headers=ADMIN,
    )
    assert not await CommerceService().has_entitlement(session, user.id, "premium_report")


# ---- the app feed ----


async def _card(api, headers, **over) -> httpx.Response:
    body = {
        "id": "new-notice",
        "cat": "Festival",
        "title_en": "Utsavam begins",
        "who_en": "Guruvayur Sri Krishna Temple",
        "temple_id": "tsr-guruvayur",
    }
    body.update(over)
    return await api.post("/content/feed", json=body, headers=headers)


async def test_the_feed_editor_is_the_owner_or_a_content_reviewer(api, session):
    assert (await _card(api, {})).status_code == 401
    assert (await _card(api, await _temple_admin(session))).status_code == 403
    assert (await _card(api, await _reviewer(session))).status_code == 201


async def test_an_empty_table_still_serves_the_curated_seed(api):
    """Every other test builds a fresh database and seeds no feed, so the
    fallback is what keeps them exercising the old behaviour."""
    body = (await api.get("/feed")).json()
    assert [c["id"] for c in body] == [
        "pooram-ilanjithara", "guruvayur-nirmalyam", "what-is-pradosham"
    ]


async def test_a_published_card_reaches_the_app(api):
    assert (await _card(api, ADMIN, published=True)).status_code == 201
    body = (await api.get("/feed")).json()
    assert [c["id"] for c in body] == ["new-notice"]


async def test_a_draft_is_invisible_to_the_app_but_not_the_console(api):
    await _card(api, ADMIN, published=False)
    # The table is no longer empty, so the seed is gone and the draft is hidden.
    assert (await api.get("/feed")).json() == []
    managed = (await api.get("/content/feed/manage", headers=ADMIN)).json()
    assert [c["id"] for c in managed] == ["new-notice"]


async def test_withdrawing_pulls_a_card_without_destroying_it(api):
    await _card(api, ADMIN, published=True)
    r = await api.post(
        "/content/feed/new-notice/published", json={"published": False}, headers=ADMIN
    )
    assert r.status_code == 200
    assert (await api.get("/feed")).json() == []
    # The text survives, which is the point: a wrong notice has to be corrected.
    managed = (await api.get("/content/feed/manage", headers=ADMIN)).json()
    assert managed[0]["title_en"] == "Utsavam begins"


async def test_an_edit_reaches_the_app_immediately(api):
    await _card(api, ADMIN, published=True)
    r = await api.patch(
        "/content/feed/new-notice", json={"title_en": "Utsavam postponed"}, headers=ADMIN
    )
    assert r.status_code == 200
    assert (await api.get("/feed")).json()[0]["title_en"] == "Utsavam postponed"


async def test_a_card_must_say_whose_words_it_carries(api):
    """GUARDRAILS §1. A card with no attribution reads as an anonymous
    authority making claims."""
    assert (await _card(api, ADMIN, who_en="")).status_code == 422
    await _card(api, ADMIN)
    blanked = await api.patch(
        "/content/feed/new-notice", json={"who_en": "  "}, headers=ADMIN
    )
    assert blanked.status_code == 422


async def test_nobody_can_type_in_an_engagement_count(api):
    """GUARDRAILS §4: `likes`/`comments` are not stored and not settable, and
    the read shape keeps serving 0 until real reactions exist."""
    rejected = await _card(api, ADMIN, likes=5000)
    assert rejected.status_code == 422

    await _card(api, ADMIN, published=True)
    assert (await api.get("/feed")).json()[0]["likes"] == 0
    patched = await api.patch(
        "/content/feed/new-notice", json={"likes": 900}, headers=ADMIN
    )
    assert patched.status_code == 422


async def test_an_unknown_category_is_rejected(api):
    assert (await _card(api, ADMIN, cat="Gossip")).status_code == 422


async def test_a_bad_id_and_a_duplicate_are_rejected(api):
    assert (await _card(api, ADMIN, id="Not A Slug")).status_code == 422
    assert (await _card(api, ADMIN)).status_code == 201
    assert (await _card(api, ADMIN)).status_code == 422


async def test_editing_an_unknown_card_is_404(api):
    r = await api.patch("/content/feed/ghost", json={"title_en": "x"}, headers=ADMIN)
    assert r.status_code == 404


async def test_the_feed_still_filters_by_temple_and_category(api):
    await _card(api, ADMIN, published=True)
    await _card(api, ADMIN, id="a-talk", cat="AstroTalk", temple_id=None,
                who_en="Nithara", published=True)
    assert len((await api.get("/feed?cat=AstroTalk")).json()) == 1
    assert len((await api.get("/feed?temple_id=tsr-guruvayur")).json()) == 1
