"""initial schema: events, predictions, model_stats

Revision ID: 001
Revises:
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("polymarket_market_id", sa.String, unique=True, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("outcomes", JSONB, nullable=False, server_default="[]"),
        sa.Column("outcome_prices", JSONB, nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("closed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("end_date", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_events_category", "events", ["category"])
    op.create_index("ix_events_active", "events", ["active"])
    op.create_index("ix_events_polymarket_market_id", "events", ["polymarket_market_id"])

    op.create_table(
        "model_stats",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_name", sa.String, unique=True, nullable=False),
        sa.Column("total_predictions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_brier_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_model_stats_model_name", "model_stats", ["model_name"])

    op.create_table(
        "predictions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("model_name", sa.String, nullable=False),
        sa.Column("probability", sa.Float, nullable=False),
        sa.Column("verdict", sa.String, nullable=False),
        sa.Column("sources", JSONB, nullable=False, server_default="[]"),
        sa.Column("brier_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("predictions")
    op.drop_table("model_stats")
    op.drop_table("events")
