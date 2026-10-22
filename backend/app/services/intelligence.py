"""Inteligencia (6.9, versión ligera): narrativas coordinadas y reporte semanal.

Groups *public pages* (monitored sources), never individual citizens: a narrative is the same message published by
several pages within a time window, grouped by embedding similarity. "Coordinated" is a publication pattern signal for
the team to review, not proof of coordination.
"""

import html
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import cosine
from app.db import utcnow
from app.i18n import t
from app.models.cases import Case, Classification
from app.models.core import Client, Topic
from app.models.generation import Piece
from app.models.metrics import PostMetrics
from app.models.monitoring import Post
from app.models.publishing import ScheduledPost
from app.models.styles import CreativeType, Directive, Format
from app.services.client_settings import get_client_settings
from app.services.veda import active_restriction

# ------------------------------------------------------------------ narratives


def coordinated_narratives(db: Session, client: Client, days: int = 7, until: datetime | None = None) -> list[dict[str, Any]]:
    settings = get_client_settings(client)
    until = until or utcnow()
    since = until - timedelta(days=days)
    window = timedelta(hours=settings.coordinated_window_hours)
    posts = [p for p in db.scalars(
        select(Post).where(Post.client_id == client.id, Post.is_history.is_(False), Post.published_at.between(since, until)).order_by(Post.published_at)
    ) if p.embedding]
    topics = {c.post_id: c.topic_slug for c in db.scalars(select(Classification).where(Classification.post_id.in_([p.id for p in posts])))}

    parent = list(range(len(posts)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    sims: dict[tuple[int, int], float] = {}
    for i, a in enumerate(posts):
        for j in range(i + 1, len(posts)):
            b = posts[j]
            if b.published_at - a.published_at > window:
                break  # posts are sorted by time
            if a.source_id is not None and a.source_id == b.source_id:
                continue
            if topics.get(a.id) and topics.get(b.id) and topics[a.id] != topics[b.id]:
                continue
            score = cosine(a.embedding, b.embedding)
            if score >= settings.repeated_similarity:
                sims[(i, j)] = score
                parent[find(j)] = find(i)

    members: dict[int, list[int]] = defaultdict(list)
    for i in range(len(posts)):
        members[find(i)].append(i)
    cases = {c.post_id: c for c in db.scalars(select(Case).where(Case.post_id.in_([p.id for p in posts])))}
    topic_names = {tp.slug: tp.name for tp in db.scalars(select(Topic).where(Topic.client_id == client.id))}
    out = []
    for idx in members.values():
        sources = {posts[i].source_id or f"manual-{posts[i].id}" for i in idx}
        if len(idx) < 2 or len(sources) < 2:
            continue
        pair_scores = [s for (i, j), s in sims.items() if i in idx and j in idx]
        mean_sim = sum(pair_scores) / len(pair_scores) if pair_scores else 0.0
        first, last = posts[idx[0]], posts[idx[-1]]
        span_h = (last.published_at - first.published_at).total_seconds() / 3600
        coordinated = len(sources) >= 3 and mean_sim >= settings.coordinated_similarity and span_h <= settings.coordinated_window_hours
        topic = Counter(topics.get(posts[i].id) for i in idx).most_common(1)[0][0]
        rows = []
        for i in idx:
            p = posts[i]
            case = cases.get(p.id)
            rows.append({
                "post_id": p.id, "source": p.source.name if p.source else t("intelligence.manual_capture"), "network": p.network, "text": p.text[:280],
                "published_at": p.published_at.isoformat(), "interactions": p.total_interactions, "alert_level": p.alert_level,
                "similarity": round(cosine(first.embedding, p.embedding), 2), "case_id": case.id if case else None, "case_code": case.code if case else None,
            })
        out.append({
            "id": first.id, "level": "coordinado" if coordinated else "repetido", "topic": topic, "topic_name": topic_names.get(topic or "", topic),
            "representative": first.text[:280], "posts": len(idx), "sources": len(sources), "mean_similarity": round(mean_sim, 2),
            "first_seen": first.published_at.isoformat(), "last_seen": last.published_at.isoformat(), "span_hours": round(span_h, 1),
            "interactions": sum(r["interactions"] for r in rows), "items": rows,
        })
    out.sort(key=lambda g: (g["level"] == "coordinado", g["sources"], g["interactions"]), reverse=True)
    return out


# ------------------------------------------------------------------ weekly report


def _count(values: list[Any]) -> list[dict[str, Any]]:
    return [{"value": k, "n": n} for k, n in Counter(v for v in values if v).most_common()]


def weekly_report(db: Session, client: Client, start: datetime | None = None, tag: str | None = None) -> dict[str, Any]:
    end = (start + timedelta(days=7)) if start else utcnow()
    start = start or end - timedelta(days=7)
    in_week = lambda col: col.between(start, end)  # noqa: E731

    posts = list(db.scalars(select(Post).where(Post.client_id == client.id, Post.is_history.is_(False), in_week(Post.published_at))))
    cases = list(db.scalars(select(Case).where(Case.client_id == client.id, in_week(Case.created_at))))
    decided = list(db.scalars(select(Case).where(Case.client_id == client.id, Case.decided_at.is_not(None), in_week(Case.decided_at))))
    pieces = list(db.scalars(select(Piece).join(Case, Case.id == Piece.case_id).where(Case.client_id == client.id, in_week(Piece.created_at))))
    approved = list(db.scalars(select(Piece).join(Case, Case.id == Piece.case_id).where(Case.client_id == client.id, Piece.approved_at.is_not(None), in_week(Piece.approved_at))))
    published = list(db.scalars(select(ScheduledPost).where(ScheduledPost.client_id == client.id, ScheduledPost.status == "publicado", in_week(ScheduledPost.published_at))))
    if tag:
        pieces = [p for p in pieces if tag in (p.effective_tags or [])]
        approved = [p for p in approved if tag in (p.effective_tags or [])]
        published = [sp for sp in published if tag in (db.get(Piece, sp.piece_id).effective_tags or [])]
    metrics = list(db.scalars(select(PostMetrics).where(PostMetrics.client_id == client.id, in_week(PostMetrics.captured_at))))
    rated = list(db.scalars(select(Case).where(Case.client_id == client.id, Case.rated_at.is_not(None), in_week(Case.rated_at))))

    topic_names = {tp.slug: tp.name for tp in db.scalars(select(Topic).where(Topic.client_id == client.id))}
    format_names = {f.slug: f"{f.code} · {f.name}" for f in db.scalars(select(Format).where(Format.client_id == client.id))}
    creative_names = {c.slug: f"{c.code} · {c.name}" for c in db.scalars(select(CreativeType).where(CreativeType.client_id == client.id))}

    topic_rows = []
    by_topic: dict[str, list[Case]] = defaultdict(list)
    for c in cases:
        by_topic[c.topic_slug or "otro"].append(c)
    for slug, items in sorted(by_topic.items(), key=lambda kv: len(kv[1]), reverse=True):
        topic_rows.append({
            "topic": slug, "name": topic_names.get(slug, slug), "cases": len(items),
            "high": sum(1 for c in items if c.alert_level in ("alto", "critico")), "against": sum(1 for c in items if c.stance == "en_contra"),
        })

    attention = [
        {"case_id": c.id, "code": c.code, "topic": topic_names.get(c.topic_slug or "", c.topic_slug), "alert_level": c.alert_level, "status": c.status,
         "reason": t("intelligence.reason_legal") if c.legal_status == "pendiente" else t("intelligence.reason_undecided")}
        for c in db.scalars(select(Case).where(Case.client_id == client.id, Case.status.in_(("interpretado", "revision_legal"))).order_by(Case.created_at.desc()))
        if c.alert_level in ("alto", "critico") or c.legal_status == "pendiente"
    ][:10]

    measured = [m for m in metrics if m.original_reach]
    reach_ratios = [m.reach / m.original_reach for m in measured]
    narratives = coordinated_narratives(db, client, days=7, until=end)
    veda = active_restriction(db, client.id, end)
    rejected = list(db.scalars(select(Directive).where(Directive.client_id == client.id, Directive.conflict_status == "rechazada_por_regla_dura", in_week(Directive.updated_at))))

    return {
        "client": client.name, "start": start.isoformat(), "end": end.isoformat(), "tag": tag, "generated_at": utcnow().isoformat(),
        "summary": {
            "posts": len(posts), "cases": len(cases), "by_alert": dict(Counter(c.alert_level or "sin_linea_base" for c in cases)),
            "by_stance": dict(Counter(c.stance for c in cases if c.stance)), "by_flow": dict(Counter(c.flow for c in cases if c.flow)),
            "complaints_routed": sum(1 for c in cases if c.canalizar_a_atencion),
        },
        "topics": topic_rows,
        "attention": attention,
        "narratives": [{k: v for k, v in n.items() if k != "items"} for n in narratives[:5]],
        "responses": {
            "decisions": _count([c.decision for c in decided]),
            "pieces": len(pieces), "approved": len(approved), "published": len(published),
            "by_style": _count([p.style_slug for p in approved]),
            "by_format": [{"value": format_names.get(r["value"], r["value"]), "n": r["n"]} for r in _count([p.format_slug for p in approved])],
            "by_strategy": _count([p.strategy for p in approved]),
            "by_creative": [{"value": creative_names.get(r["value"], r["value"]), "n": r["n"]} for r in _count([p.creative_slug for p in approved])],
        },
        "results": {
            "measured": len(metrics), "avg_reach_ratio": round(sum(reach_ratios) / len(reach_ratios), 2) if reach_ratios else None,
            "worked": sum(1 for c in rated if c.rating == "funciono"), "not_worked": sum(1 for c in rated if c.rating == "no_funciono"),
        },
        "veda": {"name": veda.name, "ends_at": veda.ends_at.isoformat() if veda.ends_at else None} if veda else None,
        "directives_rejected": [{"code": d.code, "title": d.title} for d in rejected],
    }


# ------------------------------------------------------------------ rendering

ALERT_ORDER = ("critico", "alto", "medio", "bajo", "sin_linea_base")


def _enum(group: str, value: Any) -> str:
    label = t(f"intelligence.enums.{group}.{value}")
    return str(value) if label.startswith("intelligence.") else label


def _day(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.day} {t('intelligence.months').split(',')[d.month - 1]} {d.year}"


def _sections(r: dict[str, Any]) -> list[tuple[str, list[str] | list[list[str]], list[str] | None]]:
    """(title, rows, header) — header None means rows are plain paragraphs."""
    s = r["summary"]
    out: list[tuple[str, Any, Any]] = []
    out.append((t("intelligence.report.summary"), [
        t("intelligence.report.summary_line", posts=s["posts"], cases=s["cases"], routed=s["complaints_routed"]),
        " · ".join(f"{_enum('alert_level', k)}: {s['by_alert'][k]}" for k in ALERT_ORDER if k in s["by_alert"]),
        " · ".join(f"{_enum('stance', k)}: {v}" for k, v in s["by_stance"].items()) + " · " + " · ".join(f"{t('intelligence.report.flow')} {k}: {v}" for k, v in s["by_flow"].items()),
    ], None))
    if r["veda"]:
        out.append((t("intelligence.report.veda"), [t("intelligence.report.veda_line", name=r["veda"]["name"], end=_day(r["veda"]["ends_at"]) if r["veda"]["ends_at"] else "—")], None))
    out.append((t("intelligence.report.topics"), [[x["name"], str(x["cases"]), str(x["high"]), str(x["against"])] for x in r["topics"]],
                [t("intelligence.report.topic"), t("intelligence.report.cases"), t("intelligence.report.high"), t("intelligence.report.against")]))
    out.append((t("intelligence.report.narratives"), [
        [_enum("narrative_level", n["level"]), n["topic_name"] or "—", str(n["sources"]), f"{n['mean_similarity']:.2f}", f"{n['span_hours']} h", n["representative"][:120]]
        for n in r["narratives"]
    ], [t("intelligence.report.level"), t("intelligence.report.topic"), t("intelligence.report.pages"), t("intelligence.report.similarity"), t("intelligence.report.span"), t("intelligence.report.message")]))
    out.append((t("intelligence.report.attention"), [[a["code"], a["topic"] or "—", _enum("alert_level", a["alert_level"]), a["reason"]] for a in r["attention"]],
                [t("intelligence.report.case"), t("intelligence.report.topic"), t("intelligence.report.alert"), t("intelligence.report.reason")]))
    resp = r["responses"]
    lines = [t("intelligence.report.responses_line", pieces=resp["pieces"], approved=resp["approved"], published=resp["published"])]
    if resp["decisions"]:
        lines.append(t("intelligence.report.decisions") + ": " + " · ".join(f"{_enum('decision', d['value'])}: {d['n']}" for d in resp["decisions"]))
    for key in ("by_style", "by_format", "by_strategy", "by_creative"):
        if resp[key]:
            label = (lambda v: _enum("strategy", v)) if key == "by_strategy" else str
            lines.append(t(f"intelligence.report.{key}") + ": " + " · ".join(f"{label(d['value'])} ({d['n']})" for d in resp[key]))
    out.append((t("intelligence.report.responses") + (f" · {t('intelligence.report.tag')}: {r['tag']}" if r["tag"] else ""), lines, None))
    res = r["results"]
    reach = f"{res['avg_reach_ratio']:.1f}×" if res["avg_reach_ratio"] is not None else "—"
    out.append((t("intelligence.report.results"), [t("intelligence.report.results_line", measured=res["measured"], reach=reach, worked=res["worked"], not_worked=res["not_worked"])], None))
    if r["directives_rejected"]:
        out.append((t("intelligence.report.rejected"), [f"{d['code']} · {d['title']}" for d in r["directives_rejected"]], None))
    return out


def to_markdown(r: dict[str, Any]) -> str:
    lines = [f"# {t('intelligence.report.title')} · {r['client']}", "", f"_{t('intelligence.report.period', start=_day(r['start']), end=_day(r['end']))}_", ""]
    for title, rows, header in _sections(r):
        lines += [f"## {title}", ""]
        if header is None:
            lines += [f"- {row}" for row in rows] or [f"- {t('intelligence.report.none')}"]
        elif not rows:
            lines.append(t("intelligence.report.none"))
        else:
            lines.append("| " + " | ".join(header) + " |")
            lines.append("|" + "---|" * len(header))
            lines += ["| " + " | ".join(c.replace("|", "/").replace("\n", " ") for c in row) + " |" for row in rows]
        lines.append("")
    lines += ["---", "", f"_{t('intelligence.report.footer')}_", ""]
    return "\n".join(lines)


def to_html(r: dict[str, Any]) -> str:
    e = html.escape
    parts = [
        "<!doctype html><html lang='es-MX'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{e(t('intelligence.report.title'))} · {e(r['client'])}</title>",
        "<style>body{font:15px/1.5 system-ui,sans-serif;color:#111827;max-width:880px;margin:32px auto;padding:0 16px}"
        "h1{font-size:24px;margin:0}h2{font-size:16px;margin:28px 0 8px;border-bottom:1px solid #e5e7eb;padding-bottom:4px}"
        "p.meta{color:#6b7280;margin:4px 0 0}table{border-collapse:collapse;width:100%;font-size:13px}"
        "th,td{border-bottom:1px solid #e5e7eb;padding:6px 8px;text-align:left;vertical-align:top}th{background:#f9fafb}"
        "ul{padding-left:20px}footer{margin-top:32px;color:#6b7280;font-size:12px}</style></head><body>",
        f"<h1>{e(t('intelligence.report.title'))} · {e(r['client'])}</h1>",
        f"<p class='meta'>{e(t('intelligence.report.period', start=_day(r['start']), end=_day(r['end'])))}</p>",
    ]
    for title, rows, header in _sections(r):
        parts.append(f"<h2>{e(title)}</h2>")
        if header is None:
            parts.append("<ul>" + "".join(f"<li>{e(row)}</li>" for row in rows) + "</ul>")
        elif not rows:
            parts.append(f"<p>{e(t('intelligence.report.none'))}</p>")
        else:
            parts.append("<table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in header) + "</tr></thead><tbody>")
            parts += ["<tr>" + "".join(f"<td>{e(c)}</td>" for c in row) + "</tr>" for row in rows]
            parts.append("</tbody></table>")
    parts.append(f"<footer>{e(t('intelligence.report.footer'))}</footer></body></html>")
    return "".join(parts)
