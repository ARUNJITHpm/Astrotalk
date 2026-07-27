"""The operator booking queue (console plan Part 7).

Operators could see nothing before this: the module had two routes and both
were hard-scoped to the caller. So the tests weight three things.

  1. **Scope.** This is the endpoint where a missing check leaks the most — the
     whole queue, with devotee names and phone numbers. Every operator route is
     probed from a `temple_admin`, and one test pins the case that matters most:
     an operator with no grants at all must see zero rows, not all of them.
  2. **The state machine.** `state` had two values and only the payment
     reconciler ever wrote it. Widening it opens two ways to corrupt a booking:
     an operator asserting `ok` by hand, and the reconciler undoing a
     cancellation. Both are pinned shut.
  3. **Money.** Amounts stay in paise everywhere, including the export.
"""

from datetime import UTC, date, datetime

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app as main_app
from app.modules.admin import operators as ops
from app.modules.bookings.models import PoojaBooking
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


async def _operator(session, role="temple_admin", temple_id="tvm-padmanabhaswamy",
                    email="clerk@example.com") -> dict:
    invite = await ops.invite(session, email=email, role=role, temple_id=temple_id)
    await ops.accept(session, token=invite.token, password="temple-pass-1")
    token = await ops.login(session, identifier=email, password="temple-pass-1")
    await session.commit()
    return {"Authorization": f"Bearer {token}"}


_SEQ = {"n": 0}


async def _booking(session, **over) -> PoojaBooking:
    _SEQ["n"] += 1
    base = dict(
        user_id=1,
        ref=f"NT{_SEQ['n']:06d}",
        temple_id="tvm-padmanabhaswamy",
        pooja_key="archana",
        pooja_name="Archana",
        amount_paise=5100,
        service_fee_paise=1500,
        member_name="Devotee",
        member_nak=3,
        when_label="28 Jul, 6:00 AM",
        state="ok",
        created_at=datetime(2026, 7, 20, 6, 0, tzinfo=UTC),
    )
    row = PoojaBooking(**{**base, **over})
    session.add(row)
    await session.commit()
    return row


# ---- the gate ----


async def test_the_queue_refuses_an_anonymous_caller(api):
    assert (await api.get("/bookings/queue")).status_code == 401
    assert (await api.get("/bookings/queue/1")).status_code == 401
    assert (await api.get("/bookings/queue/worklist")).status_code == 401
    assert (await api.get("/bookings/queue/export.csv")).status_code == 401
    r = await api.patch("/bookings/queue/1/status", json={"status": "completed"})
    assert r.status_code == 401


# ---- scope ----


async def test_a_temple_admin_sees_only_their_own_temples_bookings(api, session):
    await _booking(session)
    await _booking(session, temple_id="tsr-vadakkunnathan")
    headers = await _operator(session)

    page = (await api.get("/bookings/queue", headers=headers)).json()
    assert page["total"] == 1
    assert {b["temple_id"] for b in page["items"]} == {"tvm-padmanabhaswamy"}

    # The owner credential sees both.
    assert (await api.get("/bookings/queue", headers=ADMIN)).json()["total"] == 2


async def test_an_empty_scope_matches_nothing_not_everything(api, session):
    """The single most damaging mistake available in this module.
    `visible_temple_ids()` returns None for an owner and an EMPTY SET for a
    scoped operator with no grants. If the query treats them alike — the
    obvious `if temple_ids: ...` — the whole queue opens up.

    Straight at the query, because no route can currently produce an empty
    scope: `require_operator` rejects an operator holding no temple_admin
    grant before it gets this far. That makes the branch untested through HTTP
    and worth pinning here, since a later role change could reach it.
    """
    from app.modules.bookings import admin as booking_admin

    await _booking(session)

    total_owner, rows_owner = await booking_admin.queue(session, temple_ids=None)
    assert (total_owner, len(rows_owner)) == (1, 1)

    total_none, rows_none = await booking_admin.queue(session, temple_ids=frozenset())
    assert (total_none, rows_none) == (0, [])

    with pytest.raises(booking_admin.NotFound):
        await booking_admin.get_one(session, temple_ids=frozenset(), booking_id=1)


async def test_a_role_that_does_not_work_the_queue_is_refused(api, session):
    invite = await ops.invite(session, email="helper@example.com", role="support")
    await ops.accept(session, token=invite.token, password="temple-pass-1")
    token = await ops.login(session, identifier="helper@example.com", password="temple-pass-1")
    await session.commit()
    headers = {"Authorization": f"Bearer {token}"}
    assert (await api.get("/bookings/queue", headers=headers)).status_code == 403


async def test_a_booking_outside_scope_reads_as_missing_not_forbidden(api, session):
    """Refs are `NT` + six digits — short and guessable. Answering "forbidden"
    for one temple and "unknown" for another turns the lookup into an oracle."""
    other = await _booking(session, temple_id="tsr-vadakkunnathan")
    headers = await _operator(session)

    assert (await api.get(f"/bookings/queue/{other.id}", headers=headers)).status_code == 404
    by_ref = await api.get(f"/bookings/queue/by-ref/{other.ref}", headers=headers)
    assert by_ref.status_code == 404


async def test_a_scoped_operator_cannot_change_another_temples_booking(api, session):
    other = await _booking(session, temple_id="tsr-vadakkunnathan")
    headers = await _operator(session)
    r = await api.patch(
        f"/bookings/queue/{other.id}/status", json={"status": "cancelled"}, headers=headers
    )
    assert r.status_code == 404
    await session.refresh(other)
    assert other.state == "ok"


# ---- filters and paging ----


async def test_filters_narrow_the_queue(api, session):
    await _booking(session, pooja_key="archana", state="ok")
    await _booking(session, pooja_key="ganapathi_homam", state="wait")
    await _booking(session, pooja_key="neyvilakku", temple_id="tsr-vadakkunnathan")

    async def total(query: str) -> int:
        return (await api.get(f"/bookings/queue?{query}", headers=ADMIN)).json()["total"]

    assert await total("state=wait") == 1
    assert await total("pooja_key=archana") == 1
    assert await total("temple_id=tsr-vadakkunnathan") == 1
    assert await total("booked_from=2026-07-21") == 0
    assert await total("booked_to=2026-07-21") == 3


async def test_date_filters_mean_IST_days_not_UTC_ones(api, session):
    """An operator in Kerala asking for "the 21st" means the 21st in IST. This
    booking was made at 03:00 IST on the 21st, which is 21:30 UTC on the 20th —
    comparing against the stored timestamp's own date files it under the wrong
    day, and a day-boundary booking then vanishes from both days' reports."""
    await _booking(session, created_at=datetime(2026, 7, 20, 21, 30, tzinfo=UTC))

    async def total(query: str) -> int:
        return (await api.get(f"/bookings/queue?{query}", headers=ADMIN)).json()["total"]

    assert await total("booked_from=2026-07-21&booked_to=2026-07-21") == 1
    assert await total("booked_from=2026-07-20&booked_to=2026-07-20") == 0


async def test_an_unknown_state_filter_is_rejected(api):
    r = await api.get("/bookings/queue?state=elsewhere", headers=ADMIN)
    assert r.status_code == 422


async def test_a_phone_nobody_owns_matches_nothing_rather_than_everything(api, session):
    await _booking(session)
    page = (await api.get("/bookings/queue?phone=%2B910000000000", headers=ADMIN)).json()
    assert page["total"] == 0


async def test_the_ref_lookup_is_case_insensitive(api, session):
    booking = await _booking(session)
    r = await api.get(f"/bookings/queue/by-ref/{booking.ref.lower()}", headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["ref"] == booking.ref


async def test_paging_reports_the_total_before_the_page(api, session):
    for _ in range(5):
        await _booking(session)
    page = (await api.get("/bookings/queue?limit=2&offset=2", headers=ADMIN)).json()
    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert (page["limit"], page["offset"]) == (2, 2)


# ---- detail ----


async def test_the_detail_joins_the_devotee_and_the_payment(api, session):
    from app.modules.identity.schemas import UserCreate
    from app.modules.identity.service import IdentityService

    user = await IdentityService().create_user(
        session,
        UserCreate(
            name="Devotee", phone="+919812345678", password="a-real-password",
            dob=date(1990, 1, 1), tob="06:00", birth_place="Thrissur",
            lat=10.5, lng=76.2, tz="Asia/Kolkata",
        ),
    )
    await session.commit()
    booking = await _booking(session, user_id=user.id)

    body = (await api.get(f"/bookings/queue/{booking.id}", headers=ADMIN)).json()
    assert body["user_phone"] == "+919812345678"
    assert body["user_name"] == "Devotee"
    # Money stays in paise, and the total is the sum the devotee was charged.
    assert body["total_paise"] == 6600


async def test_a_missing_devotee_does_not_break_the_detail(api, session):
    """user_id is a plain int with no foreign key (AGENTS.md), so a booking can
    outlive its user. The queue must still render."""
    booking = await _booking(session, user_id=99999)
    body = (await api.get(f"/bookings/queue/{booking.id}", headers=ADMIN)).json()
    assert body["user_phone"] == ""


# ---- the state machine ----


async def test_an_operator_can_finally_complete_and_cancel(api, session):
    booking = await _booking(session)
    r = await api.patch(
        f"/bookings/queue/{booking.id}/status",
        json={"status": "completed", "note": "performed at 6am"},
        headers=ADMIN,
    )
    assert r.status_code == 200
    assert r.json()["state"] == "completed"
    assert r.json()["operator_note"] == "performed at 6am"


async def test_an_operator_cannot_declare_a_booking_paid(api, session):
    """`ok` means the reconciler saw a captured payment. If the console could
    assert it, a paid booking would be indistinguishable from a wrong click."""
    booking = await _booking(session, state="wait")
    r = await api.patch(
        f"/bookings/queue/{booking.id}/status", json={"status": "ok"}, headers=ADMIN
    )
    assert r.status_code == 409


async def test_an_unpaid_booking_can_only_be_cancelled(api, session):
    booking = await _booking(session, state="wait")
    assert (
        await api.patch(
            f"/bookings/queue/{booking.id}/status",
            json={"status": "completed"},
            headers=ADMIN,
        )
    ).status_code == 409
    assert (
        await api.patch(
            f"/bookings/queue/{booking.id}/status",
            json={"status": "cancelled"},
            headers=ADMIN,
        )
    ).status_code == 200


async def test_refunded_is_terminal(api, session):
    booking = await _booking(session)
    await api.patch(
        f"/bookings/queue/{booking.id}/status", json={"status": "refunded"}, headers=ADMIN
    )
    r = await api.patch(
        f"/bookings/queue/{booking.id}/status", json={"status": "completed"}, headers=ADMIN
    )
    assert r.status_code == 409


async def test_setting_the_same_state_twice_is_idempotent(api, session):
    booking = await _booking(session)
    first = await api.patch(
        f"/bookings/queue/{booking.id}/status", json={"status": "completed"}, headers=ADMIN
    )
    second = await api.patch(
        f"/bookings/queue/{booking.id}/status", json={"status": "completed"}, headers=ADMIN
    )
    assert first.status_code == second.status_code == 200


async def test_an_unknown_state_is_rejected(api, session):
    booking = await _booking(session)
    r = await api.patch(
        f"/bookings/queue/{booking.id}/status", json={"status": "vanished"}, headers=ADMIN
    )
    assert r.status_code == 422


async def test_a_late_capture_never_resurrects_a_cancelled_booking(api, session):
    """The reconciler read `state != "ok"`, which was the same as `== "wait"`
    when those were the only states. With a cancel path it would have promoted
    a cancelled booking back to `ok` the moment a late capture landed."""
    from app.modules.bookings.service import BookingsService
    from app.modules.commerce.models import Payment

    booking = await _booking(session, user_id=7, razorpay_order_id="order_late")
    session.add(
        Payment(
            user_id=7, product="pooja:archana", amount_paise=6600,
            razorpay_order_id="order_late", status="paid",
        )
    )
    await session.commit()
    await api.patch(
        f"/bookings/queue/{booking.id}/status", json={"status": "cancelled"}, headers=ADMIN
    )

    rows = await BookingsService().list_for_user(session, 7)
    assert [b["state"] for b in rows] == ["cancelled"]


async def test_a_note_can_be_left_without_changing_state(api, session):
    booking = await _booking(session)
    r = await api.patch(
        f"/bookings/queue/{booking.id}/note", json={"note": "devotee called"}, headers=ADMIN
    )
    assert r.status_code == 200
    assert (r.json()["operator_note"], r.json()["state"]) == ("devotee called", "ok")


# ---- worklist ----


async def test_the_worklist_groups_a_day_by_star(api, session):
    await _booking(session, member_nak=5, perform_on=date(2026, 8, 1))
    await _booking(session, member_nak=5, perform_on=date(2026, 8, 1))
    await _booking(session, member_nak=2, perform_on=date(2026, 8, 1))
    await _booking(session, member_nak=2, perform_on=date(2026, 8, 2))

    body = (
        await api.get("/bookings/queue/worklist?day=2026-08-01", headers=ADMIN)
    ).json()
    assert body["total"] == 3
    assert [(g["nak"], len(g["items"])) for g in body["groups"]] == [(2, 1), (5, 2)]


async def test_the_worklist_counts_what_it_cannot_place(api, session):
    """`when_label` is free display text, so every booking made before
    `perform_on` existed has no day. Reporting the count is honest; dropping
    them silently would make the sheet quietly wrong."""
    await _booking(session, perform_on=date(2026, 8, 1))
    await _booking(session)  # no perform_on
    body = (
        await api.get("/bookings/queue/worklist?day=2026-08-01", headers=ADMIN)
    ).json()
    assert (body["total"], body["undated"]) == (1, 1)


async def test_the_worklist_leaves_out_unpaid_and_cancelled_work(api, session):
    await _booking(session, perform_on=date(2026, 8, 1), state="wait")
    await _booking(session, perform_on=date(2026, 8, 1), state="cancelled")
    await _booking(session, perform_on=date(2026, 8, 1), state="completed")
    body = (
        await api.get("/bookings/queue/worklist?day=2026-08-01", headers=ADMIN)
    ).json()
    assert body["total"] == 1


async def test_bookings_with_no_star_still_get_a_place_on_the_sheet(api, session):
    await _booking(session, member_nak=None, perform_on=date(2026, 8, 1))
    await _booking(session, member_nak=1, perform_on=date(2026, 8, 1))
    body = (
        await api.get("/bookings/queue/worklist?day=2026-08-01", headers=ADMIN)
    ).json()
    assert [g["nak"] for g in body["groups"]] == [1, None]


async def test_the_worklist_is_scoped_too(api, session):
    await _booking(session, perform_on=date(2026, 8, 1))
    await _booking(session, temple_id="tsr-vadakkunnathan", perform_on=date(2026, 8, 1))
    headers = await _operator(session)
    body = (
        await api.get("/bookings/queue/worklist?day=2026-08-01", headers=headers)
    ).json()
    assert body["total"] == 1


# ---- export ----


async def test_the_export_is_csv_in_paise(api, session):
    await _booking(session)
    r = await api.get("/bookings/queue/export.csv", headers=ADMIN)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")

    lines = r.text.strip().splitlines()
    assert lines[0].startswith("ref,created_at,perform_on")
    assert ",5100,1500,6600," in lines[1]


async def test_the_export_is_scoped(api, session):
    await _booking(session)
    await _booking(session, temple_id="tsr-vadakkunnathan")
    headers = await _operator(session)
    body = (await api.get("/bookings/queue/export.csv", headers=headers)).text
    assert body.count("\n") == 2  # header + one row
    assert "tsr-vadakkunnathan" not in body


async def test_the_export_path_is_not_read_as_a_booking_id(api):
    """`/queue/export.csv` and `/queue/{booking_id}` overlap. Registered the
    other way round this 422s trying to parse "export.csv" as an int."""
    r = await api.get("/bookings/queue/export.csv", headers=ADMIN)
    assert r.status_code == 200


# ---- settings ----


async def test_the_service_fee_can_finally_be_changed(api, session):
    assert (await api.get("/bookings/settings", headers=ADMIN)).json() == {
        "service_fee_paise": 1500
    }
    r = await api.put(
        "/bookings/settings", json={"service_fee_paise": 2500}, headers=ADMIN
    )
    assert r.status_code == 200
    assert (await api.get("/bookings/settings", headers=ADMIN)).json() == {
        "service_fee_paise": 2500
    }


async def test_a_negative_service_fee_is_rejected(api):
    r = await api.put(
        "/bookings/settings", json={"service_fee_paise": -1}, headers=ADMIN
    )
    assert r.status_code == 422


async def test_a_temple_admin_cannot_set_the_app_wide_fee(api, session):
    headers = await _operator(session)
    r = await api.put(
        "/bookings/settings", json={"service_fee_paise": 0}, headers=headers
    )
    assert r.status_code == 403
