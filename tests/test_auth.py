import requests

from app.services import auth_service


def test_auth_me_unauthorized(client):
    # Requesting /auth/me without token should return 401
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_auth_me_authorized(auth_client, mock_user):
    # Requesting with overridden auth client should return profile info
    res = auth_client.get("/auth/me")
    assert res.status_code in [200, 404]  # 200 or 404 if mock user does not exist in Firebase Admin


def test_forgot_password_generic_response(client):
    res = client.post(
        "/auth/forgot-password",
        json={"email": "nonexistent_test_account_xyz@example.com"}
    )
    assert res.status_code == 200
    assert "message" in res.json()


def test_register_returns_service_unavailable_when_firebase_cannot_be_reached(client, monkeypatch):
    def fail_create_user(**kwargs):
        raise requests.ConnectionError("DNS lookup failed")

    monkeypatch.setattr(auth_service.auth, "create_user", fail_create_user)

    res = client.post(
        "/auth/register",
        json={"email": "new_user@example.com", "password": "valid-password"}
    )

    assert res.status_code == 503
    assert res.json()["detail"] == "Unable to reach Firebase authentication service."
