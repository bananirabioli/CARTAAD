from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORM

Network = Literal["facebook", "instagram", "x", "tiktok", "otra"]
SourceType = Literal["medio", "influencer", "pagina_ciudadana", "actor_politico"]
Priority = Literal["alta", "media", "baja"]
AccountType = Literal["propia", "aliada", "voceria"]


class SourceOut(ORM):
    id: int
    name: str
    network: Network
    handle: str
    url: str | None
    source_type: SourceType
    priority: Priority
    active: bool
    check_frequency_minutes: int
    adapter: str
    baseline_per_hour: float | None
    baseline_since: datetime | None
    last_checked_at: datetime | None
    notes: str
    created_at: datetime
    baseline_ok: bool = False
    posts_count: int = 0


class SourceIn(BaseModel):
    name: str = Field(min_length=2)
    network: Network
    handle: str = ""
    url: str | None = None
    source_type: SourceType
    priority: Priority = "media"
    active: bool = True
    check_frequency_minutes: int = Field(60, ge=5, le=1440)
    adapter: Literal["mock", "file", "social_listening", "manual"] = "mock"
    notes: str = ""


class SourcePatch(BaseModel):
    name: str | None = None
    network: Network | None = None
    handle: str | None = None
    url: str | None = None
    source_type: SourceType | None = None
    priority: Priority | None = None
    active: bool | None = None
    check_frequency_minutes: int | None = Field(None, ge=5, le=1440)
    adapter: Literal["mock", "file", "social_listening", "manual"] | None = None
    notes: str | None = None


class SnapshotOut(ORM):
    id: int
    taken_at: datetime
    likes: int
    comments: int
    shares: int


class SnapshotIn(BaseModel):
    likes: int = Field(ge=0)
    comments: int = Field(ge=0)
    shares: int = Field(ge=0)
    taken_at: datetime | None = None


class CommentOut(ORM):
    id: int
    text: str
    stance: str | None
    theme: str | None


class PostOut(ORM):
    id: int
    source_id: int | None
    source_name: str | None = None
    source_type: str | None = None
    origin: str
    network: str
    text: str
    image_key: str | None
    image_text: str
    visual_context: str
    names_blurred: bool
    url: str | None
    published_at: datetime
    captured_at: datetime
    velocity: float | None
    alert_ratio: float | None
    alert_level: str | None
    total_interactions: int
    case_id: int | None = None
    case_code: str | None = None


class PostDetail(PostOut):
    snapshots: list[SnapshotOut] = []
    comments: list[CommentOut] = []
    baseline_per_hour: float | None = None


class CheckResult(BaseModel):
    source_id: int
    created: int
    updated: int
    status: str


class ImportReport(BaseModel):
    created: int
    updated: int = 0
    errors: list[dict[str, Any]] = []


class WebhookIn(BaseModel):
    channel: Literal["whatsapp", "telegram", "otro"] = "otro"
    client_slug: str
    text: str = ""
    url: str | None = None
    network: Network = "otra"
    image_base64: str | None = None
    extra: dict[str, Any] = {}


class AccountOut(ORM):
    id: int
    network: str
    handle: str
    display_name: str
    account_type: AccountType
    format_slug: str
    default_style_slug: str | None
    registered: bool
    verified: bool
    verified_at: datetime | None
    active: bool
    notes: str


class AccountIn(BaseModel):
    network: Network
    handle: str
    display_name: str
    account_type: AccountType
    format_slug: str
    default_style_slug: str | None = None
    registered: bool = True
    active: bool = True
    notes: str = ""


class AccountPatch(BaseModel):
    display_name: str | None = None
    account_type: AccountType | None = None
    format_slug: str | None = None
    default_style_slug: str | None = None
    registered: bool | None = None
    active: bool | None = None
    notes: str | None = None
