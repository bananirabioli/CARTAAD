"""Celery app (worker + beat). Tasks live in app.tasks; CELERY_EAGER=true runs them inline (tests, local)."""

from celery import Celery

from app.config import get_settings

_s = get_settings()

celery_app = Celery("cartaad", broker=_s.redis_url, backend=_s.redis_url, include=["app.tasks"])
celery_app.conf.update(
    task_always_eager=_s.celery_eager,
    task_eager_propagates=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Mexico_City",
    enable_utc=True,
    beat_schedule={
        "publish-due-posts": {"task": "app.tasks.publish_due_posts", "schedule": 60.0},
        # The mock listening adapter invents posts: automatic ingestion only runs in demo mode.
        **(
            {
                "ingest-due-sources": {"task": "app.tasks.ingest_due_sources", "schedule": 300.0},
                "recompute-baselines": {"task": "app.tasks.recompute_baselines", "schedule": 3600.0},
            }
            if _s.demo_mode
            else {}
        ),
    },
)

app = celery_app
