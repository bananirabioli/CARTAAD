"""Inteligencia (6.9): narrativas coordinadas y reporte semanal exportable en HTML / Markdown."""

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from app.api.deps import Ctx, get_ctx
from app.services import intelligence as svc

router = APIRouter(tags=["intelligence"])


class NarrativeOut(BaseModel):
    id: int
    level: str
    topic: str | None
    topic_name: str | None
    representative: str
    posts: int
    sources: int
    mean_similarity: float
    first_seen: str
    last_seen: str
    span_hours: float
    interactions: int
    items: list[dict]


def _start(start: date | None) -> datetime | None:
    return datetime.combine(start, time.min, tzinfo=timezone.utc) if start else None


@router.get("/intelligence/narratives", response_model=list[NarrativeOut])
def narratives(ctx: Ctx = Depends(get_ctx), days: int = Query(7, ge=1, le=90)) -> list[dict]:
    return svc.coordinated_narratives(ctx.db, ctx.client, days=days)


@router.get("/intelligence/weekly-report", response_model=dict)
def weekly_report(ctx: Ctx = Depends(get_ctx), start: date | None = None, tag: str | None = None) -> dict:
    return svc.weekly_report(ctx.db, ctx.client, _start(start), tag or None)


def _filename(report: dict, ext: str) -> str:
    return f"reporte-semanal-{report['start'][:10]}.{ext}"


@router.get("/intelligence/weekly-report.md", response_class=PlainTextResponse)
def weekly_report_md(ctx: Ctx = Depends(get_ctx), start: date | None = None, tag: str | None = None) -> PlainTextResponse:
    report = svc.weekly_report(ctx.db, ctx.client, _start(start), tag or None)
    return PlainTextResponse(svc.to_markdown(report), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{_filename(report, "md")}"'})


@router.get("/intelligence/weekly-report.html", response_class=HTMLResponse)
def weekly_report_html(ctx: Ctx = Depends(get_ctx), start: date | None = None, tag: str | None = None, download: bool = False) -> HTMLResponse:
    report = svc.weekly_report(ctx.db, ctx.client, _start(start), tag or None)
    headers = {"Content-Disposition": f'attachment; filename="{_filename(report, "html")}"'} if download else {}
    return HTMLResponse(svc.to_html(report), headers=headers)
