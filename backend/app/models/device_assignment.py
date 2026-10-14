"""Registro formal de dispositivos asignados a usuarios por proyecto.

A diferencia de device_fingerprint (campo suelto en enrollment/identity),
este modelo mantiene un inventario completo: qué dispositivo usa cada
usuario, en qué proyecto, cuándo fue registrado, y si sigue activo o fue
revocado.  Permite auditoría y control de acceso por dispositivo.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class UserDeviceAssignment(Base):
    __tablename__ = "user_device_assignments"
    __table_args__ = (
        Index("ix_device_assignments_user_project", "user_id", "project_id"),
        Index("ix_device_assignments_device", "device_fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    device_fingerprint: Mapped[str] = mapped_column(String(200), nullable=False)
    device_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    device_os: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    device_model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    app_version: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    registered_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
