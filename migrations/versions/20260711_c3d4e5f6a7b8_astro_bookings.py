"""astrologer consult bookings

Adds ``astro_bookings`` behind the astrologers module (dummy directory + free
consult booking). The astrologer directory itself is static seed data; this
table is the only real state. Free consults confirm immediately, so there is no
payment/pending column (unlike the org booking engine).

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'astro_bookings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('astrologer_id', sa.String(), nullable=False),
        sa.Column('user_phone', sa.String(), nullable=False),
        # timezone-aware to match the timestamptz convention (rev a1b2c3d4e5f6).
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_min', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('astrologer_id', 'starts_at', name='uq_astro_slot'),
    )
    op.create_index(op.f('ix_astro_bookings_astrologer_id'), 'astro_bookings', ['astrologer_id'], unique=False)
    op.create_index(op.f('ix_astro_bookings_user_phone'), 'astro_bookings', ['user_phone'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_astro_bookings_user_phone'), table_name='astro_bookings')
    op.drop_index(op.f('ix_astro_bookings_astrologer_id'), table_name='astro_bookings')
    op.drop_table('astro_bookings')
