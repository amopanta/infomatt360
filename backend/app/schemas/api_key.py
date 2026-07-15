from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=180)
    permissions: list[str] = Field(default_factory=list)
    rate_limit_profile: str = Field(default="standard", pattern="^(standard|high_volume|trusted_sync)$")
    # Opcional -- ver auditoria tecnica de julio 2026, hallazgo S-004. Sin
    # expiracion (None) se comporta igual que antes de este cambio.
    expires_at: datetime | None = None


class ApiKeyRead(BaseModel):
    id: str
    project_id: str
    name: str
    key_id: str
    permissions: list[str]
    rate_limit_profile: str = "standard"
    # "active" | "revoked" | "expired". "expired" se calcula al leer (no se
    # persiste): status en la base sigue en "active" hasta que alguien la
    # revoque explicitamente, para no gastar una escritura por vencimiento.
    status: str
    created_by: str | None = None
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None


class ApiKeyCreateResponse(ApiKeyRead):
    api_key: str


class ApiKeyAuthContext(BaseModel):
    project_id: str
    key_id: str
    permissions: list[str]


class ApiKeyCheckResponse(BaseModel):
    status: str = "ok"
    project_id: str
    key_id: str
    permissions: list[str]
