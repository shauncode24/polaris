"""add explicit github linking to projects + project_intelligence_reviews

Revision ID: c1a9e5f27b4d
Revises: 94e435c82910
Create Date: 2026-07-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c1a9e5f27b4d'
down_revision: Union[str, Sequence[str], None] = '94e435c82910'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('github_repo_name', sa.String(length=255), nullable=True))
    op.add_column(
        'projects',
        sa.Column('repo_link_status', sa.String(length=30), nullable=False, server_default='unmatched'),
    )

    op.create_table(
        'project_intelligence_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('framing', sa.String(length=255), nullable=False),
        sa.Column('comparison_target', sa.String(length=255), nullable=True),
        sa.Column('review_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_project_intelligence_reviews_user_id'), 'project_intelligence_reviews', ['user_id'], unique=False
    )
    op.create_index(
        op.f('ix_project_intelligence_reviews_project_id'), 'project_intelligence_reviews', ['project_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_project_intelligence_reviews_project_id'), table_name='project_intelligence_reviews')
    op.drop_index(op.f('ix_project_intelligence_reviews_user_id'), table_name='project_intelligence_reviews')
    op.drop_table('project_intelligence_reviews')
    op.drop_column('projects', 'repo_link_status')
    op.drop_column('projects', 'github_repo_name')