import json
import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, status
from sqlmodel import Session, select
from app.core.database import engine
from app.models.transaction import Transaction
from app.models.task_result import TaskResult
from app.core.security import get_current_user
from app.tasks.verification_tasks import run_verification

router = APIRouter()

ALLOWED_EXTENSIONS = {"image/jpeg", "image/png", "application/pdf"}


@router.post(
    "/analyse",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Analyse Certificate Document (Async)",
    description="Queues certificate for AI-powered forensic verification. Returns task ID for polling status."
)
async def analyse_certificate_endpoint(
    file: UploadFile = File(..., description="Certificate file (JPEG, PNG, PDF)"),
    cert_type: str = Form(..., description="WAEC or NECO"),
    transaction_ref: Optional[str] = Form(None, description="Optional paid transaction reference"),
    current_user: dict = Depends(get_current_user)
):
    """
    Initiates async certificate verification via Celery.
    Returns 202 with task_id to poll for results via GET /status/{task_id}.
    """
    user_id = current_user.get("uid")
    email = current_user.get("email")

    if file.content_type not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only JPEG, PNG, and PDF are supported."
        )

    # Verify paid transaction exists
    with Session(engine) as session:
        if transaction_ref:
            statement = select(Transaction).where(
                Transaction.transaction_ref == transaction_ref,
                Transaction.status == "success"
            )
        else:
            statement = (
                select(Transaction)
                .where(
                    (Transaction.user_id == user_id) | (Transaction.email == email),
                    Transaction.status == "success",
                    Transaction.verification_result == None
                )
                .order_by(Transaction.created_at.desc())
            )
        transaction = session.exec(statement).first()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No confirmed paid transaction found. Please complete payment before running verification."
        )

    active_transaction_ref = transaction.transaction_ref
    file_bytes = await file.read()
    filename = file.filename

    # Convert file bytes to hex for JSON-safe transmission to Celery
    file_bytes_hex = file_bytes.hex()

    # Create TaskResult record with pending status
    task_id = str(uuid.uuid4())
    task_result = TaskResult(
        task_id=task_id,
        task_type="verification",
        status="pending",
        user_id=user_id,
        transaction_ref=active_transaction_ref
    )

    with Session(engine) as session:
        session.add(task_result)
        session.commit()

    # Dispatch to Celery with task_id
    run_verification.apply_async(
        args=[file_bytes_hex, filename, cert_type, active_transaction_ref, email],
        task_id=task_id,
        countdown=0
    )

    return {
        "task_id": task_id,
        "status": "pending",
        "transaction_ref": active_transaction_ref,
        "message": "Verification queued. Poll the status endpoint to check progress."
    }


@router.get(
    "/status/{task_id}",
    summary="Check Verification Task Status",
    description="Polls the status of an async verification task."
)
async def get_task_status(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Check the status of a verification task.
    Returns: {status, result (if complete), error (if failed)}
    """
    with Session(engine) as session:
        statement = select(TaskResult).where(TaskResult.task_id == task_id)
        task_result = session.exec(statement).first()

    if not task_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found."
        )

    # Authorization: ensure user owns this task
    if task_result.user_id != current_user.get("uid"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this task."
        )

    response = {
        "task_id": task_id,
        "status": task_result.status,
        "created_at": task_result.created_at,
        "updated_at": task_result.updated_at,
    }

    if task_result.status == "success" and task_result.result:
        try:
            response["result"] = json.loads(task_result.result)
        except json.JSONDecodeError:
            response["result"] = task_result.result

    if task_result.status == "failure" and task_result.error:
        response["error"] = task_result.error

    if task_result.completed_at:
        response["completed_at"] = task_result.completed_at

    return response


@router.get(
    "/history",
    summary="Get User Verification History",
    description="Returns all completed verification reports for the logged-in user."
)
async def get_user_verifications(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("uid")
    email = current_user.get("email")

    with Session(engine) as session:
        statement = (
            select(Transaction)
            .where(
                (Transaction.user_id == user_id) | (Transaction.email == email),
                Transaction.verification_result != None
            )
            .order_by(Transaction.created_at.desc())
        )
        records = session.exec(statement).all()

    return {
        "count": len(records),
        "verifications": [
            {
                "transaction_ref": r.transaction_ref,
                "cert_type": r.cert_type,
                "created_at": r.created_at,
                "document_score": r.document_score,
                "final_trust_score": r.final_trust_score,
                "final_verdict": r.final_verdict
            }
            for r in records
        ]
    }


@router.get(
    "/report/{transaction_ref}",
    summary="Get Detailed Verification Report",
    description="Fetches full detailed report for a specific verification by transaction reference."
)
async def get_verification_report(
    transaction_ref: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("uid")
    email = current_user.get("email")

    with Session(engine) as session:
        statement = select(Transaction).where(
            Transaction.transaction_ref == transaction_ref,
            (Transaction.user_id == user_id) | (Transaction.email == email)
        )
        record = session.exec(statement).first()

    if not record or not record.verification_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification report not found."
        )

    val_res = json.loads(record.verification_result)

    return {
        "transaction_ref": record.transaction_ref,
        "cert_type": record.cert_type,
        "created_at": record.created_at,
        "document_score": record.document_score,
        "final_trust_score": record.final_trust_score,
        "final_verdict": record.final_verdict,
        "extracted_info": val_res.get("extracted_info", {}),
        "flagged_issues": val_res.get("flagged_issues", []),
        "triggered_flags": val_res.get("triggered_flags", []),
        "tampering_signs": val_res.get("tampering_signs", [])
    }

