"""add practice attempts

Revision ID: c5f0a7b2d4e6
Revises: b4e9f6a1c3d5
Create Date: 2026-11-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c5f0a7b2d4e6"
down_revision: Union[str, None] = "b4e9f6a1c3d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "practice_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "question_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("feedback_json", postgresql.JSONB(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_practice_attempts_question_id", "practice_attempts", ["question_id"])
    op.create_index("ix_practice_attempts_user_id", "practice_attempts", ["user_id"])


def downgrade() -> None:
    op.drop_table("practice_attempts")
