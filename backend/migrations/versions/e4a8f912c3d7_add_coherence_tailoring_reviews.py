"""add resume coherence and tailoring review tables

Revision ID: e4a8f912c3d7
Revises: a7fe2c654af1
Create Date: 2026-07-28 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e4a8f912c3d7'
down_revision: Union[str, Sequence[str], None] = 'a7fe2c654af1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'resume_coherence_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('resume_id', sa.UUID(), nullable=False),
        sa.Column('target_role', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('report_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('resume_id', 'target_role', name='uq_coherence_resume_role'),
    )
    op.create_index(op.f('ix_resume_coherence_reviews_user_id'), 'resume_coherence_reviews', ['user_id'], unique=False)
    op.create_index(op.f('ix_resume_coherence_reviews_resume_id'), 'resume_coherence_reviews', ['resume_id'], unique=False)

    op.create_table(
        'resume_tailoring_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('resume_id', sa.UUID(), nullable=False),
        sa.Column('job_description_id', sa.UUID(), nullable=False),
        sa.Column('report_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ),
        sa.ForeignKeyConstraint(['job_description_id'], ['job_descriptions.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('resume_id', 'job_description_id', name='uq_tailoring_resume_jd'),
    )
    op.create_index(op.f('ix_resume_tailoring_reviews_user_id'), 'resume_tailoring_reviews', ['user_id'], unique=False)
    op.create_index(op.f('ix_resume_tailoring_reviews_resume_id'), 'resume_tailoring_reviews', ['resume_id'], unique=False)
    op.create_index(op.f('ix_resume_tailoring_reviews_job_description_id'), 'resume_tailoring_reviews', ['job_description_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_resume_tailoring_reviews_job_description_id'), table_name='resume_tailoring_reviews')
    op.drop_index(op.f('ix_resume_tailoring_reviews_resume_id'), table_name='resume_tailoring_reviews')
    op.drop_index(op.f('ix_resume_tailoring_reviews_user_id'), table_name='resume_tailoring_reviews')
    op.drop_table('resume_tailoring_reviews')
    op.drop_index(op.f('ix_resume_coherence_reviews_resume_id'), table_name='resume_coherence_reviews')
    op.drop_index(op.f('ix_resume_coherence_reviews_user_id'), table_name='resume_coherence_reviews')
    op.drop_table('resume_coherence_reviews')