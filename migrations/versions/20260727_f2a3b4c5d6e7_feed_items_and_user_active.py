"""app feed out of a Python constant, and a way to disable a user

Console plan Part 8.

  feed_items    — was FEED_ITEMS, a three-item literal in content/feed.py whose
                  own docstring flagged "admin CRUD layer on later". Same shape
                  and the same reasoning as the temple and astrologer moves:
                  editorial content nobody could edit without a redeploy. The
                  three seed cards are imported here so the app serves exactly
                  what it served before.
  users.active  — there was no way to disable an account. Defaults TRUE and is
                  backfilled TRUE, so every existing user keeps working.

Additive; `downgrade` reverses it exactly.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-27 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    feed_items = op.create_table(
        'feed_items',
        # The curated slug ("pooram-ilanjithara"), which the app already treats
        # as the card's identity, so it stays the primary key.
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('cat', sa.String(), nullable=False),
        sa.Column('image', sa.String(), nullable=False),
        sa.Column('glyph', sa.String(), nullable=False),
        sa.Column('live', sa.Boolean(), nullable=False),
        sa.Column('title_en', sa.String(), nullable=False),
        sa.Column('title_ml', sa.String(), nullable=False),
        sa.Column('body_en', sa.Text(), nullable=False),
        sa.Column('body_ml', sa.Text(), nullable=False),
        sa.Column('who_en', sa.String(), nullable=False),
        sa.Column('who_ml', sa.String(), nullable=False),
        sa.Column('temple_id', sa.String(), nullable=True),
        sa.Column('published', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_feed_items_cat'), 'feed_items', ['cat'], unique=False)
    op.create_index(
        op.f('ix_feed_items_temple_id'), 'feed_items', ['temple_id'], unique=False
    )

    # Import the curated seed in the same upgrade, so the table is never
    # briefly empty in front of a running app. `likes`/`comments` are NOT
    # columns: they were hardcoded 0 because inventing engagement counts is
    # forbidden (GUARDRAILS §4), and the API keeps serving 0 until real
    # reactions exist. A column would be an invitation to fill it in.
    from datetime import datetime, timezone

    from app.modules.content.feed import FEED_ITEMS

    now = datetime.now(timezone.utc)
    op.bulk_insert(
        feed_items,
        [
            {
                'id': item['id'],
                'cat': item['cat'],
                'image': item['image'],
                'glyph': item['glyph'],
                'live': item['live'],
                'title_en': item['title_en'],
                'title_ml': item['title_ml'],
                'body_en': item['body_en'],
                'body_ml': item['body_ml'],
                'who_en': item['who_en'],
                'who_ml': item['who_ml'],
                'temple_id': item['temple_id'],
                'published': True,
                'sort_order': index,
                'created_at': now,
                'updated_at': now,
            }
            for index, item in enumerate(FEED_ITEMS)
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_feed_items_temple_id'), table_name='feed_items')
    op.drop_index(op.f('ix_feed_items_cat'), table_name='feed_items')
    op.drop_table('feed_items')
    op.drop_column('users', 'active')
