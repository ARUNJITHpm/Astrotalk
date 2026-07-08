"""chat history in postgres

Moves chat-turn persistence from MongoDB to the ``chat_history`` table so the
sidebar history and admin chat explorer work on the single managed DB (Neon),
without standing up a separate document store.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chat_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=True),
        sa.Column('messages', sa.JSON(), nullable=False),
        sa.Column('reply', sa.Text(), nullable=False),
        # timezone-aware to match the timestamptz convention (rev a1b2c3d4e5f6).
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('llm_provider', sa.String(), nullable=True),
        sa.Column('llm_model', sa.String(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('price_inr', sa.Float(), nullable=True),
        sa.Column('price_usd', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chat_history_user_id'), 'chat_history', ['user_id'], unique=False)
    op.create_index(op.f('ix_chat_history_conversation_id'), 'chat_history', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_chat_history_created_at'), 'chat_history', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_history_created_at'), table_name='chat_history')
    op.drop_index(op.f('ix_chat_history_conversation_id'), table_name='chat_history')
    op.drop_index(op.f('ix_chat_history_user_id'), table_name='chat_history')
    op.drop_table('chat_history')
