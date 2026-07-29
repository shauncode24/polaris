"""add fork/hygiene/collaboration/architecture signals to github_project_analysis

Revision ID: f4a8b2c6d3e1
Revises: a7fe2c654af1
Create Date: 2026-07-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f4a8b2c6d3e1'
down_revision: Union[str, Sequence[str], None] = 'a7fe2c654af1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'github_project_analysis',
        sa.Column('is_fork', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        'github_project_analysis',
        sa.Column('is_meaningful_fork_contribution', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        'github_project_analysis',
        sa.Column('commit_hygiene_score', sa.Float(), server_default='0.0', nullable=False),
    )
    op.add_column(
        'github_project_analysis',
        sa.Column('collaboration_mode', sa.String(length=20), server_default='solo', nullable=False),
    )
    op.add_column(
        'github_project_analysis',
        sa.Column('collaboration_score', sa.Float(), server_default='0.0', nullable=False),
    )
    op.add_column(
        'github_project_analysis',
        sa.Column('architecture_assessment', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('github_project_analysis', 'architecture_assessment')
    op.drop_column('github_project_analysis', 'collaboration_score')
    op.drop_column('github_project_analysis', 'collaboration_mode')
    op.drop_column('github_project_analysis', 'commit_hygiene_score')
    op.drop_column('github_project_analysis', 'is_meaningful_fork_contribution')
    op.drop_column('github_project_analysis', 'is_fork')