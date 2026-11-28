"""add the phone number and LinkedIn address a user puts on a resume

Revision ID: e1b6c3d8f5a2
Revises: d9a5b2c7e4f1
Create Date: 2026-11-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1b6c3d8f5a2"
down_revision: Union[str, None] = "d9a5b2c7e4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(40), nullable=True))
    op.add_column("users", sa.Column("linkedin_url", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "linkedin_url")
    op.drop_column("users", "phone")
