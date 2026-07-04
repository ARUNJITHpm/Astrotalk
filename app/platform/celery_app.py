"""Celery application — shared queue + scheduler for the monolith.

Used by the ``celery-worker`` and ``celery-beat`` services (see docker-compose.yml).
Broker and result backend are Redis. Module task modules are autodiscovered later;
no business-logic tasks are registered yet (infrastructure only).
"""

from celery import Celery

from app.platform.config import get_settings

settings = get_settings()

celery_app = Celery(
    "tara",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_track_started=True,
    timezone="Asia/Kolkata",
    enable_utc=True,
)

# Module task modules (e.g. app.modules.whatsapp.tasks) get autodiscovered as
# they are added in later parts.
celery_app.autodiscover_tasks(["app.modules"])
