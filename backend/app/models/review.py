from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class ReviewAction(Base):
    __tablename__ = "review_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejected_field_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    approval_flow_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    approval_flow_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ReviewObservation(Base):
    """Observación de revisión por pregunta (docs/141 §6).

    Se guarda aparte de las respuestas: varias observaciones sobre un
    registro no tocan sus valores ni multiplican sus filas al exportar.
    Estados: pending, in_correction, corrected, verified, rejected.
    """

    __tablename__ = "review_observations"
    __table_args__ = (UniqueConstraint("record_id", "client_ref", name="uq_review_observation_client_ref"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    review_action_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    field_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    # Ruta dentro de un REPEAT, p. ej. "integrantes[2].edad"
    repeat_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    evidence_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_action: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    response_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    resolved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Devolución masiva o reintento: la misma fila no crea dos observaciones
    client_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
