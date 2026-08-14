# backend/migrations/versions/e5f6a7b8c9d0_add_competency_tagging.py
"""add competency tags to projects/experiences and competency_tag_cache table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('competency_tags', postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column('experiences', sa.Column('competency_tags', postgresql.ARRAY(sa.String()), nullable=True))

    op.create_table(
        'competency_tag_cache',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('text_hash', sa.String(length=64), nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_competency_tag_cache_text_hash'), 'competency_tag_cache', ['text_hash'], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_competency_tag_cache_text_hash'), table_name='competency_tag_cache')
    op.drop_table('competency_tag_cache')
    op.drop_column('experiences', 'competency_tags')
    op.drop_column('projects', 'competency_tags')