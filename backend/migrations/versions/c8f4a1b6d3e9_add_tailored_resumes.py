"""add tailored resumes

Revision ID: c8f4a1b6d3e9
Revises: b7e3f9a5c2d8
Create Date: 2026-11-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c8f4a1b6d3e9"
down_revision: Union[str, None] = "b7e3f9a5c2d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tailored_resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "job_intelligence_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_intelligence_profiles.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("content_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "job_intelligence_id", "version", name="uq_tailored_resume_version"),
    )
    op.create_index("ix_tailored_resumes_job_intelligence_id", "tailored_resumes", ["job_intelligence_id"])


def downgrade() -> None:
    op.drop_table("tailored_resumes")
