"""merge multiple heads

Revision ID: b93753a4cf90
Revises: c1a2b3d4e5f6, c1a9e5f27b4d
Create Date: 2026-07-31 10:46:37.071687

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b93753a4cf90'
down_revision: Union[str, Sequence[str], None] = ('c1a2b3d4e5f6', 'c1a9e5f27b4d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
