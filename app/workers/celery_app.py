import os
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "leadgen_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.discovery_tasks",
        "app.workers.enrichment_tasks",
        "app.workers.ai_tasks",
        "app.workers.sheets_tasks",
        "app.workers.maintenance_tasks",
    ],
)
celery_app.set_default()

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max task limit
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
)

from celery.schedules import crontab

# Celery Beat schedule for periodic daily scraping and maintenance tasks
celery_app.conf.beat_schedule = {
    "cleanup-old-jobs-daily": {
        "task": "app.workers.maintenance_tasks.cleanup_old_jobs",
        "schedule": 86400.0,  # Every 24 hours
    },
    "daily-lead-scraping-and-sync": {
        "task": "app.workers.discovery_tasks.daily_lead_scraping_and_sync",
        "schedule": crontab(hour=2, minute=0),  # Runs daily at 02:00 AM UTC (VPS midnight/early morning)
    },
}

