import uuid
import logging
from datetime import datetime, timedelta
from sqlmodel import Session, select, update, func
from sqlalchemy import and_, case, or_
from app.core.database import engine
from app.models.api_key import ApiKey
from app.models.transaction import Transaction
from app.services.credit_service import FREE_DAILY_CREDITS
from app.core.api_key_security import hash_api_key, mask_api_key as format_masked_key

logger = logging.getLogger(__name__)


def generate_api_key_string() -> str:
    return f"cvfy_{uuid.uuid4().hex}"


def mask_api_key(key: str) -> str:
    """Masks an API key for safe display, revealing only the prefix and suffix."""
    return format_masked_key(key)


def stored_key_mask(key: ApiKey) -> str:
    if not key.api_key_prefix or not key.api_key_suffix:
        return "****"
    return f"{key.api_key_prefix}...{key.api_key_suffix}"


def get_b2b_key_data(api_key: str) -> ApiKey | None:
    with Session(engine) as session:
        statement = select(ApiKey).where(ApiKey.api_key == hash_api_key(api_key))
        key = session.exec(statement).first()
    return key


def create_b2b_key(
    email: str,
    user_id: str | None = None,
    name: str = "Default API Key"
) -> tuple[ApiKey, str]:
    new_key = generate_api_key_string()
    with Session(engine) as session:
        key_obj = ApiKey(
            api_key=hash_api_key(new_key),
            api_key_prefix=new_key[:8],
            api_key_suffix=new_key[-4:],
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
        return key_obj, new_key


def rotate_b2b_key(user_id: str, key_id: str | uuid.UUID) -> tuple[ApiKey | None, str | None]:
    """
    Rotates an active API key for a user.
    Generates a new secret key string, updates the record, and returns (key_obj, new_plain_key).
    """
    try:
        parsed_id = uuid.UUID(str(key_id))
    except (ValueError, TypeError):
        return None, None

    new_key_str = generate_api_key_string()
    now = datetime.utcnow()

    with Session(engine) as session:
        key_obj = session.exec(
            select(ApiKey).where(
                ApiKey.id == parsed_id,
                ApiKey.user_id == user_id,
                ApiKey.is_active == True,
            )
        ).first()

        if not key_obj:
            return None, None

        previous_hash = key_obj.api_key
        key_obj.api_key = hash_api_key(new_key_str)
        key_obj.api_key_prefix = new_key_str[:8]
        key_obj.api_key_suffix = new_key_str[-4:]
        key_obj.updated_at = now
        session.add(key_obj)
        # A pending subscription checkout belongs to this key record. Keep its
        # reference aligned when rotating the secret before payment completes.
        session.exec(
            update(Transaction)
            .where(
                Transaction.api_key == previous_hash,
                Transaction.status == "pending",
            )
            .values(api_key=key_obj.api_key)
        )
        session.commit()
        session.refresh(key_obj)
        return key_obj, new_key_str


def revoke_b2b_key(user_id: str, key_id: str | uuid.UUID) -> bool:
    """
    Revokes (deactivates) an API key for a user.
    """
    try:
        parsed_id = uuid.UUID(str(key_id))
    except (ValueError, TypeError):
        return False

    now = datetime.utcnow()
    with Session(engine) as session:
        key_obj = session.exec(
            select(ApiKey).where(
                ApiKey.id == parsed_id,
                ApiKey.user_id == user_id,
            )
        ).first()

        if not key_obj:
            return False

        key_obj.is_active = False
        key_obj.updated_at = now
        session.add(key_obj)
        session.commit()
        return True


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
            ApiKey.api_key == hash_api_key(api_key),
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
            ApiKey.api_key == hash_api_key(api_key),
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
            .where(ApiKey.api_key == hash_api_key(api_key))
            .values(credits=ApiKey.credits + amount)
        )
        key = session.exec(
            select(ApiKey).where(ApiKey.api_key == hash_api_key(api_key))
        ).first()
        session.commit()
        return key.credits if result.rowcount > 0 and key else 0


def get_b2b_balance(api_key: str) -> int:
    key_record = get_b2b_key_data(api_key)
    if not key_record or not key_record.is_active:
        return 0
    now = datetime.utcnow()
    if key_record.subscription_expires_at and key_record.subscription_expires_at <= now:
        return FREE_DAILY_CREDITS
    if key_record.credits_reset_at <= now:
        return key_record.daily_credit_limit
    return key_record.credits


def get_user_b2b_keys(
    user_id: str | None = None, page: int = 1, page_size: int = 100
) -> tuple[list[ApiKey], int]:
    if not user_id:
        return [], 0
    with Session(engine) as session:
        total = session.exec(
            select(func.count()).select_from(ApiKey).where(ApiKey.user_id == user_id)
        ).one()
        statement = (
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return session.exec(statement).all(), total
