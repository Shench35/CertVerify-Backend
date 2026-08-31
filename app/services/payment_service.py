import uuid
import hmac
import hashlib
from datetime import datetime
from typing import Optional
import httpx
from fastapi import HTTPException, status
from sqlmodel import Session, select
from app.core.config import settings
from app.core.database import engine
from app.models.transaction import Transaction

# In-memory deduplication set (backed up by DB transaction status check)
processed_transactions = set()


async def initiate_squad_payment(
    amount_naira: float,
    email: str,
    user_id: Optional[str] = None
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
            status="pending"
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
        with Session(engine) as session:
            statement = select(Transaction).where(
                Transaction.transaction_ref == transaction_ref
            )
            tx = session.exec(statement).first()
            if tx:
                tx.status = "success"
                tx.paid_at = datetime.utcnow()
                session.add(tx)
                session.commit()

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
