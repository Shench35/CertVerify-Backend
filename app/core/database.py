from typing import Generator
from sqlmodel import create_engine, Session
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=300
)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding database sessions."""
    with Session(engine) as session:
        yield session
