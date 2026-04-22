"""add resolved_outcome to events

Revision ID: 003
Revises: 002
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("resolved_outcome", sa.String, nullable=True))


def downgrade() -> None:
    op.drop_column("events", "resolved_outcome")
