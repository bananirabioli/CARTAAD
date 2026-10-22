"""Measurement and learning (6.8): reach vs. the original post, sentiment change, A/B by variant, rating that feeds
ResponseHistory and therefore the learning context of the generator and the strategy recommender."""

import hashlib
import random
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.mock.fixtures import mock_json
from app.db import utcnow
from app.errors import AppError
from app.i18n import t
from app.models.cases import Case
from app.models.core import User
from app.models.generation import Piece
from app.models.kb import ResponseHistory
from app.models.metrics import PostMetrics
from app.models.monitoring import Post
from app.models.publishing import ScheduledPost
from app.services import audit
from app.services.cases import transition
from app.textnorm import normalize


def sentiment_of(texts: list[str]) -> dict[str, float]:
    """Aggregated comment sentiment (positive / negative / neutral shares) with the mock keyword themes."""
    if not texts:
        return {"pos": 0.0, "neg": 0.0, "neu": 1.0}
    themes = {r["theme"]: r["any"] for r in mock_json("classify_rules").get("comment_themes", [])}
    pos = neg = 0
    for text in texts:
        norm = normalize(text)
        if any(normalize(w) in norm for w in themes.get("apoyo", [])):
            pos += 1
        elif any(normalize(w) in norm for w in themes.get("molestia", []) + themes.get("pide_fuente", [])):
            neg += 1
    n = len(texts)
    return {"pos": round(pos / n, 2), "neg": round(neg / n, 2), "neu": round(1 - (pos + neg) / n, 2)}


def original_baseline(db: Session, case: Case) -> tuple[int, float]:
    post = db.get(Post, case.post_id)
    reach = int(post.total_interactions * 9) if post.total_interactions else 0  # rough reach estimate from interactions
    return reach, sentiment_of([c.text for c in post.comments])["neg"]


def record_metrics(db: Session, case: Case, user: User | None, data: dict[str, Any], source: str = "manual") -> PostMetrics:
    piece = db.get(Piece, data["piece_id"])
    if piece is None or piece.case_id != case.id:
        raise AppError(422, "invalid_value", detail="piece_id")
    if piece.status != "publicado":
        raise AppError(409, "conflict", t("metrics.not_published"))
    orig_reach, orig_neg = original_baseline(db, case)
    sp = db.scalar(select(ScheduledPost).where(ScheduledPost.piece_id == piece.id, ScheduledPost.status == "publicado"))
    m = PostMetrics(
        client_id=case.client_id, case_id=case.id, piece_id=piece.id, scheduled_post_id=sp.id if sp else None, source=source,
        original_reach=data.get("original_reach") or orig_reach, original_sentiment_neg=orig_neg, created_by_id=user.id if user else None,
        **{k: data.get(k, 0) for k in ("reach", "impressions", "likes", "comments", "shares", "sentiment_pos", "sentiment_neg", "sentiment_neu")},
        note=data.get("note", ""),
    )
    db.add(m)
    db.flush()
    if case.status == "publicado":
        transition(db, case, "medido", user, note=f"métricas de pieza {piece.id}")
    audit.record(db, action="metrics.record", entity_type="case", entity_id=case.id, client_id=case.client_id, user=user, after={"piece_id": piece.id, "reach": m.reach, "source": source})
    return m


def simulate_metrics(db: Session, case: Case, user: User | None) -> list[PostMetrics]:
    """Deterministic simulated results for every published variant (demo only)."""
    pieces = list(db.scalars(select(Piece).where(Piece.case_id == case.id, Piece.status == "publicado")))
    if not pieces:
        raise AppError(409, "conflict", t("metrics.not_published"))
    orig_reach, orig_neg = original_baseline(db, case)
    out = []
    for p in pieces:
        rng = random.Random(int(hashlib.sha256(f"{case.id}:{p.id}".encode()).hexdigest()[:8], 16))
        factor = rng.uniform(0.6, 2.4)
        reach = max(200, int((orig_reach or 2000) * factor))
        neg = round(max(0.05, min(0.9, orig_neg * rng.uniform(0.4, 1.1))), 2)
        pos = round(min(0.95 - neg, rng.uniform(0.2, 0.6)), 2)
        data = {
            "piece_id": p.id, "reach": reach, "impressions": int(reach * rng.uniform(1.2, 1.8)), "likes": int(reach * rng.uniform(0.02, 0.08)),
            "comments": int(reach * rng.uniform(0.002, 0.01)), "shares": int(reach * rng.uniform(0.003, 0.02)), "sentiment_pos": pos, "sentiment_neg": neg,
            "sentiment_neu": round(1 - pos - neg, 2), "note": "Simulado para la demo",
        }
        out.append(record_metrics(db, case, user, data, source="simulado"))
    return out


def variant_summary(db: Session, case: Case) -> list[dict[str, Any]]:
    rows = list(db.scalars(select(PostMetrics).where(PostMetrics.case_id == case.id).order_by(PostMetrics.captured_at)))
    latest: dict[int, PostMetrics] = {}
    for m in rows:
        latest[m.piece_id] = m
    out = []
    for piece_id, m in latest.items():
        piece = db.get(Piece, piece_id)
        engagement = (m.likes + m.comments + m.shares) / m.reach if m.reach else 0
        out.append({
            "piece_id": piece_id, "label": piece.creative_slug or f"copy · {piece.style_slug}", "style": piece.style_slug, "format": piece.format_slug,
            "strategy": piece.strategy, "reach": m.reach, "impressions": m.impressions, "engagement_rate": round(engagement, 4),
            "reach_ratio": round(m.reach / m.original_reach, 2) if m.original_reach else None,
            "sentiment_neg": m.sentiment_neg, "sentiment_delta": round((m.original_sentiment_neg or 0) - m.sentiment_neg, 2), "source": m.source,
        })
    if out:
        best = max(out, key=lambda r: (r["reach_ratio"] or 0) + r["sentiment_delta"])
        for r in out:
            r["winner"] = r is best and len(out) > 1
    return out


def rate_case(db: Session, case: Case, user: User, outcome: str, note: str = "") -> list[ResponseHistory]:
    if outcome not in ("funciono", "no_funciono"):
        raise AppError(422, "invalid_value", detail=outcome)
    if case.status not in ("medido", "calificado"):
        raise AppError(409, "conflict", t("cases.rated_requires_metrics"))
    summary = {r["piece_id"]: r for r in variant_summary(db, case)}
    histories = []
    for piece_id, r in summary.items():
        piece = db.get(Piece, piece_id)
        h = ResponseHistory(
            client_id=case.client_id, case_id=case.id, piece_id=piece.id, topic_slug=case.topic_slug or "", format_slug=piece.format_slug, style_slug=piece.style_slug,
            strategy=piece.strategy, creative_slug=piece.creative_slug or "", flow=piece.flow, outcome=outcome, reach_ratio=r["reach_ratio"],
            sentiment_delta=r["sentiment_delta"], summary=f"{case.code} · {r['label']}", notes=note, rated_by_id=user.id,
        )
        db.add(h)
        histories.append(h)
    case.rating, case.rating_note, case.rated_by_id, case.rated_at = outcome, note, user.id, utcnow()
    if case.status == "medido":
        transition(db, case, "calificado", user, note=f"{outcome}: {note}")
    audit.record(db, action="case.rate", entity_type="case", entity_id=case.id, client_id=case.client_id, user=user, after={"outcome": outcome, "history_rows": len(histories)}, note=note)
    return histories


def rankings(db: Session, client_id: int, topic: str | None, min_sample: int) -> dict[str, Any]:
    stmt = select(ResponseHistory).where(ResponseHistory.client_id == client_id)
    if topic:
        stmt = stmt.where(ResponseHistory.topic_slug == topic)
    rows = list(db.scalars(stmt))

    def rank(attr: str) -> list[dict[str, Any]]:
        groups: dict[str, list[ResponseHistory]] = defaultdict(list)
        for r in rows:
            if getattr(r, attr):
                groups[getattr(r, attr)].append(r)
        out = []
        for key, items in groups.items():
            ok = sum(1 for r in items if r.outcome == "funciono")
            reach = [r.reach_ratio for r in items if r.reach_ratio is not None]
            sent = [r.sentiment_delta for r in items if r.sentiment_delta is not None]
            out.append({
                "value": key, "n": len(items), "ok": ok, "rate": round(ok / len(items), 2), "sufficient": len(items) >= min_sample,
                "avg_reach_ratio": round(sum(reach) / len(reach), 2) if reach else None, "avg_sentiment_delta": round(sum(sent) / len(sent), 2) if sent else None,
            })
        out.sort(key=lambda g: (g["sufficient"], g["rate"], g["n"]), reverse=True)
        return out

    by_topic: dict[str, int] = defaultdict(int)
    for r in rows:
        by_topic[r.topic_slug] += 1
    return {
        "topic": topic, "sample_size": len(rows), "min_sample": min_sample, "sufficient": len(rows) >= min_sample,
        "formats": rank("format_slug"), "styles": rank("style_slug"), "strategies": rank("strategy"), "creatives": rank("creative_slug"), "by_topic": dict(by_topic),
    }
