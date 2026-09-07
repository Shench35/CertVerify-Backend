from datetime import datetime, timedelta

from sqlmodel import Session, select, update
from sqlalchemy import and_, case, or_

from app.core.database import engine
from app.models.api_key import ApiKey
from app.models.user_credit import UserCreditAccount

FREE_DAILY_CREDITS = 3
USER_SUBSCRIPTION_CREDITS = 20
B2B_SUBSCRIPTION_CREDITS = 1000
SUBSCRIPTION_DURATION = timedelta(days=30)
DAILY_RESET_INTERVAL = timedelta(hours=24)


def _subscription_active(expires_at: datetime | None, now: datetime) -> bool:
    return expires_at is not None and expires_at > now


def ensure_user_credit_account(user_id: str, email: str | None) -> UserCreditAccount:
    now = datetime.utcnow()
    with Session(engine) as session:
        account = session.exec(
            select(UserCreditAccount).where(UserCreditAccount.user_id == user_id)
        ).first()
        if not account:
            account = UserCreditAccount(
                user_id=user_id,
                email=email or "",
                credits=FREE_DAILY_CREDITS,
                daily_credit_limit=FREE_DAILY_CREDITS,
                credits_reset_at=now + DAILY_RESET_INTERVAL,
            )
            session.add(account)
            session.commit()
            session.refresh(account)
        return account


def _refresh_user_account(account: UserCreditAccount, now: datetime) -> None:
    if account.subscription_expires_at and account.subscription_expires_at <= now:
        account.subscription_plan = None
        account.subscription_expires_at = None
        account.daily_credit_limit = FREE_DAILY_CREDITS
        account.credits = FREE_DAILY_CREDITS
        account.credits_reset_at = now + DAILY_RESET_INTERVAL
    elif now >= account.credits_reset_at:
        account.credits = account.daily_credit_limit
        account.credits_reset_at = now + DAILY_RESET_INTERVAL


def deduct_user_credit(user_id: str, email: str | None) -> tuple[bool, int]:
    account = ensure_user_credit_account(user_id, email)
    now = datetime.utcnow()
    subscription_expired = and_(
        UserCreditAccount.subscription_expires_at.is_not(None),
        UserCreditAccount.subscription_expires_at <= now,
    )
    daily_reset_due = UserCreditAccount.credits_reset_at <= now

    statement = (
        update(UserCreditAccount)
        .where(
            UserCreditAccount.user_id == user_id,
            or_(
                UserCreditAccount.credits > 0,
                daily_reset_due,
                subscription_expired,
            ),
        )
        .values(
            credits=case(
                (subscription_expired, FREE_DAILY_CREDITS - 1),
                (daily_reset_due, UserCreditAccount.daily_credit_limit - 1),
                else_=UserCreditAccount.credits - 1,
            ),
            daily_credit_limit=case(
                (subscription_expired, FREE_DAILY_CREDITS),
                else_=UserCreditAccount.daily_credit_limit,
            ),
            subscription_plan=case(
                (subscription_expired, None),
                else_=UserCreditAccount.subscription_plan,
            ),
            subscription_expires_at=case(
                (subscription_expired, None),
                else_=UserCreditAccount.subscription_expires_at,
            ),
            credits_reset_at=case(
                (or_(daily_reset_due, subscription_expired), now + DAILY_RESET_INTERVAL),
                else_=UserCreditAccount.credits_reset_at,
            ),
            updated_at=now,
        )
    )

    with Session(engine) as session:
        result = session.exec(statement)
        account = session.exec(
            select(UserCreditAccount).where(UserCreditAccount.user_id == user_id)
        ).first()
        session.commit()
        remaining_credits = account.credits if account else 0

    return result.rowcount > 0, remaining_credits


def restore_user_credit(user_id: str) -> bool:
    """Restore one credit after a verification could not be queued."""
    now = datetime.utcnow()
    statement = (
        update(UserCreditAccount)
        .where(
            UserCreditAccount.user_id == user_id,
            UserCreditAccount.credits < UserCreditAccount.daily_credit_limit,
        )
        .values(
            credits=UserCreditAccount.credits + 1,
            updated_at=now,
        )
    )

    with Session(engine) as session:
        result = session.exec(statement)
        session.commit()

    return result.rowcount > 0


def activate_user_subscription(user_id: str, email: str | None) -> UserCreditAccount:
    account = ensure_user_credit_account(user_id, email)
    now = datetime.utcnow()
    with Session(engine) as session:
        account = session.get(UserCreditAccount, account.id)
        account.daily_credit_limit = USER_SUBSCRIPTION_CREDITS
        account.credits = USER_SUBSCRIPTION_CREDITS
        account.credits_reset_at = now + DAILY_RESET_INTERVAL
        account.subscription_plan = "user_monthly"
        account.subscription_expires_at = now + SUBSCRIPTION_DURATION
        account.updated_at = now
        session.add(account)
        session.commit()
        session.refresh(account)
        return account


def get_user_credit_status(user_id: str, email: str | None) -> UserCreditAccount:
    account = ensure_user_credit_account(user_id, email)
    now = datetime.utcnow()
    with Session(engine) as session:
        account = session.get(UserCreditAccount, account.id)
        _refresh_user_account(account, now)
        account.updated_at = now
        session.add(account)
        session.commit()
        session.refresh(account)
        return account


def refresh_b2b_key(key: ApiKey) -> ApiKey:
    now = datetime.utcnow()
    with Session(engine) as session:
        key = session.get(ApiKey, key.id)
        if key.subscription_expires_at and key.subscription_expires_at <= now:
            key.subscription_plan = None
            key.subscription_expires_at = None
            key.daily_credit_limit = FREE_DAILY_CREDITS
            key.credits = FREE_DAILY_CREDITS
            key.credits_reset_at = now + DAILY_RESET_INTERVAL
        elif now >= key.credits_reset_at:
            key.credits = key.daily_credit_limit
            key.credits_reset_at = now + DAILY_RESET_INTERVAL
        key.updated_at = now
        session.add(key)
        session.commit()
        session.refresh(key)
        return key


def activate_b2b_subscription(api_key: str) -> ApiKey | None:
    now = datetime.utcnow()
    with Session(engine) as session:
        key = session.exec(select(ApiKey).where(ApiKey.api_key == api_key)).first()
        if not key:
            return None
        key.daily_credit_limit = B2B_SUBSCRIPTION_CREDITS
        key.credits = B2B_SUBSCRIPTION_CREDITS
        key.credits_reset_at = now + DAILY_RESET_INTERVAL
        key.subscription_plan = "b2b_monthly"
        key.subscription_expires_at = now + SUBSCRIPTION_DURATION
        session.add(key)
        session.commit()
        session.refresh(key)
        return key