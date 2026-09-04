import httpx
import logging
from fastapi import HTTPException, status
from firebase_admin import auth
from firebase_admin.auth import EmailAlreadyExistsError, UserNotFoundError
from google.auth.exceptions import TransportError
from requests.exceptions import RequestException
from app.core.config import settings
from app.core.firebase import initialize_firebase
from app.services.credit_service import ensure_user_credit_account

logger = logging.getLogger(__name__)

# Ensure Firebase initialized
initialize_firebase()

IDENTITY_TOOLKIT_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
SECURE_TOKEN_URL = "https://securetoken.googleapis.com/v1/token"
SEND_OOB_CODE_URL = "https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode"


async def register_user(email: str, password: str, display_name: str | None = None) -> dict:
    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long."
        )

    try:
        user_record = auth.create_user(
            email=email,
            password=password,
            display_name=display_name,
            email_verified=False
        )
        ensure_user_credit_account(user_record.uid, user_record.email)
        return {
            "uid": user_record.uid,
            "email": user_record.email,
            "display_name": user_record.display_name,
            "message": "User registered successfully."
        }
    except EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )
    except (RequestException, TransportError) as e:
        logger.error(f"Network error creating user in Firebase: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to reach Firebase authentication service."
        )
    except Exception as e:
        logger.error(f"Error creating user in Firebase: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )


async def login_user(email: str, password: str) -> dict:
    if not settings.FIREBASE_WEB_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="FIREBASE_WEB_API_KEY is not configured on the server."
        )

    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{IDENTITY_TOOLKIT_URL}?key={settings.FIREBASE_WEB_API_KEY}",
                json=payload
            )
        except httpx.RequestError as e:
            logger.error(f"Network error during Firebase login: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to reach Firebase authentication service."
            )

    data = response.json()

    if response.status_code != 200:
        error_msg = data.get("error", {}).get("message", "INVALID_CREDENTIALS")
        if error_msg in ["EMAIL_NOT_FOUND", "INVALID_PASSWORD", "INVALID_LOGIN_CREDENTIALS"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )
        elif error_msg == "USER_DISABLED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This user account has been disabled."
            )
        elif "TOO_MANY_ATTEMPTS" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Please try again later."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Authentication failed: {error_msg}"
            )

    ensure_user_credit_account(data.get("localId"), data.get("email"))
    return {
        "access_token": data.get("idToken"),
        "refresh_token": data.get("refreshToken"),
        "expires_in": int(data.get("expiresIn", 3600)),
        "token_type": "bearer",
        "uid": data.get("localId"),
        "email": data.get("email"),
        "display_name": data.get("displayName")
    }


async def refresh_access_token(refresh_token: str) -> dict:
    if not settings.FIREBASE_WEB_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="FIREBASE_WEB_API_KEY is not configured on the server."
        )

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{SECURE_TOKEN_URL}?key={settings.FIREBASE_WEB_API_KEY}",
                data=payload
            )
        except httpx.RequestError as e:
            logger.error(f"Network error during token refresh: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to reach Firebase token service."
            )

    data = response.json()

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token."
        )

    return {
        "access_token": data.get("id_token"),
        "refresh_token": data.get("refresh_token"),
        "expires_in": int(data.get("expires_in", 3600)),
        "token_type": "bearer",
        "user_id": data.get("user_id")
    }


async def send_password_reset_email(email: str) -> dict:
    if not settings.FIREBASE_WEB_API_KEY:
        try:
            link = auth.generate_password_reset_link(email)
            return {"message": "Password reset link generated.", "reset_link": link}
        except UserNotFoundError:
            return {"message": "If the email is registered, a password reset link has been sent."}
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    payload = {"requestType": "PASSWORD_RESET", "email": email}

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{SEND_OOB_CODE_URL}?key={settings.FIREBASE_WEB_API_KEY}",
                json=payload
            )
        except Exception as e:
            logger.error(f"Error during password reset request: {e}")

    return {"message": "If the email is registered, a password reset email has been sent."}


def get_user_profile(uid: str) -> dict:
    try:
        user = auth.get_user(uid)
        return {
            "uid": user.uid,
            "email": user.email,
            "display_name": user.display_name,
            "email_verified": user.email_verified,
            "disabled": user.disabled,
            "photo_url": user.photo_url
        }
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch user profile: {str(e)}"
        )
