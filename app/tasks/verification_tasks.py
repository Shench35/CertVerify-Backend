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
    task_payload_id: str,
    filename: str,
    cert_type: str,
    transaction_ref: str,
    user_email: str,
):
    """
    Run the full forensic verification pipeline asynchronously.

    Args:
        task_payload_id: ID of the database-backed upload payload
        filename: Original filename
        cert_type: "WAEC" or "NECO"
        transaction_ref: Linked transaction reference
        user_email: User's email for notification
    """
    from app.services.validator_service import validate_document
    from app.core.database import engine
    from app.models.transaction import Transaction
    from app.models.task_result import TaskResult
    from app.models.user_credit import UserCreditAccount
    from sqlmodel import Session, select

    task_id = self.request.id

    try:
        # Load worker input from Postgres; the broker carries only a task ID.
        with Session(engine) as session:
            task_result = session.exec(
                select(TaskResult).where(TaskResult.task_id == task_payload_id)
            ).first()
            if task_result and task_result.status == "success" and task_result.result:
                return json.loads(task_result.result)
            if task_result and task_result.status == "failure":
                return {"success": False, "error": task_result.error}
            if not task_result or task_result.payload is None:
                raise ValueError("Verification payload is unavailable")
            file_bytes = task_result.payload
            task_result.status = "started"
            task_result.updated_at = datetime.utcnow()
            session.add(task_result)
            session.commit()

        # Run forensic validation pipeline
        result = validate_document(file_bytes, filename, cert_type)
        if not result.get("success"):
            raise RuntimeError(result.get("error", "Document analysis could not be completed"))

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
                    "decision_limit": result.get("decision_limit"),
                })
                task_result.updated_at = datetime.utcnow()
                task_result.completed_at = datetime.utcnow()
                task_result.payload = None
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
        logger.exception(f"Verification task failed for {transaction_ref}: {e}")

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
                # Store sanitized, user-safe error message; full details remain in server logs
                task_result.error = "Verification processing encountered an error. Please retry or contact support."
                task_result.updated_at = datetime.utcnow()
                task_result.completed_at = completed_at
                if not will_retry:
                    task_result.payload = None
                    if task_result.task_type == "verification" and not task_result.credit_refunded:
                        account = session.exec(
                            select(UserCreditAccount)
                            .where(UserCreditAccount.user_id == task_result.user_id)
                            .with_for_update()
                        ).first()
                        if account and account.credits < account.daily_credit_limit:
                            account.credits += 1
                            account.updated_at = datetime.utcnow()
                            session.add(account)
                        task_result.credit_refunded = True
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
    task_payload_id: str,
    filename: str,
    cert_type: str,
):
    """
    Run B2B verification asynchronously.
    Credit deduction and task-payload persistence happen before queueing.
    """
    from app.services.validator_service import validate_document
    from app.core.database import engine
    from app.models.task_result import TaskResult
    from app.models.api_key import ApiKey
    from app.models.user_credit import UserCreditAccount
    from sqlmodel import Session, select

    task_id = self.request.id

    try:
        with Session(engine) as session:
            task = session.exec(
                select(TaskResult).where(TaskResult.task_id == task_payload_id)
            ).first()
            if task and task.status == "success" and task.result:
                return json.loads(task.result)
            if task and task.status == "failure":
                return {"success": False, "error": task.error}
            if not task or task.payload is None:
                raise ValueError("Verification payload is unavailable")
            file_bytes = task.payload
            task.status = "started"
            task.updated_at = datetime.utcnow()
            session.add(task)
            session.commit()

        result = validate_document(file_bytes, filename, cert_type)
        if not result.get("success"):
            raise RuntimeError(result.get("error", "Document analysis could not be completed"))

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

        task_result = {
            "success": True,
            "cert_type": cert_type,
            "final_verdict": final_verdict,
            "document_score": document_score,
            "result": result,
        }
        with Session(engine) as session:
            task = session.exec(
                select(TaskResult).where(TaskResult.task_id == task_id)
            ).first()
            if task:
                task.status = "success"
                task.result = json.dumps(task_result)
                task.payload = None
                task.updated_at = datetime.utcnow()
                task.completed_at = datetime.utcnow()
                session.add(task)
                session.commit()
        logger.info(f"B2B verification complete for task {task_id}: {final_verdict}")
        return task_result

    except Exception as e:
        logger.exception("B2B verification task failed")
        retries = getattr(self.request, "retries", 0)
        will_retry = retries < VERIFICATION_MAX_RETRIES
        with Session(engine) as session:
            task = session.exec(
                select(TaskResult)
                .where(TaskResult.task_id == self.request.id)
                .with_for_update()
            ).first()
            if task:
                task.status = "retrying" if will_retry else "failure"
                task.error = "Verification processing encountered an error. Please retry or contact support."
                task.updated_at = datetime.utcnow()
                if not will_retry:
                    task.payload = None
                    task.completed_at = datetime.utcnow()
                    if task.task_type == "b2b_verification" and not task.credit_refunded:
                        key = session.exec(
                            select(ApiKey)
                            .where(ApiKey.api_key == task.api_key_hash)
                            .with_for_update()
                        ).first()
                        if key and key.credits < key.daily_credit_limit:
                            key.credits += 1
                            key.updated_at = datetime.utcnow()
                            session.add(key)
                        task.credit_refunded = True
                    elif task.task_type == "verification" and not task.credit_refunded:
                        account = session.exec(
                            select(UserCreditAccount)
                            .where(UserCreditAccount.user_id == task.user_id)
                            .with_for_update()
                        ).first()
                        if account and account.credits < account.daily_credit_limit:
                            account.credits += 1
                            account.updated_at = datetime.utcnow()
                            session.add(account)
                        task.credit_refunded = True
                session.add(task)
                session.commit()
        if will_retry:
            raise self.retry(exc=e, countdown=120, max_retries=VERIFICATION_MAX_RETRIES)
        raise
