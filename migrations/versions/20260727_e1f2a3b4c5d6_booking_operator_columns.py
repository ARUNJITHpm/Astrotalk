"""operator columns on pooja_bookings

Console plan Part 7. Operators could see nothing and record nothing: the module
had two routes, both hard-scoped to the caller, and the only writer of `state`
was the payment reconciler.

Three additive, nullable-or-defaulted columns. No existing value is altered and
no row is touched, so this is safe to run against a live database and
`downgrade` reverses it exactly.

  perform_on     — the machine-readable day the temple performs the offering.
                   `when_label` is free display text the client composes, so it
                   can never be queried; without this there is no such thing as
                   a dated worklist. NULL for every booking made before now.
  operator_note  — what the temple needs to remember about this booking.
  updated_at     — NULL until an operator first touches the row, which is also
                   how the console tells a machine-set state from a human one.

The state VOCABULARY also widens here (wait|ok → + completed|cancelled|refunded)
but `state` is a plain string column with no CHECK constraint or enum type, so
that needs no DDL — only the application-level state machine in models.py.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-27 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'pooja_bookings', sa.Column('perform_on', sa.Date(), nullable=True)
    )
    op.create_index(
        op.f('ix_pooja_bookings_perform_on'), 'pooja_bookings', ['perform_on'], unique=False
    )
    op.add_column(
        'pooja_bookings',
        sa.Column('operator_note', sa.Text(), nullable=False, server_default=''),
    )
    op.add_column(
        'pooja_bookings',
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('pooja_bookings', 'updated_at')
    op.drop_column('pooja_bookings', 'operator_note')
    op.drop_index(op.f('ix_pooja_bookings_perform_on'), table_name='pooja_bookings')
    op.drop_column('pooja_bookings', 'perform_on')
