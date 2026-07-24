"""add resumes and resume_reviews tables

Revision ID: f3c9d1a84e6b
Revises: e1b6c3a94d5f
Create Date: 2026-07-25 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f3c9d1a84e6b'
down_revision: Union[str, Sequence[str], None] = 'e1b6c3a94d5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'resumes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_resumes_user_id'), 'resumes', ['user_id'], unique=False)

    op.create_table(
        'resume_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('resume_id', sa.UUID(), nullable=True),
        sa.Column('review_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_resume_reviews_user_id'), 'resume_reviews', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_resume_reviews_user_id'), table_name='resume_reviews')
    op.drop_table('resume_reviews')
    op.drop_index(op.f('ix_resumes_user_id'), table_name='resumes')
    op.drop_table('resumes')