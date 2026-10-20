"""Planeador mensual: configuración, población objetivo, metas, plan del gestor y cortes.

Lo ejecutado no se copia: se calcula desde `runtime_records` según la
configuración del proyecto (docs/144). Las metas y el plan guardan su
historial en `planner_history`, que solo admite inserciones.
"""

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class PlannerSettings(Base):
    """Reglas de conteo por proyecto; nada queda fijo en el código."""

    __tablename__ = "planner_settings"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # "submitted": vale lo que llega; "approved": solo lo aprobado.
    count_policy: Mapped[str] = mapped_column(String(20), default="approved", nullable=False)
    # Llave de familia: participant | document_id | external_code | field
    family_key: Mapped[str] = mapped_column(String(20), default="participant", nullable=False)
    family_field: Mapped[str | None] = mapped_column(String(180), nullable=True)
    # Campo de fecha de la actividad en el formulario; sin él, la fecha de registro.
    activity_date_field: Mapped[str | None] = mapped_column(String(180), nullable=True)
    # Campo de municipio en formularios sin participante.
    municipality_field: Mapped[str | None] = mapped_column(String(180), nullable=True)
    timezone: Mapped[str] = mapped_column(String(60), default="America/Bogota", nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class PlannerPopulation(Base):
    """Población objetivo por municipio y año (familias y participantes)."""

    __tablename__ = "planner_population"
    __table_args__ = (UniqueConstraint("project_id", "year", "municipality", name="uq_planner_population_scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    municipality: Mapped[str] = mapped_column(String(120), nullable=False)
    families: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    participants: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class PlannerTarget(Base):
    """Meta de una actividad (formulario) en un mes, municipio y, si aplica, gestor."""

    __tablename__ = "planner_targets"
    __table_args__ = (UniqueConstraint("project_id", "scope_key", name="uq_planner_target_scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    municipality: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    gestor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # "records": actividades/visitas; "families": familias únicas.
    unit: Mapped[str] = mapped_column(String(20), default="records", nullable=False)
    target: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Ámbito normalizado: una sola meta por combinación (importar dos veces no duplica).
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class PlannerPlan(Base):
    """Programación del gestor: actividad, fechas y cantidad prevista."""

    __tablename__ = "planner_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    gestor_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    municipality: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    coordinator_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    planned_participants: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # scheduled | rescheduled | cancelled
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class PlannerHistory(Base):
    """Historial de metas, población y plan. Solo inserciones."""

    __tablename__ = "planner_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    previous_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_json: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    # Fila de importación ya aplicada (hash del archivo + fila): repetir la carga no suma dos veces.
    client_ref: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class PlannerCut(Base):
    """Corte cerrado de un mes: congela metas y ejecución para reportes reproducibles."""

    __tablename__ = "planner_cuts"
    __table_args__ = (UniqueConstraint("project_id", "year", "month", name="uq_planner_cut_period"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    settings_json: Mapped[str] = mapped_column(Text, nullable=False)
    closed_by: Mapped[str] = mapped_column(String(36), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
