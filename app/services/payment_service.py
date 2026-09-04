import uuid
import hmac
import hashlib
from datetime import datetime
from typing import Optional
import httpx
from fastapi import HTTPException, status
from sqlmodel import Session, select
from sqlalchemy import update
from app.core.config import settings
from app.core.database import engine
from app.models.transaction import Transaction
from app.services.credit_service import activate_b2b_subscription, activate_user_subscription

PLAN_PRICES_NAIRA = {
    "user_monthly": 5000.0,
    "b2b_monthly": 20000.0,
}


def mark_transaction_success(transaction_ref: str) -> tuple[Transaction | None, bool]:
    """Atomically mark a pending transaction successful.

    Returns the transaction and whether this call performed the state
    transition. Only the caller that transitions the row may apply payment
    side effects such as subscription activation and email delivery.
    """
    paid_at = datetime.utcnow()
    with Session(engine) as session:
        result = session.exec(
            update(Transaction)
            .where(
                Transaction.transaction_ref == transaction_ref,
                Transaction.status == "pending",
            )
            .values(status="success", paid_at=paid_at)
        )
        transitioned = result.rowcount == 1
        session.commit()

        transaction = session.exec(
            select(Transaction).where(
                Transaction.transaction_ref == transaction_ref
            )
        ).first()

    return transaction, transitioned


def apply_payment_success_side_effects(transaction: Transaction) -> None:
    """Apply subscription activation after a successful state transition."""
    if transaction.payment_plan == "user_monthly" and transaction.user_id:
        activate_user_subscription(transaction.user_id, transaction.email)
    elif transaction.payment_plan == "b2b_monthly" and transaction.api_key:
        activate_b2b_subscription(transaction.api_key)


async def initiate_squad_payment(
    amount_naira: float,
    email: str,
    user_id: Optional[str] = None,
    payment_plan: str = "user_monthly",
    api_key: Optional[str] = None,
) -> dict:
    """Creates pending transaction and calls Squad payment initiation."""
    transaction_ref = str(uuid.uuid4())

    with Session(engine) as session:
        transaction = Transaction(
            transaction_ref=transaction_ref,
            user_id=user_id,
            email=email,
            amount_naira=amount_naira,
            amount_kobo=int(amount_naira * 100),
            status="pending",
            payment_plan=payment_plan,
            api_key=api_key,
        )
        session.add(transaction)
        session.commit()

    headers = {
        "Authorization": f"Bearer {settings.SQUAD_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "amount": int(amount_naira * 100),
        "email": email,
        "currency": "NGN",
        "initiate_type": "inline",
        "transaction_ref": transaction_ref,
        "callback_url": settings.SQUAD_CALLBACK_URL
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{settings.SQUAD_BASE_URL}/transaction/initiate",
            json=body,
            headers=headers
        )

    data = res.json()
    if res.status_code != 200 or not data.get("data"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=data.get("message", "Failed to initiate payment with Squad.")
        )

    return {
        "checkout_url": data["data"]["checkout_url"],
        "transaction_ref": data["data"]["transaction_ref"]
    }


async def verify_squad_payment(transaction_ref: str) -> dict:
    """Verifies payment against database and Squad API."""
    with Session(engine) as session:
        statement = select(Transaction).where(
            Transaction.transaction_ref == transaction_ref
        )
        transaction = session.exec(statement).first()

    if not transaction:
        return {"paid": False, "status": "not_found", "message": "Transaction not found."}

    if transaction.status == "success":
        return {
            "paid": True,
            "status": "success",
            "amount": transaction.amount_naira,
            "email": transaction.email,
            "transaction_ref": transaction_ref
        }

    headers = {"Authorization": f"Bearer {settings.SQUAD_SECRET_KEY}"}

    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{settings.SQUAD_BASE_URL}/transaction/verify/{transaction_ref}",
            headers=headers
        )

    data = res.json()
    if res.status_code != 200 or not data.get("data"):
        return {"paid": False, "status": "failed", "message": data.get("message", "Verification failed")}

    tx_status = data["data"]["transaction_status"]
    if tx_status == "Success":
        tx, transitioned = mark_transaction_success(transaction_ref)
        if tx and transitioned:
            apply_payment_success_side_effects(tx)

    return {
        "paid": tx_status == "Success",
        "status": tx_status,
        "amount": data["data"]["transaction_amount"],
        "email": data["data"]["email"],
        "transaction_ref": transaction_ref
    }


def verify_webhook_signature(body_bytes: bytes, signature_header: Optional[str]) -> bool:
    """Validates HMAC signature of incoming Squad webhook."""
    if not signature_header or not settings.SQUAD_SECRET_KEY:
        return False
    computed = hmac.new(
        settings.SQUAD_SECRET_KEY.encode("utf-8"),
        body_bytes,
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(computed.lower(), signature_header.lower())
