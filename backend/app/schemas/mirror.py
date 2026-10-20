from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SUPPORTED_MIRROR_ENGINES = ("postgres", "sqlite", "mysql", "mssql")


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
    engine: Literal["postgres", "sqlite", "mysql", "mssql"]
    # Postgres / MySQL / MSSQL
    host: str | None = None
    port: int | None = None
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
    schedule_mode: Literal["full_mirror", "insert_only", "incremental"] = "full_mirror"
    # "project": el proyecto completo (participantes, asignaciones, registros
    # y una tabla por formulario, docs/146); la pantalla lo propone por
    # defecto. "records": el espejo clave-valor original (docs/102); sigue
    # siendo el valor por defecto de la API para no cambiar el contrato.
    scope: Literal["project", "records"] = "records"
    status: str = "active"


class MirrorPlanRead(BaseModel):
    id: str
    target_id: str
    name: str
    scope: str = "records"
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
    summary: dict | None = None
