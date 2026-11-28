"""record when a user's email address was confirmed

Revision ID: e7b2c9d4f6a8
Revises: d6a1b8c3e5f7
Create Date: 2026-11-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7b2c9d4f6a8"
down_revision: Union[str, None] = "d6a1b8c3e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    # Google has already shown these addresses to be their owners'. Accounts with
    # only a password have never been checked.
    op.execute("UPDATE users SET email_verified_at = now() WHERE google_id IS NOT NULL")


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
