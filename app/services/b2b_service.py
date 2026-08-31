import uuid
import logging
from sqlmodel import Session, select, text
from app.core.database import engine
from app.models.api_key import ApiKey

logger = logging.getLogger(__name__)


def generate_api_key_string() -> str:
    return f"cvfy_{uuid.uuid4().hex}"


def get_b2b_key_data(api_key: str) -> ApiKey | None:
    with Session(engine) as session:
        statement = select(ApiKey).where(ApiKey.api_key == api_key)
        return session.exec(statement).first()


def create_b2b_key(
    email: str,
    user_id: str | None = None,
    name: str = "Default API Key",
    initial_credits: int = 0
) -> ApiKey:
    new_key = generate_api_key_string()
    with Session(engine) as session:
        key_obj = ApiKey(
            api_key=new_key,
            user_id=user_id,
            email=email,
            name=name,
            credits=initial_credits,
            is_active=True
        )
        session.add(key_obj)
        session.commit()
        session.refresh(key_obj)
        return key_obj


def deduct_b2b_credit(api_key: str) -> bool:
    """Atomically deducts 1 credit in Postgres to prevent race conditions."""
    with engine.connect() as conn:
        stmt = text("""
            UPDATE api_keys
            SET credits = credits - 1
            WHERE api_key = :api_key AND is_active = true AND credits > 0
        """)
        res = conn.execute(stmt, {"api_key": api_key})
        conn.commit()
        return res.rowcount > 0


def add_b2b_credits(api_key: str, amount: int) -> int:
    """Atomically adds credits to an API key."""
    with engine.connect() as conn:
        stmt = text("""
            UPDATE api_keys
            SET credits = credits + :amount
            WHERE api_key = :api_key
            RETURNING credits;
        """)
        res = conn.execute(stmt, {"api_key": api_key, "amount": amount})
        conn.commit()
        row = res.fetchone()
        return row[0] if row else 0


def get_b2b_balance(api_key: str) -> int:
    key_record = get_b2b_key_data(api_key)
    if not key_record or not key_record.is_active:
        return 0
    return key_record.credits


def get_user_b2b_keys(user_id: str | None = None, email: str | None = None) -> list[ApiKey]:
    with Session(engine) as session:
        statement = select(ApiKey)
        if user_id and email:
            statement = statement.where((ApiKey.user_id == user_id) | (ApiKey.email == email))
        elif user_id:
            statement = statement.where(ApiKey.user_id == user_id)
        elif email:
            statement = statement.where(ApiKey.email == email)
        else:
            return []
        statement = statement.order_by(ApiKey.created_at.desc())
        return session.exec(statement).all()
