"""temple directory moves from seed_data.py into the database

The directory used to be a Python literal (app/modules/temples/seed_data.py)
bound in memory at service construction, so adding a temple or correcting a
price meant a code change and a redeploy — and the operator console could not
exist. This creates the table and imports the curated seed into it in the same
upgrade, so the running app never sees an empty directory.

Values are imported AS THEY ARE, including ``reviewed``. Flipping that flag is
an operator action (PATCH /temples/{id}/review), not a migration's business:
the flag is served to clients and changing it here would silently alter what
GET /temples/suggest returns.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-27 00:00:00.000000

"""
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    temples = op.create_table(
        'temples',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('name_ml', sa.String(), nullable=False),
        sa.Column('deity', sa.String(), nullable=False),
        sa.Column('district', sa.String(), nullable=False),
        sa.Column('town', sa.String(), nullable=False),
        sa.Column('town_ml', sa.String(), nullable=True),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lng', sa.Float(), nullable=False),
        sa.Column('famous_for', sa.Text(), nullable=False),
        sa.Column('vazhipadu', sa.JSON(), nullable=False),
        sa.Column('reviewed', sa.Boolean(), nullable=False),
        sa.Column('story', sa.Text(), nullable=True),
        sa.Column('story_ml', sa.Text(), nullable=True),
        sa.Column('hours', sa.JSON(), nullable=True),
        sa.Column('timings', sa.JSON(), nullable=True),
        sa.Column('poojas', sa.JSON(), nullable=True),
        sa.Column('rating', sa.String(), nullable=True),
        sa.Column('reviews', sa.String(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('image_key', sa.String(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_temples_deity'), 'temples', ['deity'], unique=False)
    op.create_index(op.f('ix_temples_district'), 'temples', ['district'], unique=False)

    # Import the curated seed. `sort_order` preserves the hand-curated ordering
    # the app has always listed temples in when no distance sort applies.
    from app.modules.temples.seed_data import SEED_TEMPLES

    now = datetime.now(UTC)
    op.bulk_insert(temples, [
        {
            'id': t['id'],
            'name': t['name'],
            'name_ml': t.get('name_ml', ''),
            'deity': t['deity'],
            'district': t.get('district', ''),
            'town': t.get('town', ''),
            'town_ml': t.get('town_ml'),
            'lat': t['lat'],
            'lng': t['lng'],
            'famous_for': t.get('famous_for', ''),
            'vazhipadu': list(t.get('vazhipadu', [])),
            'reviewed': bool(t.get('reviewed', False)),
            'story': t.get('story'),
            'story_ml': t.get('story_ml'),
            # tuple-of-tuples in the seed; JSON has no tuple type.
            'hours': [list(w) for w in t['hours']] if t.get('hours') else None,
            'timings': t.get('timings'),
            'poojas': t.get('poojas'),
            'rating': t.get('rating'),
            'reviews': t.get('reviews'),
            'active': True,
            'image_key': None,
            'sort_order': i,
            'created_at': now,
            'updated_at': now,
        }
        for i, t in enumerate(SEED_TEMPLES)
    ])


def downgrade() -> None:
    op.drop_index(op.f('ix_temples_district'), table_name='temples')
    op.drop_index(op.f('ix_temples_deity'), table_name='temples')
    op.drop_table('temples')
