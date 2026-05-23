"""
Celery application factory.

The broker and result backend are both Redis.
Tasks are routed to the 'validation' queue.
"""
from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "cdtool",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "app.workers.tasks.run_validation_job": {"queue": "validation"},
    },
    worker_prefetch_multiplier=1,   # one job at a time per worker slot
)
