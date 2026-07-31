"""add engineering_identities and weekly_briefs tables

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-29 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'engineering_identities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('facts_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('narrative_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('analysis_degraded', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_engineering_identities_user_id'), 'engineering_identities', ['user_id'], unique=False
    )

    op.create_table(
        'weekly_briefs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('brief_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_weekly_briefs_user_id'), 'weekly_briefs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_weekly_briefs_user_id'), table_name='weekly_briefs')
    op.drop_table('weekly_briefs')
    op.drop_index(op.f('ix_engineering_identities_user_id'), table_name='engineering_identities')
    op.drop_table('engineering_identities')