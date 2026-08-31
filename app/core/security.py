import logging
from fastapi import HTTPException, Header, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
from firebase_admin.auth import (
    ExpiredIdTokenError,
    RevokedIdTokenError,
    InvalidIdTokenError
)
from app.core.firebase import initialize_firebase

logger = logging.getLogger(__name__)

# Ensure Firebase is initialized
initialize_firebase()

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    authorization: str = Header(None)
) -> dict:
    """
    Validates Firebase ID tokens and extracts user payload.
    Returns:
    {
        "uid": str,
        "email": str,
        "email_verified": bool,
        "name": str | None,
        "picture": str | None,
        "auth_time": int,
        "claims": dict
    }
    """
    token = None
    if credentials:
        token = credentials.credentials
    elif authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token missing. Please provide Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        decoded_token = auth.verify_id_token(token, check_revoked=True)
        user_info = {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "email_verified": decoded_token.get("email_verified", False),
            "name": decoded_token.get("name"),
            "picture": decoded_token.get("picture"),
            "auth_time": decoded_token.get("auth_time"),
            "claims": decoded_token
        }

        if not user_info["uid"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: UID missing."
            )

        return user_info

    except ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired. Please log in or refresh.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""}
        )
    except RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""}
        )
    except InvalidIdTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""}
        )
    except Exception as e:
        logger.error(f"Error validating Firebase token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. Invalid token."
        )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    authorization: str = Header(None)
) -> dict | None:
    """Optional dependency: returns user dict if token is provided, None otherwise."""
    if not credentials and not authorization:
        return None
    try:
        return await get_current_user(credentials, authorization)
    except HTTPException:
        return None
