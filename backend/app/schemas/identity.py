"""Esquemas de identidad, proyectos, roles y permisos.

Estos modelos Pydantic documentan los contratos iniciales de API.
Mas adelante se conectaran con modelos SQLAlchemy y migraciones Alembic.
"""

from enum import Enum
from pydantic import BaseModel, EmailStr, Field


class UserStatus(str, Enum):
    """Estados operativos de usuario."""

    active = "active"
    suspended = "suspended"
    blocked = "blocked"


class ProjectStatus(str, Enum):
    """Estados operativos de proyecto."""

    active = "active"
    suspended = "suspended"
    closed = "closed"


class Channel(str, Enum):
    """Canales donde puede operar un usuario unico."""

    web = "web"
    android = "android"
    desktop = "desktop"


class UserCreate(BaseModel):
    """Datos requeridos para crear un usuario.

    La misma identidad debe servir para web, Android y escritorio.
    """

    full_name: str = Field(..., min_length=3)
    document_id: str = Field(..., min_length=5)
    email: EmailStr
    phone: str | None = None
    status: UserStatus = UserStatus.active
    allowed_channels: list[Channel] = [Channel.web, Channel.android, Channel.desktop]


class UserRead(UserCreate):
    """Respuesta publica de usuario sin exponer secretos."""

    id: str


class ProjectCreate(BaseModel):
    """Datos para crear un proyecto operativo."""

    name: str = Field(..., min_length=3)
    description: str | None = None
    status: ProjectStatus = ProjectStatus.active


class ProjectRead(ProjectCreate):
    """Respuesta publica de proyecto."""

    id: str


class RoleCreate(BaseModel):
    """Rol configurable por proyecto."""

    name: str = Field(..., min_length=3)
    description: str | None = None
    permissions: list[str] = []


class RoleRead(RoleCreate):
    id: str
