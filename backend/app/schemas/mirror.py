from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SUPPORTED_MIRROR_ENGINES = ("postgres", "sqlite")


class MirrorTargetConnect(BaseModel):
    """Datos de conexion a la base de datos externa que sera el espejo.

    Los campos especificos de cada motor son opcionales a nivel de schema
    porque varian por motor -- mirror_service valida cuales son requeridos
    segun `engine` (ver mirror_service._build_url). Nunca se persisten en
    texto plano: se cifran con app.core.security.encrypt_text antes de
    guardarse en MirrorTarget.conn_json (ver docs/102).
    """

    project_id: str
    name: str
    engine: Literal["postgres", "sqlite"]
    # Postgres
    host: str | None = None
    port: int = 5432
    database: str | None = None
    username: str | None = None
    password: str | None = None
    # SQLite
    file_path: str | None = None


class MirrorTargetRead(BaseModel):
    """Nunca incluye credenciales -- ver MirrorTargetConnect."""

    id: str
    project_id: str
    name: str
    engine: str
    status: str


class MirrorTargetTestConnectionResult(BaseModel):
    success: bool
    message: str


class MirrorPlanCreate(BaseModel):
    target_id: str
    name: str
    schedule_mode: Literal["full_mirror", "insert_only"] = "full_mirror"
    status: str = "active"


class MirrorPlanRead(BaseModel):
    id: str
    target_id: str
    name: str
    schedule_mode: str
    status: str
    last_result: str | None = None


class MirrorRunRead(BaseModel):
    id: str
    plan_id: str
    status: str
    records_synced: int
    values_synced: int
    triggered_by: str | None = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
