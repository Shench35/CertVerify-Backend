"""
Celery tasks for email operations.
"""

import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.email_tasks.send_payment_confirmation_task")
def send_payment_confirmation_task(self, email: str, transaction_ref: str, amount: float):
    """Send payment confirmation email asynchronously."""
    from app.services.email_service import send_payment_confirmation
    try:
        result = send_payment_confirmation(email, transaction_ref, amount)
        logger.info(f"Payment confirmation email {'sent' if result else 'failed'} for {transaction_ref}")
        return {"success": result, "email": email, "transaction_ref": transaction_ref}
    except Exception as e:
        logger.error(f"Payment confirmation email task failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="app.tasks.email_tasks.send_verification_report_task")
def send_verification_report_task(
    self,
    email: str,
    transaction_ref: str,
    cert_type: str,
    final_verdict: str,
    final_trust_score: float,
    document_score: float,
):
    """Send verification result email asynchronously."""
    from app.services.email_service import send_verification_report
    try:
        result = send_verification_report(
            email, transaction_ref, cert_type, final_verdict,
            final_trust_score, document_score,
        )
        logger.info(f"Verification report email {'sent' if result else 'failed'} for {transaction_ref}")
        return {"success": result, "email": email, "transaction_ref": transaction_ref}
    except Exception as e:
        logger.error(f"Verification report email task failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="app.tasks.email_tasks.send_b2b_credit_alert_task")
def send_b2b_credit_alert_task(self, email: str, api_key: str, credits_remaining: int):
    """Send low credit warning email asynchronously."""
    from app.services.email_service import send_b2b_credit_alert
    try:
        result = send_b2b_credit_alert(email, api_key, credits_remaining)
        logger.info(f"B2B credit alert email {'sent' if result else 'failed'} for {email}")
        return {"success": result, "email": email, "credits_remaining": credits_remaining}
    except Exception as e:
        logger.error(f"B2B credit alert email task failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="app.tasks.email_tasks.send_api_key_generated_task")
def send_api_key_generated_task(self, email: str, api_key: str, name: str):
    """Send API key generation confirmation email asynchronously."""
    from app.services.email_service import send_api_key_generated
    try:
        result = send_api_key_generated(email, api_key, name)
        logger.info(f"API key generated email {'sent' if result else 'failed'} for {email}")
        return {"success": result, "email": email}
    except Exception as e:
        logger.error(f"API key generated email task failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="app.tasks.email_tasks.send_bulk_email_task")
def send_bulk_email_task(self, subject: str, body: str, recipient_emails: list[str]):
    """Send bulk email asynchronously (admin feature)."""
    from app.services.email_service import send_bulk_emails
    try:
        result = send_bulk_emails(
            recipient_emails=recipient_emails,
            subject=subject,
            html_body=body,
        )
        logger.info(f"Bulk email task complete: {result['sent']} sent, {result['failed']} failed")
        return result
    except Exception as e:
        logger.error(f"Bulk email task failed: {e}")
        raise self.retry(exc=e, countdown=120, max_retries=2)
