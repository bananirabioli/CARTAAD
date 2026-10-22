"""SourceAdapter: where automatic captures come from.

* MockListeningAdapter — synthetic, deterministic posts and snapshots (default, offline).
* FileImportAdapter — CSV / JSON exports from any listening tool.
* SocialListeningAdapter — documented stub to plug a social-listening API later. Not active.

There is no scraping and no publishing here: adapters only read page-level data and never commenter identities (HR-03).
"""

import csv
import hashlib
import io
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from app.ai.mock.fixtures import mock_json
from app.db import utcnow
from app.models.monitoring import MonitoredSource, Post


@dataclass
class RawSnapshot:
    taken_at: datetime
    likes: int
    comments: int
    shares: int


@dataclass
class RawPost:
    text: str
    published_at: datetime
    network: str
    external_id: str | None = None
    url: str | None = None
    snapshots: list[RawSnapshot] = field(default_factory=list)
    comments: list[dict[str, Any]] = field(default_factory=list)  # raw payloads; identities are stripped on ingest
    meta: dict[str, Any] = field(default_factory=dict)


class AdapterNotConfigured(Exception):
    pass


class SourceAdapter(Protocol):
    name: str

    def fetch_new_posts(self, source: MonitoredSource, since: datetime | None) -> list[RawPost]: ...

    def fetch_snapshots(self, source: MonitoredSource, posts: list[Post]) -> dict[int, RawSnapshot]: ...


class MockListeningAdapter:
    """Generates at most one post per run and grows the interactions of recent posts. Deterministic per hour bucket."""

    name = "mock"

    def __init__(self, now: datetime | None = None, topics: list[str] | None = None):
        self.now = now or utcnow()
        self.topics = topics or ["baches", "seguridad", "agua", "obra pública"]

    def _rng(self, source: MonitoredSource, salt: str) -> random.Random:
        bucket = self.now.strftime("%Y%m%d%H")
        seed = int(hashlib.sha256(f"{source.id}:{bucket}:{salt}".encode()).hexdigest()[:12], 16)
        return random.Random(seed)

    def fetch_new_posts(self, source: MonitoredSource, since: datetime | None) -> list[RawPost]:
        rng = self._rng(source, "posts")
        chance = {"alta": 0.7, "media": 0.45, "baja": 0.25}.get(source.priority, 0.4)
        if rng.random() > chance:
            return []
        data = mock_json("listening")
        templates = data.get("templates", {}).get(source.source_type) or ["Publicación sobre {topic} en {place}."]
        text = rng.choice(templates).format(topic=rng.choice(self.topics), place=rng.choice(data.get("places", ["la ciudad"])))
        published = self.now - timedelta(minutes=rng.randint(5, 50))
        base = max(1.0, source.baseline_per_hour or 5.0)
        growth = base * rng.choice([0.6, 0.9, 1.2, 2.0, 3.5, 7.0])
        hours = max(0.1, (self.now - published).total_seconds() / 3600)
        total = int(growth * hours)
        snap = RawSnapshot(self.now, likes=int(total * 0.7), comments=int(total * 0.2), shares=total - int(total * 0.7) - int(total * 0.2))
        comments = [{"text": rng.choice(data.get("comments", ["Así es"])), "author": "omitido-en-ingesta"} for _ in range(rng.randint(0, 3))]
        ext = f"mock-{source.id}-{self.now:%Y%m%d%H}"
        return [RawPost(text=text, published_at=published, network=source.network, external_id=ext, snapshots=[snap], comments=comments, meta={"growth_per_hour": growth})]

    def fetch_snapshots(self, source: MonitoredSource, posts: list[Post]) -> dict[int, RawSnapshot]:
        out: dict[int, RawSnapshot] = {}
        for post in posts:
            if not post.snapshots or (self.now - post.published_at) > timedelta(hours=72):
                continue
            last = post.snapshots[-1]
            if last.taken_at >= self.now:
                continue
            growth = float((post.meta or {}).get("growth_per_hour") or (source.baseline_per_hour or 5.0))
            hours = (self.now - last.taken_at).total_seconds() / 3600
            age = (self.now - post.published_at).total_seconds() / 3600
            decay = 1.0 if age < 12 else 0.4 if age < 36 else 0.1
            gained = int(growth * hours * decay)
            out[post.id] = RawSnapshot(self.now, last.likes + int(gained * 0.7), last.comments + int(gained * 0.2), last.shares + gained - int(gained * 0.7) - int(gained * 0.2))
        return out


class FileImportAdapter:
    """CSV or JSON rows: source (handle or name), network, text, published_at, url, likes, comments, shares, comments_text ("|" separated)."""

    name = "file"

    def __init__(self, data: bytes, filename: str = ""):
        self.rows = self._parse(data, filename)

    @staticmethod
    def _parse(data: bytes, filename: str) -> list[dict[str, Any]]:
        text = data.decode("utf-8-sig")
        if filename.lower().endswith(".json") or text.lstrip().startswith(("[", "{")):
            parsed = json.loads(text)
            return parsed if isinstance(parsed, list) else parsed.get("posts", [])
        return list(csv.DictReader(io.StringIO(text)))

    def rows_for(self, source: MonitoredSource) -> list[dict[str, Any]]:
        keys = {source.handle.lower(), source.name.lower()}
        return [r for r in self.rows if str(r.get("source", "")).lower() in keys]

    @staticmethod
    def to_raw(row: dict[str, Any], default_network: str) -> RawPost:
        published = datetime.fromisoformat(str(row.get("published_at"))) if row.get("published_at") else utcnow()
        snap = RawSnapshot(utcnow(), int(row.get("likes") or 0), int(row.get("comments") or 0), int(row.get("shares") or 0))
        comments_text = row.get("comments_text") or []
        if isinstance(comments_text, str):
            comments_text = [c for c in comments_text.split("|") if c.strip()]
        return RawPost(
            text=str(row.get("text") or ""), published_at=published, network=str(row.get("network") or default_network), url=row.get("url") or None,
            external_id=str(row.get("id")) if row.get("id") else None, snapshots=[snap], comments=[{"text": c} for c in comments_text],
        )

    def fetch_new_posts(self, source: MonitoredSource, since: datetime | None) -> list[RawPost]:
        return [self.to_raw(r, source.network) for r in self.rows_for(source)]

    def fetch_snapshots(self, source: MonitoredSource, posts: list[Post]) -> dict[int, RawSnapshot]:
        return {}


class SocialListeningAdapter:
    """Stub for a commercial social-listening API (configure SOCIAL_LISTENING_URL and SOCIAL_LISTENING_TOKEN).

    Contract to implement:
      * fetch_new_posts: GET {url}/pages/{source.handle}/posts?since=ISO → page posts with public counters.
      * fetch_snapshots: GET {url}/posts/{external_id}/metrics → likes / comments / shares.
    Only page-level data. Never request or store commenter identities (HR-03). No publishing endpoints (HR-02).
    """

    name = "social_listening"

    def fetch_new_posts(self, source: MonitoredSource, since: datetime | None) -> list[RawPost]:
        raise AdapterNotConfigured("SocialListeningAdapter no está configurado (ver docstring).")

    def fetch_snapshots(self, source: MonitoredSource, posts: list[Post]) -> dict[int, RawSnapshot]:
        raise AdapterNotConfigured("SocialListeningAdapter no está configurado (ver docstring).")


def adapter_for(source: MonitoredSource, now: datetime | None = None, topics: list[str] | None = None) -> SourceAdapter:
    if source.adapter == "social_listening":
        return SocialListeningAdapter()
    return MockListeningAdapter(now=now, topics=topics)
