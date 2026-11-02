"""Manual capture: screenshot + copy → OCR/vision step → optional name blurring → Post (+ pipeline)."""

import re
import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.adapters.sources import RawPost, RawSnapshot
from app.ai.runner import StepMeta, run_step
from app.config import single_analysis
from app.db import utcnow
from app.errors import AppError
from app.models.core import Client, User
from app.models.monitoring import MonitoredSource, Post
from app.services import audit
from app.services.images import blur_names, normalize_image
from app.services.ingest import store_post
from app.storage import client_key, get_storage


_HANDLE = re.compile(r"(?<![\w.])@[\w.]{2,30}")
PENDING_TEXT = "(captura en análisis)"  # replaced by the text analyze_capture reads from the image


def _redact(text: str, names: list[str]) -> str:
    for name in sorted(set(names), key=len, reverse=True):
        if name.strip():
            text = re.sub(re.escape(name), "[nombre]", text, flags=re.IGNORECASE)
    return text


def resolve_source(db: Session, client_id: int, source_id: int | None, source_name: str | None, network: str, source_type: str | None) -> MonitoredSource | None:
    if source_id:
        src = db.get(MonitoredSource, source_id)
        if not src or src.client_id != client_id:
            raise AppError(404, "not_found")
        return src
    name = (source_name or "").strip()
    if not name:
        return None
    src = db.scalar(select(MonitoredSource).where(MonitoredSource.client_id == client_id, or_(MonitoredSource.name.ilike(name), MonitoredSource.handle.ilike(name))))
    if src:
        return src
    src = MonitoredSource(
        client_id=client_id, name=name, network=network, source_type=source_type or "pagina_ciudadana", priority="media", active=False, adapter="manual",
        notes="Creada desde una captura manual; revísala y actívala si se debe monitorear.",
    )
    db.add(src)
    db.flush()
    return src


def capture_manual(
    db: Session,
    client: Client,
    user: User | None,
    *,
    text: str,
    network: str,
    image: bytes | None = None,
    url: str | None = None,
    source_id: int | None = None,
    source_name: str | None = None,
    source_type: str | None = None,
    blur: bool = False,
    published_at: datetime | None = None,
    likes: int | None = None,
    comments: int | None = None,
    shares: int | None = None,
    comments_text: list[str] | None = None,
) -> Post:
    image_key = None
    image_text = visual_context = ""
    detected: list[str] = []
    meta: dict[str, str] = {}
    if image:
        data, mime = normalize_image(image)
        if not single_analysis():  # with a real provider analyze_capture reads the image later, in the same call that classifies
            ocr, _ = run_step(db, "ocr_vision", {"network": network, "user_text": text}, StepMeta(client_id=client.id, user_id=user.id if user else None), image=(data, mime))
            image_text, visual_context, detected = ocr.extracted_text, ocr.visual_context, ocr.detected_names  # type: ignore[attr-defined]
        if blur and single_analysis():  # the model reads the original; the visible copy is blurred
            meta["analysis_image_key"] = get_storage().save(client_key(client.id, "captures", f"{uuid.uuid4().hex}-orig.png"), data, "image/png")
        if blur:
            data = blur_names(data)
        image_key = get_storage().save(client_key(client.id, "captures", f"{uuid.uuid4().hex}.png"), data, "image/png")
    body = (text or "").strip() or image_text.strip()
    if not body and image_key and single_analysis():
        body = f"{PENDING_TEXT} {uuid.uuid4().hex[:8]}"  # unique so two image-only captures are not merged as duplicates
    if not body:
        raise AppError(422, "invalid_value", detail="la captura necesita copy o una imagen legible")
    if blur:
        names = [*detected, *_HANDLE.findall(body), *_HANDLE.findall(image_text)]
        body, image_text = _redact(body, names), _redact(image_text, names)
    source = resolve_source(db, client.id, source_id, source_name, network, source_type)
    snaps = []
    if any(v is not None for v in (likes, comments, shares)):
        snaps.append(RawSnapshot(utcnow(), int(likes or 0), int(comments or 0), int(shares or 0)))
    raw = RawPost(text=body, published_at=published_at or utcnow(), network=network, url=url, snapshots=snaps, comments=[{"text": c} for c in comments_text or []], meta=meta)
    post, created = store_post(
        db, client, raw, source=source, origin="manual", user=user, image_key=image_key, image_text=image_text, visual_context=visual_context, names_blurred=blur,
    )
    audit.record(db, action="post.capture_manual" if created else "post.capture_duplicate", entity_type="post", entity_id=post.id, client_id=client.id, user=user, note=f"{network} · blur={blur}")
    return post
