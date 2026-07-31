"""merge multiple heads

Revision ID: e1b3dac5f6ce
Revises: c2f8a4e91d05, e6f7a8b9c0d1
Create Date: 2026-07-31 19:57:07.244350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1b3dac5f6ce'
down_revision: Union[str, Sequence[str], None] = ('c2f8a4e91d05', 'e6f7a8b9c0d1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
