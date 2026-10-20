import uuid
import hmac
import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
import httpx
from fastapi import HTTPException, status
from sqlmodel import Session, select
from app.core.config import settings
from app.core.database import engine
from app.models.transaction import Transaction
from app.models.user_credit import UserCreditAccount
from app.models.api_key import ApiKey
from app.core.api_key_security import hash_api_key
from app.services.credit_service import (
    B2B_SUBSCRIPTION_CREDITS,
    USER_SUBSCRIPTION_CREDITS,
    SUBSCRIPTION_DURATION,
    DAILY_RESET_INTERVAL,
)

PLAN_PRICES_NAIRA = {
    "user_monthly": 5000.0,
    "b2b_monthly": 20000.0,
}


def payment_matches_order(
    transaction: Transaction,
    amount_kobo: object,
    currency: object,
    provider_ref: object,
) -> bool:
    """Check provider confirmation against the exact locally-created order."""
    try:
        confirmed_amount = Decimal(str(amount_kobo))
    except (InvalidOperation, TypeError, ValueError):
        return False

    return (
        confirmed_amount.is_finite()
        and confirmed_amount == Decimal(transaction.amount_kobo)
        and str(currency).upper() == "NGN"
        and provider_ref == transaction.transaction_ref
    )


def mark_transaction_success(transaction_ref: str) -> tuple[Transaction | None, bool]:
    """Backward-compatible entry point for atomic payment settlement."""
    return settle_payment(transaction_ref)


def settle_payment(transaction_ref: str) -> tuple[Transaction | None, bool]:
    """Atomically mark an order paid and apply its subscription once.

    The transaction row lock serializes webhook and browser verification
    retries. Updating the order, credit account/API key, and fulfillment marker
    in one database transaction makes a crash either commit all effects or
    none of them.
    """
    now = datetime.utcnow()
    with Session(engine) as session:
        transaction = session.exec(
            select(Transaction)
            .where(Transaction.transaction_ref == transaction_ref)
            .with_for_update()
        ).first()
        if not transaction:
            return None, False
        if transaction.payment_effects_applied_at:
            return transaction, False

        if transaction.payment_plan == "user_monthly" and transaction.user_id:
            account = session.exec(
                select(UserCreditAccount)
                .where(UserCreditAccount.user_id == transaction.user_id)
                .with_for_update()
            ).first()
            if not account:
                account = UserCreditAccount(
                    user_id=transaction.user_id,
                    email=transaction.email or "",
                )
            current_expiry = account.subscription_expires_at
            base = current_expiry if current_expiry and current_expiry > now else now
            account.credits = max(account.credits, USER_SUBSCRIPTION_CREDITS)
            account.daily_credit_limit = USER_SUBSCRIPTION_CREDITS
            account.credits_reset_at = now + DAILY_RESET_INTERVAL
            account.subscription_plan = "user_monthly"
            account.subscription_expires_at = base + SUBSCRIPTION_DURATION
            account.updated_at = now
            session.add(account)
        elif transaction.payment_plan == "b2b_monthly" and transaction.api_key:
            key = session.exec(
                select(ApiKey)
                .where(ApiKey.api_key == transaction.api_key)
                .with_for_update()
            ).first()
            if not key:
                # Leave the payment pending so the fulfillment can be retried
                # after the missing API key is corrected.
                raise ValueError("B2B API key for paid order was not found")
            current_expiry = key.subscription_expires_at
            base = current_expiry if current_expiry and current_expiry > now else now
            key.credits = max(key.credits, B2B_SUBSCRIPTION_CREDITS)
            key.daily_credit_limit = B2B_SUBSCRIPTION_CREDITS
            key.credits_reset_at = now + DAILY_RESET_INTERVAL
            key.subscription_plan = "b2b_monthly"
            key.subscription_expires_at = base + SUBSCRIPTION_DURATION
            key.updated_at = now
            session.add(key)

        transaction.status = "success"
        transaction.paid_at = transaction.paid_at or now
        transaction.payment_effects_applied_at = now
        session.add(transaction)
        session.commit()
        session.refresh(transaction)
        return transaction, True


async def initiate_squad_payment(
    amount_naira: float,
    email: str,
    user_id: Optional[str] = None,
    payment_plan: str = "user_monthly",
    api_key: Optional[str] = None,
) -> dict:
    """Creates pending transaction and calls Squad payment initiation."""
    if not settings.SQUAD_CALLBACK_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment callback URL is not configured.",
        )
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
            api_key=hash_api_key(api_key) if api_key else None,
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

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(
                f"{settings.SQUAD_BASE_URL}/transaction/initiate",
                json=body,
                headers=headers
            )
    except httpx.RequestError as exc:
        # Keep the order pending because a network timeout cannot establish
        # whether Squad accepted the initiation request.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment provider could not be reached. Check payment history before retrying.",
        ) from exc

    try:
        data = res.json()
    except ValueError:
        data = {}
    provider_data = data.get("data") if isinstance(data, dict) else None
    if (
        res.status_code != 200
        or not isinstance(provider_data, dict)
        or provider_data.get("transaction_ref") != transaction_ref
        or not provider_data.get("checkout_url")
    ):
        with Session(engine) as session:
            pending = session.exec(
                select(Transaction).where(
                    Transaction.transaction_ref == transaction_ref,
                    Transaction.status == "pending",
                )
            ).first()
            if pending:
                pending.status = "initiation_failed"
                session.add(pending)
                session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(data.get("message") if isinstance(data, dict) else None)
            or "Failed to initiate payment with Squad."
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
        return {
            "paid": False,
            "status": "not_found",
            "message": "Transaction not found.",
            "transaction_ref": transaction_ref,
        }

    if transaction.status == "success" and transaction.payment_effects_applied_at:
        return {
            "paid": True,
            "status": "success",
            "amount": transaction.amount_naira,
            "email": transaction.email,
            "transaction_ref": transaction_ref
        }

    if transaction.payment_plan not in PLAN_PRICES_NAIRA:
        return {
            "paid": False,
            "status": transaction.status,
            "message": "This transaction is not a payment order.",
            "amount": transaction.amount_naira,
            "email": transaction.email,
            "transaction_ref": transaction_ref,
        }

    headers = {"Authorization": f"Bearer {settings.SQUAD_SECRET_KEY}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(
                f"{settings.SQUAD_BASE_URL}/transaction/verify/{transaction_ref}",
                headers=headers
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to verify payment with the provider. Please retry shortly.",
        ) from exc

    try:
        data = res.json()
    except ValueError:
        data = {}
    provider_data = data.get("data") if isinstance(data, dict) else None
    if res.status_code != 200 or not isinstance(provider_data, dict):
        message = data.get("message", "Verification failed") if isinstance(data, dict) else "Verification failed"
        return {
            "paid": False,
            "status": "failed",
            "message": message,
            "amount": transaction.amount_naira,
            "email": transaction.email,
            "transaction_ref": transaction_ref,
        }

    tx_status = provider_data.get("transaction_status")
    is_success = str(tx_status or "").strip().lower() == "success"
    if is_success:
        if not payment_matches_order(
            transaction,
            provider_data.get("transaction_amount"),
            provider_data.get("transaction_currency_id"),
            provider_data.get("transaction_ref"),
        ):
            return {
                "paid": False,
                "status": "mismatch",
                "message": "Provider payment details do not match this order.",
                "amount": transaction.amount_naira,
                "email": transaction.email,
                "transaction_ref": transaction_ref,
            }
        settle_payment(transaction_ref)

    return {
        "paid": is_success,
        "status": str(tx_status or "unknown"),
        "amount": transaction.amount_naira,
        "email": transaction.email,
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
