# backend/migrations/versions/d8a4b2c91f3a_add_github_analysis_tables.py
"""add github_project_analysis and portfolio_analysis

Revision ID: d8a4b2c91f3a
Revises: c7f3a91d2b4e
Create Date: 2026-07-24 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd8a4b2c91f3a'
down_revision: Union[str, Sequence[str], None] = 'c7f3a91d2b4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'github_project_analysis',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('repo_name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('primary_language', sa.String(length=50), nullable=True),
        sa.Column('technologies', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('capabilities', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('is_backend', sa.Boolean(), nullable=False),
        sa.Column('is_frontend', sa.Boolean(), nullable=False),
        sa.Column('is_database', sa.Boolean(), nullable=False),
        sa.Column('is_containerized', sa.Boolean(), nullable=False),
        sa.Column('has_readme', sa.Boolean(), nullable=False),
        sa.Column('has_tests', sa.Boolean(), nullable=False),
        sa.Column('has_ci', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_activity_days', sa.Integer(), nullable=True),
        sa.Column('activity_score', sa.Float(), nullable=False),
        sa.Column('quality_score', sa.Float(), nullable=False),
        sa.Column('maintenance_score', sa.Float(), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'repo_name', name='uq_repo_analysis_user_repo'),
    )
    op.create_index(
        op.f('ix_github_project_analysis_user_id'), 'github_project_analysis', ['user_id'], unique=False
    )

    op.create_table(
        'portfolio_analysis',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('snapshot_id', sa.UUID(), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('active_projects', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('neglected_projects', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('strongest_projects', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('recently_active_projects', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('technology_distribution', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('quality_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('observations', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['snapshot_id'], ['profile_snapshots.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_portfolio_analysis_user_id'), 'portfolio_analysis', ['user_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_portfolio_analysis_user_id'), table_name='portfolio_analysis')
    op.drop_table('portfolio_analysis')
    op.drop_index(op.f('ix_github_project_analysis_user_id'), table_name='github_project_analysis')
    op.drop_table('github_project_analysis')