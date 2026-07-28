"""add github_portfolio_reviews table

Revision ID: d1e2f3a4b5c6
Revises: 33109497beb1
Create Date: 2026-07-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = '33109497beb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'github_portfolio_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('review_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_github_portfolio_reviews_user_id'), 'github_portfolio_reviews', ['user_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_github_portfolio_reviews_user_id'), table_name='github_portfolio_reviews')
    op.drop_table('github_portfolio_reviews')