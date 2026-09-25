import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

VeilleType = Literal[
    "technologique", "concurrentielle", "reglementaire", "securite", "marche", "autre"
]
Role = Literal["viewer", "editor", "admin"]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]
# Plafond haut : argon2 sur un mot de passe de plusieurs Mo est un vecteur de DoS.
Password = Annotated[str, StringConstraints(min_length=12, max_length=256)]
LoginPassword = Annotated[str, StringConstraints(min_length=1, max_length=256)]
TotpCode = Annotated[str, StringConstraints(pattern=r"^\d{6}$")]
HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
Url = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=2048)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth -------------------------------------------------------------------------------


class LoginIn(Strict):
    email: Email
    password: LoginPassword


class LoginOut(Out):
    mfa_enrolled: bool


class MfaCodeIn(Strict):
    code: TotpCode


class MfaEnrollOut(Out):
    otpauth_uri: str
    secret: str


class MeOut(Out):
    id: uuid.UUID
    email: str
    role: Role


class PasswordChangeIn(Strict):
    current_password: LoginPassword
    new_password: Password


# --- Thèmes / groupes / sources -----------------------------------------------------------


class ThemeIn(Strict):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    color: HexColor = "#4f6bed"


class ThemePatch(Strict):
    name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)] | None
    ) = None
    color: HexColor | None = None


class ThemeOut(Out):
    id: uuid.UUID
    name: str
    color: str


class GroupIn(Strict):
    name: Name
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ""
    veille_type: VeilleType
    theme_id: uuid.UUID
    enabled: bool = True


class GroupPatch(Strict):
    name: Name | None = None
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None
    ) = None
    veille_type: VeilleType | None = None
    theme_id: uuid.UUID | None = None
    enabled: bool | None = None


class SourceIn(Strict):
    name: Name
    url: Url
    enabled: bool = True


class SourcePatch(Strict):
    name: Name | None = None
    url: Url | None = None
    enabled: bool | None = None


class SourceOut(Out):
    id: uuid.UUID
    group_id: uuid.UUID
    name: str
    url: str
    enabled: bool
    last_fetch_at: datetime | None
    last_status: Literal["ok", "error"] | None
    last_error: str | None
    consecutive_failures: int


class GroupOut(Out):
    id: uuid.UUID
    name: str
    description: str
    veille_type: VeilleType
    theme: ThemeOut
    enabled: bool
    source_count: int
    failing_source_count: int
    created_at: datetime
    updated_at: datetime


class GroupDetailOut(GroupOut):
    sources: list[SourceOut]


# --- Articles ---------------------------------------------------------------------------


class ArticleSourceRef(Out):
    id: uuid.UUID
    name: str


class ArticleGroupRef(Out):
    id: uuid.UUID
    name: str
    veille_type: VeilleType


class ArticleOut(Out):
    id: int
    link: str
    title: str
    snippet: str
    published_at: datetime
    source: ArticleSourceRef
    group: ArticleGroupRef
    theme: ThemeOut


class ArticlePage(Out):
    items: list[ArticleOut]
    next_cursor: str | None


# --- Utilisateurs / audit -----------------------------------------------------------------


class UserIn(Strict):
    email: Email
    password: Password
    role: Role = "viewer"


class UserPatch(Strict):
    role: Role | None = None
    is_active: bool | None = None


class UserOut(Out):
    id: uuid.UUID
    email: str
    role: Role
    is_active: bool
    totp_confirmed: bool
    locked_until: datetime | None
    created_at: datetime


class AuditOut(Out):
    id: int
    at: datetime
    actor_kind: str
    actor_user_id: uuid.UUID | None
    action: str
    target: str | None
    ip: str | None


# --- Interne (n8n) ----------------------------------------------------------------------


class InternalSourceOut(Out):
    id: uuid.UUID
    url: str


class IngestArticleIn(BaseModel):
    # Volontairement permissif : un article mal formé est écarté individuellement
    # au lieu de faire échouer tout le lot d'une source.
    model_config = ConfigDict(extra="ignore")

    link: Annotated[str, StringConstraints(max_length=4096)] | None = None
    title: Annotated[str, StringConstraints(max_length=4096)] | None = None
    snippet: Annotated[str, StringConstraints(max_length=20000)] | None = None
    published_at: Annotated[str, StringConstraints(max_length=64)] | None = None


class IngestIn(Strict):
    source_id: uuid.UUID
    ok: bool
    error: Annotated[str, StringConstraints(max_length=2000)] | None = None
    articles: list[IngestArticleIn] = Field(default_factory=list, max_length=500)


class IngestOut(Out):
    inserted: int
    rejected: int
