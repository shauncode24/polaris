"""drop tables no code reads or writes

agent_feedback, goal_events, readiness_scores and embeddings were created as
placeholders for features that were never built. All four were empty. The
downgrade recreates them (empty).

The `vector` extension is left in place: the first migration creates it and
replays of the history import pgvector.

Revision ID: c7e4a9b2d1f8
Revises: b8d2f5a1c3e9
Create Date: 2026-11-25 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'c7e4a9b2d1f8'
down_revision: Union[str, Sequence[str], None] = 'b8d2f5a1c3e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('agent_feedback')
    op.drop_table('goal_events')
    op.drop_table('readiness_scores')
    op.drop_table('embeddings')


def downgrade() -> None:
    op.create_table(
        'embeddings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_table', sa.String(length=100), nullable=False),
        sa.Column('source_id', sa.UUID(), nullable=False),
        sa.Column('vector', Vector(1536), nullable=False),
        sa.Column('text_chunk', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'readiness_scores',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('goal_id', sa.UUID(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('basis', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_readiness_scores_user_id', 'readiness_scores', ['user_id'])
    op.create_table(
        'goal_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('goal_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_goal_events_goal_id', 'goal_events', ['goal_id'])
    op.create_table(
        'agent_feedback',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('agent_name', sa.String(length=100), nullable=False),
        sa.Column('input_ref', sa.String(length=500), nullable=True),
        sa.Column('output_ref', sa.String(length=500), nullable=True),
        sa.Column('accepted', sa.Boolean(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_feedback_user_id', 'agent_feedback', ['user_id'])
