"""astrologer directory moves from seed_data.py into the database

Same move as the temple directory (a7b8c9d0e1f2), for the same reason: the
directory was a Python literal bound in memory at service construction, so a
real practitioner could not be onboarded without a code change and a redeploy.

All 28 seeded entries are imported ACTIVE, preserving today's behaviour — they
are generated placeholders ("kozhikode-astro-1"), and the consumer app already
declines to render them (app-nithara/src/screens/Astro.tsx:128). Hiding them is
an operator action against PATCH /astrologers/{id}/active once Part 5 lands,
not something a migration should decide.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-27 00:30:00.000000

"""
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    astrologers = op.create_table(
        'astrologers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('name_ml', sa.String(), nullable=False),
        sa.Column('district', sa.String(), nullable=False),
        sa.Column('town', sa.String(), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lng', sa.Float(), nullable=False),
        sa.Column('specialties', sa.JSON(), nullable=False),
        sa.Column('experience_years', sa.Integer(), nullable=False),
        sa.Column('languages', sa.JSON(), nullable=False),
        sa.Column('rating', sa.Float(), nullable=False),
        sa.Column('bio_ml', sa.Text(), nullable=False),
        sa.Column('availability', sa.JSON(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('price_paise_per_min', sa.Integer(), nullable=False),
        sa.Column('photo_key', sa.String(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_astrologers_district'), 'astrologers', ['district'], unique=False
    )

    from app.modules.astrologers.seed_data import SEED_ASTROLOGERS

    now = datetime.now(UTC)
    op.bulk_insert(astrologers, [
        {
            'id': a['id'],
            'name': a['name'],
            'name_ml': a.get('name_ml', ''),
            'district': a['district'],
            'town': a.get('town', ''),
            'lat': a['lat'],
            'lng': a['lng'],
            'specialties': list(a.get('specialties', [])),
            'experience_years': int(a.get('experience_years', 0)),
            'languages': list(a.get('languages', [])),
            'rating': float(a.get('rating', 0.0)),
            'bio_ml': a.get('bio_ml', ''),
            'availability': [dict(w) for w in a.get('availability', [])],
            'active': True,
            # Consults are free today; 0 keeps the directory working until an
            # operator sets a real rate.
            'price_paise_per_min': 0,
            'photo_key': None,
            'sort_order': i,
            'created_at': now,
            'updated_at': now,
        }
        for i, a in enumerate(SEED_ASTROLOGERS)
    ])


def downgrade() -> None:
    op.drop_index(op.f('ix_astrologers_district'), table_name='astrologers')
    op.drop_table('astrologers')
