"""mark one job per user as the primary target

Revision ID: f1a7c3e9b5d2
Revises: e4b8c2d6f1a3
Create Date: 2026-11-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a7c3e9b5d2"
down_revision: Union[str, None] = "e4b8c2d6f1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "job_intelligence_profiles",
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    # At most one primary job per user.
    op.create_index(
        "uq_job_intelligence_primary", "job_intelligence_profiles", ["user_id"],
        unique=True, postgresql_where=sa.text("is_primary"),
    )


def downgrade() -> None:
    op.drop_index("uq_job_intelligence_primary", table_name="job_intelligence_profiles")
    op.drop_column("job_intelligence_profiles", "is_primary")
