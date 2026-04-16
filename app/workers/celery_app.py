from celery import Celery
from app.core.config import settings

# Create the Celery app WITHOUT include= to avoid circular import:
# tasks.py imports celery_app, so celery_app must be fully created first.
celery_app = Celery(
    "ragdesk_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Register task modules AFTER the app object is fully created
    include=["app.workers.tasks"],
)
