import json
import uuid
from sqlmodel import Session
from app.core.database import engine
from app.models.transaction import Transaction
from app.services.credit_service import get_user_credit_status


def test_validator_exposes_final_score_as_document_score(monkeypatch):
    from app.services import validator_service

    monkeypatch.setattr(
        validator_service,
        "analyse_certificate",
        lambda *_args: {
            "success": True,
            "authenticity_score": 92,
            "extracted_info": {
                "registration_number": "2410017335DI",
                "exam_year": "2024",
                "date_of_birth": "10/10/2005",
                "subject_count": 9,
                "subjects": [
                    {"subject": "English Language", "grade": "C5", "remark": "CREDIT"}
                ],
            },
            "field_checks": {},
            "flagged_issues": [],
            "tampering_signs": [],
            "confidence_note": "",
        },
    )

    result = validator_service.validate_document(b"document", "result.pdf", "NECO")

    assert result["document_score"] == result["final_score"]
    assert result["document_score"] == 92


def test_verification_retry_state_is_not_terminal_until_exhausted():
    from app.tasks.verification_tasks import _task_failure_state

    assert _task_failure_state(0) == ("retrying", None)
    assert _task_failure_state(1) == ("retrying", None)
    status, completed_at = _task_failure_state(2)
    assert status == "failure"
    assert completed_at is not None


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
    # New users receive three daily verification credits without a payment.
    assert res.status_code == 202
    assert res.json()["credits_remaining"] >= 0


def test_analyse_rejects_mismatched_file_content(auth_client, sample_certificate_image):
    response = auth_client.post(
        "/AI_pipeline/verify/analyse",
        files={"file": ("cert.jpg", b"not an image", "image/jpeg")},
        data={"cert_type": "WAEC"},
    )

    assert response.status_code == 400


def test_analyse_rejects_invalid_cert_type(auth_client, sample_certificate_image):
    response = auth_client.post(
        "/AI_pipeline/verify/analyse",
        files={"file": ("cert.jpg", sample_certificate_image, "image/jpeg")},
        data={"cert_type": "INVALID_TYPE"},
    )
    assert response.status_code == 422



def test_analyse_rejects_oversized_upload(auth_client, monkeypatch):
    from app.services import upload_validation

    monkeypatch.setattr(upload_validation, "MAX_UPLOAD_BYTES", 4)
    response = auth_client.post(
        "/AI_pipeline/verify/analyse",
        files={"file": ("cert.jpg", b"\xff\xd8\xff\x00\x00", "image/jpeg")},
        data={"cert_type": "WAEC"},
    )

    assert response.status_code == 400


def test_analyse_restores_credit_when_dispatch_fails(
    auth_client, sample_certificate_image, monkeypatch, mock_user
):
    from app.api.v1 import verification

    before = get_user_credit_status(mock_user["uid"], mock_user["email"]).credits
    monkeypatch.setattr(
        verification.run_verification,
        "apply_async",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("broker unavailable")),
    )

    res = auth_client.post(
        "/AI_pipeline/verify/analyse",
        files={"file": ("cert.jpg", sample_certificate_image, "image/jpeg")},
        data={"cert_type": "WAEC"},
    )

    assert res.status_code == 503
    assert get_user_credit_status(mock_user["uid"], mock_user["email"]).credits == before


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


def test_verification_history_and_report_enforce_strict_user_id(auth_client, mock_user):
    ref_owner = str(uuid.uuid4())
    ref_other_user = str(uuid.uuid4())
    ref_unassigned = str(uuid.uuid4())

    with Session(engine) as session:
        session.add(Transaction(
            transaction_ref=ref_owner,
            user_id=mock_user["uid"],
            email=mock_user["email"],
            amount_naira=0,
            amount_kobo=0,
            status="success",
            cert_type="WAEC",
            document_score=88.0,
            final_trust_score=88.0,
            final_verdict="AUTHENTIC",
            verification_result=json.dumps({"extracted_info": {"candidate_name": "Owner"}}),
        ))
        session.add(Transaction(
            transaction_ref=ref_other_user,
            user_id="another-user-uid",
            email=mock_user["email"],
            amount_naira=0,
            amount_kobo=0,
            status="success",
            cert_type="WAEC",
            document_score=50.0,
            final_trust_score=50.0,
            final_verdict="SUSPICIOUS",
            verification_result=json.dumps({"extracted_info": {"candidate_name": "Other"}}),
        ))
        session.add(Transaction(
            transaction_ref=ref_unassigned,
            user_id=None,
            email=mock_user["email"],
            amount_naira=0,
            amount_kobo=0,
            status="success",
            cert_type="NECO",
            document_score=90.0,
            final_trust_score=90.0,
            final_verdict="AUTHENTIC",
            verification_result=json.dumps({"extracted_info": {"candidate_name": "Unassigned"}}),
        ))
        session.commit()

    # 1. History endpoint only returns owner's transaction
    hist_res = auth_client.get("/AI_pipeline/verify/history")
    assert hist_res.status_code == 200
    refs = [v["transaction_ref"] for v in hist_res.json()["verifications"]]
    assert ref_owner in refs
    assert ref_other_user not in refs
    assert ref_unassigned not in refs

    # 2. Report endpoint allows access only for owner
    rep_owner = auth_client.get(f"/AI_pipeline/verify/report/{ref_owner}")
    assert rep_owner.status_code == 200
    assert rep_owner.json()["transaction_ref"] == ref_owner

    rep_other = auth_client.get(f"/AI_pipeline/verify/report/{ref_other_user}")
    assert rep_other.status_code == 404

    rep_unassigned = auth_client.get(f"/AI_pipeline/verify/report/{ref_unassigned}")
    assert rep_unassigned.status_code == 404

