"""add github_repo_analysis_cache table

Revision ID: b9e1f4a7c2d8
Revises: f4a8b2c6d3e1
Create Date: 2026-07-29 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b9e1f4a7c2d8'
down_revision: Union[str, Sequence[str], None] = 'f4a8b2c6d3e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'github_repo_analysis_cache',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('repo_name', sa.String(length=255), nullable=False),
        sa.Column('last_commit_sha', sa.String(length=64), nullable=False),
        sa.Column('commit_hygiene', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('pr_stats', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('collaboration', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('fork_contribution_commits', sa.Integer(), server_default='0', nullable=False),
        sa.Column('architecture_assessment', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'repo_name', name='uq_repo_cache_user_repo'),
    )
    op.create_index(
        op.f('ix_github_repo_analysis_cache_user_id'), 'github_repo_analysis_cache', ['user_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_github_repo_analysis_cache_user_id'), table_name='github_repo_analysis_cache')
    op.drop_table('github_repo_analysis_cache')
