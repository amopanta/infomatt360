"""
Proyecto: InfoMatt360
Modulo: Runtime Records
Responsabilidad: Persistir respuestas capturadas desde formularios renderizados por Runtime.
Dependencias: SQLAlchemy, Base declarativa del backend.
Notas: No se crean tablas fisicas por formulario; los valores se guardan en estructura flexible.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    """Genera identificadores UUID portables entre motores SQL."""
    return str(uuid4())


class RuntimeRecord(Base):
    """Cabecera de una captura realizada desde Runtime.

    Guarda contexto de proyecto, plantilla y version para poder reconstruir
    historicamente el formulario usado en la captura.
    """

    __tablename__ = "runtime_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="submitted", nullable=False)
    submitted_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    device_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class RuntimeRecordValue(Base):
    """Valor individual capturado para un componente del formulario.

    field_value_json se almacena como texto JSON para soportar valores simples
    y complejos: texto, GPS, firma, archivos, OCR, listas o matrices.
    """

    __tablename__ = "runtime_record_values"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    record_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    component_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    field_name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    field_value_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
