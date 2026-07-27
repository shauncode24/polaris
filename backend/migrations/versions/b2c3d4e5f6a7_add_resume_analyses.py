"""add resume_analyses table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-27 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'resume_analyses',
        sa.Column('id',            UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',       UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=False),
        sa.Column('resume_id',     UUID(as_uuid=True), sa.ForeignKey('resumes.id'), nullable=True),
        sa.Column('analysis_json', JSONB,               nullable=False, server_default='{}'),
        sa.Column('created_at',    sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )
    op.create_index('ix_resume_analyses_user_id', 'resume_analyses', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_resume_analyses_user_id', table_name='resume_analyses')
    op.drop_table('resume_analyses')
