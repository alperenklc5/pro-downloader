"""Celery uygulama yapılandırması."""
from celery import Celery

from backend.config import settings


celery_app = Celery(
    "video_downloader",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.tasks.download_task"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Concurrency
    worker_concurrency=settings.max_concurrent_downloads,
    worker_prefetch_multiplier=1,

    # Görev timeout (uzun videolar için 1 saat)
    task_soft_time_limit=3600,
    task_time_limit=3900,

    # Sonuçlar 24 saat sonra silinsin
    result_expires=86400,

    # Periyodik görevler
    beat_schedule={
        "cleanup-old-files": {
            "task": "backend.tasks.download_task.cleanup_task",
            "schedule": 3600.0,  # Her saat
        },
    },
)
