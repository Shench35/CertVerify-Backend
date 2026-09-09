"""Initial schema — all tables as defined by current SQLModel models.

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-09-09

For existing databases that already have these tables, run:
    alembic stamp head
to mark the database as up-to-date without executing the migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── transaction_records ──────────────────────────────────
    op.create_table(
        "transaction_records",
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_ref", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("amount_naira", sa.Float(), nullable=False),
        sa.Column("amount_kobo", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payment_plan", sa.String(), nullable=True),
        sa.Column("api_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("cert_type", sa.String(), nullable=True),
        sa.Column("verification_result", sa.String(), nullable=True),
        sa.Column("questions", sa.String(), nullable=True),
        sa.Column("document_score", sa.Float(), nullable=True),
        sa.Column("knowledge_score", sa.Float(), nullable=True),
        sa.Column("final_trust_score", sa.Float(), nullable=True),
        sa.Column("final_verdict", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("transaction_id"),
    )
    op.create_index(
        op.f("ix_transaction_records_transaction_ref"),
        "transaction_records",
        ["transaction_ref"],
        unique=True,
    )
    op.create_index(
        op.f("ix_transaction_records_user_id"),
        "transaction_records",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_transaction_records_email"),
        "transaction_records",
        ["email"],
    )
    op.create_index(
        op.f("ix_transaction_records_payment_plan"),
        "transaction_records",
        ["payment_plan"],
    )
    op.create_index(
        op.f("ix_transaction_records_api_key"),
        "transaction_records",
        ["api_key"],
    )

    # ── api_keys ─────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("api_key", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("daily_credit_limit", sa.Integer(), nullable=False),
        sa.Column("credits_reset_at", sa.DateTime(), nullable=False),
        sa.Column("subscription_plan", sa.String(), nullable=True),
        sa.Column("subscription_expires_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_api_keys_api_key"), "api_keys", ["api_key"], unique=True
    )
    op.create_index(op.f("ix_api_keys_user_id"), "api_keys", ["user_id"])
    op.create_index(op.f("ix_api_keys_email"), "api_keys", ["email"])

    # ── task_results ─────────────────────────────────────────
    op.create_table(
        "task_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("task_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("transaction_ref", sa.String(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_task_results_task_id"),
        "task_results",
        ["task_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_task_results_task_type"), "task_results", ["task_type"]
    )
    op.create_index(
        op.f("ix_task_results_status"), "task_results", ["status"]
    )
    op.create_index(
        op.f("ix_task_results_user_id"), "task_results", ["user_id"]
    )
    op.create_index(
        op.f("ix_task_results_transaction_ref"),
        "task_results",
        ["transaction_ref"],
    )

    # ── user_credit_accounts ─────────────────────────────────
    op.create_table(
        "user_credit_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("daily_credit_limit", sa.Integer(), nullable=False),
        sa.Column("credits_reset_at", sa.DateTime(), nullable=False),
        sa.Column("subscription_plan", sa.String(), nullable=True),
        sa.Column("subscription_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_credit_accounts_user_id"),
        "user_credit_accounts",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_user_credit_accounts_email"),
        "user_credit_accounts",
        ["email"],
    )


def downgrade() -> None:
    op.drop_table("user_credit_accounts")
    op.drop_table("task_results")
    op.drop_table("api_keys")
    op.drop_table("transaction_records")
