"""
Admin service layer — business logic for admin panel operations.
"""

import logging
from datetime import datetime
from typing import Optional

from firebase_admin import auth
from sqlmodel import Session, select, func, col, text

from app.core.database import engine
from app.models.transaction import Transaction
from app.models.api_key import ApiKey

logger = logging.getLogger(__name__)


# ─── Dashboard Statistics ────────────────────────────────────

def get_dashboard_stats() -> dict:
    """Aggregate platform-wide statistics for the admin dashboard."""
    with Session(engine) as session:
        # Transaction stats
        total_txns = session.exec(
            select(func.count()).select_from(Transaction)
        ).one()

        successful_txns = session.exec(
            select(func.count()).select_from(Transaction).where(
                Transaction.status == "success"
            )
        ).one()

        pending_txns = session.exec(
            select(func.count()).select_from(Transaction).where(
                Transaction.status == "pending"
            )
        ).one()

        total_revenue = session.exec(
            select(func.coalesce(func.sum(Transaction.amount_naira), 0.0)).where(
                Transaction.status == "success"
            )
        ).one()

        # Verification stats
        total_verifications = session.exec(
            select(func.count()).select_from(Transaction).where(
                Transaction.verification_result.is_not(None)  # type: ignore[union-attr]
            )
        ).one()

        verdicts_authentic = session.exec(
            select(func.count()).select_from(Transaction).where(
                Transaction.final_verdict == "AUTHENTIC"
            )
        ).one()

        verdicts_suspicious = session.exec(
            select(func.count()).select_from(Transaction).where(
                Transaction.final_verdict == "SUSPICIOUS"
            )
        ).one()

        verdicts_high_risk = session.exec(
            select(func.count()).select_from(Transaction).where(
                Transaction.final_verdict == "HIGH_RISK"
            )
        ).one()

        # API key stats
        total_api_keys = session.exec(
            select(func.count()).select_from(ApiKey)
        ).one()

        total_credits = session.exec(
            select(func.coalesce(func.sum(ApiKey.credits), 0))
        ).one()

        # Count unique user_ids across transactions
        total_users_in_txns = session.exec(
            select(func.count(func.distinct(Transaction.user_id))).where(
                Transaction.user_id.is_not(None)  # type: ignore[union-attr]
            )
        ).one()

    # Also try to count Firebase users
    firebase_user_count = _count_firebase_users()

    return {
        "total_users": firebase_user_count or total_users_in_txns,
        "total_transactions": total_txns,
        "total_revenue_naira": float(total_revenue),
        "total_verifications": total_verifications,
        "pending_transactions": pending_txns,
        "successful_transactions": successful_txns,
        "verdicts_authentic": verdicts_authentic,
        "verdicts_suspicious": verdicts_suspicious,
        "verdicts_high_risk": verdicts_high_risk,
        "total_api_keys": total_api_keys,
        "total_b2b_credits_issued": total_credits,
    }


def _count_firebase_users() -> int:
    """Count all Firebase Auth users. Returns 0 on failure."""
    try:
        count = 0
        page = auth.list_users()
        while page:
            count += len(page.users)
            page = page.get_next_page()
        return count
    except Exception as e:
        logger.warning(f"Failed to count Firebase users: {e}")
        return 0


# ─── User Management ────────────────────────────────────────

def list_firebase_users(page: int = 1, page_size: int = 20) -> dict:
    """
    List Firebase Auth users with pagination.
    Firebase doesn't support offset-based pagination natively,
    so we fetch all and slice (acceptable for admin panel use).
    """
    try:
        all_users = []
        firebase_page = auth.list_users()
        while firebase_page:
            for user in firebase_page.users:
                all_users.append({
                    "uid": user.uid,
                    "email": user.email,
                    "display_name": user.display_name,
                    "email_verified": user.email_verified,
                    "disabled": user.disabled,
                    "created_at": (
                        user.user_metadata.creation_timestamp
                        if user.user_metadata else None
                    ),
                    "last_sign_in": (
                        user.user_metadata.last_sign_in_timestamp
                        if user.user_metadata else None
                    ),
                    "photo_url": user.photo_url,
                    "custom_claims": user.custom_claims,
                })
            firebase_page = firebase_page.get_next_page()

        total = len(all_users)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = all_users[start:end]

        return {
            "users": paginated,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error(f"Failed to list Firebase users: {e}")
        raise


def get_firebase_user_detail(uid: str) -> dict:
    """Get detailed Firebase user information."""
    user = auth.get_user(uid)
    return {
        "uid": user.uid,
        "email": user.email,
        "display_name": user.display_name,
        "email_verified": user.email_verified,
        "disabled": user.disabled,
        "created_at": (
            user.user_metadata.creation_timestamp
            if user.user_metadata else None
        ),
        "last_sign_in": (
            user.user_metadata.last_sign_in_timestamp
            if user.user_metadata else None
        ),
        "photo_url": user.photo_url,
        "custom_claims": user.custom_claims,
    }


def set_admin_claim(uid: str, is_admin: bool) -> dict:
    """Set or revoke admin custom claim on a Firebase user."""
    user = auth.get_user(uid)
    current_claims = user.custom_claims or {}

    if is_admin:
        current_claims["admin"] = True
    else:
        current_claims.pop("admin", None)

    auth.set_custom_user_claims(uid, current_claims)
    return {
        "uid": uid,
        "admin": is_admin,
        "message": f"Admin {'granted' if is_admin else 'revoked'} for {user.email}",
    }


def disable_user(uid: str, disabled: bool) -> dict:
    """Disable or enable a Firebase user account."""
    auth.update_user(uid, disabled=disabled)
    user = auth.get_user(uid)
    return {
        "uid": uid,
        "email": user.email,
        "disabled": user.disabled,
        "message": f"User {'disabled' if disabled else 'enabled'} successfully.",
    }


# ─── Transaction Management ─────────────────────────────────

def list_transactions(
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    verdict_filter: Optional[str] = None,
    email_filter: Optional[str] = None,
) -> dict:
    """List all transactions with optional filters and pagination."""
    with Session(engine) as session:
        query = select(Transaction)
        count_query = select(func.count()).select_from(Transaction)

        if status_filter:
            query = query.where(Transaction.status == status_filter)
            count_query = count_query.where(Transaction.status == status_filter)

        if verdict_filter:
            query = query.where(Transaction.final_verdict == verdict_filter)
            count_query = count_query.where(
                Transaction.final_verdict == verdict_filter
            )

        if email_filter:
            query = query.where(Transaction.email.contains(email_filter))  # type: ignore[union-attr]
            count_query = count_query.where(
                Transaction.email.contains(email_filter)  # type: ignore[union-attr]
            )

        total = session.exec(count_query).one()

        query = query.order_by(Transaction.created_at.desc())  # type: ignore[union-attr]
        query = query.offset((page - 1) * page_size).limit(page_size)
        transactions = session.exec(query).all()

        return {
            "transactions": [
                {
                    "transaction_id": str(t.transaction_id),
                    "transaction_ref": t.transaction_ref,
                    "user_id": t.user_id,
                    "email": t.email,
                    "amount_naira": t.amount_naira,
                    "status": t.status,
                    "created_at": t.created_at,
                    "paid_at": t.paid_at,
                    "cert_type": t.cert_type,
                    "document_score": t.document_score,
                    "knowledge_score": t.knowledge_score,
                    "final_trust_score": t.final_trust_score,
                    "final_verdict": t.final_verdict,
                }
                for t in transactions
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


def get_transaction_detail(transaction_ref: str) -> dict | None:
    """Get full transaction detail including verification results."""
    with Session(engine) as session:
        txn = session.exec(
            select(Transaction).where(
                Transaction.transaction_ref == transaction_ref
            )
        ).first()

        if not txn:
            return None

        return {
            "transaction_id": str(txn.transaction_id),
            "transaction_ref": txn.transaction_ref,
            "user_id": txn.user_id,
            "email": txn.email,
            "amount_naira": txn.amount_naira,
            "status": txn.status,
            "created_at": txn.created_at,
            "paid_at": txn.paid_at,
            "cert_type": txn.cert_type,
            "document_score": txn.document_score,
            "knowledge_score": txn.knowledge_score,
            "final_trust_score": txn.final_trust_score,
            "final_verdict": txn.final_verdict,
            "verification_result": txn.verification_result,
            "questions": txn.questions,
        }


# ─── API Key Management ─────────────────────────────────────

def list_api_keys(
    page: int = 1,
    page_size: int = 20,
    active_only: bool = False,
) -> dict:
    """List all B2B API keys with optional filter and pagination."""
    with Session(engine) as session:
        query = select(ApiKey)
        count_query = select(func.count()).select_from(ApiKey)

        if active_only:
            query = query.where(ApiKey.is_active == True)
            count_query = count_query.where(ApiKey.is_active == True)

        total = session.exec(count_query).one()

        query = query.order_by(ApiKey.created_at.desc())  # type: ignore[union-attr]
        query = query.offset((page - 1) * page_size).limit(page_size)
        keys = session.exec(query).all()

        return {
            "api_keys": [
                {
                    "id": str(k.id),
                    "api_key": k.api_key,
                    "user_id": k.user_id,
                    "email": k.email,
                    "name": k.name,
                    "credits": k.credits,
                    "is_active": k.is_active,
                    "created_at": k.created_at,
                }
                for k in keys
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


def update_api_key(
    api_key_str: str,
    credits: Optional[int] = None,
    is_active: Optional[bool] = None,
    name: Optional[str] = None,
) -> dict | None:
    """Update an API key's credits, active status, or name."""
    with Session(engine) as session:
        key = session.exec(
            select(ApiKey).where(ApiKey.api_key == api_key_str)
        ).first()

        if not key:
            return None

        if credits is not None:
            key.credits = credits
        if is_active is not None:
            key.is_active = is_active
        if name is not None:
            key.name = name

        session.add(key)
        session.commit()
        session.refresh(key)

        return {
            "id": str(key.id),
            "api_key": key.api_key,
            "user_id": key.user_id,
            "email": key.email,
            "name": key.name,
            "credits": key.credits,
            "is_active": key.is_active,
            "created_at": key.created_at,
            "message": "API key updated successfully.",
        }


# ─── Verification Overview ──────────────────────────────────

def list_verifications(
    page: int = 1,
    page_size: int = 20,
    verdict_filter: Optional[str] = None,
    cert_type_filter: Optional[str] = None,
) -> dict:
    """List all verification results with optional filters."""
    with Session(engine) as session:
        query = select(Transaction).where(
            Transaction.verification_result.is_not(None)  # type: ignore[union-attr]
        )
        count_query = select(func.count()).select_from(Transaction).where(
            Transaction.verification_result.is_not(None)  # type: ignore[union-attr]
        )

        if verdict_filter:
            query = query.where(Transaction.final_verdict == verdict_filter)
            count_query = count_query.where(
                Transaction.final_verdict == verdict_filter
            )

        if cert_type_filter:
            query = query.where(Transaction.cert_type == cert_type_filter)
            count_query = count_query.where(
                Transaction.cert_type == cert_type_filter
            )

        total = session.exec(count_query).one()

        query = query.order_by(Transaction.created_at.desc())  # type: ignore[union-attr]
        query = query.offset((page - 1) * page_size).limit(page_size)
        records = session.exec(query).all()

        return {
            "verifications": [
                {
                    "transaction_ref": r.transaction_ref,
                    "user_id": r.user_id,
                    "email": r.email,
                    "cert_type": r.cert_type,
                    "created_at": r.created_at,
                    "document_score": r.document_score,
                    "final_trust_score": r.final_trust_score,
                    "final_verdict": r.final_verdict,
                }
                for r in records
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
