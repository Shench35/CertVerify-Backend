import uuid
from datetime import datetime
from sqlmodel import SQLModel, Field


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True
    )
    api_key: str = Field(index=True, unique=True)
    user_id: str | None = Field(default=None, index=True)
    email: str = Field(index=True)
    name: str = Field(default="Default API Key")
    credits: int = Field(default=0)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
