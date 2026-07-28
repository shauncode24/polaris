"""add tagline and updated_at to projects

Revision ID: c9d4e2f8a1b3
Revises: b2c3d4e5f6a7
Create Date: 2026-07-28 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c9d4e2f8a1b3'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('tagline', sa.String(length=255), nullable=True))
    op.add_column(
        'projects',
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_column('projects', 'updated_at')
    op.drop_column('projects', 'tagline')