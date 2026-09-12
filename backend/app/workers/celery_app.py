from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "test_generator",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    worker_prefetch_multiplier=1, # Important: Prevent slow workers from hoarding tasks
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True, # Acknowledge task only after completion
    worker_max_tasks_per_child=100, # Prevent memory leaks
)

celery_app.autodiscover_tasks(['app.workers'])
