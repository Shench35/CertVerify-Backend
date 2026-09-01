"""
Admin panel request/response schemas.
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


# ─── Dashboard ───────────────────────────────────────────────

class DashboardStatsResponse(BaseModel):
    """Aggregate statistics for the admin dashboard."""
    total_users: int = 0
    total_transactions: int = 0
    total_revenue_naira: float = 0.0
    total_verifications: int = 0
    pending_transactions: int = 0
    successful_transactions: int = 0
    verdicts_authentic: int = 0
    verdicts_suspicious: int = 0
    verdicts_high_risk: int = 0
    total_api_keys: int = 0
    total_b2b_credits_issued: int = 0


# ─── User Management ────────────────────────────────────────

class AdminUserListItem(BaseModel):
    """Firebase user summary for admin user list."""
    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    email_verified: bool = False
    disabled: bool = False
    created_at: Optional[str] = None
    last_sign_in: Optional[str] = None
    photo_url: Optional[str] = None
    custom_claims: Optional[dict] = None


class AdminUserListResponse(BaseModel):
    """Paginated user list response."""
    users: list[AdminUserListItem]
    total: int
    page: int
    page_size: int


class SetAdminRequest(BaseModel):
    """Request to grant/revoke admin privileges."""
    uid: str
    is_admin: bool = True


class DisableUserRequest(BaseModel):
    """Request to disable/enable a user account."""
    uid: str
    disabled: bool = True


# ─── Transaction Management ─────────────────────────────────

class AdminTransactionItem(BaseModel):
    """Transaction record for admin views."""
    transaction_id: str
    transaction_ref: str
    user_id: Optional[str] = None
    email: str
    amount_naira: float
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None
    cert_type: Optional[str] = None
    document_score: Optional[float] = None
    knowledge_score: Optional[float] = None
    final_trust_score: Optional[float] = None
    final_verdict: Optional[str] = None


class AdminTransactionListResponse(BaseModel):
    """Paginated transaction list for admin."""
    transactions: list[AdminTransactionItem]
    total: int
    page: int
    page_size: int


# ─── API Key Management ─────────────────────────────────────

class AdminApiKeyItem(BaseModel):
    """API key details for admin views."""
    id: str
    api_key: str
    user_id: Optional[str] = None
    email: str
    name: str
    credits: int
    is_active: bool
    created_at: datetime


class AdminApiKeyListResponse(BaseModel):
    """Paginated API key list for admin."""
    api_keys: list[AdminApiKeyItem]
    total: int
    page: int
    page_size: int


class UpdateApiKeyRequest(BaseModel):
    """Admin request to modify an API key."""
    credits: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    name: Optional[str] = None


# ─── Verification Reports (Admin View) ──────────────────────

class AdminVerificationItem(BaseModel):
    """Verification record for admin oversight."""
    transaction_ref: str
    user_id: Optional[str] = None
    email: str
    cert_type: Optional[str] = None
    created_at: datetime
    document_score: Optional[float] = None
    final_trust_score: Optional[float] = None
    final_verdict: Optional[str] = None


class AdminVerificationListResponse(BaseModel):
    """Paginated verification list for admin."""
    verifications: list[AdminVerificationItem]
    total: int
    page: int
    page_size: int


# ─── Bulk Operations ────────────────────────────────────────

class BulkEmailRequest(BaseModel):
    """Send email to a list of recipients."""
    subject: str
    body: str
    recipient_emails: list[str] = Field(..., min_length=1)


class BulkEmailResponse(BaseModel):
    """Response for bulk email operation."""
    task_id: str
    message: str
    recipient_count: int
