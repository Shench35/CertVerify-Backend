import uuid
import logging
from datetime import datetime, timedelta
from sqlmodel import Session, select, update
from sqlalchemy import and_, case, or_
from app.core.database import engine
from app.models.api_key import ApiKey
from app.services.credit_service import FREE_DAILY_CREDITS, refresh_b2b_key

logger = logging.getLogger(__name__)


def generate_api_key_string() -> str:
    return f"cvfy_{uuid.uuid4().hex}"


def get_b2b_key_data(api_key: str) -> ApiKey | None:
    with Session(engine) as session:
        statement = select(ApiKey).where(ApiKey.api_key == api_key)
        key = session.exec(statement).first()
    return refresh_b2b_key(key) if key else None


def create_b2b_key(
    email: str,
    user_id: str | None = None,
    name: str = "Default API Key",
    initial_credits: int = FREE_DAILY_CREDITS
) -> ApiKey:
    new_key = generate_api_key_string()
    with Session(engine) as session:
        key_obj = ApiKey(
            api_key=new_key,
            user_id=user_id,
            email=email,
            name=name,
            credits=FREE_DAILY_CREDITS,
            daily_credit_limit=FREE_DAILY_CREDITS,
            credits_reset_at=datetime.utcnow() + timedelta(hours=24),
            is_active=True
        )
        session.add(key_obj)
        session.commit()
        session.refresh(key_obj)
        return key_obj


def deduct_b2b_credit(api_key: str) -> bool:
    """Atomically deducts 1 credit in Postgres to prevent race conditions."""
    now = datetime.utcnow()
    subscription_expired = and_(
        ApiKey.subscription_expires_at.is_not(None),
        ApiKey.subscription_expires_at <= now,
    )
    daily_reset_due = ApiKey.credits_reset_at <= now

    statement = (
        update(ApiKey)
        .where(
            ApiKey.api_key == api_key,
            ApiKey.is_active,
            or_(ApiKey.credits > 0, daily_reset_due, subscription_expired),
        )
        .values(
            credits=case(
                (subscription_expired, FREE_DAILY_CREDITS - 1),
                (daily_reset_due, ApiKey.daily_credit_limit - 1),
                else_=ApiKey.credits - 1,
            ),
            daily_credit_limit=case(
                (subscription_expired, FREE_DAILY_CREDITS),
                else_=ApiKey.daily_credit_limit,
            ),
            subscription_plan=case(
                (subscription_expired, None),
                else_=ApiKey.subscription_plan,
            ),
            subscription_expires_at=case(
                (subscription_expired, None),
                else_=ApiKey.subscription_expires_at,
            ),
            credits_reset_at=case(
                (or_(daily_reset_due, subscription_expired), now + timedelta(hours=24)),
                else_=ApiKey.credits_reset_at,
            ),
            updated_at=now,
        )
    )

    with Session(engine) as session:
        result = session.exec(statement)
        session.commit()
        return result.rowcount > 0


def restore_b2b_credit(api_key: str) -> bool:
    """Restore one credit when a B2B verification cannot be queued."""
    now = datetime.utcnow()
    statement = (
        update(ApiKey)
        .where(
            ApiKey.api_key == api_key,
            ApiKey.credits < ApiKey.daily_credit_limit,
        )
        .values(
            credits=ApiKey.credits + 1,
            updated_at=now,
        )
    )

    with Session(engine) as session:
        result = session.exec(statement)
        session.commit()

    return result.rowcount > 0


def add_b2b_credits(api_key: str, amount: int) -> int:
    """Atomically adds credits to an API key."""
    with Session(engine) as session:
        result = session.exec(
            update(ApiKey)
            .where(ApiKey.api_key == api_key)
            .values(credits=ApiKey.credits + amount)
        )
        key = session.exec(
            select(ApiKey).where(ApiKey.api_key == api_key)
        ).first()
        session.commit()
        return key.credits if result.rowcount > 0 and key else 0


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
