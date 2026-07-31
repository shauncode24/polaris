"""add project claim audit, intelligence, interview questions, and portfolio narrative caching tables

Revision ID: c2f8a4e91d05
Revises: 94e435c82910
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c2f8a4e91d05'
down_revision: Union[str, Sequence[str], None] = 'a3f7c92d1b0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old project_intelligence_reviews table first (which was created in c1a9e5f27b4d)
    # as its schema changes completely in this new revision.
    op.drop_table('project_intelligence_reviews')

    op.create_table(
        'project_claim_audit_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('report_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_claim_audit_project'),
    )
    op.create_index(
        op.f('ix_project_claim_audit_reviews_user_id'), 'project_claim_audit_reviews', ['user_id'], unique=False
    )

    op.create_table(
        'project_intelligence_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('framing', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('comparison_target', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('report_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'framing', 'comparison_target', name='uq_intelligence_project_framing'),
    )
    op.create_index(
        op.f('ix_project_intelligence_reviews_user_id'), 'project_intelligence_reviews', ['user_id'], unique=False
    )

    op.create_table(
        'project_interview_questions_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('report_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_interview_questions_project'),
    )
    op.create_index(
        op.f('ix_project_interview_questions_reviews_user_id'),
        'project_interview_questions_reviews', ['user_id'], unique=False
    )

    op.create_table(
        'portfolio_narrative_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('report_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_portfolio_narrative_reviews_user_id'), 'portfolio_narrative_reviews', ['user_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_portfolio_narrative_reviews_user_id'), table_name='portfolio_narrative_reviews')
    op.drop_table('portfolio_narrative_reviews')
    op.drop_index(
        op.f('ix_project_interview_questions_reviews_user_id'), table_name='project_interview_questions_reviews'
    )
    op.drop_table('project_interview_questions_reviews')
    op.drop_index(op.f('ix_project_intelligence_reviews_user_id'), table_name='project_intelligence_reviews')
    op.drop_table('project_intelligence_reviews')
    op.drop_index(op.f('ix_project_claim_audit_reviews_user_id'), table_name='project_claim_audit_reviews')
    op.drop_table('project_claim_audit_reviews')

    # Recreate the old project_intelligence_reviews table as defined in c1a9e5f27b4d
    op.create_table(
        'project_intelligence_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('framing', sa.String(length=255), nullable=False),
        sa.Column('comparison_target', sa.String(length=255), nullable=True),
        sa.Column('review_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_project_intelligence_reviews_user_id'), 'project_intelligence_reviews', ['user_id'], unique=False
    )
    op.create_index(
        op.f('ix_project_intelligence_reviews_project_id'), 'project_intelligence_reviews', ['project_id'], unique=False
    )