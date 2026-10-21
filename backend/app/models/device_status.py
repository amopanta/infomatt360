"""Estado reportado por cada equipo de campo y recorrido del gestor.

La app móvil informa periódicamente (latido) cuántos registros tiene
guardados sin enviar, cuándo sincronizó por última vez y los últimos
errores, para que el supervisor vea desde la web qué tablets necesitan
atención sin pedirle nada al gestor. En el mismo envío llegan los puntos
GPS del recorrido, tomados automáticamente mientras la app está abierta.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class FieldDeviceStatus(Base):
    """Último estado conocido de un equipo, uno por (equipo, usuario)."""

    __tablename__ = "field_device_status"
    __table_args__ = (UniqueConstraint("device_id", "user_id", name="uq_field_device_status_device_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    device_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    device_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    platform: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    app_version: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    pending_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conflict_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    draft_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pending_evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    oldest_pending_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    recent_errors_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    last_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_location_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    # Borrado remoto (H07): lo pide un administrador; el equipo lo recibe en
    # su siguiente latido, borra los datos del usuario y lo confirma.
    wipe_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    wipe_requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    wipe_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class FieldRoutePoint(Base):
    """Punto del recorrido de un gestor. Visible solo para supervisión."""

    __tablename__ = "field_route_points"
    __table_args__ = (
        UniqueConstraint("device_id", "user_id", "recorded_at", name="uq_field_route_point"),
        Index("ix_field_route_points_project_user_time", "project_id", "user_id", "recorded_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    device_id: Mapped[str] = mapped_column(String(120), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
