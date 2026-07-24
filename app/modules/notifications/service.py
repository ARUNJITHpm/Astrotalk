"""Public service for the notifications module (GROWTH_PLAN.md Part 3).

First real job: festival update notifications. The cron endpoint runs daily;
for every partner-temple festival exactly T-3 days out, every subscriber who
opted in gets ONE WhatsApp template message — consent and the 24h cap are
enforced inside the whatsapp module's ``send_template``, and this module's
``notification_log`` guarantees once-per-festival-per-phone even if the cron
fires repeatedly.

Copy is a fixed template (no LLM): an invitation with a date, nothing more.
No urgency, no consequences (GUARDRAILS.md §1).
"""

from datetime import UTC, date as date_type, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import DeviceToken, NotificationLog
from app.platform import metrics
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# How many days before a festival the update goes out.
FESTIVAL_LEAD_DAYS = 3
# How many days before a family member's nakshatram day the push goes out.
NAKSHATRAM_LEAD_DAYS = 3


def _festival_message(temple_name_ml: str, festival: str, day: date_type) -> str:
    return (
        f"🪔 {temple_name_ml}\n"
        f"{festival} — {day.strftime('%d-%m-%Y')} ന് നടക്കും. "
        "ദർശനത്തിന് വരുന്നെങ്കിൽ സമാധാനത്തോടെ പോയി വരൂ.\n"
        "ഉത്സവ വിശേഷങ്ങൾ അറിയാൻ താര ആപ്പും ഉണ്ട് കൂടെ."
    )


class NotificationsService:
    async def run_festivals(
        self, session: AsyncSession, today: date_type | None = None
    ) -> dict:
        """One daily run: notify subscribers of festivals T-3 days away.

        Returns a summary {target_day, festivals, sent, skipped}. Idempotent:
        the notification_log unique row per (festival, phone) means re-runs
        and scheduler retries never double-send.
        """
        # Public services only (AGENTS.md); local imports keep module load light.
        from app.modules.temples.service import TemplesService
        from app.modules.whatsapp.service import WhatsappService

        today = today or datetime.now(UTC).date()
        target_day = today + timedelta(days=FESTIVAL_LEAD_DAYS)
        temples = TemplesService()
        whatsapp = WhatsappService()
        festivals = await temples.partner_festivals_on(session, target_day)

        sent = 0
        skipped = 0
        for festival in festivals:
            temple = temples.get_temple(festival["temple_id"]) or {}
            temple_name = temple.get("name_ml") or temple.get("name") or festival["temple_id"]
            message = _festival_message(
                temple_name, festival["name_ml"] or festival["name"], festival["day"]
            )
            dedupe_key = f"festival:{festival['id']}"
            for phone in await temples.subscriber_phones(session, festival["temple_id"]):
                already = (
                    await session.execute(
                        select(NotificationLog).where(
                            NotificationLog.kind == "festival",
                            NotificationLog.dedupe_key == dedupe_key,
                            NotificationLog.phone == phone,
                        )
                    )
                ).scalars().first()
                if already is not None:
                    skipped += 1
                    continue
                if await whatsapp.send_template(session, phone, message):
                    session.add(
                        NotificationLog(kind="festival", dedupe_key=dedupe_key, phone=phone)
                    )
                    await session.flush()
                    sent += 1
                    metrics.increment("notifications.festival_sends")
                else:
                    skipped += 1  # no consent or capped — whatsapp module said no
        logger.info(
            "notifications: festival run for %s -> %s festivals, %s sent, %s skipped",
            target_day, len(festivals), sent, skipped,
        )
        return {
            "target_day": target_day.isoformat(),
            "festivals": len(festivals),
            "sent": sent,
            "skipped": skipped,
        }

    # ---- app push: register devices + nakshatram reminders (Part 4) ----

    async def register_device(
        self, session: AsyncSession, user_id: int, token: str, platform: str = "android"
    ) -> DeviceToken:
        """Register (or re-point) an FCM token. Same token re-registering just
        updates its owner/platform — installs move between accounts."""
        existing = (
            await session.execute(select(DeviceToken).where(DeviceToken.token == token))
        ).scalars().first()
        if existing is not None:
            existing.user_id = user_id
            existing.platform = platform
            device = existing
        else:
            device = DeviceToken(user_id=user_id, token=token, platform=platform)
            session.add(device)
        await session.flush()
        return device

    async def run_nakshatram_reminders(
        self,
        session: AsyncSession,
        today: date_type | None = None,
        lead_days: int = NAKSHATRAM_LEAD_DAYS,
    ) -> dict:
        """Push each registered user a reminder when a family member's nakshatram
        day is ``lead_days`` away. Idempotent per (member, star-date) via the
        notification_log, so scheduler retries never double-send."""
        from app.modules.astrology_engine.service import AstrologyEngineService
        from app.modules.identity.service import IdentityService

        today = today or date_type.today()
        user_ids = list(
            (await session.execute(select(DeviceToken.user_id).distinct())).scalars().all()
        )
        if not user_ids:
            return {"target_lead_days": lead_days, "reminders_sent": 0}

        members = await IdentityService().members_with_nakshatram(session, user_ids)
        engine = AstrologyEngineService()
        names = engine.nakshatra_names()
        from app.modules.notifications.push_client import PushClient

        push = PushClient()
        sent = 0
        for member in members:
            star_day = await engine.next_nakshatram_day(member["nak"], from_day=today)
            if star_day is None or (star_day - today).days != lead_days:
                continue
            dedupe_key = f"{member['member_id']}:{star_day.isoformat()}"
            recipient = f"u{member['user_id']}"  # the log keys on recipient, not phone
            already = (
                await session.execute(
                    select(NotificationLog).where(
                        NotificationLog.kind == "nakshatram",
                        NotificationLog.dedupe_key == dedupe_key,
                        NotificationLog.phone == recipient,
                    )
                )
            ).scalars().first()
            if already is not None:
                continue

            star = names[member["nak"]]
            who = "Your" if member["is_self"] else f"{member['name']}'s"
            title = f"{star} nakshatram in {lead_days} days"
            body = f"{who} nakshatram falls on {star_day.strftime('%d %b')}. Book a pooja."
            tokens = list(
                (
                    await session.execute(
                        select(DeviceToken.token).where(
                            DeviceToken.user_id == member["user_id"]
                        )
                    )
                ).scalars().all()
            )
            for token in tokens:
                await push.send(
                    token, title, body,
                    {"type": "nakshatram", "member_id": str(member["member_id"])},
                )
            session.add(
                NotificationLog(kind="nakshatram", dedupe_key=dedupe_key, phone=recipient)
            )
            sent += 1
            metrics.increment("notifications.nakshatram_sends")

        logger.info("notifications: nakshatram run -> %s reminders sent", sent)
        return {"target_lead_days": lead_days, "reminders_sent": sent}
