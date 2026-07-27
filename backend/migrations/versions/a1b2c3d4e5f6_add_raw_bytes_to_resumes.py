"""add raw_bytes to resumes table

Revision ID: a1b2c3d4e5f6
Revises: f3c9d1a84e6b
Create Date: 2026-07-27 16:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = ('f3c9d1a84e6b', 'f9c2a17d3e6b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'resumes',
        sa.Column('raw_bytes', sa.LargeBinary(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('resumes', 'raw_bytes')
