"""SQLAlchemy models for the notifications module (internal — do not import elsewhere).

``notification_log`` makes every proactive notification idempotent: one row
per (kind, dedupe_key, phone). The festival cron may fire many times a day
(schedulers retry, admins click the button) — a send must happen exactly once.
"""

from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class NotificationLog(Base):
    __tablename__ = "notification_log"
    __table_args__ = (
        UniqueConstraint("kind", "dedupe_key", "phone", name="uq_notification_once"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str]  # e.g. "festival"
    # What makes this notification unique, e.g. "festival:{festival_id}".
    dedupe_key: Mapped[str] = mapped_column(index=True)
    phone: Mapped[str]
    sent_at: Mapped[datetime] = mapped_column(default=_utcnow)
