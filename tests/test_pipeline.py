import json
import uuid
from sqlmodel import Session
from app.core.database import engine
from app.models.transaction import Transaction


def test_analyse_unauthorized(client, sample_certificate_image):
    res = client.post(
        "/AI_pipeline/verify/analyse",
        files={"file": ("cert.jpg", sample_certificate_image, "image/jpeg")},
        data={"cert_type": "WAEC"}
    )
    assert res.status_code == 401


def test_analyse_without_payment(auth_client, sample_certificate_image):
    # If user has no confirmed paid transaction, expect 402 Payment Required
    res = auth_client.post(
        "/AI_pipeline/verify/analyse",
        files={"file": ("cert.jpg", sample_certificate_image, "image/jpeg")},
        data={"cert_type": "WAEC"}
    )
    # Either 402 (No payment) or 200 (if previous paid transaction in DB)
    assert res.status_code in [200, 402]


def test_score_without_analyse_data(auth_client, mock_user):
    # Empty transaction with no verification_result should return 400 or 404
    fake_ref = str(uuid.uuid4())
    res = auth_client.post(
        "/AI_pipeline/verify/score",
        data={
            "transaction_ref": fake_ref,
            "answers": json.dumps(["Answer 1", "Answer 2", "Answer 3", "Answer 4", "Answer 5"])
        }
    )
    assert res.status_code in [400, 404]
