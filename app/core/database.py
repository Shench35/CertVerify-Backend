from typing import Generator
from sqlalchemy import text
from sqlmodel import SQLModel, create_engine, Session
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=300
)


def init_db():
    """Initializes all database tables registered in SQLModel metadata."""
    SQLModel.metadata.create_all(engine)
    # Keep existing installations compatible until a formal migration tool is added.
    with engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE transaction_records ADD COLUMN IF NOT EXISTS payment_plan VARCHAR"
        ))
        connection.execute(text(
            "ALTER TABLE transaction_records ADD COLUMN IF NOT EXISTS api_key VARCHAR"
        ))
        connection.execute(text(
            "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS daily_credit_limit INTEGER NOT NULL DEFAULT 3"
        ))
        connection.execute(text(
            "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS credits_reset_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
        ))
        connection.execute(text(
            "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR"
        ))
        connection.execute(text(
            "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS subscription_expires_at TIMESTAMP"
        ))
        connection.execute(text(
            "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
        ))
        connection.execute(text(
            "UPDATE api_keys SET credits = 3 WHERE credits IS NULL"
        ))


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding database sessions."""
    with Session(engine) as session:
        yield session
