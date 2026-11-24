"""add linkedin_profiles, provenance source columns, missing indexes

The models gained these (LinkedIn ingestion, per-row provenance) without a
migration, so a database built from migrations did not match the models and
any insert into projects/experiences/educations failed on the missing
`source` column.

Revision ID: a9c1e7d4b2f6
Revises: 4f3bed28b4b2
Create Date: 2026-11-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a9c1e7d4b2f6'
down_revision: Union[str, Sequence[str], None] = '4f3bed28b4b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'linkedin_profiles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('parsed_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_linkedin_profiles_user_id', 'linkedin_profiles', ['user_id'])

    # Existing rows all came from resume ingestion, hence the 'resume' default.
    for table in ('experiences', 'educations', 'projects'):
        op.add_column(
            table,
            sa.Column('source', sa.String(length=20), nullable=False, server_default='resume'),
        )

    op.create_index(
        'ix_project_claim_audit_reviews_project_id', 'project_claim_audit_reviews', ['project_id']
    )
    op.create_index(
        'ix_project_intelligence_reviews_project_id', 'project_intelligence_reviews', ['project_id']
    )
    op.create_index(
        'ix_project_interview_questions_reviews_project_id',
        'project_interview_questions_reviews',
        ['project_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_project_interview_questions_reviews_project_id', table_name='project_interview_questions_reviews')
    op.drop_index('ix_project_intelligence_reviews_project_id', table_name='project_intelligence_reviews')
    op.drop_index('ix_project_claim_audit_reviews_project_id', table_name='project_claim_audit_reviews')
    for table in ('projects', 'educations', 'experiences'):
        op.drop_column(table, 'source')
    op.drop_index('ix_linkedin_profiles_user_id', table_name='linkedin_profiles')
    op.drop_table('linkedin_profiles')
