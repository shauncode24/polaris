"""add resume_id to experiences and projects

Revision ID: a2d5e6f1b3c8
Revises: f3c9d1a84e6b
Create Date: 2026-07-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a2d5e6f1b3c8'
down_revision: Union[str, Sequence[str], None] = 'f3c9d1a84e6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('experiences', sa.Column('resume_id', sa.UUID(), nullable=True))
    op.add_column('projects', sa.Column('resume_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_experiences_resume_id', 'experiences', 'resumes', ['resume_id'], ['id'])
    op.create_foreign_key('fk_projects_resume_id', 'projects', 'resumes', ['resume_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_projects_resume_id', 'projects', type_='foreignkey')
    op.drop_constraint('fk_experiences_resume_id', 'experiences', type_='foreignkey')
    op.drop_column('projects', 'resume_id')
    op.drop_column('experiences', 'resume_id')
