"""add prediction result fields

Revision ID: 009_add_prediction_result_fields
Revises: 008_add_refresh_token_sessions
Create Date: 2026-04-19 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "009_add_prediction_result_fields"
down_revision: Union[str, None] = "008_add_refresh_token_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "predictions",
        sa.Column("predicted_outcome", sa.String(), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column(
            "result_status",
            sa.String(),
            nullable=False,
            server_default="pending",
        ),
    )


def downgrade() -> None:
    op.drop_column("predictions", "result_status")
    op.drop_column("predictions", "predicted_outcome")
