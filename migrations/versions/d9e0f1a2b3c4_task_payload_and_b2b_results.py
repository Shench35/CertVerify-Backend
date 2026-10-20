"""Persist worker inputs and B2B task ownership/results.

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("task_results", sa.Column("api_key_hash", sa.String(), nullable=True))
    op.add_column("task_results", sa.Column("credit_refunded", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("task_results", sa.Column("payload", sa.LargeBinary(), nullable=True))
    op.create_index(
        op.f("ix_task_results_api_key_hash"), "task_results", ["api_key_hash"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_task_results_api_key_hash"), table_name="task_results")
    op.drop_column("task_results", "payload")
    op.drop_column("task_results", "credit_refunded")
    op.drop_column("task_results", "api_key_hash")
