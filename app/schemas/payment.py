from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class InitiatePaymentRequest(BaseModel):
    amount_naira: float = Field(..., gt=0, example=2500.0, description="Amount in Naira")
    email: Optional[str] = Field(None, example="user@example.com", description="User email (optional if using Bearer token)")


class InitiatePaymentResponse(BaseModel):
    checkout_url: str
    transaction_ref: str


class VerifyPaymentResponse(BaseModel):
    paid: bool
    status: str
    amount: float
    email: str
    transaction_ref: str
    message: Optional[str] = None


class TransactionResponse(BaseModel):
    transaction_ref: str
    email: str
    amount_naira: float
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None
    cert_type: Optional[str] = None
    final_trust_score: Optional[float] = None
    final_verdict: Optional[str] = None
