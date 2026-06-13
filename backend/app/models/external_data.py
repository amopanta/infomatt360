"""
Proyecto: InfoMatt360
Modulo: External Data
Responsabilidad: Registrar fuentes externas tipo pulldata, enlaces compartidos y operaciones masivas.
Notas: Permite que formularios complejos consuman bases externas sin congelar datos en el dispositivo.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    """Genera UUID portable entre motores SQL."""
    return str(uuid4())


class ExternalDataSource(Base):
    """Fuente externa reutilizable por uno o varios formularios.

    Puede representar CSV, XLSX, API, Google Drive, SharePoint u otro enlace
    que el sistema sincronice de forma programada o bajo demanda.
    """

    __tablename__ = "external_data_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    source_type: Mapped[str] = mapped_column(String(60), nullable=False, default="csv_url")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    key_field: Mapped[str] = mapped_column(String(180), nullable=False, default="id")
    sync_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="on_open")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class FormDataSourceBinding(Base):
    """Relaciona una fuente externa con una plantilla del Builder.

    Esta tabla permite replicar una misma fuente a muchos formularios sin
    configurarla manualmente uno a uno.
    """

    __tablename__ = "form_data_source_bindings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    data_source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(120), nullable=False)
    filter_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class BulkPublishJob(Base):
    """Operacion masiva de publicacion o vinculacion de formularios.

    Guarda trazabilidad cuando un usuario selecciona varios formularios por
    checklist o filtro y aplica una accion en lote.
    """

    __tablename__ = "bulk_publish_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_template_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
