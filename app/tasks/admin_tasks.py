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
