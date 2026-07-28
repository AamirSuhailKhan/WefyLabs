import os
from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "leadscore_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.followup_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task execution
    beat_schedule={
        "check-hourly-followups": {
            "task": "app.tasks.followup_tasks.check_and_schedule_followups",
            "schedule": crontab(minute=0, hour="*"),  # Every hour at minute 0
        },
    }
)
