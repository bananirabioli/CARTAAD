from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORM

ClientType = Literal["gobierno", "partido", "candidatura"]
Role = Literal["analista", "aprobador", "legal", "diseno", "admin"]


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ViewAsIn(BaseModel):
    role: Role
    kb_owner: bool = False


class SelectClientIn(BaseModel):
    client_id: int


class ClientOut(ORM):
    id: int
    name: str
    slug: str
    client_type: ClientType
    default_tone: str
    default_style_slug: str | None
    restrictions: str


class ClientIn(BaseModel):
    name: str = Field(min_length=2)
    slug: str = Field(min_length=2, pattern=r"^[a-z0-9_-]+$")
    client_type: ClientType
    default_tone: str = ""
    default_style_slug: str | None = None
    restrictions: str = ""


class ClientPatch(BaseModel):
    name: str | None = None
    client_type: ClientType | None = None
    default_tone: str | None = None
    default_style_slug: str | None = None
    restrictions: str | None = None


class UserOut(ORM):
    id: int
    email: str
    name: str
    role: Role
    kb_owner: bool
    active: bool
    is_demo: bool


class UserAdminOut(UserOut):
    client_ids: list[int] = []


class UserIn(BaseModel):
    email: EmailStr
    name: str
    role: Role
    kb_owner: bool = False
    password: str = Field(min_length=8)
    client_ids: list[int] = []


class UserPatch(BaseModel):
    name: str | None = None
    role: Role | None = None
    kb_owner: bool | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8)
    client_ids: list[int] | None = None


class MeOut(BaseModel):
    user: UserOut
    client: ClientOut
    clients: list[ClientOut]
    permissions: list[str]
    demo_mode: bool
    llm_provider: str
    restriction: dict[str, Any] | None = None
    reminders: list[dict[str, Any]] = []


class TopicOut(ORM):
    id: int
    slug: str
    name: str
    keywords: list[str]
    active: bool


class TopicIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    keywords: list[str] = []
    active: bool = True


class TopicPatch(BaseModel):
    name: str | None = None
    keywords: list[str] | None = None
    active: bool | None = None


class SettingsOut(BaseModel):
    settings: dict[str, Any]


class SettingsPatch(BaseModel):
    patch: dict[str, Any]


class HardRuleOut(BaseModel):
    id: str
    title: str
    description: str


class AuditQuery(BaseModel):
    entity_type: str | None = None
    entity_id: str | None = None
    action: str | None = None
    since: datetime | None = None
