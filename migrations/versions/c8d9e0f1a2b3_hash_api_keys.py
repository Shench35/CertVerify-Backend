"""Store B2B API keys as SHA-256 digests.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
"""
import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _already_hashed(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("api_key_prefix", sa.String(), nullable=True))
    op.add_column("api_keys", sa.Column("api_key_suffix", sa.String(), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, api_key FROM api_keys")).all()
    for row_id, value in rows:
        if not _already_hashed(value):
            connection.execute(
                sa.text(
                    "UPDATE api_keys SET api_key = :digest, api_key_prefix = :prefix, "
                    "api_key_suffix = :suffix WHERE id = :row_id"
                ),
                {
                    "digest": _digest(value),
                    "prefix": value[:8],
                    "suffix": value[-4:],
                    "row_id": row_id,
                },
            )

    # Pending B2B payments retain the key reference used at checkout. Convert
    # those values too so they continue to resolve after key hashing.
    payments = connection.execute(
        sa.text("SELECT transaction_id, api_key FROM transaction_records WHERE api_key IS NOT NULL")
    ).all()
    for transaction_id, value in payments:
        if not _already_hashed(value):
            connection.execute(
                sa.text(
                    "UPDATE transaction_records SET api_key = :digest "
                    "WHERE transaction_id = :transaction_id"
                ),
                {"digest": _digest(value), "transaction_id": transaction_id},
            )


def downgrade() -> None:
    op.drop_column("api_keys", "api_key_suffix")
    op.drop_column("api_keys", "api_key_prefix")
