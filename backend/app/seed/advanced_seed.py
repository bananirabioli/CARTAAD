"""Three cases already advanced through the real pipeline, in different states (section 13):

* Flujo A, `calificado`: published, measured (simulated) and rated "funcionó".
* Flujo A, `en_revision`: three style variants and copilot versions (v1 → v3) waiting for the approver.
* Flujo B, `programado`: approved pieces scheduled for tomorrow plus a package for allies.

Every step goes through the same services as the API, so hard rules, validators and audit apply.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.cases import Case
from app.models.core import Client, User
from app.models.generation import Piece
from app.models.monitoring import OwnedAccount
from app.services.cases import decide
from app.services.generation import generate_proposal, start_generation
from app.services.metrics import rate_case, simulate_metrics
from app.services.pieces import run_copilot, verify_figure
from app.services.publishing import approval_blockers, approve, create_ally_package, publish, schedule


def _case(db: Session, client: Client, topic: str, message_type: str, stance: str) -> Case | None:
    return db.scalar(
        select(Case).where(Case.client_id == client.id, Case.status == "interpretado", Case.topic_slug == topic, Case.message_type == message_type, Case.stance == stance)
        .order_by((Case.alert_level == "alto").desc(), Case.id.desc())
    )


def _account(db: Session, client: Client, fmt: str) -> OwnedAccount:
    return db.scalar(select(OwnedAccount).where(OwnedAccount.client_id == client.id, OwnedAccount.format_slug == fmt, OwnedAccount.account_type == "propia", OwnedAccount.registered.is_(True)))


def _generate(db: Session, case: Case, user: User) -> list[Piece]:
    proposal = start_generation(db, case, user)
    generate_proposal(db, proposal, user)
    db.flush()
    return list(proposal.pieces)


def _approve(db: Session, piece: Piece, approver: User) -> bool:
    for fig in piece.figures:
        if fig.piece_version == piece.current_version and fig.status == "pendiente":
            verify_figure(db, piece, fig, approver, "verificada", note="Cotejada con el documento fuente")
    db.flush()
    if approval_blockers(db, piece):
        return False
    approve(db, piece, approver, note="Revisado para la demo")
    return True


def _first_approvable(db: Session, pieces: list[Piece], approver: User) -> Piece | None:
    for piece in pieces:
        if piece.validation_status != "block" and _approve(db, piece, approver):
            return piece
    return None


def _creatives(pieces: list[Piece], preferred: list[str]) -> list[Piece]:
    rank = {slug: i for i, slug in enumerate(preferred)}
    return sorted((p for p in pieces if p.kind == "creative" and p.creative_slug in rank), key=lambda p: rank[p.creative_slug])


def _render(db: Session, pieces: list[Piece]) -> None:
    from app.render.renderer import render_piece

    for piece in pieces:
        if piece.kind == "creative" and piece.render_status == "pendiente":
            render_piece(db, piece)


def seed_advanced_cases(db: Session, clients: dict[str, Client]) -> None:
    client = clients["municipio-ejemplo"]
    analyst = db.scalar(select(User).where(User.email == "analista@demo.mx"))
    approver = db.scalar(select(User).where(User.email == "aprobador@demo.mx"))
    if db.scalar(select(Case.id).where(Case.client_id == client.id, Case.status.in_(("calificado", "programado", "en_revision"))).limit(1)):
        return
    clasico = _account(db, client, "formato_clasico")
    touched: list[Piece] = []

    # 1 · Flujo A, published, measured and rated.
    case = _case(db, client, "seguridad", "dato_falso", "en_contra")
    if case:
        decide(db, case, analyst, decision="responder", strategy="desmentir", style_slug="institucional", account_id=clasico.id)
        pieces = _generate(db, case, analyst)
        copy = _first_approvable(db, [p for p in pieces if p.kind == "copy"], approver)
        creative = _first_approvable(db, _creatives(pieces, ["dato_duro", "carrusel_explicativo", "infografia"]), approver)
        # A/B: the creative (with the copy as its text) and the copy alone are published as two variants.
        for piece, text in [(creative, copy), (copy, None)]:
            if piece is None:
                continue
            when = utcnow() + timedelta(minutes=5)
            sp = schedule(db, approver, client.id, piece=piece, account_id=clasico.id, scheduled_at=when, copy_piece=text)
            publish(db, sp, approver, now=when)
        db.flush()
        if case.status == "publicado":
            simulate_metrics(db, case, analyst)
            rate_case(db, case, analyst, "funciono", "El dato oficial bajó el tono de los comentarios; la variante con creativo tuvo más alcance.")
        touched += pieces

    # 2 · Flujo A, three style variants and copilot versions, waiting for approval.
    case = _case(db, client, "agua", "dato_falso", "en_contra")
    if case:
        decide(db, case, analyst, decision="responder", strategy="desmentir", style_slug="cercano", account_id=clasico.id)
        pieces = _generate(db, case, analyst)
        copy = next((p for p in pieces if p.kind == "copy" and p.style_slug == "cercano"), None)
        if copy:
            run_copilot(db, copy, analyst, action="mas_corto")
            run_copilot(db, copy, analyst, action="mas_empatico")
        touched += pieces

    # 3 · Flujo B, approved and scheduled for tomorrow, with a package for allies.
    case = _case(db, client, "obra_publica", "opinion", "a_favor")
    if case:
        decide(db, case, analyst, decision="responder", account_id=clasico.id)
        pieces = _generate(db, case, analyst)
        copy = _first_approvable(db, [p for p in pieces if p.kind == "copy"], approver)
        creative = _first_approvable(db, _creatives(pieces, ["agradecimiento", "pieza_aliados", "carrusel_resultados", "repost_contexto"]), approver)
        tomorrow = (utcnow() + timedelta(days=1)).replace(hour=16, minute=0, second=0, microsecond=0)
        if creative:
            schedule(db, approver, client.id, piece=creative, account_id=clasico.id, scheduled_at=tomorrow, copy_piece=copy)
            ids = [p.id for p in (creative, copy) if p]
            create_ally_package(db, approver, case, title="Parque rehabilitado: material para compartir", message="Gracias por difundir información verificada.", piece_ids=ids, expires_in_days=14)
        touched += pieces

    db.flush()
    _render(db, touched)
