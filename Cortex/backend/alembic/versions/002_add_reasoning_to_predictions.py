"""add reasoning and confidence_score to predictions

Revision ID: 002
Revises: 001
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("predictions", sa.Column("reasoning", sa.Text, nullable=False, server_default=""))
    op.add_column("predictions", sa.Column("confidence_score", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("predictions", "confidence_score")
    op.drop_column("predictions", "reasoning")
