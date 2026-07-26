"""add github/leetcode sync credentials to users

Revision ID: a8f3d2c91e4b
Revises: e7a1c9d3f2b5
Create Date: 2026-07-26 15:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a8f3d2c91e4b'
down_revision: Union[str, Sequence[str], None] = 'e7a1c9d3f2b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('github_username', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('github_token', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('leetcode_username', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'leetcode_username')
    op.drop_column('users', 'github_token')
    op.drop_column('users', 'github_username')