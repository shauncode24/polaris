"""store each repo's description and URL on its analysis row

Lets GitHub-sourced projects be built from the database alone, without a
live GitHub call. Existing rows are filled in on the next sync.

Revision ID: e4b8c2d6f1a3
Revises: d3a7b5c9e1f2
Create Date: 2026-11-25 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e4b8c2d6f1a3'
down_revision: Union[str, Sequence[str], None] = 'd3a7b5c9e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('github_project_analysis', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('github_project_analysis', sa.Column('html_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('github_project_analysis', 'html_url')
    op.drop_column('github_project_analysis', 'description')
