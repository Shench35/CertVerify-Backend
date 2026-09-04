import uuid
from datetime import datetime
from sqlmodel import SQLModel, Field


class Transaction(SQLModel, table=True):
    __tablename__ = "transaction_records"

    transaction_id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True
    )
    transaction_ref: str = Field(index=True, unique=True)
    user_id: str | None = Field(default=None, index=True)  # Firebase UID
    email: str = Field(index=True)
    amount_naira: float
    amount_kobo: int
    status: str = Field(default="pending")
    payment_plan: str | None = Field(default=None, index=True)
    api_key: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: datetime | None = Field(default=None)

    # Forensic AI Pipeline results
    cert_type: str | None = Field(default=None)
    verification_result: str | None = Field(default=None)  # Serialized JSON string
    questions: str | None = Field(default=None)            # Serialized JSON string
    document_score: float | None = Field(default=None)
    knowledge_score: float | None = Field(default=None)
    final_trust_score: float | None = Field(default=None)
    final_verdict: str | None = Field(default=None)
