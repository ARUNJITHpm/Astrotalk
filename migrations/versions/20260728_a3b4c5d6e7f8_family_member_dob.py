"""a date of birth on the family board

Console plan Part 12.

  family_members.dob — the board carried a name, a relation and a nakshatram,
                       and nothing else. An operator taking a booking over the
                       phone is routinely told a relative's age, and had nowhere
                       to put it.

A DATE, not an age. An age is right for one year and silently wrong after that,
and this is the column a star-day reminder and a chart would be computed from.
The console derives and displays the age; nothing stores it.

Nullable with no backfill, because it genuinely is unknown for every existing
row and a default here would be an invented birthday. GUARDRAILS §4 applies to
it exactly as it does to `users.dob`: it may appear in one user's detail fetched
by id, and never in a URL, a query string or a list response.

Additive; `downgrade` reverses it exactly.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-07-28 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('family_members', sa.Column('dob', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('family_members', 'dob')
