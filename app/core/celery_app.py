"""
Celery application factory for CertVerify background tasks.

Usage:
    # Start the worker:
    celery -A app.core.celery_app worker --loglevel=info

    # Start the beat scheduler (for periodic tasks):
    celery -A app.core.celery_app beat --loglevel=info
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "certverify",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task behavior
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Result expiry (24 hours)
    result_expires=86400,

    # Task routing
    task_routes={
        "app.tasks.verification_tasks.*": {"queue": "verification"},
        "app.tasks.email_tasks.*": {"queue": "email"},
        "app.tasks.admin_tasks.*": {"queue": "admin"},
    },

    # Task autodiscovery
    include=[
        "app.tasks.verification_tasks",
        "app.tasks.email_tasks",
        "app.tasks.admin_tasks",
    ],
)

# Default queue for unrouted tasks
celery_app.conf.task_default_queue = "default"
