"""
Admin panel API endpoints.
All endpoints require admin authentication via get_admin_user dependency.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import get_admin_user
from app.schemas.admin import (
    DashboardStatsResponse,
    AdminUserListResponse,
    AdminUserListItem,
    SetAdminRequest,
    DisableUserRequest,
    AdminTransactionListResponse,
    AdminApiKeyListResponse,
    UpdateApiKeyRequest,
    AdminVerificationListResponse,
    BulkEmailRequest,
    BulkEmailResponse,
)
from app.services import admin_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Dashboard ───────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(admin: dict = Depends(get_admin_user)):
    """Get aggregate platform statistics for the admin dashboard."""
    try:
        stats = admin_service.get_dashboard_stats()
        return stats
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard statistics.",
        )


# ─── User Management ────────────────────────────────────────

@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: dict = Depends(get_admin_user),
):
    """List all Firebase users with pagination."""
    try:
        result = admin_service.list_firebase_users(page=page, page_size=page_size)
        return result
    except Exception as e:
        logger.error(f"List users error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users.",
        )


@router.get("/users/{uid}", response_model=AdminUserListItem)
async def get_user_detail(uid: str, admin: dict = Depends(get_admin_user)):
    """Get detailed information about a specific user."""
    try:
        user = admin_service.get_firebase_user_detail(uid)
        return user
    except Exception as e:
        logger.error(f"Get user detail error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {uid} not found.",
        )


@router.post("/users/set-admin")
async def set_admin(
    request: SetAdminRequest,
    admin: dict = Depends(get_admin_user),
):
    """Grant or revoke admin privileges for a user."""
    try:
        result = admin_service.set_admin_claim(
            uid=request.uid, is_admin=request.is_admin
        )
        return result
    except Exception as e:
        logger.exception(f"Set admin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update admin status.",
        )


@router.post("/users/disable")
async def disable_user(
    request: DisableUserRequest,
    admin: dict = Depends(get_admin_user),
):
    """Disable or enable a user account."""
    try:
        result = admin_service.disable_user(
            uid=request.uid, disabled=request.disabled
        )
        return result
    except Exception as e:
        logger.exception(f"Disable user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update user status.",
        )


# ─── Transaction Management ─────────────────────────────────

@router.get("/transactions", response_model=AdminTransactionListResponse)
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    verdict: Optional[str] = None,
    email: Optional[str] = None,
    admin: dict = Depends(get_admin_user),
):
    """List all transactions with optional filters and pagination."""
    try:
        result = admin_service.list_transactions(
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            verdict_filter=verdict,
            email_filter=email,
        )
        return result
    except Exception as e:
        logger.error(f"List transactions error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list transactions.",
        )


@router.get("/transactions/{transaction_ref}")
async def get_transaction_detail(
    transaction_ref: str,
    admin: dict = Depends(get_admin_user),
):
    """Get full transaction detail including verification results."""
    result = admin_service.get_transaction_detail(transaction_ref)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_ref} not found.",
        )
    return result


# ─── API Key Management ─────────────────────────────────────

@router.get("/api-keys", response_model=AdminApiKeyListResponse)
async def list_api_keys(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    active_only: bool = Query(False),
    admin: dict = Depends(get_admin_user),
):
    """List all B2B API keys with pagination."""
    try:
        result = admin_service.list_api_keys(
            page=page, page_size=page_size, active_only=active_only
        )
        return result
    except Exception as e:
        logger.error(f"List API keys error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys.",
        )


@router.patch("/api-keys/{api_key}")
async def update_api_key(
    api_key: str,
    request: UpdateApiKeyRequest,
    admin: dict = Depends(get_admin_user),
):
    """Update an API key's credits, active status, or name."""
    result = admin_service.update_api_key(
        api_key_str=api_key,
        credits=request.credits,
        is_active=request.is_active,
        name=request.name,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key not found.",
        )
    return result


from app.schemas.verification import CertificateType


# ─── Verification Overview ──────────────────────────────────

@router.get("/verifications", response_model=AdminVerificationListResponse)
async def list_verifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    verdict: Optional[str] = None,
    cert_type: Optional[CertificateType] = None,
    admin: dict = Depends(get_admin_user),
):
    """List all verifications with optional filters."""
    try:
        result = admin_service.list_verifications(
            page=page,
            page_size=page_size,
            verdict_filter=verdict,
            cert_type_filter=cert_type.value if cert_type else None,
        )
        return result
    except Exception as e:
        logger.error(f"List verifications error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list verifications.",
        )


# ─── Bulk Email ──────────────────────────────────────────────

@router.post("/email/send-bulk", response_model=BulkEmailResponse)
async def send_bulk_email(
    request: BulkEmailRequest,
    admin: dict = Depends(get_admin_user),
):
    """Send a bulk email to specified recipients via Celery task."""
    from app.tasks.email_tasks import send_bulk_email_task

    task = send_bulk_email_task.delay(
        subject=request.subject,
        body=request.body,
        recipient_emails=request.recipient_emails,
    )

    return BulkEmailResponse(
        task_id=task.id,
        message="Bulk email task queued successfully.",
        recipient_count=len(request.recipient_emails),
    )
