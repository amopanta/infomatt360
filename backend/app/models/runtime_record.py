"""
Proyecto: InfoMatt360
Modulo: Runtime Records
Responsabilidad: Persistir respuestas capturadas desde formularios renderizados por Runtime.
Dependencias: SQLAlchemy, Base declarativa del backend.
Notas: No se crean tablas fisicas por formulario; los valores se guardan en estructura flexible.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.time import utc_now


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
    # Enlace real de subformulario (estilo ActivityInfo): si este registro es
    # una fila hija capturada dentro de un campo LINKED_SUBFORM de otro
    # registro, aqui queda el id del registro padre y el nombre del campo
    # que lo contiene. Es una fila propia en runtime_records, no un grupo
    # embebido en el JSON del padre (a diferencia de REPEAT).
    parent_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    parent_field_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    # Participante como eje central (ver docs/98): permite ver, desde un
    # unico participante, todos los formularios capturados sobre el sin
    # importar el canal (web, movil, carga masiva, API). Se completa de
    # forma explicita (payload) o por coincidencia automatica de un campo
    # DOCUMENT_ID contra Participant.document_id -- ver
    # runtime_record_service._match_participant.
    participant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    approval_flow_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    approval_flow_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    approval_flow_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="submitted", nullable=False)
    submitted_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    device_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    duplicate_flag: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    # Bloqueo optimista: se incrementa en cada correccion de un valor de
    # campo (ver runtime_record_service.correct_field). No tiene relacion
    # con `version_id` (la version de la PLANTILLA usada al capturar).
    lock_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
