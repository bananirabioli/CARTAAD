"""Celery tasks. Each opens its own DB session."""

from app.worker import celery_app


@celery_app.task(name="app.tasks.ingest_due_sources")
def ingest_due_sources() -> int:
    from app.db import SessionLocal
    from app.services.ingest import due_sources, run_source

    with SessionLocal() as db:
        sources = due_sources(db)
        for source in sources:
            run_source(db, source)
            db.commit()
        return len(sources)


@celery_app.task(name="app.tasks.recompute_baselines")
def recompute_baselines() -> int:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models.monitoring import MonitoredSource
    from app.services.alert import refresh_source_baseline

    with SessionLocal() as db:
        sources = list(db.scalars(select(MonitoredSource)))
        for source in sources:
            refresh_source_baseline(db, source)
        db.commit()
        return len(sources)


@celery_app.task(name="app.tasks.publish_due_posts")
def publish_due_posts() -> int:
    return 0


@celery_app.task(name="app.tasks.process_document")
def process_document_task(document_id: int) -> int:
    from app.db import SessionLocal
    from app.models.kb import SourceDocument
    from app.services.documents import process_document

    with SessionLocal() as db:
        doc = db.get(SourceDocument, document_id)
        if doc is None:
            return 0
        n = process_document(db, doc)
        db.commit()
        return n
