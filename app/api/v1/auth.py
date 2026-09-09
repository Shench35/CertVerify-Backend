from fastapi import APIRouter, Depends, status
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    AuthResponse
)
from app.services.auth_service import (
    register_user,
    login_user,
    refresh_access_token,
    send_password_reset_email,
    get_user_profile
)
from app.core.security import get_current_user

router = APIRouter()



@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Registers a new candidate or organization account with Firebase Auth."
)
async def register(payload: RegisterRequest):
    return await register_user(
        email=payload.email,
        password=payload.password,
        display_name=payload.full_name
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="User Login",
    description="Authenticates with Firebase Identity Toolkit and returns ID & refresh tokens."
)
async def login(payload: LoginRequest):
    return await login_user(
        email=payload.email,
        password=payload.password
    )


@router.post(
    "/refresh",
    summary="Refresh Access Token",
    description="Exchanges a valid refresh token for a fresh Firebase ID token."
)
async def refresh_token(payload: RefreshTokenRequest):
    return await refresh_access_token(payload.refresh_token)


@router.post(
    "/forgot-password",
    summary="Forgot Password",
    description="Sends a password reset email via Firebase to the registered user."
)
async def forgot_password(payload: ForgotPasswordRequest):
    return await send_password_reset_email(payload.email)


@router.get(
    "/me",
    summary="Get Current User Profile",
    description="Returns the authenticated user's profile verified via Bearer ID token."
)
async def get_me(current_user: dict = Depends(get_current_user)):
    profile = get_user_profile(current_user["uid"])
    return {
        "user": profile,
        "token_claims": current_user
    }


