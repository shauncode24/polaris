"""merge multiple heads

Revision ID: 94e435c82910
Revises: b9e1f4a7c2d8, e4a8f912c3d7
Create Date: 2026-07-29 09:37:46.473835

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94e435c82910'
down_revision: Union[str, Sequence[str], None] = ('b9e1f4a7c2d8', 'e4a8f912c3d7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
