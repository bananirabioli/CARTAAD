"""Celery tasks. Each opens its own DB session."""

from app.worker import celery_app


@celery_app.task(name="app.tasks.ingest_due_sources")
def ingest_due_sources() -> int:
    return 0


@celery_app.task(name="app.tasks.recompute_baselines")
def recompute_baselines() -> int:
    return 0


@celery_app.task(name="app.tasks.publish_due_posts")
def publish_due_posts() -> int:
    return 0
