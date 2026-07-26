"""pooja catalogue and booking settings out of Python constants

Three tables:
  - ``poojas``           the master offering catalogue, was DEFAULT_POOJAS, a
                         four-item constant in temples/service.py shared
                         verbatim by all 53 temples.
  - ``temple_poojas``    per-temple overrides. The override slot has existed in
                         the seed schema from the start and not one temple used
                         it, so every temple offers the identical four items at
                         identical prices. Seeded empty — an override is
                         something an operator creates.
  - ``booking_settings`` a single row holding the ₹15 service fee, was
                         SERVICE_FEE_PAISE in bookings/service.py.

Amounts are stored in paise, like every other money column in the app. The
catalogue served to clients converts to whole rupees under ``amount``, which is
the existing API contract (PoojaCatalogueItem.amount).

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-27 01:00:00.000000

"""
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    poojas = op.create_table(
        'poojas',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('name_ml', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount_paise', sa.Integer(), nullable=False),
        sa.Column('lead_days', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )

    op.create_table(
        'temple_poojas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('temple_id', sa.String(), nullable=False),
        sa.Column('pooja_key', sa.String(), nullable=False),
        # NULL = inherit the master value. Inheriting is the common case and
        # must not require copying the price.
        sa.Column('amount_paise', sa.Integer(), nullable=True),
        sa.Column('lead_days', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('temple_id', 'pooja_key', name='uq_temple_pooja'),
    )
    op.create_index(
        op.f('ix_temple_poojas_temple_id'), 'temple_poojas', ['temple_id'], unique=False
    )
    op.create_index(
        op.f('ix_temple_poojas_pooja_key'), 'temple_poojas', ['pooja_key'], unique=False
    )

    settings = op.create_table(
        'booking_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_fee_paise', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    from app.modules.bookings.service import SERVICE_FEE_PAISE
    from app.modules.temples.service import DEFAULT_POOJAS

    now = datetime.now(UTC)
    op.bulk_insert(poojas, [
        {
            'key': p['key'],
            'name': p['name'],
            'name_ml': p.get('name_ml', ''),
            'description': None,
            # DEFAULT_POOJAS carries whole rupees; the column is paise.
            'amount_paise': int(p['amount']) * 100,
            'lead_days': int(p['lead_days']),
            'active': True,
            'sort_order': i,
            'created_at': now,
            'updated_at': now,
        }
        for i, p in enumerate(DEFAULT_POOJAS)
    ])
    op.bulk_insert(settings, [
        {'id': 1, 'service_fee_paise': SERVICE_FEE_PAISE, 'updated_at': now},
    ])


def downgrade() -> None:
    op.drop_table('booking_settings')
    op.drop_index(op.f('ix_temple_poojas_pooja_key'), table_name='temple_poojas')
    op.drop_index(op.f('ix_temple_poojas_temple_id'), table_name='temple_poojas')
    op.drop_table('temple_poojas')
    op.drop_table('poojas')
