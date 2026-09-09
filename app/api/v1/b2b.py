import logging
import uuid
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Header, Depends, status
from app.schemas.b2b import CreateApiKeyRequest, AddCreditsRequest
from app.services.b2b_service import (
    create_b2b_key,
    deduct_b2b_credit,
    restore_b2b_credit,
    add_b2b_credits,
    get_b2b_balance,
    get_user_b2b_keys,
    get_b2b_key_data,
    mask_api_key,
    rotate_b2b_key,
    revoke_b2b_key,
)
from app.core.security import get_current_user
from app.tasks.verification_tasks import run_b2b_verification
from app.services.upload_validation import read_and_validate_upload
from app.schemas.verification import CertificateType

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/keys/generate",
    status_code=status.HTTP_201_CREATED,
    summary="Generate B2B API Key",
    description="Creates a new API key for external B2B verification integration. The full secret key is only returned once."
)
async def generate_key(
    payload: CreateApiKeyRequest,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("uid")
    email = current_user.get("email") or payload.email

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required to generate an API key."
        )

    api_key_record = create_b2b_key(
        email=email,
        user_id=user_id,
        name=payload.name,
    )

    return {
        "id": str(api_key_record.id),
        "api_key": api_key_record.api_key,
        "masked_key": mask_api_key(api_key_record.api_key),
        "name": api_key_record.name,
        "credits": api_key_record.credits,
        "is_active": api_key_record.is_active,
        "created_at": api_key_record.created_at,
        "message": "API key generated successfully. Save this secret key securely — it will not be displayed in full again."
    }


@router.get(
    "/keys",
    summary="List User API Keys",
    description="Retrieves all API keys belonging to the authenticated account with secrets masked."
)
async def list_keys(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("uid")
    keys = get_user_b2b_keys(user_id=user_id)
    return {
        "count": len(keys),
        "api_keys": [
            {
                "id": str(k.id),
                "masked_key": mask_api_key(k.api_key),
                "name": k.name,
                "credits": k.credits,
                "is_active": k.is_active,
                "created_at": k.created_at
            }
            for k in keys
        ]
    }


@router.post(
    "/keys/{key_id}/rotate",
    summary="Rotate B2B API Key",
    description="Generates a new secret key for an existing API key record. The old secret key is invalidated immediately."
)
async def rotate_key_endpoint(
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("uid")
    key_obj, new_plain_key = rotate_b2b_key(user_id=user_id, key_id=key_id)
    if not key_obj or not new_plain_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active API key not found or does not belong to this account."
        )

    return {
        "id": str(key_obj.id),
        "api_key": new_plain_key,
        "masked_key": mask_api_key(new_plain_key),
        "name": key_obj.name,
        "credits": key_obj.credits,
        "is_active": key_obj.is_active,
        "message": "API key rotated successfully. Save this new secret key securely — it will not be displayed in full again."
    }


@router.post(
    "/keys/{key_id}/revoke",
    summary="Revoke B2B API Key",
    description="Deactivates an API key immediately, preventing any further verification requests."
)
@router.delete(
    "/keys/{key_id}",
    summary="Revoke B2B API Key (DELETE)",
    description="Deactivates an API key immediately, preventing any further verification requests."
)
async def revoke_key_endpoint(
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("uid")
    success = revoke_b2b_key(user_id=user_id, key_id=key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or does not belong to this account."
        )

    return {
        "success": True,
        "message": "API key revoked successfully."
    }


@router.post(
    "/credits/add",
    summary="Top-Up API Key Credits",
    description="Adds credits to an existing API key."
)
async def top_up_credits(
    payload: AddCreditsRequest,
    current_user: dict = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Manual credit top-ups are disabled. Purchase the B2B monthly subscription for 1,000 credits.",
    )


@router.post(
    "/verify",
    status_code=status.HTTP_202_ACCEPTED,
    summary="B2B Certificate Forensic Verification",
    description="Direct verification endpoint for third-party systems using API key authentication."
)
async def verify_certificate_b2b(
    file: UploadFile = File(..., description="Certificate image (PNG/JPG) or PDF"),
    cert_type: CertificateType = Form(..., description="Certificate type: WAEC or NECO"),
    x_api_key: str = Header(..., alias="X-API-Key", description="B2B API Key")
):
    key_data = get_b2b_key_data(x_api_key)
    if not key_data or not key_data.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or deactivated API key."
        )

    if key_data.credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No verification credits remaining. Please purchase or top up credits."
        )

    file_bytes = await read_and_validate_upload(file)

    # Atomic credit deduction
    deducted = deduct_b2b_credit(x_api_key)
    if not deducted:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Could not deduct verification credit. Insufficient balance."
        )

    task_id = str(uuid.uuid4())
    try:
        filename = file.filename or "certificate"
        run_b2b_verification.apply_async(
            args=[file_bytes.hex(), filename, cert_type.value, x_api_key],
            task_id=task_id,
            countdown=0,
        )
    except Exception:
        try:
            restored = restore_b2b_credit(x_api_key)
        except Exception:
            restored = False
            logger.exception("Failed to restore B2B credit after queue failure")
        if not restored:
            logger.error("B2B credit restoration was not confirmed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification could not be queued. No credit was consumed.",
        )

    return {
        "task_id": task_id,
        "status": "pending",
        "credits_remaining": get_b2b_balance(x_api_key),
        "message": "Verification queued. Retrieve the task result from the Celery result backend.",
    }
