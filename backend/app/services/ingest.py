"""Ingest captured posts: dedupe, sanitize comments (HR-03), snapshots, embeddings, alert level, pipeline."""

import hashlib
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.sources import AdapterNotConfigured, RawPost, adapter_for
from app.ai.embeddings import embed
from app.db import utcnow
from app.guardrails.hard_rules import strip_commenter_identity
from app.models.core import Client, Topic, User
from app.models.monitoring import Comment, MonitoredSource, Post
from app.services import audit, pipeline
from app.services.alert import add_snapshot, apply_alert, refresh_source_baseline
from app.services.client_settings import get_client_settings
from app.textnorm import normalize


def content_hash(text: str, network: str, source_id: int | None) -> str:
    return hashlib.sha256(f"{normalize(text)}|{network}|{source_id or 'manual'}".encode()).hexdigest()


def find_duplicate(db: Session, client_id: int, text: str, network: str, source_id: int | None) -> Post | None:
    h = content_hash(text, network, source_id)
    found = db.scalar(select(Post).where(Post.client_id == client_id, Post.content_hash == h))
    if found or source_id is None:
        return found
    # A manual capture of an automatically captured post (or vice versa) is the same publication.
    return db.scalar(select(Post).where(Post.client_id == client_id, Post.content_hash == content_hash(text, network, None)))


def add_comments(db: Session, post: Post, raw_comments: list[dict[str, Any]]) -> int:
    added = 0
    for raw in raw_comments:
        clean, _dropped = strip_commenter_identity(raw)
        text = (clean.get("text") or "").strip()
        if text:
            db.add(Comment(post_id=post.id, text=text[:1000], stance=clean.get("stance"), theme=clean.get("theme")))
            added += 1
    return added


def store_post(
    db: Session,
    client: Client,
    raw: RawPost,
    *,
    source: MonitoredSource | None,
    origin: str = "automatica",
    user: User | None = None,
    image_key: str | None = None,
    image_text: str = "",
    visual_context: str = "",
    names_blurred: bool = False,
    run_pipeline: bool = True,
    is_history: bool = False,
) -> tuple[Post, bool]:
    """Returns (post, created). Duplicates get their snapshots and comments merged instead."""
    existing = find_duplicate(db, client.id, raw.text, raw.network, source.id if source else None)
    if existing:
        for snap in raw.snapshots:
            add_snapshot(db, existing, snap.likes, snap.comments, snap.shares, snap.taken_at)
        add_comments(db, existing, raw.comments)
        apply_alert(existing, get_client_settings(client))
        return existing, False
    post = Post(
        client_id=client.id, source_id=source.id if source else None, origin=origin, network=raw.network, text=raw.text, url=raw.url,
        published_at=raw.published_at, captured_by_id=user.id if user else None, content_hash=content_hash(raw.text, raw.network, source.id if source else None),
        external_id=raw.external_id, image_key=image_key, image_text=image_text, visual_context=visual_context, names_blurred=names_blurred,
        embedding=embed(f"{raw.text} {image_text}"), meta=raw.meta, is_history=is_history,
    )
    if source is not None:
        post.source = source
    db.add(post)
    db.flush()
    for snap in raw.snapshots:
        add_snapshot(db, post, snap.likes, snap.comments, snap.shares, snap.taken_at)
    add_comments(db, post, raw.comments)
    db.flush()
    apply_alert(post, get_client_settings(client))
    if run_pipeline and not is_history:
        pipeline.process_post(db, post, user)
    return post, True


def run_source(db: Session, source: MonitoredSource, now: datetime | None = None, user: User | None = None) -> dict[str, Any]:
    now = now or utcnow()
    client = db.get(Client, source.client_id)
    topics = [t.name.lower() for t in db.scalars(select(Topic).where(Topic.client_id == client.id, Topic.active.is_(True)))]
    adapter = adapter_for(source, now=now, topics=topics)
    created = updated = 0
    try:
        recent = list(db.scalars(select(Post).where(Post.source_id == source.id, Post.published_at >= now - timedelta(hours=72))))
        for post_id, snap in adapter.fetch_snapshots(source, recent).items():
            post = db.get(Post, post_id)
            add_snapshot(db, post, snap.likes, snap.comments, snap.shares, snap.taken_at)
            apply_alert(post, get_client_settings(client), now)
            updated += 1
        for raw in adapter.fetch_new_posts(source, source.last_checked_at):
            _, was_created = store_post(db, client, raw, source=source, user=user)
            created += int(was_created)
        status = "ok"
    except AdapterNotConfigured as exc:
        status = str(exc)
    source.last_checked_at = now
    refresh_source_baseline(db, source, now)
    audit.record(db, action="source.check", entity_type="source", entity_id=source.id, client_id=source.client_id, user=user, note=f"{adapter.name}: {created} nuevas, {updated} actualizadas · {status}")
    return {"source_id": source.id, "created": created, "updated": updated, "status": status}


def due_sources(db: Session, now: datetime | None = None) -> list[MonitoredSource]:
    now = now or utcnow()
    rows = db.scalars(select(MonitoredSource).where(MonitoredSource.active.is_(True)))
    return [s for s in rows if s.last_checked_at is None or s.last_checked_at + timedelta(minutes=s.check_frequency_minutes) <= now]
