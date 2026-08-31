from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(..., example="user@example.com", description="User email address")
    password: str = Field(..., min_length=6, example="SecurePassword123!", description="User password (min 6 chars)")
    full_name: str | None = Field(None, example="John Doe", description="Display name")


class LoginRequest(BaseModel):
    email: str = Field(..., example="user@example.com")
    password: str = Field(..., example="SecurePassword123!")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Firebase refresh token")


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., example="user@example.com")


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"
    uid: str
    email: str
    display_name: str | None = None


class UserResponse(BaseModel):
    uid: str
    email: str
    display_name: str | None = None
    email_verified: bool = False
    disabled: bool = False
    photo_url: str | None = None
