"""pooja bookings

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pooja_bookings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('ref', sa.String(), nullable=False),
        sa.Column('temple_id', sa.String(), nullable=False),
        sa.Column('pooja_key', sa.String(), nullable=False),
        sa.Column('pooja_name', sa.String(), nullable=False),
        sa.Column('amount_paise', sa.Integer(), nullable=False),
        sa.Column('service_fee_paise', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=True),
        sa.Column('member_name', sa.String(), nullable=False),
        sa.Column('member_nak', sa.Integer(), nullable=True),
        sa.Column('when_label', sa.String(), nullable=False),
        sa.Column('razorpay_order_id', sa.String(), nullable=True),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pooja_bookings_user_id'), 'pooja_bookings', ['user_id'], unique=False)
    op.create_index(op.f('ix_pooja_bookings_ref'), 'pooja_bookings', ['ref'], unique=True)
    op.create_index(op.f('ix_pooja_bookings_temple_id'), 'pooja_bookings', ['temple_id'], unique=False)
    op.create_index(
        op.f('ix_pooja_bookings_razorpay_order_id'), 'pooja_bookings', ['razorpay_order_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_pooja_bookings_razorpay_order_id'), table_name='pooja_bookings')
    op.drop_index(op.f('ix_pooja_bookings_temple_id'), table_name='pooja_bookings')
    op.drop_index(op.f('ix_pooja_bookings_ref'), table_name='pooja_bookings')
    op.drop_index(op.f('ix_pooja_bookings_user_id'), table_name='pooja_bookings')
    op.drop_table('pooja_bookings')
