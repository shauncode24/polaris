"""add repo_created_at to github_project_analysis

Revision ID: d5e6f7a8b9c0
Revises: c1a2b3d4e5f6
Create Date: 2026-07-29 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'b93753a4cf90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'github_project_analysis',
        sa.Column('repo_created_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('github_project_analysis', 'repo_created_at')