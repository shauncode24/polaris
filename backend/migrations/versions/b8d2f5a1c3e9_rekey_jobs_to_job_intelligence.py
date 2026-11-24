"""re-key goals and tailoring reviews onto job_intelligence_profiles; drop job_descriptions

JobIntelligenceProfileRow is now the single job record. Existing
job_descriptions rows are mapped to a profile either through their own
job_intelligence_id or, for older rows without one, through the same
sha256(stripped raw_text) hash the app uses as source_text_hash.

Data handling:
  * goals.job_description_id   -> goals.job_intelligence_id. A goal whose job
    cannot be mapped keeps existing but loses its job link.
  * resume_tailoring_reviews   -> re-keyed the same way. Rows that cannot be
    mapped are deleted: they are a regenerable cache.
  * capability_requirements    -> dropped (never read or written by the app).
  * job_descriptions           -> dropped.

The downgrade restores the schema, not the data.

Revision ID: b8d2f5a1c3e9
Revises: a9c1e7d4b2f6
Create Date: 2026-11-25 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b8d2f5a1c3e9'
down_revision: Union[str, Sequence[str], None] = 'a9c1e7d4b2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # jd_id -> job_intelligence_id, resolved directly or by text hash.
    op.execute(
        r"""
        CREATE TEMP TABLE jd_to_job AS
        SELECT
            jd.id AS jd_id,
            COALESCE(
                jd.job_intelligence_id,
                (
                    SELECT p.id
                    FROM job_intelligence_profiles p
                    WHERE p.user_id = jd.user_id
                      AND p.source_text_hash = encode(
                          sha256(convert_to(regexp_replace(jd.raw_text, '^\s+|\s+$', '', 'g'), 'UTF8')),
                          'hex'
                      )
                    ORDER BY p.created_at DESC
                    LIMIT 1
                )
            ) AS job_intelligence_id
        FROM job_descriptions jd
        """
    )

    # --- goals ---------------------------------------------------------
    op.add_column('goals', sa.Column('job_intelligence_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'goals_job_intelligence_id_fkey', 'goals', 'job_intelligence_profiles',
        ['job_intelligence_id'], ['id'],
    )
    op.execute(
        """
        UPDATE goals g
        SET job_intelligence_id = m.job_intelligence_id
        FROM jd_to_job m
        WHERE g.job_description_id = m.jd_id
        """
    )
    op.drop_column('goals', 'job_description_id')

    # --- resume_tailoring_reviews -------------------------------------
    op.add_column('resume_tailoring_reviews', sa.Column('job_intelligence_id', sa.UUID(), nullable=True))
    op.execute(
        """
        UPDATE resume_tailoring_reviews r
        SET job_intelligence_id = m.job_intelligence_id
        FROM jd_to_job m
        WHERE r.job_description_id = m.jd_id
        """
    )
    op.execute("DELETE FROM resume_tailoring_reviews WHERE job_intelligence_id IS NULL")
    # Two legacy jobs can map to one profile: keep only the newest report.
    op.execute(
        """
        DELETE FROM resume_tailoring_reviews a
        USING resume_tailoring_reviews b
        WHERE a.resume_id = b.resume_id
          AND a.job_intelligence_id = b.job_intelligence_id
          AND (a.created_at < b.created_at OR (a.created_at = b.created_at AND a.id < b.id))
        """
    )
    # Dropping the column also drops its FK, unique constraint and index.
    op.drop_column('resume_tailoring_reviews', 'job_description_id')
    op.alter_column('resume_tailoring_reviews', 'job_intelligence_id', nullable=False)
    op.create_foreign_key(
        'resume_tailoring_reviews_job_intelligence_id_fkey', 'resume_tailoring_reviews',
        'job_intelligence_profiles', ['job_intelligence_id'], ['id'],
    )
    op.create_index(
        'ix_resume_tailoring_reviews_job_intelligence_id', 'resume_tailoring_reviews', ['job_intelligence_id']
    )
    op.create_unique_constraint(
        'uq_tailoring_resume_job', 'resume_tailoring_reviews', ['resume_id', 'job_intelligence_id']
    )

    # --- legacy tables ---------------------------------------------------
    op.drop_table('capability_requirements')
    op.drop_table('job_descriptions')
    op.execute("DROP TABLE jd_to_job")


def downgrade() -> None:
    """Restores the old schema only; job rows, goal links and cached
    tailoring reports are not restored."""
    op.create_table(
        'job_descriptions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=255), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('extracted_requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('analysis_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('job_intelligence_id', sa.UUID(), nullable=True),
        sa.Column('company_intelligence_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['job_intelligence_id'], ['job_intelligence_profiles.id']),
        sa.ForeignKeyConstraint(['company_intelligence_id'], ['company_intelligence_profiles.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_job_descriptions_user_id', 'job_descriptions', ['user_id'])
    op.create_table(
        'capability_requirements',
        sa.Column('job_description_id', sa.UUID(), nullable=False),
        sa.Column('capability_id', sa.UUID(), nullable=False),
        sa.Column('importance', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['job_description_id'], ['job_descriptions.id']),
        sa.ForeignKeyConstraint(['capability_id'], ['capabilities.id']),
        sa.PrimaryKeyConstraint('job_description_id', 'capability_id'),
    )

    op.execute("DELETE FROM resume_tailoring_reviews")
    op.drop_column('resume_tailoring_reviews', 'job_intelligence_id')
    op.add_column('resume_tailoring_reviews', sa.Column('job_description_id', sa.UUID(), nullable=False))
    op.create_foreign_key(
        'resume_tailoring_reviews_job_description_id_fkey', 'resume_tailoring_reviews',
        'job_descriptions', ['job_description_id'], ['id'],
    )
    op.create_index(
        'ix_resume_tailoring_reviews_job_description_id', 'resume_tailoring_reviews', ['job_description_id']
    )
    op.create_unique_constraint(
        'uq_tailoring_resume_jd', 'resume_tailoring_reviews', ['resume_id', 'job_description_id']
    )

    op.drop_column('goals', 'job_intelligence_id')
    op.add_column('goals', sa.Column('job_description_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'goals_job_description_id_fkey', 'goals', 'job_descriptions', ['job_description_id'], ['id']
    )
