"""Base de conocimiento (6.4). Lectura para todos los roles; curaduría para kb_owner."""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import func, or_, select

from app.api.deps import Ctx, get_ctx, next_code, owned, require
from app.db import utcnow
from app.errors import invalid
from app.models.kb import (
    Actor,
    ApprovedImage,
    Brief,
    Competence,
    DocumentChunk,
    Fact,
    GovLevel,
    KeyMessage,
    ResponseHistory,
    SourceDocument,
)
from app.schemas.common import Message, Page
from app.schemas.kb import (
    ActorIn,
    ActorOut,
    BriefIn,
    BriefOut,
    CompetenceIn,
    CompetenceOut,
    DocumentDetail,
    DocumentOut,
    DocumentPatch,
    FactIn,
    FactOut,
    FactPatch,
    GovLevelIn,
    GovLevelOut,
    HistoryOut,
    ImageOut,
    ImagePatch,
    ImportReport,
    KeyMessageIn,
    KeyMessageOut,
    SearchHit,
)
from app.services import audit
from app.services.facts import fact_out, import_facts_csv, refresh_embedding
from app.services.semantic import search_text
from app.storage import client_key, get_storage

router = APIRouter(prefix="/kb", tags=["kb"])

ALLOWED_DOC_TYPES = {"application/pdf"}
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


def _audit(ctx: Ctx, action: str, entity: str, obj, before=None):  # noqa: ANN001
    audit.record(ctx.db, action=action, entity_type=entity, entity_id=obj.id, client_id=ctx.client_id, user=ctx.user, before=before, after=audit.snapshot(obj))


# ------------------------------------------------------------------ gov levels


@router.get("/gov-levels", response_model=list[GovLevelOut])
def list_levels(ctx: Ctx = Depends(get_ctx)) -> list[GovLevel]:
    return list(ctx.db.scalars(select(GovLevel).where(GovLevel.client_id == ctx.client_id).order_by(GovLevel.ord)))


@router.post("/gov-levels", response_model=GovLevelOut, status_code=201)
def create_level(body: GovLevelIn, ctx: Ctx = Depends(require("kb.curate"))) -> GovLevel:
    level = GovLevel(client_id=ctx.client_id, **body.model_dump())
    ctx.db.add(level)
    ctx.db.flush()
    _audit(ctx, "gov_level.create", "gov_level", level)
    ctx.db.commit()
    return level


# ------------------------------------------------------------------ facts


@router.get("/facts", response_model=Page[FactOut])
def list_facts(
    ctx: Ctx = Depends(get_ctx),
    q: str | None = None,
    topic_id: int | None = None,
    gov_level_id: int | None = None,
    status: str | None = Query(None, pattern="^(vigente|vencido|sin_documento|sin_verificar)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[FactOut]:
    stmt = select(Fact).where(Fact.client_id == ctx.client_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Fact.statement.ilike(like), Fact.code.ilike(like), Fact.notes.ilike(like)))
    if topic_id:
        stmt = stmt.where(Fact.topic_id == topic_id)
    if gov_level_id:
        stmt = stmt.where(Fact.gov_level_id == gov_level_id)
    now = utcnow()
    if status == "vigente":
        stmt = stmt.where(or_(Fact.valid_until.is_(None), Fact.valid_until >= now))
    elif status == "vencido":
        stmt = stmt.where(Fact.valid_until < now)
    elif status == "sin_documento":
        stmt = stmt.where(Fact.document_id.is_(None))
    elif status == "sin_verificar":
        stmt = stmt.where(Fact.verified_at.is_(None))
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = ctx.db.scalars(stmt.order_by(Fact.code).offset((page - 1) * page_size).limit(page_size))
    return Page(items=[fact_out(ctx.db, f) for f in rows], total=total, page=page, page_size=page_size)


@router.get("/facts/{fact_id}", response_model=FactOut)
def get_fact(fact_id: int, ctx: Ctx = Depends(get_ctx)) -> FactOut:
    return fact_out(ctx.db, owned(ctx.db, Fact, fact_id, ctx.client_id))


def _check_refs(ctx: Ctx, data: dict) -> None:
    if data.get("document_id"):
        owned(ctx.db, SourceDocument, data["document_id"], ctx.client_id)
    if data.get("gov_level_id"):
        owned(ctx.db, GovLevel, data["gov_level_id"], ctx.client_id)


@router.post("/facts", response_model=FactOut, status_code=201)
def create_fact(body: FactIn, ctx: Ctx = Depends(require("kb.curate"))) -> FactOut:
    data = body.model_dump()
    _check_refs(ctx, data)
    fact = Fact(client_id=ctx.client_id, code=next_code(ctx.db, ctx.client_id, "fact", "H"), **data)
    refresh_embedding(fact)
    ctx.db.add(fact)
    ctx.db.flush()
    _audit(ctx, "fact.create", "fact", fact)
    ctx.db.commit()
    return fact_out(ctx.db, fact)


@router.patch("/facts/{fact_id}", response_model=FactOut)
def update_fact(fact_id: int, body: FactPatch, ctx: Ctx = Depends(require("kb.curate"))) -> FactOut:
    fact = owned(ctx.db, Fact, fact_id, ctx.client_id)
    before = audit.snapshot(fact)
    data = body.model_dump(exclude_unset=True)
    _check_refs(ctx, data)
    for k, v in data.items():
        setattr(fact, k, v)
    if {"statement", "value", "unit", "base", "period_label", "period_start", "period_end", "fact_date", "document_id"} & data.keys():
        fact.verified_by_id, fact.verified_at = None, None  # a changed fact must be re-verified
    refresh_embedding(fact)
    _audit(ctx, "fact.update", "fact", fact, before)
    ctx.db.commit()
    return fact_out(ctx.db, fact)


@router.post("/facts/{fact_id}/verify", response_model=FactOut)
def verify_fact(fact_id: int, ctx: Ctx = Depends(require("fact.verify"))) -> FactOut:
    fact = owned(ctx.db, Fact, fact_id, ctx.client_id)
    before = audit.snapshot(fact)
    fact.verified_by_id, fact.verified_at = ctx.user.id, utcnow()
    _audit(ctx, "fact.verify", "fact", fact, before)
    ctx.db.commit()
    return fact_out(ctx.db, fact)


@router.post("/facts/import", response_model=ImportReport)
async def import_facts(file: UploadFile = File(...), ctx: Ctx = Depends(require("kb.curate"))) -> ImportReport:
    data = await file.read()
    report = import_facts_csv(ctx.db, ctx.client_id, data, lambda: next_code(ctx.db, ctx.client_id, "fact", "H"))
    audit.record(ctx.db, action="fact.import", entity_type="fact", client_id=ctx.client_id, user=ctx.user, after=report, note=file.filename or "")
    ctx.db.commit()
    return ImportReport(**report)


# ------------------------------------------------------------------ documents


def _doc_out(ctx: Ctx, doc: SourceDocument) -> DocumentOut:
    chunks = ctx.db.scalar(select(func.count()).where(DocumentChunk.document_id == doc.id)) or 0
    facts = ctx.db.scalar(select(func.count()).where(Fact.document_id == doc.id)) or 0
    return DocumentOut.model_validate(doc).model_copy(update={"chunk_count": chunks, "fact_count": facts})


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(ctx: Ctx = Depends(get_ctx), q: str | None = None) -> list[DocumentOut]:
    stmt = select(SourceDocument).where(SourceDocument.client_id == ctx.client_id)
    if q:
        stmt = stmt.where(SourceDocument.title.ilike(f"%{q}%"))
    return [_doc_out(ctx, d) for d in ctx.db.scalars(stmt.order_by(SourceDocument.issued_at.desc()))]


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: int, ctx: Ctx = Depends(get_ctx)) -> DocumentDetail:
    doc = owned(ctx.db, SourceDocument, doc_id, ctx.client_id)
    base = _doc_out(ctx, doc)
    return DocumentDetail(**base.model_dump(), chunks=[c for c in doc.chunks])


@router.post("/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    issuer: str = Form(""),
    doc_type: str = Form("informe"),
    issued_at: datetime | None = Form(None),
    url: str | None = Form(None),
    gov_level_id: int | None = Form(None),
    topic_id: int | None = Form(None),
    ctx: Ctx = Depends(require("kb.curate")),
) -> DocumentOut:
    if file.content_type not in ALLOWED_DOC_TYPES:
        raise invalid("solo se aceptan PDF")
    data = await file.read()
    doc = SourceDocument(
        client_id=ctx.client_id, title=title, issuer=issuer, doc_type=doc_type, issued_at=issued_at, url=url,
        gov_level_id=gov_level_id, topic_id=topic_id, status="pendiente", created_by_id=ctx.user.id,
    )
    ctx.db.add(doc)
    ctx.db.flush()
    doc.file_key = get_storage().save(client_key(ctx.client_id, "documents", f"{doc.id}.pdf"), data, "application/pdf")
    _audit(ctx, "document.upload", "document", doc)
    ctx.db.commit()
    from app.tasks import process_document_task

    process_document_task.delay(doc.id)
    ctx.db.refresh(doc)
    return _doc_out(ctx, doc)


@router.patch("/documents/{doc_id}", response_model=DocumentOut)
def update_document(doc_id: int, body: DocumentPatch, ctx: Ctx = Depends(require("kb.curate"))) -> DocumentOut:
    doc = owned(ctx.db, SourceDocument, doc_id, ctx.client_id)
    before = audit.snapshot(doc)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(doc, k, v)
    _audit(ctx, "document.update", "document", doc, before)
    ctx.db.commit()
    return _doc_out(ctx, doc)


# ------------------------------------------------------------------ semantic search


@router.get("/search", response_model=list[SearchHit])
def search(q: str = Query(min_length=2), limit: int = Query(12, ge=1, le=50), ctx: Ctx = Depends(get_ctx)) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for fact, score in search_text(ctx.db, Fact, q, Fact.client_id == ctx.client_id, limit=limit):
        hits.append(SearchHit(kind="fact", id=fact.id, title=fact.code, snippet=fact.statement, score=round(score, 3), ref={"document_id": fact.document_id}))
    for chunk, score in search_text(ctx.db, DocumentChunk, q, DocumentChunk.client_id == ctx.client_id, limit=limit):
        hits.append(
            SearchHit(kind="chunk", id=chunk.id, title=chunk.document.title, snippet=chunk.text[:280], score=round(score, 3), ref={"document_id": chunk.document_id, "page": chunk.page})
        )
    for brief, score in search_text(ctx.db, Brief, q, Brief.client_id == ctx.client_id, limit=limit):
        hits.append(SearchHit(kind="brief", id=brief.id, title=brief.title, snippet=brief.body_md[:280], score=round(score, 3)))
    hits.sort(key=lambda h: h.score, reverse=True)
    return [h for h in hits if h.score > 0.05][:limit]


# ------------------------------------------------------------------ briefs


@router.get("/briefs", response_model=list[BriefOut])
def list_briefs(ctx: Ctx = Depends(get_ctx)) -> list[Brief]:
    return list(ctx.db.scalars(select(Brief).where(Brief.client_id == ctx.client_id).order_by(Brief.title)))


@router.post("/briefs", response_model=BriefOut, status_code=201)
def create_brief(body: BriefIn, ctx: Ctx = Depends(require("kb.curate"))) -> Brief:
    from app.ai.embeddings import embed

    brief = Brief(client_id=ctx.client_id, updated_by_id=ctx.user.id, embedding=embed(f"{body.title} {body.body_md}"), **body.model_dump())
    ctx.db.add(brief)
    ctx.db.flush()
    _audit(ctx, "brief.create", "brief", brief)
    ctx.db.commit()
    return brief


@router.put("/briefs/{brief_id}", response_model=BriefOut)
def update_brief(brief_id: int, body: BriefIn, ctx: Ctx = Depends(require("kb.curate"))) -> Brief:
    from app.ai.embeddings import embed

    brief = owned(ctx.db, Brief, brief_id, ctx.client_id)
    before = audit.snapshot(brief)
    for k, v in body.model_dump().items():
        setattr(brief, k, v)
    brief.embedding = embed(f"{brief.title} {brief.body_md}")
    brief.updated_by_id, brief.updated_at = ctx.user.id, utcnow()
    _audit(ctx, "brief.update", "brief", brief, before)
    ctx.db.commit()
    return brief


# ------------------------------------------------------------------ key messages


@router.get("/key-messages", response_model=list[KeyMessageOut])
def list_key_messages(ctx: Ctx = Depends(get_ctx)) -> list[KeyMessage]:
    return list(ctx.db.scalars(select(KeyMessage).where(KeyMessage.client_id == ctx.client_id).order_by(KeyMessage.priority.desc())))


@router.post("/key-messages", response_model=KeyMessageOut, status_code=201)
def create_key_message(body: KeyMessageIn, ctx: Ctx = Depends(require("kb.curate"))) -> KeyMessage:
    km = KeyMessage(client_id=ctx.client_id, **body.model_dump())
    ctx.db.add(km)
    ctx.db.flush()
    _audit(ctx, "key_message.create", "key_message", km)
    ctx.db.commit()
    return km


@router.put("/key-messages/{km_id}", response_model=KeyMessageOut)
def update_key_message(km_id: int, body: KeyMessageIn, ctx: Ctx = Depends(require("kb.curate"))) -> KeyMessage:
    km = owned(ctx.db, KeyMessage, km_id, ctx.client_id)
    before = audit.snapshot(km)
    for k, v in body.model_dump().items():
        setattr(km, k, v)
    _audit(ctx, "key_message.update", "key_message", km, before)
    ctx.db.commit()
    return km


# ------------------------------------------------------------------ actors


@router.get("/actors", response_model=list[ActorOut])
def list_actors(ctx: Ctx = Depends(get_ctx)) -> list[Actor]:
    return list(ctx.db.scalars(select(Actor).where(Actor.client_id == ctx.client_id).order_by(Actor.name)))


@router.post("/actors", response_model=ActorOut, status_code=201)
def create_actor(body: ActorIn, ctx: Ctx = Depends(require("kb.curate"))) -> Actor:
    actor = Actor(client_id=ctx.client_id, **body.model_dump())
    ctx.db.add(actor)
    ctx.db.flush()
    _audit(ctx, "actor.create", "actor", actor)
    ctx.db.commit()
    return actor


@router.put("/actors/{actor_id}", response_model=ActorOut)
def update_actor(actor_id: int, body: ActorIn, ctx: Ctx = Depends(require("kb.curate"))) -> Actor:
    actor = owned(ctx.db, Actor, actor_id, ctx.client_id)
    before = audit.snapshot(actor)
    for k, v in body.model_dump().items():
        setattr(actor, k, v)
    _audit(ctx, "actor.update", "actor", actor, before)
    ctx.db.commit()
    return actor


# ------------------------------------------------------------------ competences


@router.get("/competences", response_model=list[CompetenceOut])
def list_competences(ctx: Ctx = Depends(get_ctx)) -> list[Competence]:
    return list(ctx.db.scalars(select(Competence).where(Competence.client_id == ctx.client_id).order_by(Competence.topic_id, Competence.gov_level_id)))


@router.post("/competences", response_model=CompetenceOut, status_code=201)
def create_competence(body: CompetenceIn, ctx: Ctx = Depends(require("kb.curate"))) -> Competence:
    owned(ctx.db, GovLevel, body.gov_level_id, ctx.client_id)
    comp = Competence(client_id=ctx.client_id, **body.model_dump())
    ctx.db.add(comp)
    ctx.db.flush()
    _audit(ctx, "competence.create", "competence", comp)
    ctx.db.commit()
    return comp


@router.put("/competences/{comp_id}", response_model=CompetenceOut)
def update_competence(comp_id: int, body: CompetenceIn, ctx: Ctx = Depends(require("kb.curate"))) -> Competence:
    comp = owned(ctx.db, Competence, comp_id, ctx.client_id)
    owned(ctx.db, GovLevel, body.gov_level_id, ctx.client_id)
    before = audit.snapshot(comp)
    for k, v in body.model_dump().items():
        setattr(comp, k, v)
    _audit(ctx, "competence.update", "competence", comp, before)
    ctx.db.commit()
    return comp


# ------------------------------------------------------------------ approved images


@router.get("/images", response_model=list[ImageOut])
def list_images(
    ctx: Ctx = Depends(get_ctx), image_type: str | None = None, topic_id: int | None = None, tag: str | None = None, q: str | None = None
) -> list[ApprovedImage]:
    stmt = select(ApprovedImage).where(ApprovedImage.client_id == ctx.client_id)
    if image_type:
        stmt = stmt.where(ApprovedImage.image_type == image_type)
    if topic_id:
        stmt = stmt.where(ApprovedImage.topic_id == topic_id)
    if q:
        stmt = stmt.where(ApprovedImage.title.ilike(f"%{q}%"))
    rows = list(ctx.db.scalars(stmt.order_by(ApprovedImage.id.desc())))
    return [r for r in rows if not tag or tag in (r.tags or [])]


@router.post("/images", response_model=ImageOut, status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    title: str = Form(...),
    credit: str = Form(""),
    license: str = Form(""),
    image_type: str = Form("foto_real"),
    taken_at: datetime | None = Form(None),
    tags: str = Form(""),
    topic_id: int | None = Form(None),
    ctx: Ctx = Depends(require("assets.upload")),
) -> ApprovedImage:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise invalid("formato de imagen no permitido")
    if image_type not in ("foto_real", "ilustracion"):
        raise invalid("tipo de imagen")
    if image_type == "foto_real" and not credit.strip():
        raise invalid("una foto real requiere crédito (HR-06)")
    data = await file.read()
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[file.content_type]
    img = ApprovedImage(
        client_id=ctx.client_id, title=title, credit=credit, license=license, image_type=image_type, taken_at=taken_at,
        tags=[t.strip() for t in tags.split(",") if t.strip()], topic_id=topic_id, file_key="", created_by_id=ctx.user.id,
        meta={"ilustracion": image_type == "ilustracion"},
    )
    ctx.db.add(img)
    ctx.db.flush()
    img.file_key = get_storage().save(client_key(ctx.client_id, "images", f"{img.id}.{ext}"), data, file.content_type)
    _audit(ctx, "image.upload", "image", img)
    ctx.db.commit()
    return img


@router.patch("/images/{image_id}", response_model=ImageOut)
def update_image(image_id: int, body: ImagePatch, ctx: Ctx = Depends(require("assets.upload"))) -> ApprovedImage:
    img = owned(ctx.db, ApprovedImage, image_id, ctx.client_id)
    before = audit.snapshot(img)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(img, k, v)
    if img.image_type == "foto_real" and not img.credit.strip():
        raise invalid("una foto real requiere crédito (HR-06)")
    img.meta = {**(img.meta or {}), "ilustracion": img.image_type == "ilustracion"}
    _audit(ctx, "image.update", "image", img, before)
    ctx.db.commit()
    return img


# ------------------------------------------------------------------ response history


@router.get("/history", response_model=list[HistoryOut])
def list_history(
    ctx: Ctx = Depends(get_ctx), topic: str | None = None, style: str | None = None, format: str | None = None, strategy: str | None = None
) -> list[ResponseHistory]:
    stmt = select(ResponseHistory).where(ResponseHistory.client_id == ctx.client_id)
    if topic:
        stmt = stmt.where(ResponseHistory.topic_slug == topic)
    if style:
        stmt = stmt.where(ResponseHistory.style_slug == style)
    if format:
        stmt = stmt.where(ResponseHistory.format_slug == format)
    if strategy:
        stmt = stmt.where(ResponseHistory.strategy == strategy)
    return list(ctx.db.scalars(stmt.order_by(ResponseHistory.created_at.desc()).limit(300)))


@router.get("/stats", response_model=dict[str, int])
def kb_stats(ctx: Ctx = Depends(get_ctx)) -> dict[str, int]:
    def count(model) -> int:  # noqa: ANN001
        return ctx.db.scalar(select(func.count()).where(model.client_id == ctx.client_id)) or 0

    now = utcnow()
    return {
        "facts": count(Fact),
        "facts_expired": ctx.db.scalar(select(func.count()).where(Fact.client_id == ctx.client_id, Fact.valid_until < now)) or 0,
        "facts_without_document": ctx.db.scalar(select(func.count()).where(Fact.client_id == ctx.client_id, Fact.document_id.is_(None))) or 0,
        "documents": count(SourceDocument),
        "chunks": count(DocumentChunk),
        "briefs": count(Brief),
        "key_messages": count(KeyMessage),
        "actors": count(Actor),
        "competences": count(Competence),
        "images": count(ApprovedImage),
        "history": count(ResponseHistory),
    }


@router.delete("/key-messages/{km_id}", response_model=Message)
def delete_key_message(km_id: int, ctx: Ctx = Depends(require("kb.curate"))) -> Message:
    km = owned(ctx.db, KeyMessage, km_id, ctx.client_id)
    audit.record(ctx.db, action="key_message.delete", entity_type="key_message", entity_id=km.id, client_id=ctx.client_id, user=ctx.user, before=audit.snapshot(km))
    ctx.db.delete(km)
    ctx.db.commit()
    return Message()
