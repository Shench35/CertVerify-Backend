"""
TaskResult model for tracking async Celery task status and results.
"""

import uuid
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text


class TaskResult(SQLModel, table=True):
    """Tracks async Celery task status and results in the database."""
    __tablename__ = "task_results"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: str = Field(index=True, unique=True)
    task_type: str = Field(index=True)
    status: str = Field(default="pending", index=True)  # pending, started, success, failure
    user_id: str | None = Field(default=None, index=True)
    transaction_ref: str | None = Field(default=None, index=True)
    result: str | None = Field(default=None, sa_column=Column(Text))  # JSON stringified
    error: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)
