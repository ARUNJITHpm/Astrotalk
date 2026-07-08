"""timestamps to timestamptz (fix asyncpg aware-datetime inserts)

Every model timestamp is a timezone-aware UTC value (``datetime.now(UTC)``),
but the columns were created as naive ``TIMESTAMP``. asyncpg refuses to encode
an aware datetime into a naive ``timestamp`` column ("can't subtract
offset-naive and offset-aware datetimes"), so on Postgres EVERY insert and
datetime comparison 500s (registration, login/session creation, ...). Convert
all timestamp columns to ``TIMESTAMP WITH TIME ZONE``; existing naive values
are interpreted as UTC (which is what the app always wrote).

Postgres-only: SQLite has no distinct timestamptz type and dev/test build the
schema via create_all, so this is a no-op there.

Revision ID: a1b2c3d4e5f6
Revises: 35ff1a0bb2fe
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '35ff1a0bb2fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column) for every DateTime column in the schema.
_TS_COLUMNS: list[tuple[str, str]] = [
    ("users", "created_at"),
    ("sessions", "expires_at"),
    ("sessions", "created_at"),
    ("charts", "computed_at"),
    ("referral_codes", "reward_granted_at"),
    ("referral_codes", "created_at"),
    ("referrals", "created_at"),
    ("content_posts", "created_at"),
    ("content_posts", "published_at"),
    ("share_cards", "created_at"),
    ("wa_consent", "opted_in_at"),
    ("wa_consent", "opted_out_at"),
    ("wa_message_log", "sent_at"),
    ("notification_log", "sent_at"),
    ("temple_partners", "created_at"),
    ("temple_festivals", "created_at"),
    ("temple_subscriptions", "created_at"),
    ("payments", "created_at"),
    ("payments", "paid_at"),
    ("entitlements", "expires_at"),
    ("entitlements", "created_at"),
    ("customer_notes", "created_at"),
    ("availability_slots", "created_at"),
    ("bookings", "starts_at"),
    ("bookings", "created_at"),
    ("orgs", "created_at"),
    ("orgs", "billing_updated_at"),
]


def _alter(to_type: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite: no distinct timestamptz; schema comes from create_all.
    for table, column in _TS_COLUMNS:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
            f'TYPE {to_type} USING "{column}" AT TIME ZONE \'UTC\''
        )


def upgrade() -> None:
    _alter("TIMESTAMP WITH TIME ZONE")


def downgrade() -> None:
    _alter("TIMESTAMP WITHOUT TIME ZONE")
