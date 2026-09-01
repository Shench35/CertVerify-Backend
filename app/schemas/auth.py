from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(..., description="User email address", json_schema_extra={"example": "user@example.com"})
    password: str = Field(..., min_length=6, description="User password (min 6 chars)", json_schema_extra={"example": "SecurePassword123!"})
    full_name: str | None = Field(None, description="Display name", json_schema_extra={"example": "John Doe"})


class LoginRequest(BaseModel):
    email: str = Field(..., json_schema_extra={"example": "user@example.com"})
    password: str = Field(..., json_schema_extra={"example": "SecurePassword123!"})


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Firebase refresh token")


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., json_schema_extra={"example": "user@example.com"})


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
