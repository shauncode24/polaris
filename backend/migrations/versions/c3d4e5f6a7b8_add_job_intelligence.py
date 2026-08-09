# backend/migrations/versions/c3d4e5f6a7b8_add_job_intelligence.py
"""add job_intelligence_profiles, company_intelligence_profiles, gap_analysis_results

Revision ID: c3d4e5f6a7b8
Revises: b1c3d5e7f9a1
Create Date: 2026-08-07 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b1c3d5e7f9a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'job_intelligence_profiles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('source_text_hash', sa.String(length=64), nullable=False),
        sa.Column('profile_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_job_intelligence_profiles_user_id'), 'job_intelligence_profiles', ['user_id'], unique=False)
    op.create_index(op.f('ix_job_intelligence_profiles_source_text_hash'), 'job_intelligence_profiles', ['source_text_hash'], unique=False)

    op.create_table(
        'company_intelligence_profiles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('source_text_hash', sa.String(length=64), nullable=False),
        sa.Column('profile_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_company_intelligence_profiles_user_id'), 'company_intelligence_profiles', ['user_id'], unique=False)
    op.create_index(op.f('ix_company_intelligence_profiles_source_text_hash'), 'company_intelligence_profiles', ['source_text_hash'], unique=False)

    op.create_table(
        'gap_analysis_results',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('job_intelligence_id', sa.UUID(), nullable=False),
        sa.Column('company_intelligence_id', sa.UUID(), nullable=True),
        sa.Column('report_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('category_breakdown_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('overall_match_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('narrative_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('analysis_degraded', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['job_intelligence_id'], ['job_intelligence_profiles.id'], ),
        sa.ForeignKeyConstraint(['company_intelligence_id'], ['company_intelligence_profiles.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_gap_analysis_results_user_id'), 'gap_analysis_results', ['user_id'], unique=False)
    op.create_index(op.f('ix_gap_analysis_results_job_intelligence_id'), 'gap_analysis_results', ['job_intelligence_id'], unique=False)

    op.add_column('job_descriptions', sa.Column('job_intelligence_id', sa.UUID(), nullable=True))
    op.add_column('job_descriptions', sa.Column('company_intelligence_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_job_descriptions_job_intelligence_id', 'job_descriptions',
        'job_intelligence_profiles', ['job_intelligence_id'], ['id'],
    )
    op.create_foreign_key(
        'fk_job_descriptions_company_intelligence_id', 'job_descriptions',
        'company_intelligence_profiles', ['company_intelligence_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_job_descriptions_company_intelligence_id', 'job_descriptions', type_='foreignkey')
    op.drop_constraint('fk_job_descriptions_job_intelligence_id', 'job_descriptions', type_='foreignkey')
    op.drop_column('job_descriptions', 'company_intelligence_id')
    op.drop_column('job_descriptions', 'job_intelligence_id')

    op.drop_index(op.f('ix_gap_analysis_results_job_intelligence_id'), table_name='gap_analysis_results')
    op.drop_index(op.f('ix_gap_analysis_results_user_id'), table_name='gap_analysis_results')
    op.drop_table('gap_analysis_results')

    op.drop_index(op.f('ix_company_intelligence_profiles_source_text_hash'), table_name='company_intelligence_profiles')
    op.drop_index(op.f('ix_company_intelligence_profiles_user_id'), table_name='company_intelligence_profiles')
    op.drop_table('company_intelligence_profiles')

    op.drop_index(op.f('ix_job_intelligence_profiles_source_text_hash'), table_name='job_intelligence_profiles')
    op.drop_index(op.f('ix_job_intelligence_profiles_user_id'), table_name='job_intelligence_profiles')
    op.drop_table('job_intelligence_profiles')