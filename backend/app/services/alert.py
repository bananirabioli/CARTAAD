"""Alert level (section 4), computed with rules from interaction snapshots — never by the LLM.

velocity = (likes + comments + shares gained in the window) / hours
ratio    = velocity / baseline of that page
level    = bajo < medio (1.5x) ≤ alto (3x) ≤ critico (6x), thresholds configurable per client.
If the page has less than `baseline_min_days` of history the level is `sin_linea_base`.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.monitoring import InteractionSnapshot, MonitoredSource, Post
from app.services.client_settings import ClientSettings

ALERT_LEVELS = ("bajo", "medio", "alto", "critico")
NO_BASELINE = "sin_linea_base"
BASELINE_LOOKBACK_DAYS = 30
MIN_HOURS = 0.25


@dataclass
class AlertResult:
    level: str
    velocity: float
    ratio: float | None
    baseline: float | None
    window_hours: float
    gained: int


def level_for_ratio(ratio: float, settings: ClientSettings) -> str:
    th = settings.alert_thresholds
    if ratio >= th.critico:
        return "critico"
    if ratio >= th.alto:
        return "alto"
    if ratio >= th.medio:
        return "medio"
    return "bajo"


def velocity_for(post: Post, window_hours: float, now: datetime | None = None) -> tuple[float, int, float]:
    """(velocity per hour, interactions gained, hours) over the last `window_hours` of snapshots."""
    snaps = sorted(post.snapshots, key=lambda s: s.taken_at)
    if not snaps:
        return 0.0, 0, 0.0
    latest = snaps[-1]
    start_time = latest.taken_at - timedelta(hours=window_hours)
    earlier = [s for s in snaps if s.taken_at <= start_time]
    if earlier:
        base_total, base_time = earlier[-1].total, earlier[-1].taken_at
    else:  # post younger than the window: count from publication with zero interactions
        base_total, base_time = 0, min(post.published_at, snaps[0].taken_at)
    hours = max(MIN_HOURS, (latest.taken_at - base_time).total_seconds() / 3600)
    gained = max(0, latest.total - base_total)
    return gained / hours, gained, hours


def compute_baseline(db: Session, source: MonitoredSource, now: datetime | None = None) -> tuple[float | None, datetime | None]:
    """Average interactions per hour across all snapshot intervals of the page in the last 30 days."""
    now = now or utcnow()
    since = now - timedelta(days=BASELINE_LOOKBACK_DAYS)
    posts = db.scalars(select(Post).where(Post.source_id == source.id, Post.published_at >= since))
    gained, hours, first_seen = 0.0, 0.0, None
    for post in posts:
        snaps = sorted(post.snapshots, key=lambda s: s.taken_at)
        prev_total, prev_time = 0, post.published_at
        for snap in snaps:
            dt = (snap.taken_at - prev_time).total_seconds() / 3600
            if dt > 0:
                gained += max(0, snap.total - prev_total)
                hours += dt
            prev_total, prev_time = snap.total, snap.taken_at
        if snaps and (first_seen is None or post.published_at < first_seen):
            first_seen = post.published_at
    if hours <= 0:
        return None, first_seen
    return gained / hours, first_seen


def refresh_source_baseline(db: Session, source: MonitoredSource, now: datetime | None = None) -> None:
    baseline, since = compute_baseline(db, source, now)
    source.baseline_per_hour = round(baseline, 3) if baseline is not None else None
    source.baseline_since = since
    source.baseline_computed_at = now or utcnow()


def baseline_sufficient(source: MonitoredSource | None, settings: ClientSettings, now: datetime | None = None) -> bool:
    if source is None or source.baseline_per_hour is None or source.baseline_since is None:
        return False
    return (now or utcnow()) - source.baseline_since >= timedelta(days=settings.baseline_min_days)


def compute_alert(post: Post, settings: ClientSettings, now: datetime | None = None) -> AlertResult:
    velocity, gained, hours = velocity_for(post, settings.alert_window_hours, now)
    source = post.source
    if not baseline_sufficient(source, settings, now) or not source or not source.baseline_per_hour:
        return AlertResult(NO_BASELINE, round(velocity, 2), None, source.baseline_per_hour if source else None, round(hours, 2), gained)
    ratio = velocity / source.baseline_per_hour
    return AlertResult(level_for_ratio(ratio, settings), round(velocity, 2), round(ratio, 2), source.baseline_per_hour, round(hours, 2), gained)


def apply_alert(post: Post, settings: ClientSettings, now: datetime | None = None) -> AlertResult:
    result = compute_alert(post, settings, now)
    post.velocity, post.alert_ratio, post.alert_level = result.velocity, result.ratio, result.level
    snaps = post.snapshots
    post.total_interactions = max((s.total for s in snaps), default=0)
    post.alert_computed_at = now or utcnow()
    return result


def add_snapshot(db: Session, post: Post, likes: int, comments: int, shares: int, taken_at: datetime | None = None) -> InteractionSnapshot:
    snap = InteractionSnapshot(post_id=post.id, likes=likes, comments=comments, shares=shares, taken_at=taken_at or utcnow())
    db.add(snap)
    post.snapshots.append(snap)
    return snap
