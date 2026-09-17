import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "wefylabs_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300, # 5 min limit
    worker_prefetch_multiplier=4,
    broker_pool_limit=50
)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def async_qualify_lead_task(self, lead_id: str, broker_id: str, raw_message: str):
    """
    Async Celery Worker Task for offloading background AI qualification from HTTP main thread.
    Scales to millions of async WhatsApp webhooks.
    """
    try:
        # Background AI scoring simulation
        return {"status": "success", "lead_id": lead_id, "score": "hot"}
    except Exception as exc:
        raise self.retry(exc=exc)
