"""
Celery tasks for certificate verification operations.
Offloads heavy AI + forensic processing from the request handler.
"""

import json
import logging
from datetime import datetime
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)
VERIFICATION_MAX_RETRIES = 2


def _task_failure_state(retries: int) -> tuple[str, datetime | None]:
    """Return the externally visible state for the current retry attempt."""
    if retries < VERIFICATION_MAX_RETRIES:
        return "retrying", None
    return "failure", datetime.utcnow()


@celery_app.task(bind=True, name="app.tasks.verification_tasks.run_verification")
def run_verification(
    self,
    file_bytes_hex: str,
    filename: str,
    cert_type: str,
    transaction_ref: str,
    user_email: str,
):
    """
    Run the full forensic verification pipeline asynchronously.

    Args:
        file_bytes_hex: Hex-encoded file bytes (JSON-safe transport)
        filename: Original filename
        cert_type: "WAEC" or "NECO"
        transaction_ref: Linked transaction reference
        user_email: User's email for notification
    """
    from app.services.validator_service import validate_document
    from app.core.database import engine
    from app.models.transaction import Transaction
    from app.models.task_result import TaskResult
    from sqlmodel import Session, select

    task_id = self.request.id

    try:
        file_bytes = bytes.fromhex(file_bytes_hex)

        # Update task status to "started"
        with Session(engine) as session:
            task_result = session.exec(
                select(TaskResult).where(TaskResult.task_id == task_id)
            ).first()
            if task_result:
                task_result.status = "started"
                task_result.updated_at = datetime.utcnow()
                session.add(task_result)
                session.commit()

        # Run forensic validation pipeline
        result = validate_document(file_bytes, filename, cert_type)

        document_score = result.get(
            "document_score",
            result.get("final_score", result.get("gemini_score", 0)),
        )
        final_trust_score = document_score  # May be updated with knowledge_score later
        if final_trust_score >= 75:
            final_verdict = "AUTHENTIC"
        elif final_trust_score >= 40:
            final_verdict = "SUSPICIOUS"
        else:
            final_verdict = "HIGH_RISK"

        # Update the transaction record in DB
        with Session(engine) as session:
            txn = session.exec(
                select(Transaction).where(
                    Transaction.transaction_ref == transaction_ref
                )
            ).first()

            if txn:
                txn.cert_type = cert_type
                txn.verification_result = json.dumps(result)
                txn.document_score = document_score
                txn.final_trust_score = final_trust_score
                txn.final_verdict = final_verdict
                session.add(txn)
                session.commit()

        # Update TaskResult with success status
        with Session(engine) as session:
            task_result = session.exec(
                select(TaskResult).where(TaskResult.task_id == task_id)
            ).first()
            if task_result:
                task_result.status = "success"
                task_result.result = json.dumps({
                    "transaction_ref": transaction_ref,
                    "final_verdict": final_verdict,
                    "final_trust_score": final_trust_score,
                    "document_score": document_score,
                })
                task_result.updated_at = datetime.utcnow()
                task_result.completed_at = datetime.utcnow()
                session.add(task_result)
                session.commit()

        # Queue the verification report email
        from app.tasks.email_tasks import send_verification_report_task
        send_verification_report_task.delay(
            email=user_email,
            transaction_ref=transaction_ref,
            cert_type=cert_type,
            final_verdict=final_verdict,
            final_trust_score=final_trust_score,
            document_score=document_score,
        )

        logger.info(
            f"Verification complete for {transaction_ref}: "
            f"{final_verdict} (score: {final_trust_score})"
        )

        return {
            "success": True,
            "transaction_ref": transaction_ref,
            "final_verdict": final_verdict,
            "final_trust_score": final_trust_score,
            "document_score": document_score,
        }

    except Exception as e:
        logger.error(f"Verification task failed for {transaction_ref}: {e}")

        retries = getattr(self.request, "retries", 0)
        task_status, completed_at = _task_failure_state(retries)
        will_retry = task_status == "retrying"

        # Keep retrying tasks non-terminal so clients do not see a false failure.
        with Session(engine) as session:
            task_result = session.exec(
                select(TaskResult).where(TaskResult.task_id == task_id)
            ).first()
            if task_result:
                task_result.status = task_status
                task_result.error = str(e)
                task_result.updated_at = datetime.utcnow()
                task_result.completed_at = completed_at
                session.add(task_result)
                session.commit()

        if will_retry:
            raise self.retry(
                exc=e,
                countdown=120,
                max_retries=VERIFICATION_MAX_RETRIES,
            )
        raise



@celery_app.task(bind=True, name="app.tasks.verification_tasks.run_b2b_verification")
def run_b2b_verification(
    self,
    file_bytes_hex: str,
    filename: str,
    cert_type: str,
    api_key: str,
):
    """
    Run B2B verification asynchronously.
    Credit deduction should happen BEFORE queuing this task.
    """
    from app.services.validator_service import validate_document

    try:
        file_bytes = bytes.fromhex(file_bytes_hex)
        result = validate_document(file_bytes, filename, cert_type)

        document_score = result.get(
            "document_score",
            result.get("final_score", result.get("gemini_score", 0)),
        )
        if document_score >= 75:
            final_verdict = "AUTHENTIC"
        elif document_score >= 40:
            final_verdict = "SUSPICIOUS"
        else:
            final_verdict = "HIGH_RISK"

        logger.info(f"B2B verification complete for key {api_key[:8]}...: {final_verdict}")

        return {
            "success": True,
            "final_verdict": final_verdict,
            "document_score": document_score,
            "result": result,
        }

    except Exception as e:
        logger.error(f"B2B verification task failed: {e}")
        raise self.retry(exc=e, countdown=120, max_retries=2)
