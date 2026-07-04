"""Celery worker + beat entrypoint.

Run with:  celery -A worker.celery_app worker --loglevel=info
           celery -A worker.celery_app beat   --loglevel=info

Reuses the shared platform Celery app and registers the daily WhatsApp task plus
its beat schedule. The first live WhatsApp send needs human approval
(AGENTS.md / GUARDRAILS.md §3); with MOCK_WHATSAPP=true (default) it only logs.
"""

import asyncio

from celery.schedules import crontab

from app.modules.whatsapp.tasks import send_daily_message
from app.platform.celery_app import celery_app


@celery_app.task(name="whatsapp.send_daily_message")
def send_daily_message_task() -> str:
    """Sync Celery wrapper around the async daily pipeline."""
    return asyncio.run(send_daily_message())


# The shared app's timezone is Asia/Kolkata, so 05:30 IST == 00:00 UTC.
celery_app.conf.beat_schedule = {
    "daily-whatsapp-channel-message": {
        "task": "whatsapp.send_daily_message",
        "schedule": crontab(hour=5, minute=30),  # 05:30 IST = 00:00 UTC
    }
}
