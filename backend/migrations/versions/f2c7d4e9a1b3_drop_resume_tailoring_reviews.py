"""drop the cached tailoring reports, replaced by the tailored resume

The rows were a cache of generated advice and nothing reads them any more. The
downgrade restores the table, empty.

Revision ID: f2c7d4e9a1b3
Revises: e1b6c3d8f5a2
Create Date: 2026-11-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f2c7d4e9a1b3"
down_revision: Union[str, None] = "e1b6c3d8f5a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "resume_tailoring_reviews"


def upgrade() -> None:
    op.drop_table(TABLE)  # its indexes and constraints go with it


def downgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("resume_id", sa.UUID(), nullable=False),
        sa.Column("report_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("job_intelligence_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="resume_tailoring_reviews_pkey"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="resume_tailoring_reviews_user_id_fkey"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], name="resume_tailoring_reviews_resume_id_fkey"),
        sa.ForeignKeyConstraint(
            ["job_intelligence_id"], ["job_intelligence_profiles.id"],
            name="resume_tailoring_reviews_job_intelligence_id_fkey",
        ),
        sa.UniqueConstraint("resume_id", "job_intelligence_id", name="uq_tailoring_resume_job"),
    )
    for column in ("user_id", "resume_id", "job_intelligence_id"):
        op.create_index(f"ix_{TABLE}_{column}", TABLE, [column])
