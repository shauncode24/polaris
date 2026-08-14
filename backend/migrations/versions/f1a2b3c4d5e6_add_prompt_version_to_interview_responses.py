# backend/migrations/versions/f1a2b3c4d5e6_add_prompt_version_to_interview_responses.py
"""add prompt_version to interview_responses

Tracks which prompt version produced each persisted InterviewResponse, so a
bad answer can be traced back to the exact prompt that generated it — an
explicit Phase 3 deliverable from the implementation plan (§Q, §R).

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-08-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable — existing rows simply have no prompt_version (that's correct
    # and expected; they were generated before version tracking was added).
    op.add_column(
        'interview_responses',
        sa.Column('prompt_version', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('interview_responses', 'prompt_version')
