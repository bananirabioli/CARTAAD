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
    """Simulated publication of due scheduled posts; gates (HR-02/04/09) are re-checked at publish time."""
    from app.db import SessionLocal
    from app.services.publishing import publish_due

    with SessionLocal() as db:
        n = publish_due(db)
        db.commit()
        return n


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


@celery_app.task(name="app.tasks.generate_proposal")
def generate_proposal_task(proposal_id: int, user_id: int | None = None) -> str:
    from app.db import SessionLocal
    from app.models.cases import Case
    from app.models.core import User
    from app.models.generation import Proposal
    from app.services.cases import transition
    from app.services.generation import generate_proposal

    with SessionLocal() as db:
        proposal = db.get(Proposal, proposal_id)
        user = db.get(User, user_id) if user_id else None
        try:
            if (proposal.options or {}).get("mode") == "content":
                from app.services.content import generate_content_proposal, video_pieces_to_render

                generate_content_proposal(db, proposal, user)
                db.commit()
                for piece_id in video_pieces_to_render(proposal):
                    render_video_task.delay(piece_id)
            else:
                generate_proposal(db, proposal, user)
                db.commit()
            return "listo"
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            proposal = db.get(Proposal, proposal_id)
            proposal.status, proposal.error = "error", str(exc)[:1000]
            case = db.get(Case, proposal.case_id)
            if case.status == "generando":
                transition(db, case, "listo_para_generar", user, note="error de generación")
            db.commit()
            if celery_app.conf.task_always_eager:
                raise
            return "error"


@celery_app.task(name="app.tasks.render_piece")
def render_piece_task(piece_id: int) -> int:
    from app.db import SessionLocal
    from app.models.generation import Piece
    from app.render.renderer import render_piece

    with SessionLocal() as db:
        piece = db.get(Piece, piece_id)
        if piece is None:
            return 0
        keys = render_piece(db, piece)
        db.commit()
        return len(keys)


@celery_app.task(name="app.tasks.render_video")
def render_video_task(piece_id: int) -> str:
    from app.db import SessionLocal
    from app.models.generation import Piece
    from app.services.content import render_video

    with SessionLocal() as db:
        piece = db.get(Piece, piece_id)
        if piece is None or piece.kind != "video":
            return "no_aplica"
        piece.render_status = "generando"
        db.commit()
        render_video(db, piece)
        db.commit()
        return piece.render_status
