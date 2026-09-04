from datetime import datetime
import uuid

from sqlmodel import Field, SQLModel


class UserCreditAccount(SQLModel, table=True):
    __tablename__ = "user_credit_accounts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: str = Field(index=True, unique=True)
    email: str = Field(index=True)
    credits: int = Field(default=3)
    daily_credit_limit: int = Field(default=3)
    credits_reset_at: datetime = Field(default_factory=datetime.utcnow)
    subscription_plan: str | None = Field(default=None)
    subscription_expires_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)