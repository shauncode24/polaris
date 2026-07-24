"""add skill_aliases table

Revision ID: c7f3a91d2b4e
Revises: bea5f4751892
Create Date: 2026-07-24 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c7f3a91d2b4e'
down_revision: Union[str, Sequence[str], None] = 'bea5f4751892'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'skill_aliases',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('raw_string', sa.String(length=255), nullable=False),
        sa.Column('canonical_name', sa.String(length=255), nullable=True),
        sa.Column('is_valid_skill', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_skill_aliases_raw_string'), 'skill_aliases', ['raw_string'], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_skill_aliases_raw_string'), table_name='skill_aliases')
    op.drop_table('skill_aliases')