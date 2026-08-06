"""the home temple a devotee chose

NITHARA-BUILD-PLAN Part 6. Onboarding's whole job is "choose your temple", and
the answer lived in `localStorage` — so reinstalling the app, clearing site data
or opening it on a second phone silently threw it away and sent the devotee back
through onboarding. That quietly punishes the no-signup promise: the account
survives (it is keyed by a server-minted anon id), and the one thing the person
actually told us did not.

  users.home_temple_id — the chosen temple's id, or NULL for an account that has
                         not chosen one. Nullable with no backfill, because
                         "not chosen yet" is a real and common state and any
                         default would be us picking somebody's temple for them.

Deliberately NOT a foreign key to `temples.id`. Identity and temples are
separate modules that compose through services rather than each other's tables
(AGENTS.md), and a database-level constraint here would also make retiring a
temple from the directory fail against every account that chose it. The route
validates the id before storing; a temple that later disappears simply stops
resolving, which the app already handles by offering onboarding again.

Additive; `downgrade` reverses it exactly.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-08-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('home_temple_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'home_temple_id')
