"""add interview_responses table

Revision ID: c4e8f21a9b6d
Revises: b7f2a48c1d9e
Create Date: 2026-07-25 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c4e8f21a9b6d'
down_revision: Union[str, Sequence[str], None] = 'b7f2a48c1d9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'interview_responses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(length=100), nullable=False),
        sa.Column('response_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_interview_responses_user_id'), 'interview_responses', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_interview_responses_user_id'), table_name='interview_responses')
    op.drop_table('interview_responses')