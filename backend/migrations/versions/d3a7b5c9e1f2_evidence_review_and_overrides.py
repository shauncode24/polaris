"""review state, hide flag and dedupe key on evidence rows, skill overrides, evidence timestamp

Revision ID: d3a7b5c9e1f2
Revises: c7e4a9b2d1f8
Create Date: 2026-11-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd3a7b5c9e1f2'
down_revision: Union[str, Sequence[str], None] = 'c7e4a9b2d1f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_REVIEWED_TABLES = ('experiences', 'projects', 'educations')


def upgrade() -> None:
    for table in _REVIEWED_TABLES:
        op.add_column(table, sa.Column('review_state', sa.String(length=20), nullable=False, server_default='auto'))
        op.add_column(table, sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default=sa.false()))
        op.add_column(table, sa.Column('dedupe_key', sa.String(length=255), nullable=True))
        op.create_index(f'ix_{table}_dedupe_key', table, ['dedupe_key'])

    op.create_index(
        'uq_project_user_github_repo', 'projects', ['user_id', 'github_repo_name'],
        unique=True, postgresql_where=sa.text("source = 'github'"),
    )

    op.add_column('users', sa.Column('evidence_updated_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        'user_skill_overrides',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('skill_id', sa.UUID(), nullable=False),
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id']),
        sa.PrimaryKeyConstraint('user_id', 'skill_id'),
    )


def downgrade() -> None:
    op.drop_table('user_skill_overrides')
    op.drop_column('users', 'evidence_updated_at')
    op.drop_index('uq_project_user_github_repo', table_name='projects')
    for table in reversed(_REVIEWED_TABLES):
        op.drop_index(f'ix_{table}_dedupe_key', table_name=table)
        op.drop_column(table, 'dedupe_key')
        op.drop_column(table, 'is_hidden')
        op.drop_column(table, 'review_state')
