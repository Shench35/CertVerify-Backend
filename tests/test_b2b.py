import uuid
from datetime import datetime, timedelta
from sqlmodel import Session

from app.core.database import engine
from app.models.api_key import ApiKey
from app.models.user_credit import UserCreditAccount
from app.services.b2b_service import (
    create_b2b_key,
    deduct_b2b_credit,
    add_b2b_credits,
    get_b2b_balance,
    get_b2b_key_data
)
from app.services.credit_service import (
    activate_b2b_subscription,
    activate_user_subscription,
    deduct_user_credit,
    ensure_user_credit_account,
    get_user_credit_status,
)


def test_b2b_key_lifecycle(auth_client, mock_user):
    # 1. Generate Key via API
    key_name = f"Test Integration Key {uuid.uuid4().hex[:6]}"
    res = auth_client.post(
        "/third_party/api/v1/keys/generate",
        json={"name": key_name, "initial_credits": 999}
    )
    assert res.status_code == 201
    data = res.json()
    api_key = data["api_key"]
    assert api_key.startswith("cvfy_")
    assert data["credits"] == 3

    # 2. List Keys via API
    res_list = auth_client.get("/third_party/api/v1/keys")
    assert res_list.status_code == 200
    keys = res_list.json()["api_keys"]
    assert any(k["api_key"] == api_key for k in keys)

    # 3. Arbitrary top-ups are disabled; subscriptions control paid credits.
    res_topup = auth_client.post(
        "/third_party/api/v1/credits/add",
        json={"api_key": api_key, "credits": 10}
    )
    assert res_topup.status_code == 410

    # 4. Deduct credit service call
    deducted = deduct_b2b_credit(api_key)
    assert deducted is True
    assert get_b2b_balance(api_key) == 2


def test_b2b_verification_is_queued(auth_client, sample_certificate_image, monkeypatch):
    from app.api.v1 import b2b

    key_response = auth_client.post(
        "/third_party/api/v1/keys/generate",
        json={"name": "Queue Test Key"},
    )
    api_key = key_response.json()["api_key"]
    queued = {}

    def fake_apply_async(*, args, task_id, countdown):
        queued.update(args=args, task_id=task_id, countdown=countdown)

    monkeypatch.setattr(b2b.run_b2b_verification, "apply_async", fake_apply_async)
    response = auth_client.post(
        "/third_party/api/v1/verify",
        headers={"X-API-Key": api_key},
        files={"file": ("cert.jpg", sample_certificate_image, "image/jpeg")},
        data={"cert_type": "WAEC"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert queued["args"][0] == sample_certificate_image.hex()
    assert queued["args"][2] == "WAEC"


def test_user_credits_reset_and_subscription_expiry():
    user_id = f"credit-test-{uuid.uuid4().hex}"
    email = f"{user_id}@example.com"

    account = ensure_user_credit_account(user_id, email)
    assert account.credits == 3
    assert deduct_user_credit(user_id, email) == (True, 2)
    assert deduct_user_credit(user_id, email) == (True, 1)
    assert deduct_user_credit(user_id, email) == (True, 0)
    assert deduct_user_credit(user_id, email) == (False, 0)

    with Session(engine) as session:
        account = session.get(UserCreditAccount, account.id)
        account.credits_reset_at = datetime.utcnow() - timedelta(seconds=1)
        session.add(account)
        session.commit()

    assert get_user_credit_status(user_id, email).credits == 3
    account = activate_user_subscription(user_id, email)
    assert account.credits == 20
    assert account.daily_credit_limit == 20
    assert account.subscription_plan == "user_monthly"


def test_b2b_subscription_sets_monthly_allowance():
    key_value = f"cvfy_{uuid.uuid4().hex}"
    with Session(engine) as session:
        key = ApiKey(api_key=key_value, email="b2b@example.com", credits=3)
        session.add(key)
        session.commit()

    activated = activate_b2b_subscription(key_value)
    assert activated is not None
    assert activated.credits == 1000
    assert activated.daily_credit_limit == 1000
    assert activated.subscription_plan == "b2b_monthly"
