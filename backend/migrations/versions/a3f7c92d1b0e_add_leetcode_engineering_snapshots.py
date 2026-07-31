"""add leetcode_engineering_snapshots table

Revision ID: a3f7c92d1b0e
Revises: 94e435c82910
Create Date: 2026-07-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a3f7c92d1b0e'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'leetcode_engineering_snapshots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('leetcode_snapshot_id', sa.UUID(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_event', sa.String(length=50), nullable=False),
        sa.Column('leetcode_score', sa.Float(), nullable=False),
        sa.Column('github_score', sa.Float(), nullable=False),
        sa.Column('quadrant_label', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('company_readiness', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('resume_claims', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['leetcode_snapshot_id'], ['profile_snapshots.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_leetcode_engineering_snapshots_user_id'),
        'leetcode_engineering_snapshots', ['user_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_leetcode_engineering_snapshots_user_id'), table_name='leetcode_engineering_snapshots')
    op.drop_table('leetcode_engineering_snapshots')