"""Importación desde una base de datos externa (docs/146).

Reutiliza las conexiones de la base espejo (`mirror_targets`) como origen.
Cada importación lee una tabla o vista y crea o actualiza participantes,
respuestas de un formulario o asignaciones, siempre con los servicios que ya
validan permisos y reglas.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class DbImport(Base):
    __tablename__ = "db_imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)  # mirror_targets.id
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    # participants | records | assignments
    entity: Mapped[str] = mapped_column(String(20), nullable=False)
    source_table: Mapped[str] = mapped_column(String(180), nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # {"campo_destino": "columna_origen"}
    mapping_json: Mapped[str] = mapped_column(Text, nullable=False)
    # Columna de origen que identifica cada fila (documento, código, id externo).
    key_column: Mapped[str] = mapped_column(String(180), nullable=False)
    # Opcional: columna creciente (fecha de actualización o id) para traer solo lo nuevo.
    cursor_column: Mapped[str | None] = mapped_column(String(180), nullable=True)
    last_cursor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    record_status: Mapped[str] = mapped_column(String(20), default="submitted", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    last_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class DbImportRun(Base):
    __tablename__ = "db_import_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    import_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="running", nullable=False)
    rows_read: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unchanged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DbImportKey(Base):
    """Fila de origen ya importada: evita duplicar y detecta cambios por hash."""

    __tablename__ = "db_import_keys"
    __table_args__ = (UniqueConstraint("import_id", "source_key", name="uq_db_import_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    import_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
