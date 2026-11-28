"""keep the dates of experiences and education as stated

Revision ID: d9a5b2c7e4f1
Revises: c8f4a1b6d3e9
Create Date: 2026-11-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9a5b2c7e4f1"
down_revision: Union[str, None] = "c8f4a1b6d3e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("experiences", "educations")
COLUMNS = ("start_date_text", "end_date_text")


def upgrade() -> None:
    for table in TABLES:
        for column in COLUMNS:
            op.add_column(table, sa.Column(column, sa.String(50), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        for column in COLUMNS:
            op.drop_column(table, column)
