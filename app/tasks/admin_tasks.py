"""
Celery tasks for admin operations.
"""

import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.admin_tasks.generate_platform_report")
def generate_platform_report(self):
    """
    Generate a comprehensive platform activity report.
    Can be scheduled as a periodic task via Celery Beat.
    """
    from app.services import admin_service

    try:
        stats = admin_service.get_dashboard_stats()
        logger.info(f"Platform report generated: {stats}")
        return {
            "success": True,
            "report": stats,
        }
    except Exception as e:
        logger.error(f"Platform report generation failed: {e}")
        raise self.retry(exc=e, countdown=300, max_retries=2)


@celery_app.task(bind=True, name="app.tasks.admin_tasks.cleanup_expired_transactions")
def cleanup_expired_transactions(self, hours_threshold: int = 24):
    """
    Mark stale pending transactions as expired.
    Transactions pending for longer than `hours_threshold` are updated.
    """
    from datetime import datetime, timedelta
    from sqlmodel import Session, select
    from app.core.database import engine
    from app.models.transaction import Transaction

    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours_threshold)

        with Session(engine) as session:
            stale_txns = session.exec(
                select(Transaction).where(
                    Transaction.status == "pending",
                    Transaction.created_at < cutoff,
                )
            ).all()

            count = 0
            for txn in stale_txns:
                txn.status = "expired"
                session.add(txn)
                count += 1

            session.commit()

        logger.info(f"Cleaned up {count} expired transactions (older than {hours_threshold}h)")
        return {"success": True, "expired_count": count}

    except Exception as e:
        logger.error(f"Transaction cleanup failed: {e}")
        raise self.retry(exc=e, countdown=300, max_retries=2)


@celery_app.task(bind=True, name="app.tasks.admin_tasks.cleanup_verification_tasks")
def cleanup_verification_tasks(self, result_retention_days: int = 30, stale_hours: int = 48):
    """Expire abandoned uploads and remove old task-level result copies."""
    from datetime import datetime, timedelta
    from sqlmodel import Session, select
    from app.core.database import engine
    from app.models.task_result import TaskResult
    from app.models.api_key import ApiKey
    from app.models.user_credit import UserCreditAccount

    try:
        now = datetime.utcnow()
        stale_before = now - timedelta(hours=stale_hours)
        retain_after = now - timedelta(days=result_retention_days)
        with Session(engine) as session:
            stale_tasks = session.exec(
                select(TaskResult)
                .where(
                    TaskResult.status.in_(["pending", "started", "retrying"]),
                    TaskResult.updated_at < stale_before,
                )
                .with_for_update()
            ).all()

            for task in stale_tasks:
                task.status = "failure"
                task.error = "Verification task expired before completion. Please submit it again."
                task.completed_at = now
                task.updated_at = now
                task.payload = None
                if not task.credit_refunded:
                    if task.task_type == "b2b_verification":
                        account = session.exec(
                            select(ApiKey)
                            .where(ApiKey.api_key == task.api_key_hash)
                            .with_for_update()
                        ).first()
                        if account and account.credits < account.daily_credit_limit:
                            account.credits += 1
                            account.updated_at = now
                            session.add(account)
                        task.credit_refunded = True
                    elif task.task_type == "verification":
                        account = session.exec(
                            select(UserCreditAccount)
                            .where(UserCreditAccount.user_id == task.user_id)
                            .with_for_update()
                        ).first()
                        if account and account.credits < account.daily_credit_limit:
                            account.credits += 1
                            account.updated_at = now
                            session.add(account)
                        task.credit_refunded = True
                session.add(task)

            expired_results = session.exec(
                select(TaskResult).where(
                    TaskResult.status.in_(["success", "failure"]),
                    TaskResult.completed_at.is_not(None),
                    TaskResult.completed_at < retain_after,
                )
            ).all()
            removed_count = len(expired_results)
            for task in expired_results:
                session.delete(task)
            session.commit()

        return {
            "success": True,
            "stale_tasks_expired": len(stale_tasks),
            "old_task_results_removed": removed_count,
        }
    except Exception as e:
        logger.exception("Verification task cleanup failed")
        raise self.retry(exc=e, countdown=300, max_retries=2)

