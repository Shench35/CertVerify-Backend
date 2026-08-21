from sqlmodel import SQLModel, Field
from datetime import datetime
import uuid

class Transaction(SQLModel, table=True):
    __tablename__ = "transaction_records"

    transaction_id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True
    )
    transaction_ref: str = Field(index=True, unique=True)
    email: str
    amount_naira: float
    amount_kobo: int
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: datetime | None = Field(default=None)

    # AI Pipeline results — stored as JSON strings
    cert_type: str | None = Field(default=None)
    verification_result: str | None = Field(default=None)
    questions: str | None = Field(default=None)
    document_score: float | None = Field(default=None)
    final_trust_score: float | None = Field(default=None)
    final_verdict: str | None = Field(default=None)