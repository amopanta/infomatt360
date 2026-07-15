from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.time import utc_now


def new_uuid() -> str:
    return str(uuid4())


class UserProjectAssignment(Base):
    __tablename__ = "user_project_assignments"
    __table_args__ = (
        Index("ix_assignments_user_project_status", "user_id", "project_id", "status"),
        Index("ix_assignments_project_status_role", "project_id", "status", "role_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    role_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class UserOrganizationAssignment(Base):
    """Asignacion de un rol a un usuario a nivel de Organizacion completa.

    Distinta de UserProjectAssignment (rol por un unico proyecto): un rol
    asignado aqui aplica a todos los proyectos de la organizacion, existentes
    y futuros, sin necesidad de asignaciones individuales por proyecto (ver
    docs/101 -- jerarquia de roles / "Administrador nacional").
    """

    __tablename__ = "user_organization_assignments"
    __table_args__ = (
        Index("ix_org_assignments_user_org_status", "user_id", "organization_id", "status"),
        Index("ix_org_assignments_org_status_role", "organization_id", "status", "role_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    role_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
