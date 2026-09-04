from typing import Optional
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Header, Depends, status
from app.schemas.b2b import CreateApiKeyRequest, AddCreditsRequest
from app.services.b2b_service import (
    create_b2b_key,
    deduct_b2b_credit,
    add_b2b_credits,
    get_b2b_balance,
    get_user_b2b_keys,
    get_b2b_key_data
)
from app.services.validator_service import validate_document
from app.core.security import get_current_user

router = APIRouter()


@router.post(
    "/keys/generate",
    status_code=status.HTTP_201_CREATED,
    summary="Generate B2B API Key",
    description="Creates a new API key for external B2B verification integration."
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
        initial_credits=payload.initial_credits
    )

    return {
        "api_key": api_key_record.api_key,
        "name": api_key_record.name,
        "credits": api_key_record.credits,
        "created_at": api_key_record.created_at,
        "message": "API key generated successfully. Add verification credits to start verifying."
    }


@router.get(
    "/keys",
    summary="List User API Keys",
    description="Retrieves all API keys belonging to the authenticated account."
)
async def list_keys(current_user: dict = Depends(get_current_user)):
    keys = get_user_b2b_keys(
        user_id=current_user.get("uid"),
        email=current_user.get("email")
    )
    return {
        "count": len(keys),
        "api_keys": [
            {
                "api_key": k.api_key,
                "name": k.name,
                "credits": k.credits,
                "is_active": k.is_active,
                "created_at": k.created_at
            }
            for k in keys
        ]
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
    summary="B2B Certificate Forensic Verification",
    description="Direct verification endpoint for third-party systems using API key authentication."
)
async def verify_certificate_b2b(
    file: UploadFile = File(..., description="Certificate image (PNG/JPG) or PDF"),
    cert_type: str = Form(..., description="WAEC or NECO"),
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

    allowed = {"image/jpeg", "image/png", "application/pdf"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only JPEG, PNG, and PDF are supported."
        )

    # Atomic credit deduction
    deducted = deduct_b2b_credit(x_api_key)
    if not deducted:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Could not deduct verification credit. Insufficient balance."
        )

    file_bytes = await file.read()
    filename = file.filename

    result = validate_document(file_bytes, filename, cert_type)
    result["credits_remaining"] = get_b2b_balance(x_api_key)

    return result
