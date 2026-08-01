"""add source_event to engineering_identities

Revision ID: a4b7d2f91c68
Revises: f2a9c3d8e1b4
Create Date: 2026-08-01 00:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a4b7d2f91c68'
down_revision: Union[str, Sequence[str], None] = 'f2a9c3d8e1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Mirrors LeetcodeEngineeringSnapshot.source_event — the proven,
    # already-working "append-only, tagged with the real trigger" pattern
    # this fix extends to EngineeringIdentity.
    op.add_column(
        'engineering_identities',
        sa.Column('source_event', sa.String(length=50), nullable=False, server_default='manual_refresh'),
    )


def downgrade() -> None:
    op.drop_column('engineering_identities', 'source_event')