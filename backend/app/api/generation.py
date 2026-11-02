"""Generación (6.5), piezas, copiloto con versiones, verificación por cifra y revisión legal por pieza."""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import Ctx, get_ctx, owned, require
from app.db import utcnow
from app.errors import AppError
from app.models.cases import Case
from app.models.core import User
from app.models.generation import ConsentRecord, FigureCheck, Piece, Proposal, Review
from app.models.kb import Fact
from app.models.monitoring import OwnedAccount
from app.schemas.generation import (
    ContentIn,
    CopilotIn,
    CopilotOut,
    GenerateContentIn,
    GenerateIn,
    PieceDetail,
    PieceLegalIn,
    PieceOut,
    ProposalOut,
    RevertIn,
    VerifyFigureIn,
    VersionDetail,
    VersionOut,
)
from app.services import audit
from app.services import pieces as piece_svc
from app.services.catalog import active_style, format_style_slugs, get_format, style_allowed_for_format
from app.services.facts import fact_out
from app.services.generation import start_generation
from app.services.publishing import approval_blockers
from app.services import publishing as pub_svc
from app.storage import client_key, get_storage

router = APIRouter(tags=["generation"])


def piece_out(ctx: Ctx, piece: Piece, model: type[PieceOut] = PieceOut) -> PieceOut:
    case = ctx.db.get(Case, piece.case_id)
    account = ctx.db.get(OwnedAccount, piece.account_id) if piece.account_id else None
    blockers = approval_blockers(ctx.db, piece) if piece.status in ("generado", "bloqueado") else []
    extra = {
        "figures_total": len(piece.figures), "figures_verified": sum(1 for f in piece.figures if f.status == "verificada"), "case_code": case.code if case else None,
        "account_handle": account.handle if account else None, "approvable": piece.status == "generado" and not blockers, "approval_blockers": blockers,
    }
    if model is PieceDetail:
        ids = {i for s in piece.content.get("segments") or [] for i in s.get("fact_ids") or []}
        ids |= {i for s in (piece.content.get("slots") or {}).values() for i in s.get("fact_ids") or []}
        ids |= {i for s in piece.content.get("slides") or [] for i in s.get("fact_ids") or []}
        ids |= {f.fact_id for f in piece.figures if f.fact_id}
        facts = list(ctx.db.scalars(select(Fact).where(Fact.client_id == ctx.client_id, Fact.id.in_(ids)))) if ids else []
        consent = ctx.db.scalar(select(ConsentRecord).where(ConsentRecord.piece_id == piece.id).order_by(ConsentRecord.id.desc()))
        reviews = ctx.db.scalars(select(Review).where(Review.piece_id == piece.id).order_by(Review.id.desc()).limit(30))
        users = {u.id: u.name for u in ctx.db.scalars(select(User))}
        fmt = get_format(ctx.db, ctx.client_id, piece.format_slug)
        style = active_style(ctx.db, ctx.client_id, piece.style_slug)
        allowed = [s for s in format_style_slugs(fmt) if (st := active_style(ctx.db, ctx.client_id, s)) and style_allowed_for_format(st, fmt)] if fmt else []
        extra.update(
            figures=list(piece.figures), red_team_notes=[n for n in piece.red_team_notes if n.piece_version == piece.current_version] or list(piece.red_team_notes),
            versions=[VersionOut.model_validate(v).model_copy(update={"author_name": users.get(v.author_id) if v.author_id else None}) for v in reversed(piece.versions)],
            facts=[fact_out(ctx.db, f) for f in facts],
            consent={"id": consent.id, "person_label": consent.person_label, "file_key": consent.file_key, "signed_at": consent.signed_at.isoformat() if consent.signed_at else None} if consent else None,
            reviews=[{"action": r.action, "who": users.get(r.user_id), "note": r.note, "version": r.piece_version, "at": r.created_at.isoformat()} for r in reviews],
            style_intensity=[style.intensity_min, style.intensity_max] if style else [], allowed_styles=allowed,
        )
    return model.model_validate(piece).model_copy(update=extra)


def _proposal_out(ctx: Ctx, p: Proposal) -> ProposalOut:
    pieces = list(ctx.db.scalars(select(Piece).where(Piece.proposal_id == p.id).order_by(Piece.kind.desc(), Piece.id)))
    ids: set[int] = set()
    for x in pieces:
        ids |= {i for s in x.content.get("segments") or [] for i in s.get("fact_ids") or []}
        ids |= {i for s in (x.content.get("slots") or {}).values() for i in s.get("fact_ids") or []}
        ids |= {i for s in x.content.get("slides") or [] for i in s.get("fact_ids") or []}
    facts = list(ctx.db.scalars(select(Fact).where(Fact.client_id == ctx.client_id, Fact.id.in_(ids)))) if ids else []
    return ProposalOut.model_validate(p).model_copy(update={"pieces": [piece_out(ctx, x) for x in pieces], "facts": [fact_out(ctx.db, f) for f in facts]})


@router.post("/cases/{case_id}/generate", response_model=ProposalOut, status_code=202)
def generate(case_id: int, body: GenerateIn, ctx: Ctx = Depends(require("generation.run"))) -> ProposalOut:
    case = owned(ctx.db, Case, case_id, ctx.client_id)
    proposal = start_generation(ctx.db, case, ctx.user, body.variant_styles)
    ctx.db.commit()
    from app.tasks import generate_proposal_task

    generate_proposal_task.delay(proposal.id, ctx.user.id)
    ctx.db.expire_all()
    return _proposal_out(ctx, ctx.db.get(Proposal, proposal.id))


@router.post("/cases/{case_id}/generate-content", response_model=ProposalOut, status_code=202)
def generate_content(case_id: int, body: GenerateContentIn, ctx: Ctx = Depends(require("generation.run"))) -> ProposalOut:
    """MVP: decide «responder» with the main account and generate copies, images and (optionally) a video in one go."""
    from app.services.content import start_content_generation

    case = owned(ctx.db, Case, case_id, ctx.client_id)
    proposal = start_content_generation(
        ctx.db, case, ctx.user, strategy=body.strategy, style_slug=body.style_slug, variant_slugs=body.variant_styles, network=body.network,
        image_count=body.image_count, video=body.video, instructions=body.instructions,
    )
    ctx.db.commit()
    from app.tasks import generate_proposal_task

    generate_proposal_task.delay(proposal.id, ctx.user.id)
    ctx.db.expire_all()
    return _proposal_out(ctx, ctx.db.get(Proposal, proposal.id))


@router.get("/cases/{case_id}/proposals", response_model=list[ProposalOut])
def list_proposals(case_id: int, ctx: Ctx = Depends(get_ctx)) -> list[ProposalOut]:
    owned(ctx.db, Case, case_id, ctx.client_id)
    rows = ctx.db.scalars(select(Proposal).where(Proposal.case_id == case_id).order_by(Proposal.id.desc()))
    return [_proposal_out(ctx, p) for p in rows]


@router.get("/proposals/{proposal_id}", response_model=ProposalOut)
def get_proposal(proposal_id: int, ctx: Ctx = Depends(get_ctx)) -> ProposalOut:
    return _proposal_out(ctx, owned(ctx.db, Proposal, proposal_id, ctx.client_id))


@router.get("/pieces/{piece_id}", response_model=PieceDetail)
def get_piece(piece_id: int, ctx: Ctx = Depends(get_ctx)) -> PieceOut:
    return piece_out(ctx, owned(ctx.db, Piece, piece_id, ctx.client_id), PieceDetail)


@router.get("/pieces/{piece_id}/versions/{version}", response_model=VersionDetail)
def get_version(piece_id: int, version: int, ctx: Ctx = Depends(get_ctx)) -> VersionDetail:
    piece = owned(ctx.db, Piece, piece_id, ctx.client_id)
    v = next((x for x in piece.versions if x.version == version), None)
    if not v:
        raise AppError(404, "not_found")
    return VersionDetail.model_validate(v)


@router.put("/pieces/{piece_id}/content", response_model=PieceDetail)
def edit_content(piece_id: int, body: ContentIn, ctx: Ctx = Depends(require("piece.edit"))) -> PieceOut:
    piece = owned(ctx.db, Piece, piece_id, ctx.client_id)
    piece_svc.edit_piece(ctx.db, piece, ctx.user, body.model_dump(exclude_none=True, exclude={"note"}), body.note)
    ctx.db.commit()
    piece_svc.enqueue_pending_render(piece)
    return piece_out(ctx, piece, PieceDetail)


@router.post("/pieces/{piece_id}/copilot", response_model=CopilotOut)
def copilot(piece_id: int, body: CopilotIn, ctx: Ctx = Depends(require("copilot.use"))) -> CopilotOut:
    piece = owned(ctx.db, Piece, piece_id, ctx.client_id)
    result = piece_svc.run_copilot(ctx.db, piece, ctx.user, action=body.action, instruction=body.instruction, style_slug=body.style_slug)
    if not result["applied"]:
        audit.record(ctx.db, action="piece.copilot_refused", entity_type="piece", entity_id=piece.id, client_id=ctx.client_id, user=ctx.user, note=f"{body.action}: {result['message']}")
    ctx.db.commit()
    piece_svc.enqueue_pending_render(piece)
    return CopilotOut(**result, piece=piece_out(ctx, piece, PieceDetail))


@router.post("/pieces/{piece_id}/revert", response_model=PieceDetail)
def revert(piece_id: int, body: RevertIn, ctx: Ctx = Depends(require("piece.edit"))) -> PieceOut:
    piece = owned(ctx.db, Piece, piece_id, ctx.client_id)
    piece_svc.revert_piece(ctx.db, piece, ctx.user, body.version)
    ctx.db.commit()
    piece_svc.enqueue_pending_render(piece)
    return piece_out(ctx, piece, PieceDetail)


@router.post("/pieces/{piece_id}/figures/{figure_id}/verify", response_model=PieceDetail)
def verify(piece_id: int, figure_id: int, body: VerifyFigureIn, ctx: Ctx = Depends(require("figure.verify"))) -> PieceOut:
    piece = owned(ctx.db, Piece, piece_id, ctx.client_id)
    figure = ctx.db.get(FigureCheck, figure_id)
    if not figure:
        raise AppError(404, "not_found")
    piece_svc.verify_figure(ctx.db, piece, figure, ctx.user, body.status, body.note)
    ctx.db.commit()
    return piece_out(ctx, piece, PieceDetail)


@router.post("/pieces/{piece_id}/legal", response_model=PieceDetail)
def piece_legal(piece_id: int, body: PieceLegalIn, ctx: Ctx = Depends(require("piece.legal"))) -> PieceOut:
    piece = owned(ctx.db, Piece, piece_id, ctx.client_id)
    if len(body.note.strip()) < 3:
        raise AppError(422, "invalid_value", detail="note")
    piece.legal_required = True
    piece.legal_status = "liberada" if body.action == "liberar" else "bloqueada"
    piece.legal_note, piece.legal_by_id, piece.legal_at = body.note.strip(), ctx.user.id, utcnow()
    ctx.db.add(Review(client_id=ctx.client_id, piece_id=piece.id, case_id=piece.case_id, user_id=ctx.user.id, action=f"legal_{body.action}", piece_version=piece.current_version, note=body.note))
    audit.record(ctx.db, action=f"piece.legal_{body.action}", entity_type="piece", entity_id=piece.id, client_id=ctx.client_id, user=ctx.user, note=body.note)
    ctx.db.commit()
    return piece_out(ctx, piece, PieceDetail)


@router.post("/pieces/{piece_id}/rerender", response_model=PieceDetail)
def rerender(piece_id: int, ctx: Ctx = Depends(require("piece.edit"))) -> PieceOut:
    from app.render.renderer import render_piece

    piece = owned(ctx.db, Piece, piece_id, ctx.client_id)
    if piece_svc._eager():
        render_piece(ctx.db, piece)
    else:
        piece.render_status = "pendiente"
    ctx.db.commit()
    piece_svc.enqueue_pending_render(piece)
    return piece_out(ctx, piece, PieceDetail)


@router.get("/pieces/{piece_id}/preview", response_class=HTMLResponse)
def preview(piece_id: int, slide: int = 0, ctx: Ctx = Depends(get_ctx)) -> HTMLResponse:
    from app.render.renderer import render_html, render_model

    piece = owned(ctx.db, Piece, piece_id, ctx.client_id)
    models = render_model(ctx.db, piece)
    return HTMLResponse(render_html(models[min(slide, len(models) - 1)]))


@router.post("/pieces/{piece_id}/consent", response_model=PieceDetail)
async def attach_consent(
    piece_id: int,
    person_label: str = Form(...),
    testimony: str = Form(...),
    signed_at: datetime | None = Form(None),
    file: UploadFile = File(...),
    ctx: Ctx = Depends(require("piece.edit")),
) -> PieceOut:
    """HR-07: a real testimony needs its signed consent attached; the testimony text goes into the piece as a new version."""
    piece = owned(ctx.db, Piece, piece_id, ctx.client_id)
    if piece.creative_slug != "voz_ciudadana":
        raise AppError(422, "invalid_value", detail="solo aplica a «Voz ciudadana»")
    if file.content_type not in ("application/pdf", "image/png", "image/jpeg"):
        raise AppError(422, "invalid_value", detail="el consentimiento debe ser PDF o imagen")
    data = await file.read()
    ext = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[file.content_type]
    record = ConsentRecord(client_id=ctx.client_id, piece_id=piece.id, person_label=person_label.strip(), testimony=testimony.strip(), signed_at=signed_at, file_key="", uploaded_by_id=ctx.user.id)
    ctx.db.add(record)
    ctx.db.flush()
    record.file_key = get_storage().save(client_key(ctx.client_id, "consents", f"{record.id}.{ext}"), data, file.content_type)
    slots = dict((piece.content or {}).get("slots") or {})
    slots["cita"] = {"text": testimony.strip(), "fact_ids": []}
    slots["persona"] = {"text": person_label.strip(), "fact_ids": []}
    piece.missing_inputs = []
    ctx.db.add(Review(client_id=ctx.client_id, piece_id=piece.id, case_id=piece.case_id, user_id=ctx.user.id, action="consentimiento", piece_version=piece.current_version, note=person_label))
    audit.record(ctx.db, action="piece.consent", entity_type="piece", entity_id=piece.id, client_id=ctx.client_id, user=ctx.user, note=person_label)
    piece_svc.edit_piece(ctx.db, piece, ctx.user, {"slots": slots}, "testimonio real con consentimiento")
    ctx.db.commit()
    piece_svc.enqueue_pending_render(piece)
    return piece_out(ctx, piece, PieceDetail)


class _NoteIn(BaseModel):
    note: str = ""


class _ReasonIn(BaseModel):
    reason: str


@router.post("/pieces/{piece_id}/approve", response_model=PieceDetail)
def approve(piece_id: int, body: _NoteIn, ctx: Ctx = Depends(require("piece.approve"))) -> PieceOut:
    """HR-09: human approval only with every figure verified, legal released, consent attached and no blocking findings."""
    piece = owned(ctx.db, Piece, piece_id, ctx.client_id)
    pub_svc.approve(ctx.db, piece, ctx.user, body.note)
    ctx.db.commit()
    return piece_out(ctx, piece, PieceDetail)


@router.post("/pieces/{piece_id}/discard", response_model=PieceDetail)
def discard(piece_id: int, body: _ReasonIn, ctx: Ctx = Depends(require("piece.discard"))) -> PieceOut:
    piece = owned(ctx.db, Piece, piece_id, ctx.client_id)
    pub_svc.discard(ctx.db, piece, ctx.user, body.reason)
    ctx.db.commit()
    return piece_out(ctx, piece, PieceDetail)
