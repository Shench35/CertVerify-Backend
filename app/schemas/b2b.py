from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CreateApiKeyRequest(BaseModel):
    name: str = Field(default="My API Key", description="Friendly identifier for key")
    email: Optional[str] = Field(default=None, description="Owner email (optional if using Bearer token)")



class AddCreditsRequest(BaseModel):
    api_key: str = Field(..., description="Target API Key")
    credits: int = Field(..., gt=0, description="Credits count to add")


class ApiKeyListItem(BaseModel):
    id: str
    name: str
    masked_key: str
    credits: int
    is_active: bool
    created_at: datetime


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    masked_key: str
    credits: int
    is_active: bool
    created_at: datetime


class ApiKeyCreatedResponse(BaseModel):
    id: str
    api_key: str
    masked_key: str
    name: str
    credits: int
    is_active: bool
    created_at: datetime
    message: str


class ApiKeyRotatedResponse(BaseModel):
    id: str
    api_key: str
    masked_key: str
    name: str
    credits: int
    is_active: bool
    message: str
