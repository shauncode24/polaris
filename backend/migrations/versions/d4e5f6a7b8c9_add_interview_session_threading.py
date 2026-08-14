"""add interview session threading

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('interview_responses', sa.Column('session_id', sa.UUID(), nullable=True))
    op.add_column('interview_responses', sa.Column('parent_response_id', sa.UUID(), nullable=True))
    op.add_column('interview_responses', sa.Column('correction_of', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_interview_responses_parent_response_id', 'interview_responses',
        'interview_responses', ['parent_response_id'], ['id'],
    )
    op.create_foreign_key(
        'fk_interview_responses_correction_of', 'interview_responses',
        'interview_responses', ['correction_of'], ['id'],
    )
    op.create_index(
        op.f('ix_interview_responses_session_id'), 'interview_responses', ['session_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_interview_responses_session_id'), table_name='interview_responses')
    op.drop_constraint('fk_interview_responses_correction_of', 'interview_responses', type_='foreignkey')
    op.drop_constraint('fk_interview_responses_parent_response_id', 'interview_responses', type_='foreignkey')
    op.drop_column('interview_responses', 'correction_of')
    op.drop_column('interview_responses', 'parent_response_id')
    op.drop_column('interview_responses', 'session_id')