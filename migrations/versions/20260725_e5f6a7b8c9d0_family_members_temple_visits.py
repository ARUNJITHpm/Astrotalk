"""family members and temple visits

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-25 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'family_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('rel', sa.String(), nullable=False),
        sa.Column('nak', sa.Integer(), nullable=True),
        sa.Column('is_self', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_family_members_user_id'), 'family_members', ['user_id'], unique=False
    )
    op.create_table(
        'temple_visits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('temple_id', sa.String(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'temple_id', 'day', name='uq_visit_user_temple_day'),
    )
    op.create_index(op.f('ix_temple_visits_user_id'), 'temple_visits', ['user_id'], unique=False)
    op.create_index(op.f('ix_temple_visits_temple_id'), 'temple_visits', ['temple_id'], unique=False)
    op.create_index(op.f('ix_temple_visits_day'), 'temple_visits', ['day'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_temple_visits_day'), table_name='temple_visits')
    op.drop_index(op.f('ix_temple_visits_temple_id'), table_name='temple_visits')
    op.drop_index(op.f('ix_temple_visits_user_id'), table_name='temple_visits')
    op.drop_table('temple_visits')
    op.drop_index(op.f('ix_family_members_user_id'), table_name='family_members')
    op.drop_table('family_members')
