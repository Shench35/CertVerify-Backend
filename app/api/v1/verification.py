import json
from typing import Optional
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, status
from sqlmodel import Session, select
from app.core.database import engine
from app.models.transaction import Transaction
from app.services.validator_service import validate_document
from app.core.security import get_current_user

router = APIRouter()

ALLOWED_EXTENSIONS = {"image/jpeg", "image/png", "application/pdf"}


@router.post(
    "/analyse",
    summary="Analyse Certificate Document",
    description="Runs multimodal forensic checks with Gemini and returns the final trust score and verdict."
)
async def analyse_certificate_endpoint(
    file: UploadFile = File(..., description="Certificate file (JPEG, PNG, PDF)"),
    cert_type: str = Form(..., description="WAEC or NECO"),
    transaction_ref: Optional[str] = Form(None, description="Optional paid transaction reference"),
    current_user: dict = Depends(get_current_user)
):
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

    # Forensic analysis & rule validation
    validation_result = validate_document(file_bytes, filename, cert_type)
    if not validation_result.get("success"):
        return {
            "success": False,
            "error": validation_result.get("error", "Analysis failed.")
        }

    if validation_result.get("type_mismatch"):
        return {
            "success": False,
            "type_mismatch": True,
            "message": validation_result.get("message"),
            "detected_type": validation_result.get("detected_type")
        }

    document_score = validation_result.get("final_score", 0)

    # Final verdict based on document forensic score alone
    if document_score >= 75:
        final_verdict = "AUTHENTIC"
    elif document_score >= 40:
        final_verdict = "SUSPICIOUS"
    else:
        final_verdict = "HIGH_RISK"

    # Save to database
    with Session(engine) as session:
        statement = select(Transaction).where(
            Transaction.transaction_ref == active_transaction_ref
        )
        tx = session.exec(statement).first()
        if tx:
            tx.user_id = user_id
            tx.cert_type = cert_type
            tx.verification_result = json.dumps(validation_result)
            tx.document_score = document_score
            tx.final_trust_score = document_score
            tx.final_verdict = final_verdict
            session.add(tx)
            session.commit()

    return {
        "success": True,
        "transaction_ref": active_transaction_ref,
        "final_trust_score": round(document_score, 1),
        "final_verdict": final_verdict,
        "document_score": round(document_score, 1),
        "flagged_issues": validation_result.get("flagged_issues", []),
        "triggered_flags": validation_result.get("triggered_flags", []),
        "tampering_signs": validation_result.get("tampering_signs", []),
        "extracted_info": validation_result.get("extracted_info", {}),
        "confidence_note": validation_result.get("confidence_note", ""),
        "message": "Document verification complete."
    }



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
