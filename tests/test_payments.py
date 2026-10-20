import uuid
import json
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.core.database import engine
from app.models.transaction import Transaction
from app.models.user_credit import UserCreditAccount
from app.services.credit_service import SUBSCRIPTION_DURATION
from app.services.payment_service import (
    mark_transaction_success,
    settle_payment,
    verify_webhook_signature,
)


def test_payment_history_endpoint(auth_client, mock_user):
    # Insert a test transaction with matching user_id
    tx_ref = str(uuid.uuid4())
    with Session(engine) as session:
        tx = Transaction(
            transaction_ref=tx_ref,
            user_id=mock_user["uid"],
            email=mock_user["email"],
            amount_naira=1500.0,
            amount_kobo=150000,
            status="success",
            paid_at=datetime.utcnow()
        )
        session.add(tx)
        session.commit()

    # Query payment history
    res = auth_client.get("/payment/history")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 1
    assert any(t["transaction_ref"] == tx_ref for t in data["transactions"])


def test_payment_history_excludes_same_email_different_or_null_user_id(auth_client, mock_user):
    # Transaction with same email but user_id is NULL
    tx_null_uid = str(uuid.uuid4())
    # Transaction with same email but belonging to another UID
    tx_other_uid = str(uuid.uuid4())

    with Session(engine) as session:
        session.add(Transaction(
            transaction_ref=tx_null_uid,
            user_id=None,
            email=mock_user["email"],
            amount_naira=1000.0,
            amount_kobo=100000,
            status="success",
            paid_at=datetime.utcnow()
        ))
        session.add(Transaction(
            transaction_ref=tx_other_uid,
            user_id="other-user-uid-999",
            email=mock_user["email"],
            amount_naira=2000.0,
            amount_kobo=200000,
            status="success",
            paid_at=datetime.utcnow()
        ))
        session.commit()

    # History strictly queries by user_id and MUST NOT include either of these
    res = auth_client.get("/payment/history")
    assert res.status_code == 200
    refs = [t["transaction_ref"] for t in res.json()["transactions"]]
    assert tx_null_uid not in refs
    assert tx_other_uid not in refs




def test_payment_verification_requires_transaction_ownership(client):
    response = client.get(f"/payment/pay/verify/{uuid.uuid4()}")

    assert response.status_code == 401


def test_payment_verification_hides_other_users_transactions(auth_client):
    tx_ref = str(uuid.uuid4())
    with Session(engine) as session:
        session.add(Transaction(
            transaction_ref=tx_ref,
            user_id="different-user-id",
            email="other-user@example.com",
            amount_naira=5000.0,
            amount_kobo=500000,
            status="success",
            paid_at=datetime.utcnow(),
        ))
        session.commit()

    response = auth_client.get(f"/payment/pay/verify/{tx_ref}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment transaction not found."


def test_transaction_success_transition_is_idempotent():
    tx_ref = str(uuid.uuid4())
    with Session(engine) as session:
        session.add(Transaction(
            transaction_ref=tx_ref,
            email="idempotency-test@example.com",
            amount_naira=5000.0,
            amount_kobo=500000,
            status="pending",
        ))
        session.commit()

    first_transaction, first_transitioned = mark_transaction_success(tx_ref)
    second_transaction, second_transitioned = mark_transaction_success(tx_ref)

    assert first_transaction.status == "success"
    assert first_transitioned is True
    assert second_transaction.status == "success"
    assert second_transitioned is False


def test_second_payment_extends_active_subscription():
    user_id = f"sub-test-{uuid.uuid4().hex}"
    transaction_refs = [str(uuid.uuid4()), str(uuid.uuid4())]
    with Session(engine) as session:
        for transaction_ref in transaction_refs:
            session.add(Transaction(
                transaction_ref=transaction_ref,
                user_id=user_id,
                email="subscription-test@example.com",
                amount_naira=5000.0,
                amount_kobo=500000,
                status="pending",
                payment_plan="user_monthly",
            ))
        session.commit()

    settle_payment(transaction_refs[0])
    with Session(engine) as session:
        account = session.exec(
            select(UserCreditAccount).where(UserCreditAccount.user_id == user_id)
        ).first()
        first_expiry = account.subscription_expires_at

    settle_payment(transaction_refs[1])
    with Session(engine) as session:
        account = session.exec(
            select(UserCreditAccount).where(UserCreditAccount.user_id == user_id)
        ).first()
        second_expiry = account.subscription_expires_at

    assert abs((second_expiry - first_expiry - SUBSCRIPTION_DURATION).total_seconds()) < 60


def test_payment_after_expiry_starts_from_now():
    user_id = f"sub-test-{uuid.uuid4().hex}"
    transaction_refs = [str(uuid.uuid4()), str(uuid.uuid4())]
    with Session(engine) as session:
        for transaction_ref in transaction_refs:
            session.add(Transaction(
                transaction_ref=transaction_ref,
                user_id=user_id,
                email="subscription-test@example.com",
                amount_naira=5000.0,
                amount_kobo=500000,
                status="pending",
                payment_plan="user_monthly",
            ))
        session.commit()

    settle_payment(transaction_refs[0])
    with Session(engine) as session:
        account = session.exec(
            select(UserCreditAccount).where(UserCreditAccount.user_id == user_id)
        ).first()
        account.subscription_expires_at = datetime.utcnow() - timedelta(days=1)
        session.add(account)
        session.commit()

    settle_payment(transaction_refs[1])
    with Session(engine) as session:
        account = session.exec(
            select(UserCreditAccount).where(UserCreditAccount.user_id == user_id)
        ).first()
        new_expiry = account.subscription_expires_at

    expected_expiry = datetime.utcnow() + SUBSCRIPTION_DURATION
    assert abs((new_expiry - expected_expiry).total_seconds()) < 60


def test_repeat_payment_does_not_reduce_credits():
    user_id = f"sub-test-{uuid.uuid4().hex}"
    transaction_refs = [str(uuid.uuid4()), str(uuid.uuid4())]
    with Session(engine) as session:
        for transaction_ref in transaction_refs:
            session.add(Transaction(
                transaction_ref=transaction_ref,
                user_id=user_id,
                email="subscription-test@example.com",
                amount_naira=5000.0,
                amount_kobo=500000,
                status="pending",
                payment_plan="user_monthly",
            ))
        session.commit()

    settle_payment(transaction_refs[0])
    with Session(engine) as session:
        account = session.exec(
            select(UserCreditAccount).where(UserCreditAccount.user_id == user_id)
        ).first()
        account.credits = 25
        session.add(account)
        session.commit()

    settle_payment(transaction_refs[1])
    with Session(engine) as session:
        account = session.exec(
            select(UserCreditAccount).where(UserCreditAccount.user_id == user_id)
        ).first()
        assert account.credits >= 25


def test_settle_payment_is_idempotent_for_same_transaction():
    user_id = f"sub-test-{uuid.uuid4().hex}"
    transaction_ref = str(uuid.uuid4())
    with Session(engine) as session:
        session.add(Transaction(
            transaction_ref=transaction_ref,
            user_id=user_id,
            email="subscription-test@example.com",
            amount_naira=5000.0,
            amount_kobo=500000,
            status="pending",
            payment_plan="user_monthly",
        ))
        session.commit()

    first_transaction, first_transitioned = settle_payment(transaction_ref)
    with Session(engine) as session:
        account = session.exec(
            select(UserCreditAccount).where(UserCreditAccount.user_id == user_id)
        ).first()
        first_expiry = account.subscription_expires_at

    second_transaction, second_transitioned = settle_payment(transaction_ref)
    with Session(engine) as session:
        account = session.exec(
            select(UserCreditAccount).where(UserCreditAccount.user_id == user_id)
        ).first()
        second_expiry = account.subscription_expires_at

    assert first_transaction is not None
    assert first_transitioned is True
    assert second_transaction is not None
    assert second_transitioned is False
    assert second_expiry == first_expiry


def test_webhook_signature_verification_helper():
    payload = b'{"Event":"charge_successful"}'
    # Invalid signature should return False
    assert verify_webhook_signature(payload, "invalid_signature_string") is False
    assert verify_webhook_signature(payload, None) is False


def test_webhook_rejects_unsigned_request(client):
    tx_ref = str(uuid.uuid4())
    with Session(engine) as session:
        session.add(Transaction(
            transaction_ref=tx_ref,
            email="webhook-test@example.com",
            amount_naira=5000.0,
            amount_kobo=500000,
            status="pending",
        ))
        session.commit()

    payload = {
        "Event": "charge_successful",
        "Body": {
            "transaction_ref": tx_ref,
            "transaction_status": "Success",
        },
    }
    response = client.post("/payment/webhook", content=json.dumps(payload))

    assert response.status_code == 200
    assert response.json() == {"status": "rejected", "reason": "invalid signature"}

    with Session(engine) as session:
        transaction = session.exec(
            select(Transaction).where(Transaction.transaction_ref == tx_ref)
        ).first()
        assert transaction.status == "pending"
