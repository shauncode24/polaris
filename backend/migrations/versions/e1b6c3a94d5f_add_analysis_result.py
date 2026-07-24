"""add analysis_result to job_descriptions

Revision ID: e1b6c3a94d5f
Revises: d8a4b2c91f3a
Create Date: 2026-07-24 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e1b6c3a94d5f'
down_revision: Union[str, Sequence[str], None] = 'd8a4b2c91f3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'job_descriptions',
        sa.Column('analysis_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('job_descriptions', 'analysis_result')