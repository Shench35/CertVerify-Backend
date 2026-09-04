import json
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Request, Header, Depends, HTTPException, status
from sqlmodel import Session, select
from app.core.database import engine
from app.models.transaction import Transaction
from app.schemas.payment import InitiatePaymentRequest, InitiatePaymentResponse, VerifyPaymentResponse
from app.services.payment_service import (
    initiate_squad_payment,
    verify_squad_payment,
    verify_webhook_signature,
    mark_transaction_success,
    apply_payment_success_side_effects,
)
from app.core.security import get_current_user, get_optional_user
from app.services.b2b_service import get_b2b_key_data
from app.services.payment_service import PLAN_PRICES_NAIRA

router = APIRouter()


@router.post(
    "/pay/initiate",
    response_model=InitiatePaymentResponse,
    summary="Initiate Payment",
    description="Creates a transaction record and returns the Squad checkout URL."
)
async def initiate_payment(
    payload: InitiatePaymentRequest,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    user_id = current_user.get("uid") if current_user else None
    email = (current_user.get("email") if current_user else None) or payload.email

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is required to initiate payment."
        )

    expected_amount = PLAN_PRICES_NAIRA[payload.plan]
    if payload.amount_naira != expected_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{payload.plan} costs {expected_amount:.0f} Naira."
        )
    if payload.plan == "user_monthly" and not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login is required for a user subscription.")
    if payload.plan == "b2b_monthly":
        if not current_user or not payload.api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login and an API key are required for a B2B subscription.")
        key = get_b2b_key_data(payload.api_key)
        if not key or key.user_id != current_user.get("uid"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The API key does not belong to this account.")

    res = await initiate_squad_payment(
        amount_naira=payload.amount_naira,
        email=email,
        user_id=user_id,
        payment_plan=payload.plan,
        api_key=payload.api_key,
    )
    return res


@router.get(
    "/pay/verify/{transaction_ref}",
    response_model=VerifyPaymentResponse,
    summary="Verify Payment",
    description="Checks payment confirmation with Squad API and updates database."
)
async def verify_payment(
    transaction_ref: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("uid")
    with Session(engine) as session:
        transaction = session.exec(
            select(Transaction).where(
                Transaction.transaction_ref == transaction_ref,
                Transaction.user_id == user_id,
            )
        ).first()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment transaction not found.",
        )

    res = await verify_squad_payment(transaction_ref)
    return res


@router.post(
    "/webhook",
    summary="Squad Payment Webhook",
    description="Receives automated payment confirmation events from Squad."
)
async def squad_webhook(
    request: Request,
    x_squad_encrypted_body: Optional[str] = Header(None)
):
    body_bytes = await request.body()

    if not verify_webhook_signature(body_bytes, x_squad_encrypted_body):
        return {"status": "rejected", "reason": "invalid signature"}

    payload = json.loads(body_bytes)
    if payload.get("Event") != "charge_successful":
        return {"status": "ignored", "reason": "not a charge event"}

    body = payload.get("Body", {})
    transaction_ref = body.get("transaction_ref")
    transaction_status = body.get("transaction_status")

    if transaction_status != "Success":
        return {"status": "ignored", "reason": "transaction not successful"}

    tx, transitioned = mark_transaction_success(transaction_ref)
    if not tx:
        return {"status": "ignored", "reason": "transaction not found"}
    if not transitioned:
        return {"status": "ignored", "reason": "already processed"}

    apply_payment_success_side_effects(tx)

    # Queue payment confirmation email asynchronously
    if tx.email:
        from app.tasks.email_tasks import send_payment_confirmation_task
        send_payment_confirmation_task.delay(
            email=tx.email,
            transaction_ref=transaction_ref,
            amount=tx.amount_naira
        )

    return {"status": "success", "transaction_ref": transaction_ref}


@router.get(
    "/paymentsuccess",
    summary="Payment Browser Callback",
    description="Landing redirect page for user following inline payment."
)
async def payment_callback(reference: str = None):
    if not reference:
        return {"message": "No transaction reference received."}
    res = await verify_squad_payment(reference)
    return {
        "message": "Payment processed successfully.",
        "transaction_ref": reference,
        "status": res.get("status")
    }


@router.get(
    "/history",
    summary="Get Payment History",
    description="Lists all payment transactions for the authenticated user."
)
async def get_payment_history(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("uid")
    email = current_user.get("email")

    with Session(engine) as session:
        statement = (
            select(Transaction)
            .where((Transaction.user_id == user_id) | (Transaction.email == email))
            .order_by(Transaction.created_at.desc())
        )
        transactions = session.exec(statement).all()

    return {
        "count": len(transactions),
        "transactions": transactions
    }
