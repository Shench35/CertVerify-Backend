from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class InitiatePaymentRequest(BaseModel):
    amount_naira: float = Field(..., gt=0, description="Amount in Naira", json_schema_extra={"example": 5000.0})
    email: Optional[str] = Field(None, description="User email (optional if using Bearer token)", json_schema_extra={"example": "user@example.com"})
    plan: Literal["user_monthly", "b2b_monthly"] = Field(default="user_monthly")
    api_key: Optional[str] = Field(default=None, description="Required for the B2B monthly plan")


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
