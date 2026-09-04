import uuid
import json
from datetime import datetime
from sqlmodel import Session, select
from app.core.database import engine
from app.models.transaction import Transaction
from app.services.payment_service import mark_transaction_success, verify_webhook_signature


def test_payment_history_endpoint(auth_client, mock_user):
    # Insert a test transaction
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
