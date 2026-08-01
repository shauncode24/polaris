"""add user_id to skill_evidence and backfill

Revision ID: f2a9c3d8e1b4
Revises: e1b3dac5f6ce
Create Date: 2026-08-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f2a9c3d8e1b4'
down_revision: Union[str, Sequence[str], None] = 'e1b3dac5f6ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add nullable first — this is a data-carrying migration.
    #    SkillEvidence previously had NO user_id at all, meaning every
    #    reader that queried by skill_id alone silently pooled evidence
    #    across EVERY user in the system (see gap_analysis.py,
    #    role_fit_scoping.py, get_all_skill_confidences, and
    #    interview/context_builder.py, all fixed alongside this migration).
    op.add_column('skill_evidence', sa.Column('user_id', sa.UUID(), nullable=True))

    # 2. Backfill from whichever real, user-owned row each evidence row
    #    traces back to via its source_id.
    op.execute("""
        UPDATE skill_evidence se
        SET user_id = p.user_id
        FROM projects p
        WHERE se.source_type = 'project' AND se.source_id = p.id
    """)
    op.execute("""
        UPDATE skill_evidence se
        SET user_id = e.user_id
        FROM experiences e
        WHERE se.source_type = 'experience' AND se.source_id = e.id
    """)
    op.execute("""
        UPDATE skill_evidence se
        SET user_id = g.user_id
        FROM github_project_analysis g
        WHERE se.source_type = 'github_repo' AND se.source_id = g.id
    """)
    op.execute("""
        UPDATE skill_evidence se
        SET user_id = c.user_id
        FROM certificates c
        WHERE se.source_type = 'certificate' AND se.source_id = c.id
    """)

    # 3. leetcode_tag rows have NO source_id at all (see leetcode_sync.py
    #    — there's no per-tag DB row to reference), so they cannot be
    #    backfilled by any join. Rather than leave these as an ambiguous,
    #    ownerless liability, delete them: a LeetCode re-sync regenerates
    #    them correctly, now with user_id set at write time from day one.
    op.execute("DELETE FROM skill_evidence WHERE user_id IS NULL")

    # 4. Every remaining row now has a real, verified owner — enforce it.
    op.alter_column('skill_evidence', 'user_id', nullable=False)
    op.create_foreign_key(
        'fk_skill_evidence_user_id', 'skill_evidence', 'users', ['user_id'], ['id'],
    )
    op.create_index(op.f('ix_skill_evidence_user_id'), 'skill_evidence', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_skill_evidence_user_id'), table_name='skill_evidence')
    op.drop_constraint('fk_skill_evidence_user_id', 'skill_evidence', type_='foreignkey')
    op.drop_column('skill_evidence', 'user_id')