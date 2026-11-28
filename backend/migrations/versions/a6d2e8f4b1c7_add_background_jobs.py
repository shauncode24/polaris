"""add background jobs

Revision ID: a6d2e8f4b1c7
Revises: f1a7c3e9b5d2
Create Date: 2026-11-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a6d2e8f4b1c7"
down_revision: Union[str, None] = "f1a7c3e9b5d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("kind", sa.String(60), nullable=False),
        sa.Column("dedupe_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("error_status", sa.Integer(), nullable=True),
        sa.Column("error_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    # The same work can't run twice at once for one user.
    op.create_index(
        "uq_background_jobs_running", "background_jobs", ["user_id", "dedupe_key"],
        unique=True, postgresql_where=sa.text("status = 'running'"),
    )
    op.create_index("ix_background_jobs_user_created", "background_jobs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("background_jobs")
