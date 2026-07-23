import os
from celery import Celery
from app.core.config import settings

# Ensure tasks are discovered
celery_app = Celery(
    "farmmate_tasks",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.application.documents.tasks"]
)

# Configure Celery options (e.g., timezone)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    # Late acks and worker lost configurations
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
