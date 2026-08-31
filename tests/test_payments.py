import uuid
from datetime import datetime
from sqlmodel import Session
from app.core.database import engine
from app.models.transaction import Transaction
from app.services.payment_service import verify_webhook_signature


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


def test_webhook_signature_verification_helper():
    payload = b'{"Event":"charge_successful"}'
    # Invalid signature should return False
    assert verify_webhook_signature(payload, "invalid_signature_string") is False
    assert verify_webhook_signature(payload, None) is False
