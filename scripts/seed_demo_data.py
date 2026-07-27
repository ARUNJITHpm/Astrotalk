"""Fill the operator console with realistic-looking demo data, and take it back out.

The console (build plan Parts 5-8) is hard to look at against an empty
database: an empty queue and an empty worklist look identical to a broken one.
This creates enough bookings, payments, consults and festivals to exercise every
filter, state and grouping the console offers.

    python scripts/seed_demo_data.py            # create
    python scripts/seed_demo_data.py --purge    # remove exactly what it created
    python scripts/seed_demo_data.py --reset    # purge, then create fresh

**Everything it writes is tagged**, so removal is exact rather than a guess:

  - users            phone starts with ``+9199000000``
  - pooja bookings   ref starts with ``NTDEMO``
  - payments         razorpay_order_id starts with ``order_demo_``
  - astro bookings   note starts with ``[demo]``
  - partners         slug starts with ``demo-``
  - festivals        name starts with ``[demo] ``

Nothing real is touched. ``--purge`` deletes only rows carrying those markers,
so it is safe to run against a database that also holds live data — which is
exactly the situation here.

⚠️ Reads DATABASE_URL, which on this machine points at PRODUCTION. That is
deliberate (the owner asked for demo data there), but check where you are
pointed before running it anywhere else.
"""

import argparse
import asyncio
import random
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402

from app.modules.astrologers.models import AstroBooking  # noqa: E402
from app.modules.bookings.models import PoojaBooking  # noqa: E402
from app.modules.commerce.models import Payment  # noqa: E402
from app.modules.identity.models import User  # noqa: E402
from app.modules.temples.models import (  # noqa: E402
    TempleFestival,
    TemplePartner,
)
from app.platform.db import async_session_factory  # noqa: E402

DEMO_PHONE_PREFIX = "+9199000000"
DEMO_REF_PREFIX = "NTDEMO"
DEMO_ORDER_PREFIX = "order_demo_"
DEMO_NOTE_PREFIX = "[demo]"
DEMO_SLUG_PREFIX = "demo-"
DEMO_FESTIVAL_PREFIX = "[demo] "

# Deterministic, so re-running --reset gives the same demo every time.
RANDOM = random.Random(20260727)

PEOPLE = [
    ("Ananya Nair", "Thrissur", 10.5276, 76.2144),
    ("Rajesh Menon", "Kochi", 9.9312, 76.2673),
    ("Lakshmi Pillai", "Thiruvananthapuram", 8.5241, 76.9366),
    ("Vishnu Warrier", "Kozhikode", 11.2588, 75.7804),
    ("Meera Krishnan", "Palakkad", 10.7867, 76.6548),
    ("Arun Kumar", "Kannur", 11.8745, 75.3704),
]

# Real ids from the seeded directory, so the console's temple filter has
# something to filter by and the worklist groups across more than one temple.
TEMPLES = [
    "tvm-padmanabhaswamy",
    "tsr-vadakkunnathan",
    "ekm-chottanikkara",
    "tsr-guruvayur",
]

OFFERINGS = [
    ("pushpanjali", "Pushpanjali", 10100),
    ("archana", "Archana", 5100),
    ("neyvilakku", "Neyvilakku", 7500),
    ("ganapathi_homam", "Ganapathi Homam", 125000),
]

NOTES = [
    "",
    "",
    "",
    "Devotee called to confirm the timing.",
    "Prasadam to be couriered.",
    "Rescheduled once at the devotee's request.",
]


async def purge() -> dict[str, int]:
    """Delete exactly what this script creates, and nothing else."""
    counts: dict[str, int] = {}
    async with async_session_factory() as session:
        users = (
            await session.execute(
                select(User).where(User.phone.like(f"{DEMO_PHONE_PREFIX}%"))
            )
        ).scalars().all()
        user_ids = [u.id for u in users]

        for label, statement in (
            (
                "pooja_bookings",
                delete(PoojaBooking).where(PoojaBooking.ref.like(f"{DEMO_REF_PREFIX}%")),
            ),
            (
                "payments",
                delete(Payment).where(
                    Payment.razorpay_order_id.like(f"{DEMO_ORDER_PREFIX}%")
                ),
            ),
            (
                "astro_bookings",
                delete(AstroBooking).where(
                    AstroBooking.note.like(f"{DEMO_NOTE_PREFIX}%")
                ),
            ),
            (
                "temple_festivals",
                delete(TempleFestival).where(
                    TempleFestival.name.like(f"{DEMO_FESTIVAL_PREFIX}%")
                ),
            ),
            (
                "temple_partners",
                delete(TemplePartner).where(
                    TemplePartner.slug.like(f"{DEMO_SLUG_PREFIX}%")
                ),
            ),
        ):
            counts[label] = (await session.execute(statement)).rowcount or 0

        # Users last: the rows above reference them by plain int.
        if user_ids:
            counts["users"] = (
                await session.execute(delete(User).where(User.id.in_(user_ids)))
            ).rowcount or 0
        else:
            counts["users"] = 0
        await session.commit()
    return counts


async def seed() -> dict[str, int]:
    counts = {"users": 0, "pooja_bookings": 0, "payments": 0, "astro_bookings": 0,
              "temple_partners": 0, "temple_festivals": 0}
    today = datetime.now(UTC).date()

    async with async_session_factory() as session:
        existing = (
            await session.execute(
                select(User.id).where(User.phone.like(f"{DEMO_PHONE_PREFIX}%"))
            )
        ).scalars().first()
        if existing is not None:
            print("demo users already present — run --purge or --reset first")
            return counts

        users = []
        for index, (name, place, lat, lng) in enumerate(PEOPLE, start=1):
            user = User(
                phone=f"{DEMO_PHONE_PREFIX}{index:02d}",
                name=name,
                dob=date(1985 + index, (index % 12) + 1, (index * 3 % 28) + 1),
                birth_time=time(6 + index % 12, (index * 7) % 60),
                birth_place=place,
                lat=lat,
                lng=lng,
                tz="Asia/Kolkata",
            )
            session.add(user)
            users.append(user)
        await session.flush()
        counts["users"] = len(users)

        # 24 bookings across four weeks, so every date filter has something on
        # both sides of it, and every state appears at least twice.
        states = (
            ["ok"] * 9 + ["completed"] * 6 + ["wait"] * 4
            + ["cancelled"] * 3 + ["refunded"] * 2
        )
        for index, state in enumerate(states):
            user = users[index % len(users)]
            temple_id = TEMPLES[index % len(TEMPLES)]
            key, display, amount = OFFERINGS[index % len(OFFERINGS)]
            booked_at = datetime.combine(
                today - timedelta(days=RANDOM.randint(0, 27)),
                time(RANDOM.randrange(5, 20), RANDOM.choice((0, 15, 30, 45))),
                UTC,
            )
            # Work that will actually be performed is packed into the next few
            # days, so "today" and "tomorrow" on the worklist are never empty —
            # an empty worklist looks identical to a broken one. Everything else
            # spreads across the past fortnight. A few carry no date at all on
            # purpose: that is what every booking made before Part 7 looks like,
            # and the worklist has to report them rather than drop them.
            if index % 8 == 7:
                perform_on = None
            elif state in ("ok", "completed"):
                perform_on = today + timedelta(days=index % 4)
            else:
                perform_on = today + timedelta(days=RANDOM.randint(-14, 5))
            order_id = None
            if state != "wait" or index % 3 == 0:
                order_id = f"{DEMO_ORDER_PREFIX}{index:04d}"
                session.add(
                    Payment(
                        user_id=user.id,
                        product=f"pooja:{key}",
                        amount_paise=amount + 1500,
                        razorpay_order_id=order_id,
                        status="paid" if state in ("ok", "completed", "refunded") else "created",
                        created_at=booked_at,
                        paid_at=booked_at + timedelta(minutes=2) if state != "wait" else None,
                    )
                )
                counts["payments"] += 1

            session.add(
                PoojaBooking(
                    user_id=user.id,
                    ref=f"{DEMO_REF_PREFIX}{index:03d}",
                    temple_id=temple_id,
                    pooja_key=key,
                    pooja_name=display,
                    amount_paise=amount,
                    service_fee_paise=1500,
                    member_name=user.name.split()[0],
                    member_nak=RANDOM.randrange(0, 27),
                    when_label=(
                        perform_on.strftime("%d %b, 6:00 AM") if perform_on else ""
                    ),
                    perform_on=perform_on,
                    razorpay_order_id=order_id,
                    state=state,
                    operator_note=RANDOM.choice(NOTES),
                    created_at=booked_at,
                )
            )
            counts["pooja_bookings"] += 1

        # A few consults, on real directory ids, over the coming fortnight.
        for index in range(6):
            starts = datetime.combine(
                today + timedelta(days=index + 1), time(4, 30), UTC
            ) + timedelta(minutes=30 * (index % 4))
            session.add(
                AstroBooking(
                    astrologer_id=f"thrissur-astro-{(index % 2) + 1}",
                    user_phone=users[index % len(users)].phone,
                    starts_at=starts,
                    duration_min=30,
                    status=("confirmed", "completed", "no_show")[index % 3],
                    note=f"{DEMO_NOTE_PREFIX} sample consult {index + 1}",
                )
            )
            counts["astro_bookings"] += 1

        # One partner temple with a festival calendar, so the microsite, the QR
        # poster and the festival editor all have something to show.
        partner_temple = TEMPLES[0]
        already = (
            await session.execute(
                select(TemplePartner).where(TemplePartner.temple_id == partner_temple)
            )
        ).scalars().first()
        if already is None:
            session.add(
                TemplePartner(
                    temple_id=partner_temple,
                    slug=f"{DEMO_SLUG_PREFIX}padmanabhaswamy",
                    contact_name="Demo Temple Office",
                    contact_phone=f"{DEMO_PHONE_PREFIX}99",
                    tier="partner",
                )
            )
            counts["temple_partners"] = 1
        for offset, label in ((6, "Utsavam"), (20, "Aarattu"), (45, "Navaratri")):
            session.add(
                TempleFestival(
                    temple_id=partner_temple,
                    name=f"{DEMO_FESTIVAL_PREFIX}{label}",
                    name_ml=label,
                    day=today + timedelta(days=offset),
                )
            )
            counts["temple_festivals"] += 1

        await session.commit()
    return counts


async def _run(args: argparse.Namespace) -> int:
    if args.purge or args.reset:
        print("purging demo rows…")
        for table, n in (await purge()).items():
            print(f"  {table:18} -{n}")
    if not args.purge:
        print("seeding demo rows…")
        for table, n in (await seed()).items():
            print(f"  {table:18} +{n}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--purge", action="store_true", help="remove demo rows and stop")
    parser.add_argument("--reset", action="store_true", help="purge, then seed fresh")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
