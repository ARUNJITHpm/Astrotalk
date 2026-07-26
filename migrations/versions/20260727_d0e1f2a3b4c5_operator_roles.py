"""operator accounts, roles, sessions and invites

Console plan Part 4. Until now there was exactly one privilege level: the owner,
a per-temple operator and a content reviewer all presented the same token and
could do everything.

Operators are deliberately NOT `users` rows — that table requires dob,
birth_place, lat, lng and tz (all NOT NULL) because it models a devotee with a
natal chart, and a temple clerk should not need one to sign in.

Seeded empty. The first owner is created by scripts/grant_role.py; everyone
after that is invited from the console. Nothing here changes existing access:
the admin token and the admin_phones session both still resolve to a full owner.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-27 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'operators',
        sa.Column('id', sa.Integer(), nullable=False),
        # Either identifies the operator; at least one is always set. Both are
        # unique, and Postgres permits many NULLs in a unique column.
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        # Null until the invite is redeemed.
        sa.Column('password_hash', sa.String(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_operators_email'), 'operators', ['email'], unique=True)
    op.create_index(op.f('ix_operators_phone'), 'operators', ['phone'], unique=True)

    op.create_table(
        'operator_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('operator_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        # NULL = unscoped. A temple_admin always carries one.
        sa.Column('temple_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['operator_id'], ['operators.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('operator_id', 'role', 'temple_id', name='uq_operator_role'),
    )
    op.create_index(
        op.f('ix_operator_roles_operator_id'), 'operator_roles', ['operator_id'], unique=False
    )
    op.create_index(op.f('ix_operator_roles_role'), 'operator_roles', ['role'], unique=False)
    op.create_index(
        op.f('ix_operator_roles_temple_id'), 'operator_roles', ['temple_id'], unique=False
    )

    op.create_table(
        'operator_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('operator_id', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['operator_id'], ['operators.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_operator_sessions_token'), 'operator_sessions', ['token'], unique=True)
    op.create_index(
        op.f('ix_operator_sessions_operator_id'), 'operator_sessions', ['operator_id'], unique=False
    )

    op.create_table(
        'operator_invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('temple_id', sa.String(), nullable=True),
        sa.Column('invited_by', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_operator_invites_token'), 'operator_invites', ['token'], unique=True)
    op.create_index(op.f('ix_operator_invites_email'), 'operator_invites', ['email'], unique=False)
    op.create_index(op.f('ix_operator_invites_phone'), 'operator_invites', ['phone'], unique=False)


def downgrade() -> None:
    op.drop_table('operator_invites')
    op.drop_table('operator_sessions')
    op.drop_table('operator_roles')
    op.drop_table('operators')
