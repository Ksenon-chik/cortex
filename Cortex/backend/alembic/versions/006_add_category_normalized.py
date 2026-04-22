"""add category_normalized to events

Revision ID: 006
Revises: 005
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("category_normalized", sa.String(), nullable=False, server_default="Other"),
    )
    op.create_index("ix_events_category_normalized", "events", ["category_normalized"])


def downgrade() -> None:
    op.drop_index("ix_events_category_normalized")
    op.drop_column("events", "category_normalized")
