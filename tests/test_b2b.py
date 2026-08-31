import uuid
from app.services.b2b_service import (
    create_b2b_key,
    deduct_b2b_credit,
    add_b2b_credits,
    get_b2b_balance,
    get_b2b_key_data
)


def test_b2b_key_lifecycle(auth_client, mock_user):
    # 1. Generate Key via API
    key_name = f"Test Integration Key {uuid.uuid4().hex[:6]}"
    res = auth_client.post(
        "/third_party/api/v1/keys/generate",
        json={"name": key_name, "initial_credits": 5}
    )
    assert res.status_code == 201
    data = res.json()
    api_key = data["api_key"]
    assert api_key.startswith("cvfy_")
    assert data["credits"] == 5

    # 2. List Keys via API
    res_list = auth_client.get("/third_party/api/v1/keys")
    assert res_list.status_code == 200
    keys = res_list.json()["api_keys"]
    assert any(k["api_key"] == api_key for k in keys)

    # 3. Top-Up Credits via API
    res_topup = auth_client.post(
        "/third_party/api/v1/credits/add",
        json={"api_key": api_key, "credits": 10}
    )
    assert res_topup.status_code == 200
    assert res_topup.json()["new_balance"] == 15

    # 4. Deduct credit service call
    deducted = deduct_b2b_credit(api_key)
    assert deducted is True
    assert get_b2b_balance(api_key) == 14
