from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Header, status
from third_party_service import (
    create_api_key,
    is_key_valid,
    has_credits,
    deduct_credit,
    get_credits_balance
)
from validator import validator

third_party_route = APIRouter()


@third_party_route.post("/api/v1/credits/purchase")
def purchase_credit(email: str):
    api_key = create_api_key(email)
    return {
        "api_key": api_key,
        "credits": 0,
        "message": "API key created successfully. Purchase credits to start verifying."
    }


@third_party_route.post("/api/v1/verify")
async def verify_certificate(
    file: UploadFile = File(...),
    cert_type: str = Form(...),
    x_api_key: str = Header(...)  # API key in header
):
    # Check key is valid
    if not is_key_valid(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    # Check credits available
    if not has_credits(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No credits remaining. Please purchase more credits."
        )

    # Validate file type
    allowed = {"image/jpeg", "image/png", "application/pdf"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only JPEG, PNG and PDF allowed."
        )

    # Deduct one credit
    deduct_credit(x_api_key)

    # Read file
    file_bytes = await file.read()
    filename = file.filename

    # Run verification pipeline
    result = validator(file_bytes, filename, cert_type)

    # Add credits remaining to response
    result["credits_remaining"] = get_credits_balance(x_api_key)

    return result