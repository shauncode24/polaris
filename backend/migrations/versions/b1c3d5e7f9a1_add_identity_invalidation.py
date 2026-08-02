"""add invalidation fields to engineering_identities

Revision ID: b1c3d5e7f9a1
Revises: a4b7d2f91c68
Create Date: 2026-08-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b1c3d5e7f9a1'
down_revision: Union[str, Sequence[str], None] = 'a4b7d2f91c68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'engineering_identities',
        sa.Column('is_invalidated', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column('engineering_identities', sa.Column('invalidated_reason', sa.Text(), nullable=True))
    op.add_column(
        'engineering_identities',
        sa.Column('invalidated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('engineering_identities', 'invalidated_at')
    op.drop_column('engineering_identities', 'invalidated_reason')
    op.drop_column('engineering_identities', 'is_invalidated')