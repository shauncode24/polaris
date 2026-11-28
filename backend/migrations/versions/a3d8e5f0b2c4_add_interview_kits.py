"""add interview kits and their questions

Revision ID: a3d8e5f0b2c4
Revises: f2c7d4e9a1b3
Create Date: 2026-11-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a3d8e5f0b2c4"
down_revision: Union[str, None] = "f2c7d4e9a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_kits",
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
        sa.Column("seniority", sa.String(20), nullable=False),
        sa.Column("notice", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "job_intelligence_id", "version", name="uq_interview_kit_version"),
    )
    op.create_index("ix_interview_kits_job_intelligence_id", "interview_kits", ["job_intelligence_id"])

    op.create_table(
        "interview_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "kit_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interview_kits.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("skills", postgresql.JSONB(), nullable=False),
        sa.Column("competencies", postgresql.JSONB(), nullable=False),
        sa.Column("origin", sa.String(10), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=False),
        sa.Column("thin_evidence", sa.Boolean(), nullable=True),
        sa.UniqueConstraint("kit_id", "position", name="uq_interview_question_position"),
    )


def downgrade() -> None:
    op.drop_table("interview_questions")
    op.drop_table("interview_kits")
