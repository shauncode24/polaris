"""add career_plans table

Revision ID: b7f2a48c1d9e
Revises: a2d5e6f1b3c8
Create Date: 2026-07-25 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b7f2a48c1d9e'
down_revision: Union[str, Sequence[str], None] = 'a2d5e6f1b3c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'career_plans',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('goal_id', sa.UUID(), nullable=False),
        sa.Column('plan_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_career_plans_user_id'), 'career_plans', ['user_id'], unique=False)
    op.create_index(op.f('ix_career_plans_goal_id'), 'career_plans', ['goal_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_career_plans_goal_id'), table_name='career_plans')
    op.drop_index(op.f('ix_career_plans_user_id'), table_name='career_plans')
    op.drop_table('career_plans')