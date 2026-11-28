"""add when an interview kit's evidence was matched

Revision ID: b4e9f6a1c3d5
Revises: a3d8e5f0b2c4
Create Date: 2026-11-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4e9f6a1c3d5"
down_revision: Union[str, None] = "a3d8e5f0b2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("interview_kits", sa.Column("evidence_mapped_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("interview_kits", sa.Column("evidence_notice", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("interview_kits", "evidence_notice")
    op.drop_column("interview_kits", "evidence_mapped_at")
