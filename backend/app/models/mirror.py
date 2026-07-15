from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class MirrorTarget(Base):
    __tablename__ = "mirror_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    engine: Mapped[str] = mapped_column(String(60), nullable=False)
    conn_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class MirrorPlan(Base):
    __tablename__ = "mirror_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    tables_json: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_mode: Mapped[str] = mapped_column(String(60), default="manual", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    last_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class MirrorRun(Base):
    """Historial de cada corrida real de sincronizacion de un MirrorPlan.

    Mismo patron que BackupJob (app/models/backup.py): status="running" al
    crear, se cierra a "completed"/"failed" al terminar. Ver docs/102.
    """

    __tablename__ = "mirror_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    plan_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="running", nullable=False)
    records_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    values_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    triggered_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
