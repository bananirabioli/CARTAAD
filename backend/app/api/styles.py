"""Estilos, etiquetas, directrices, catálogos (formatos, creativos, matriz), modo veda y registro de IA."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import Ctx, get_ctx, next_code, owned, require
from app.db import utcnow
from app.errors import AppError, conflict, not_found
from app.guardrails.hard_rules import restriction_active
from app.i18n import t
from app.models.core import User
from app.models.ops import AiRun, RestrictionMode
from app.models.styles import CreativeFormatCompat, CreativeType, Directive, Format, Style, Tag, TagDimension
from app.schemas.common import Message, Page
from app.schemas.styles import (
    AiRunDetail,
    AiRunOut,
    CreativeTypeIn,
    CreativeTypeOut,
    CreativeTypePatch,
    DirectiveFields,
    DirectiveOut,
    DirectivePatch,
    DirectiveTransitionIn,
    FindingDecisionIn,
    FormatIn,
    FormatOut,
    FormatPatch,
    MatrixCell,
    MatrixOut,
    ResolvePreviewIn,
    RestrictionIn,
    RestrictionOut,
    StyleIn,
    StyleOut,
    StylePatch,
    StyleTestIn,
    StyleTestOut,
    StyleTransitionIn,
    TagDimensionIn,
    TagDimensionOut,
    TagIn,
)
from app.services import audit
from app.services import styles as style_svc
from app.services.directive_checker import can_activate, check_directive
from app.services.permissions import KB_OWNER_DIRECTIVE_TYPES
from app.services.style_resolver import directive_in_force, resolve

router = APIRouter(tags=["styles"])


def _user_name(ctx: Ctx, user_id: int | None) -> str | None:
    user = ctx.db.get(User, user_id) if user_id else None
    return user.name if user else None


# ------------------------------------------------------------------ tags


@router.get("/tags", response_model=list[TagDimensionOut])
def list_tags(ctx: Ctx = Depends(get_ctx)) -> list[TagDimension]:
    return list(ctx.db.scalars(select(TagDimension).where(TagDimension.client_id == ctx.client_id).order_by(TagDimension.ord)))


@router.post("/tags", response_model=TagDimensionOut, status_code=201)
def create_dimension(body: TagDimensionIn, ctx: Ctx = Depends(require("catalog.manage"))) -> TagDimension:
    if ctx.db.scalar(select(TagDimension).where(TagDimension.client_id == ctx.client_id, TagDimension.slug == body.slug)):
        raise conflict(body.slug)
    count = ctx.db.scalar(select(func.count()).where(TagDimension.client_id == ctx.client_id)) or 0
    dim = TagDimension(client_id=ctx.client_id, ord=count, **body.model_dump())
    ctx.db.add(dim)
    ctx.db.flush()
    audit.record(ctx.db, action="tag_dimension.create", entity_type="tag_dimension", entity_id=dim.id, client_id=ctx.client_id, user=ctx.user, after=audit.snapshot(dim))
    ctx.db.commit()
    return dim


@router.post("/tags/{dimension_id}/values", response_model=TagDimensionOut, status_code=201)
def add_tag(dimension_id: int, body: TagIn, ctx: Ctx = Depends(require("catalog.manage"))) -> TagDimension:
    dim = owned(ctx.db, TagDimension, dimension_id, ctx.client_id)
    if any(tag.slug == body.slug for tag in dim.tags):
        raise conflict(body.slug)
    tag = Tag(dimension_id=dim.id, client_id=ctx.client_id, slug=body.slug, name=body.name, ord=len(dim.tags))
    ctx.db.add(tag)
    ctx.db.flush()
    audit.record(ctx.db, action="tag.create", entity_type="tag", entity_id=tag.id, client_id=ctx.client_id, user=ctx.user, after=audit.snapshot(tag))
    ctx.db.commit()
    ctx.db.refresh(dim)
    return dim


@router.delete("/tags/{dimension_id}/values/{tag_id}", response_model=Message)
def delete_tag(dimension_id: int, tag_id: int, ctx: Ctx = Depends(require("catalog.manage"))) -> Message:
    owned(ctx.db, TagDimension, dimension_id, ctx.client_id)
    tag = ctx.db.get(Tag, tag_id)
    if not tag or tag.dimension_id != dimension_id:
        raise not_found()
    audit.record(ctx.db, action="tag.delete", entity_type="tag", entity_id=tag.id, client_id=ctx.client_id, user=ctx.user, before=audit.snapshot(tag))
    ctx.db.delete(tag)
    ctx.db.commit()
    return Message()


# ------------------------------------------------------------------ styles


def _style_out(ctx: Ctx, style: Style, with_versions: bool = False) -> StyleOut:
    out = StyleOut.model_validate(style).model_copy(update={"is_base": style.client_id is None, "legal_approved_by_name": _user_name(ctx, style.legal_approved_by_id)})
    if with_versions and style.client_id is not None:
        rows = ctx.db.scalars(select(Style).where(Style.client_id == style.client_id, Style.slug == style.slug).order_by(Style.version.desc()))
        out.versions = [{"id": r.id, "version": r.version, "status": r.status, "change_note": r.change_note, "updated_at": r.updated_at.isoformat()} for r in rows]
    return out


def _get_style(ctx: Ctx, style_id: int, allow_base: bool = False) -> Style:
    style = ctx.db.get(Style, style_id)
    if style is None or (style.client_id != ctx.client_id and not (allow_base and style.client_id is None)):
        raise not_found()
    return style


@router.get("/styles", response_model=list[StyleOut])
def list_styles(ctx: Ctx = Depends(get_ctx), include_base: bool = False, all_versions: bool = False, status: str | None = None) -> list[StyleOut]:
    rows = list(ctx.db.scalars(select(Style).where(Style.client_id == ctx.client_id).order_by(Style.name, Style.version.desc())))
    if not all_versions:
        latest: dict[str, Style] = {}
        for s in rows:
            current = latest.get(s.slug)
            # Show the active version if there is one, plus any newer draft is reachable through `versions`.
            if current is None or (s.status == "activo" and current.status != "activo"):
                latest[s.slug] = s
        rows = list(latest.values())
    if status:
        rows = [s for s in rows if s.status == status]
    out = [_style_out(ctx, s, with_versions=True) for s in rows]
    if include_base:
        out += [_style_out(ctx, s) for s in ctx.db.scalars(select(Style).where(Style.client_id.is_(None)).order_by(Style.name))]
    return out


@router.get("/styles/{style_id}", response_model=StyleOut)
def get_style(style_id: int, ctx: Ctx = Depends(get_ctx)) -> StyleOut:
    return _style_out(ctx, _get_style(ctx, style_id, allow_base=True), with_versions=True)


@router.post("/styles", response_model=StyleOut, status_code=201)
def create_style(body: StyleIn, ctx: Ctx = Depends(require("style.edit"))) -> StyleOut:
    if ctx.db.scalar(select(Style.id).where(Style.client_id == ctx.client_id, Style.slug == body.slug)):
        raise AppError(409, "conflict", t("styles.errors.slug_exists", slug=body.slug))
    data = body.model_dump(exclude={"slug"})
    style_svc.assert_style_ok(data, style_svc.client_rules(ctx.db, ctx.client_id))
    style = Style(client_id=ctx.client_id, slug=body.slug, version=1, status="borrador", created_by_id=ctx.user.id, change_note="Creado", **data)
    if style.risk == "alto":
        style.requires_legal = True
    ctx.db.add(style)
    ctx.db.flush()
    audit.record(ctx.db, action="style.create", entity_type="style", entity_id=style.id, client_id=ctx.client_id, user=ctx.user, after=style_svc.export_style(style))
    ctx.db.commit()
    return _style_out(ctx, style, with_versions=True)


@router.post("/styles/{style_id}/clone", response_model=StyleOut, status_code=201)
def clone_style(style_id: int, new_slug: str | None = Query(None, pattern=r"^[a-z0-9_]+$"), ctx: Ctx = Depends(require("style.edit"))) -> StyleOut:
    """Clone a base template or a client style. Without `new_slug` it creates the next version of the same slug."""
    source = _get_style(ctx, style_id, allow_base=True)
    slug = new_slug or source.slug
    if new_slug and ctx.db.scalar(select(Style.id).where(Style.client_id == ctx.client_id, Style.slug == new_slug)):
        raise AppError(409, "conflict", t("styles.errors.slug_exists", slug=new_slug))
    data = {f: getattr(source, f) for f in style_svc.EDITABLE_FIELDS}
    if new_slug:
        data["name"] = f"{source.name} (copia)"
    style = Style(
        client_id=ctx.client_id, slug=slug, version=style_svc.latest_version(ctx.db, ctx.client_id, slug) + 1, status="borrador",
        parent_id=source.id, created_by_id=ctx.user.id, change_note=f"Clonado de {source.slug} v{source.version}", **data,
    )
    ctx.db.add(style)
    ctx.db.flush()
    audit.record(ctx.db, action="style.clone", entity_type="style", entity_id=style.id, client_id=ctx.client_id, user=ctx.user, note=style.change_note)
    ctx.db.commit()
    return _style_out(ctx, style, with_versions=True)


@router.patch("/styles/{style_id}", response_model=StyleOut)
def update_style(style_id: int, body: StylePatch, ctx: Ctx = Depends(get_ctx)) -> StyleOut:
    style = _get_style(ctx, style_id)
    changes = body.model_dump(exclude_unset=True)
    note = changes.pop("change_note", "") or ""
    visual_only = set(changes) <= set(style_svc.VISUAL_FIELDS)
    if not (ctx.can("style.edit") or (visual_only and ctx.can("style.visual_guide"))):
        raise AppError(403, "forbidden", permission="style.edit")
    before = style_svc.export_style(style)
    if style.status in ("activo", "archivado"):
        target = style_svc.new_version_from(ctx.db, style, ctx.user, changes, note or "Edición")
    else:
        style_svc.update_draft(style, changes)
        if note:
            style.change_note = note
        target = style
    audit.record(ctx.db, action="style.update", entity_type="style", entity_id=target.id, client_id=ctx.client_id, user=ctx.user, before=before, after=style_svc.export_style(target))
    ctx.db.commit()
    return _style_out(ctx, target, with_versions=True)


@router.post("/styles/{style_id}/transition", response_model=StyleOut)
def transition_style(style_id: int, body: StyleTransitionIn, ctx: Ctx = Depends(get_ctx)) -> StyleOut:
    style = _get_style(ctx, style_id)
    ctx.require("style.activate" if body.status in ("activo", "archivado") else "style.edit")
    before = style.status
    style_svc.transition(ctx.db, style, body.status, ctx.user)
    audit.record(ctx.db, action=f"style.{body.status}", entity_type="style", entity_id=style.id, client_id=ctx.client_id, user=ctx.user, before={"status": before}, after={"status": style.status}, note=body.note)
    ctx.db.commit()
    return _style_out(ctx, style, with_versions=True)


@router.post("/styles/{style_id}/legal-approve", response_model=StyleOut)
def legal_approve_style(style_id: int, ctx: Ctx = Depends(require("style.approve_high_risk"))) -> StyleOut:
    style = _get_style(ctx, style_id)
    style.legal_approved_by_id, style.legal_approved_at = ctx.user.id, utcnow()
    if style.status == "borrador":
        style.status = "revision"
    audit.record(ctx.db, action="style.legal_approve", entity_type="style", entity_id=style.id, client_id=ctx.client_id, user=ctx.user, note=f"{style.slug} v{style.version}")
    ctx.db.commit()
    return _style_out(ctx, style, with_versions=True)


@router.post("/styles/{style_id}/test", response_model=StyleTestOut)
def test_style(style_id: int, body: StyleTestIn, ctx: Ctx = Depends(get_ctx)) -> dict[str, Any]:
    if not (ctx.can("generation.run") or ctx.can("style.edit") or ctx.can("style.visual_guide")):
        raise AppError(403, "forbidden", permission="generation.run")
    style = _get_style(ctx, style_id)
    result = style_svc.test_style(ctx.db, ctx.client, style, ctx.user, body.text, body.flow)
    ctx.db.commit()
    return result


@router.get("/styles/{style_id}/export", response_model=dict[str, Any])
def export_style(style_id: int, ctx: Ctx = Depends(get_ctx)) -> dict[str, Any]:
    return style_svc.export_style(_get_style(ctx, style_id, allow_base=True))


@router.post("/styles/import", response_model=StyleOut, status_code=201)
def import_style(body: dict[str, Any], ctx: Ctx = Depends(require("style.edit"))) -> StyleOut:
    style = style_svc.import_style(ctx.db, ctx.client_id, body, ctx.user)
    audit.record(ctx.db, action="style.import", entity_type="style", entity_id=style.id, client_id=ctx.client_id, user=ctx.user, after=style_svc.export_style(style))
    ctx.db.commit()
    return _style_out(ctx, style, with_versions=True)


@router.post("/styles/resolve-preview", response_model=dict[str, Any])
def resolve_preview(body: ResolvePreviewIn, ctx: Ctx = Depends(get_ctx)) -> dict[str, Any]:
    from app.services.catalog import active_style

    style = active_style(ctx.db, ctx.client_id, body.style_slug)
    if not style:
        raise not_found()
    adjustments = {"intensity": body.intensity} if body.intensity else {}
    resolved = resolve(ctx.db, ctx.client_id, style, topic=body.topic, format_slug=body.format_slug, account_id=body.account_id, flow=body.flow, adjustments=adjustments)
    return {**resolved.summary(), "style_block": resolved.style_block()}


# ------------------------------------------------------------------ directives


def _directive_out(ctx: Ctx, d: Directive) -> DirectiveOut:
    return DirectiveOut.model_validate(d).model_copy(
        update={"created_by_name": _user_name(ctx, d.created_by_id), "approved_by_name": _user_name(ctx, d.approved_by_id), "in_force": directive_in_force(d, utcnow())}
    )


def _can_activate_type(ctx: Ctx, d: Directive) -> bool:
    return ctx.can("directive.activate") or (ctx.can("directive.activate_kb") and d.dtype in KB_OWNER_DIRECTIVE_TYPES)


@router.get("/directives", response_model=list[DirectiveOut])
def list_directives(ctx: Ctx = Depends(get_ctx), all_versions: bool = False, status: str | None = None, dtype: str | None = None) -> list[DirectiveOut]:
    rows = list(ctx.db.scalars(select(Directive).where(Directive.client_id == ctx.client_id).order_by(Directive.code, Directive.version.desc())))
    if not all_versions:
        latest: dict[str, Directive] = {}
        for d in rows:
            latest.setdefault(d.code, d)
        rows = list(latest.values())
    if status:
        rows = [d for d in rows if d.status == status]
    if dtype:
        rows = [d for d in rows if d.dtype == dtype]
    return [_directive_out(ctx, d) for d in rows]


@router.get("/directives/{directive_id}", response_model=DirectiveOut)
def get_directive(directive_id: int, ctx: Ctx = Depends(get_ctx)) -> DirectiveOut:
    return _directive_out(ctx, owned(ctx.db, Directive, directive_id, ctx.client_id))


@router.get("/directives/{directive_id}/versions", response_model=list[DirectiveOut])
def directive_versions(directive_id: int, ctx: Ctx = Depends(get_ctx)) -> list[DirectiveOut]:
    d = owned(ctx.db, Directive, directive_id, ctx.client_id)
    rows = ctx.db.scalars(select(Directive).where(Directive.client_id == ctx.client_id, Directive.code == d.code).order_by(Directive.version.desc()))
    return [_directive_out(ctx, r) for r in rows]


@router.post("/directives", response_model=DirectiveOut, status_code=201)
def create_directive(body: DirectiveFields, ctx: Ctx = Depends(require("directive.propose"))) -> DirectiveOut:
    d = Directive(client_id=ctx.client_id, code=next_code(ctx.db, ctx.client_id, "directive", "D"), version=1, status="borrador", created_by_id=ctx.user.id, **body.model_dump())
    ctx.db.add(d)
    ctx.db.flush()
    report = check_directive(ctx.db, d, user_id=ctx.user.id)
    audit.record(ctx.db, action="directive.create", entity_type="directive", entity_id=d.id, client_id=ctx.client_id, user=ctx.user, after=audit.snapshot(d), note=report["status"])
    ctx.db.commit()
    return _directive_out(ctx, d)


@router.patch("/directives/{directive_id}", response_model=DirectiveOut)
def update_directive(directive_id: int, body: DirectivePatch, ctx: Ctx = Depends(require("directive.propose"))) -> DirectiveOut:
    d = owned(ctx.db, Directive, directive_id, ctx.client_id)
    changes = body.model_dump(exclude_unset=True)
    before = audit.snapshot(d)
    if d.status in ("activa", "archivada", "rechazada"):
        latest = ctx.db.scalar(select(func.max(Directive.version)).where(Directive.client_id == ctx.client_id, Directive.code == d.code)) or d.version
        fields = {k: getattr(d, k) for k in DirectiveFields.model_fields}
        fields.update(changes)
        target = Directive(client_id=ctx.client_id, code=d.code, version=latest + 1, status="borrador", created_by_id=ctx.user.id, **fields)
        ctx.db.add(target)
        ctx.db.flush()
    else:
        for k, v in changes.items():
            setattr(d, k, v)
        d.updated_at = utcnow()
        target = d
    report = check_directive(ctx.db, target, user_id=ctx.user.id)
    audit.record(ctx.db, action="directive.update", entity_type="directive", entity_id=target.id, client_id=ctx.client_id, user=ctx.user, before=before, after=audit.snapshot(target), note=report["status"])
    ctx.db.commit()
    return _directive_out(ctx, target)


@router.post("/directives/{directive_id}/check", response_model=DirectiveOut)
def recheck_directive(directive_id: int, ctx: Ctx = Depends(get_ctx)) -> DirectiveOut:
    d = owned(ctx.db, Directive, directive_id, ctx.client_id)
    before = d.conflict_status
    report = check_directive(ctx.db, d, user_id=ctx.user.id)
    audit.record(ctx.db, action="directive.check", entity_type="directive", entity_id=d.id, client_id=ctx.client_id, user=ctx.user, before={"conflict_status": before}, after={"conflict_status": report["status"]})
    ctx.db.commit()
    return _directive_out(ctx, d)


@router.post("/directives/{directive_id}/findings", response_model=DirectiveOut)
def decide_finding(directive_id: int, body: FindingDecisionIn, ctx: Ctx = Depends(get_ctx)) -> DirectiveOut:
    """Confirm or dismiss an AI-suggested conflict (human confirmation required by 6.10)."""
    d = owned(ctx.db, Directive, directive_id, ctx.client_id)
    if not (_can_activate_type(ctx, d) or ctx.can("legal.review")):
        raise AppError(403, "forbidden", permission="directive.activate")
    report = dict(d.conflict_report or {})
    findings = [dict(f) for f in report.get("findings", [])]
    target = next((f for f in findings if f["id"] == body.finding_id and f.get("ai_suggested")), None)
    if not target:
        raise AppError(404, "not_found", t("directives.errors.finding_missing"))
    target["confirmed"] = body.confirmed
    d.conflict_report = {**report, "findings": findings}
    check_directive(ctx.db, d, user_id=ctx.user.id)
    audit.record(ctx.db, action="directive.ai_finding", entity_type="directive", entity_id=d.id, client_id=ctx.client_id, user=ctx.user, after={"finding": body.finding_id, "confirmed": body.confirmed})
    ctx.db.commit()
    return _directive_out(ctx, d)


@router.post("/directives/{directive_id}/transition", response_model=DirectiveOut)
def transition_directive(directive_id: int, body: DirectiveTransitionIn, ctx: Ctx = Depends(get_ctx)) -> DirectiveOut:
    d = owned(ctx.db, Directive, directive_id, ctx.client_id)
    allowed = {"borrador": {"en_revision", "activa", "archivada"}, "en_revision": {"borrador", "activa", "rechazada", "archivada"}, "activa": {"archivada"}, "archivada": {"borrador"}, "rechazada": {"borrador"}}
    if body.status not in allowed.get(d.status, set()):
        raise AppError(409, "conflict", t("directives.errors.bad_status", status=d.status))
    if body.status in ("activa", "archivada", "rechazada"):
        if not _can_activate_type(ctx, d):
            raise AppError(403, "forbidden", t("directives.errors.forbidden_type", dtype=d.dtype))
    else:
        ctx.require("directive.propose")
    before = d.status
    if body.status == "activa":
        check_directive(ctx.db, d, user_id=ctx.user.id)
        ok, reason = can_activate(d)
        if not ok:
            ctx.db.commit()  # keep the refreshed conflict report
            raise AppError(409, "directive_blocked", reason, details={"conflict_status": d.conflict_status})
        for other in ctx.db.scalars(select(Directive).where(Directive.client_id == ctx.client_id, Directive.code == d.code, Directive.status == "activa", Directive.id != d.id)):
            other.status = "archivada"
        d.approved_by_id, d.approved_at = ctx.user.id, utcnow()
    d.status = body.status
    d.updated_at = utcnow()
    audit.record(ctx.db, action=f"directive.{body.status}", entity_type="directive", entity_id=d.id, client_id=ctx.client_id, user=ctx.user, before={"status": before}, after={"status": d.status}, note=body.note)
    ctx.db.commit()
    return _directive_out(ctx, d)


@router.post("/directives/recheck-all", response_model=list[DirectiveOut])
def recheck_all(ctx: Ctx = Depends(require("directive.activate"))) -> list[DirectiveOut]:
    rows = list(ctx.db.scalars(select(Directive).where(Directive.client_id == ctx.client_id, Directive.status.in_(("borrador", "en_revision", "activa")))))
    for d in rows:
        check_directive(ctx.db, d, user_id=ctx.user.id)
    audit.record(ctx.db, action="directive.recheck_all", entity_type="directive", client_id=ctx.client_id, user=ctx.user, note=f"{len(rows)} directrices")
    ctx.db.commit()
    return [_directive_out(ctx, d) for d in rows]


# ------------------------------------------------------------------ catalogs


@router.get("/catalog/formats", response_model=list[FormatOut])
def list_formats(ctx: Ctx = Depends(get_ctx)) -> list[Format]:
    return list(ctx.db.scalars(select(Format).where(Format.client_id == ctx.client_id).order_by(Format.ord)))


@router.post("/catalog/formats", response_model=FormatOut, status_code=201)
def create_format(body: FormatIn, ctx: Ctx = Depends(require("catalog.manage"))) -> Format:
    if ctx.db.scalar(select(Format.id).where(Format.client_id == ctx.client_id, Format.slug == body.slug)):
        raise conflict(body.slug)
    n = len(list(ctx.db.scalars(select(Format.id).where(Format.client_id == ctx.client_id))))
    allowed = body.allowed_style_slugs or [body.default_style_slug]
    fmt = Format(client_id=ctx.client_id, code=f"F{n + 1}", ord=n, **body.model_dump(exclude={"allowed_style_slugs"}), allowed_style_slugs=allowed)
    ctx.db.add(fmt)
    ctx.db.flush()
    # A new format accepts every creative until the matrix says otherwise.
    for ct in ctx.db.scalars(select(CreativeType).where(CreativeType.client_id == ctx.client_id)):
        ctx.db.add(CreativeFormatCompat(client_id=ctx.client_id, creative_slug=ct.slug, format_slug=fmt.slug, level="full", note=""))
    audit.record(ctx.db, action="format.create", entity_type="format", entity_id=fmt.id, client_id=ctx.client_id, user=ctx.user, after=audit.snapshot(fmt))
    ctx.db.commit()
    return fmt


@router.patch("/catalog/formats/{format_id}", response_model=FormatOut)
def update_format(format_id: int, body: FormatPatch, ctx: Ctx = Depends(require("catalog.manage"))) -> Format:
    fmt = owned(ctx.db, Format, format_id, ctx.client_id)
    before = audit.snapshot(fmt)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(fmt, k, v)
    audit.record(ctx.db, action="format.update", entity_type="format", entity_id=fmt.id, client_id=ctx.client_id, user=ctx.user, before=before, after=audit.snapshot(fmt))
    ctx.db.commit()
    return fmt


@router.get("/catalog/creatives", response_model=list[CreativeTypeOut])
def list_creatives(ctx: Ctx = Depends(get_ctx), flow: str | None = None) -> list[CreativeType]:
    stmt = select(CreativeType).where(CreativeType.client_id == ctx.client_id)
    if flow:
        stmt = stmt.where(CreativeType.flow == flow)
    return list(ctx.db.scalars(stmt.order_by(CreativeType.ord)))


@router.post("/catalog/creatives", response_model=CreativeTypeOut, status_code=201)
def create_creative(body: CreativeTypeIn, ctx: Ctx = Depends(require("catalog.manage"))) -> CreativeType:
    if ctx.db.scalar(select(CreativeType.id).where(CreativeType.client_id == ctx.client_id, CreativeType.slug == body.slug)):
        raise conflict(body.slug)
    n = len(list(ctx.db.scalars(select(CreativeType.id).where(CreativeType.client_id == ctx.client_id, CreativeType.flow == body.flow))))
    ct = CreativeType(client_id=ctx.client_id, code=f"{body.flow}{n + 1}", ord=100 + n, is_comparison=False, **body.model_dump())
    ctx.db.add(ct)
    ctx.db.flush()
    for fmt in ctx.db.scalars(select(Format).where(Format.client_id == ctx.client_id)):
        ctx.db.add(CreativeFormatCompat(client_id=ctx.client_id, creative_slug=ct.slug, format_slug=fmt.slug, level="full", note=""))
    audit.record(ctx.db, action="creative.create", entity_type="creative_type", entity_id=ct.id, client_id=ctx.client_id, user=ctx.user, after=audit.snapshot(ct))
    ctx.db.commit()
    return ct


@router.patch("/catalog/creatives/{creative_id}", response_model=CreativeTypeOut)
def update_creative(creative_id: int, body: CreativeTypePatch, ctx: Ctx = Depends(require("catalog.manage"))) -> CreativeType:
    ct = owned(ctx.db, CreativeType, creative_id, ctx.client_id)
    before = audit.snapshot(ct)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(ct, k, v)
    audit.record(ctx.db, action="creative.update", entity_type="creative_type", entity_id=ct.id, client_id=ctx.client_id, user=ctx.user, before=before, after=audit.snapshot(ct))
    ctx.db.commit()
    return ct


@router.get("/catalog/matrix", response_model=MatrixOut)
def get_matrix(ctx: Ctx = Depends(get_ctx)) -> MatrixOut:
    cells = ctx.db.scalars(select(CreativeFormatCompat).where(CreativeFormatCompat.client_id == ctx.client_id))
    return MatrixOut(
        creatives=[CreativeTypeOut.model_validate(c) for c in list_creatives(ctx)],
        formats=[FormatOut.model_validate(f) for f in list_formats(ctx)],
        cells=[MatrixCell(creative_slug=c.creative_slug, format_slug=c.format_slug, level=c.level, note=c.note) for c in cells],
    )


@router.put("/catalog/matrix", response_model=MatrixCell)
def set_matrix_cell(body: MatrixCell, ctx: Ctx = Depends(require("catalog.manage"))) -> MatrixCell:
    row = ctx.db.scalar(
        select(CreativeFormatCompat).where(
            CreativeFormatCompat.client_id == ctx.client_id, CreativeFormatCompat.creative_slug == body.creative_slug, CreativeFormatCompat.format_slug == body.format_slug
        )
    )
    before = audit.snapshot(row) if row else None
    if row is None:
        row = CreativeFormatCompat(client_id=ctx.client_id, creative_slug=body.creative_slug, format_slug=body.format_slug, level=body.level, note=body.note)
        ctx.db.add(row)
    else:
        row.level, row.note = body.level, body.note
    ctx.db.flush()
    audit.record(ctx.db, action="matrix.update", entity_type="matrix", entity_id=row.id, client_id=ctx.client_id, user=ctx.user, before=before, after=audit.snapshot(row), only_changes=before is not None)
    ctx.db.commit()
    return body


# ------------------------------------------------------------------ modo veda


def _restriction_out(r: RestrictionMode) -> RestrictionOut:
    return RestrictionOut.model_validate(r).model_copy(update={"in_effect": restriction_active(r, utcnow())})


@router.get("/veda", response_model=list[RestrictionOut])
def list_restrictions(ctx: Ctx = Depends(get_ctx)) -> list[RestrictionOut]:
    rows = ctx.db.scalars(select(RestrictionMode).where(RestrictionMode.client_id == ctx.client_id).order_by(RestrictionMode.starts_at.desc()))
    return [_restriction_out(r) for r in rows]


@router.post("/veda", response_model=RestrictionOut, status_code=201)
def create_restriction(body: RestrictionIn, ctx: Ctx = Depends(require("veda.manage"))) -> RestrictionOut:
    r = RestrictionMode(client_id=ctx.client_id, created_by_id=ctx.user.id, **body.model_dump())
    ctx.db.add(r)
    ctx.db.flush()
    audit.record(ctx.db, action="veda.create", entity_type="veda", entity_id=r.id, client_id=ctx.client_id, user=ctx.user, after=audit.snapshot(r))
    ctx.db.commit()
    return _restriction_out(r)


@router.put("/veda/{restriction_id}", response_model=RestrictionOut)
def update_restriction(restriction_id: int, body: RestrictionIn, ctx: Ctx = Depends(require("veda.manage"))) -> RestrictionOut:
    r = owned(ctx.db, RestrictionMode, restriction_id, ctx.client_id)
    before = audit.snapshot(r)
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    audit.record(ctx.db, action="veda.update", entity_type="veda", entity_id=r.id, client_id=ctx.client_id, user=ctx.user, before=before, after=audit.snapshot(r))
    ctx.db.commit()
    return _restriction_out(r)


# ------------------------------------------------------------------ AI runs


@router.get("/ai-runs", response_model=Page[AiRunOut])
def list_ai_runs(
    ctx: Ctx = Depends(get_ctx), step: str | None = None, case_id: int | None = None, piece_id: int | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
) -> Page[AiRunOut]:
    stmt = select(AiRun).where(AiRun.client_id == ctx.client_id)
    if step:
        stmt = stmt.where(AiRun.step == step)
    if case_id:
        stmt = stmt.where(AiRun.case_id == case_id)
    if piece_id:
        stmt = stmt.where(AiRun.piece_id == piece_id)
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = ctx.db.scalars(stmt.order_by(AiRun.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return Page(items=[AiRunOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/ai-runs/{run_id}", response_model=AiRunDetail)
def get_ai_run(run_id: int, ctx: Ctx = Depends(get_ctx)) -> AiRun:
    return owned(ctx.db, AiRun, run_id, ctx.client_id)
