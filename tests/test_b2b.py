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
    get_b2b_key_data,
    mask_api_key,
)
from app.services.credit_service import (
    activate_b2b_subscription,
    activate_user_subscription,
    deduct_user_credit,
    ensure_user_credit_account,
    get_user_credit_status,
)


def test_b2b_key_lifecycle(auth_client, mock_user):
    # 1. Generate Key via API — full secret returned once
    key_name = f"Test Integration Key {uuid.uuid4().hex[:6]}"
    res = auth_client.post(
        "/third_party/api/v1/keys/generate",
        json={"name": key_name}
    )
    assert res.status_code == 201
    data = res.json()
    api_key = data["api_key"]
    key_id = data["id"]
    assert api_key.startswith("cvfy_")
    assert data["credits"] == 3
    assert data["masked_key"] == mask_api_key(api_key)

    # 2. List Keys via API — secrets must be MASKED
    res_list = auth_client.get("/third_party/api/v1/keys")
    assert res_list.status_code == 200
    keys = res_list.json()["api_keys"]
    # Plain bearer key must NEVER appear in list output
    assert not any(k.get("api_key") == api_key for k in keys)
    # Masked key must match
    matching = [k for k in keys if k["id"] == key_id]
    assert len(matching) == 1
    assert matching[0]["masked_key"] == mask_api_key(api_key)

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


def test_b2b_keys_list_excludes_same_email_other_user_id(auth_client, mock_user):
    # Key created with same email but belonging to another user_id or NULL user_id
    other_key_val = f"cvfy_{uuid.uuid4().hex}"
    null_key_val = f"cvfy_{uuid.uuid4().hex}"

    with Session(engine) as session:
        session.add(ApiKey(
            api_key=other_key_val,
            user_id="other-user-999",
            email=mock_user["email"],
            name="Other User Key",
            credits=3,
        ))
        session.add(ApiKey(
            api_key=null_key_val,
            user_id=None,
            email=mock_user["email"],
            name="Unclaimed Key",
            credits=3,
        ))
        session.commit()

    # Keys list strictly queries by user_id and MUST NOT include keys owned by another/null user_id
    res = auth_client.get("/third_party/api/v1/keys")
    assert res.status_code == 200
    listed_masked = [k["masked_key"] for k in res.json()["api_keys"]]
    assert mask_api_key(other_key_val) not in listed_masked
    assert mask_api_key(null_key_val) not in listed_masked


def test_b2b_key_rotation(auth_client, mock_user):
    # Create key
    gen_res = auth_client.post(
        "/third_party/api/v1/keys/generate",
        json={"name": "Key to Rotate"}
    )
    assert gen_res.status_code == 201
    old_key = gen_res.json()["api_key"]
    key_id = gen_res.json()["id"]

    # Rotate key
    rot_res = auth_client.post(f"/third_party/api/v1/keys/{key_id}/rotate")
    assert rot_res.status_code == 200
    rot_data = rot_res.json()
    new_key = rot_data["api_key"]

    assert new_key != old_key
    assert new_key.startswith("cvfy_")
    assert rot_data["masked_key"] == mask_api_key(new_key)

    # Old key is no longer valid in database
    assert get_b2b_key_data(old_key) is None
    # New key is active with existing credits
    new_key_data = get_b2b_key_data(new_key)
    assert new_key_data is not None
    assert new_key_data.is_active is True
    assert new_key_data.credits == 3


def test_b2b_key_revocation(auth_client, sample_certificate_image):
    # Create key
    gen_res = auth_client.post(
        "/third_party/api/v1/keys/generate",
        json={"name": "Key to Revoke"}
    )
    api_key = gen_res.json()["api_key"]
    key_id = gen_res.json()["id"]

    # Revoke key via DELETE
    rev_res = auth_client.delete(f"/third_party/api/v1/keys/{key_id}")
    assert rev_res.status_code == 200
    assert rev_res.json()["success"] is True

    # Verification using revoked key fails with 401
    ver_res = auth_client.post(
        "/third_party/api/v1/verify",
        headers={"X-API-Key": api_key},
        files={"file": ("cert.jpg", sample_certificate_image, "image/jpeg")},
        data={"cert_type": "WAEC"},
    )
    assert ver_res.status_code == 401


def test_b2b_verify_rejects_invalid_cert_type(auth_client, sample_certificate_image):
    gen_res = auth_client.post(
        "/third_party/api/v1/keys/generate",
        json={"name": "Type Validation Key"}
    )
    api_key = gen_res.json()["api_key"]

    res = auth_client.post(
        "/third_party/api/v1/verify",
        headers={"X-API-Key": api_key},
        files={"file": ("cert.jpg", sample_certificate_image, "image/jpeg")},
        data={"cert_type": "CAMBRIDGE"},
    )
    assert res.status_code == 422



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
