from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORM

ImageType = Literal["foto_real", "ilustracion"]
ActorType = Literal["gobierno_municipal", "gobierno_estatal", "gobierno_federal", "partido", "funcionario_rol", "organismo", "medio", "organizacion", "otro"]
Outcome = Literal["funciono", "no_funciono"]


class GovLevelOut(ORM):
    id: int
    slug: str
    name: str
    ord: int


class GovLevelIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    ord: int = 0


class DocumentRef(ORM):
    id: int
    title: str
    issuer: str
    issued_at: datetime | None
    url: str | None
    file_key: str | None


class FactOut(ORM):
    id: int
    code: str
    statement: str
    value: float | None
    unit: str
    base: str
    period_label: str
    period_start: datetime | None
    period_end: datetime | None
    fact_date: datetime | None
    document_id: int | None
    document: DocumentRef | None = None
    gov_level_id: int | None
    gov_level_name: str | None = None
    topic_id: int | None
    topic_slug: str | None = None
    verified_by_id: int | None
    verified_by_name: str | None = None
    verified_at: datetime | None
    valid_until: datetime | None
    notes: str
    expired: bool = False
    source_label: str = ""
    created_at: datetime


class FactIn(BaseModel):
    statement: str = Field(min_length=5)
    value: float | None = None
    unit: str = ""
    base: str = "total"
    period_label: str = ""
    period_start: datetime | None = None
    period_end: datetime | None = None
    fact_date: datetime | None = None
    document_id: int | None = None
    gov_level_id: int | None = None
    topic_id: int | None = None
    valid_until: datetime | None = None
    notes: str = ""


class FactPatch(BaseModel):
    statement: str | None = None
    value: float | None = None
    unit: str | None = None
    base: str | None = None
    period_label: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    fact_date: datetime | None = None
    document_id: int | None = None
    gov_level_id: int | None = None
    topic_id: int | None = None
    valid_until: datetime | None = None
    notes: str | None = None


class ImportReport(BaseModel):
    created: int
    updated: int = 0
    errors: list[dict[str, Any]] = []


class DocumentOut(ORM):
    id: int
    title: str
    doc_type: str
    issuer: str
    issued_at: datetime | None
    url: str | None
    file_key: str | None
    gov_level_id: int | None
    topic_id: int | None
    pages: int
    status: str
    error: str
    chunk_count: int = 0
    fact_count: int = 0
    created_at: datetime


class ChunkOut(ORM):
    id: int
    ord: int
    page: int
    text: str


class DocumentDetail(DocumentOut):
    chunks: list[ChunkOut] = []


class DocumentPatch(BaseModel):
    title: str | None = None
    doc_type: str | None = None
    issuer: str | None = None
    issued_at: datetime | None = None
    url: str | None = None
    gov_level_id: int | None = None
    topic_id: int | None = None


class SearchHit(BaseModel):
    kind: Literal["fact", "chunk", "brief"]
    id: int
    title: str
    snippet: str
    score: float
    ref: dict[str, Any] = {}


class BriefOut(ORM):
    id: int
    topic_id: int | None
    title: str
    body_md: str
    updated_at: datetime


class BriefIn(BaseModel):
    topic_id: int | None = None
    title: str
    body_md: str = ""


class KeyMessageOut(ORM):
    id: int
    topic_id: int | None
    text: str
    tone_note: str
    priority: int
    active: bool


class KeyMessageIn(BaseModel):
    topic_id: int | None = None
    text: str
    tone_note: str = ""
    priority: int = Field(50, ge=1, le=100)
    active: bool = True


class ActorOut(ORM):
    id: int
    name: str
    aliases: list[str]
    actor_type: str
    gov_level_id: int | None
    is_own: bool
    notes: str


class ActorIn(BaseModel):
    name: str
    aliases: list[str] = []
    actor_type: ActorType = "otro"
    gov_level_id: int | None = None
    is_own: bool = False
    notes: str = ""


class CompetenceOut(ORM):
    id: int
    gov_level_id: int
    topic_id: int | None
    description: str
    legal_basis: str


class CompetenceIn(BaseModel):
    gov_level_id: int
    topic_id: int | None = None
    description: str
    legal_basis: str = ""


class ImageOut(ORM):
    id: int
    title: str
    file_key: str
    credit: str
    license: str
    taken_at: datetime | None
    tags: list[str]
    image_type: ImageType
    topic_id: int | None
    approved: bool
    meta: dict[str, Any]
    created_at: datetime


class ImagePatch(BaseModel):
    title: str | None = None
    credit: str | None = None
    license: str | None = None
    taken_at: datetime | None = None
    tags: list[str] | None = None
    image_type: ImageType | None = None
    topic_id: int | None = None
    approved: bool | None = None


class HistoryOut(ORM):
    id: int
    case_id: int | None
    piece_id: int | None
    topic_slug: str
    format_slug: str
    style_slug: str
    strategy: str
    creative_slug: str
    flow: str
    outcome: Outcome
    reach_ratio: float | None
    sentiment_delta: float | None
    summary: str
    notes: str
    created_at: datetime
