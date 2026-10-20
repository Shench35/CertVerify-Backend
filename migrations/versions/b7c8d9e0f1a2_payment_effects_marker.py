"""Track successful payment fulfillment for safe retries.

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transaction_records",
        sa.Column("payment_effects_applied_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transaction_records", "payment_effects_applied_at")
