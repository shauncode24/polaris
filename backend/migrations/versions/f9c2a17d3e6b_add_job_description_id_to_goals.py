"""add job_description_id to goals

Revision ID: f9c2a17d3e6b
Revises: a8f3d2c91e4b
Create Date: 2026-07-27 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f9c2a17d3e6b'
down_revision: Union[str, Sequence[str], None] = 'a8f3d2c91e4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('goals', sa.Column('job_description_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_goals_job_description_id', 'goals', 'job_descriptions',
        ['job_description_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_goals_job_description_id', 'goals', type_='foreignkey')
    op.drop_column('goals', 'job_description_id')