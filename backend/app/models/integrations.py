from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class IntegrationSource(Base):
    """Conexion a un sistema externo (ej. cuenta de ActivityInfo/TolaData).

    `credentials_encrypted` guarda el API key/token cifrado (Fernet, igual
    que los tokens OAuth de Google Drive) -- nunca se expone en
    `IntegrationSourceRead`. `config_json` es para configuracion no
    secreta (headers extra, identificador de base de datos, etc.).
    """

    __tablename__ = "integration_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    source_type: Mapped[str] = mapped_column(String(60), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    credentials_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class IntegrationMap(Base):
    """Mapeo de campos de una plantilla hacia el esquema del sistema externo.

    `template_id` vincula el mapeo a un formulario del Builder: al
    aprobarse un registro de esa plantilla, se dispara el envio (ver
    `integration_service.push_approved_record`). Sin `template_id`
    (mapeos creados antes de esta version), el mapeo queda inerte para el
    disparo automatico pero sigue disponible para uso manual.
    """

    __tablename__ = "integration_maps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    template_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    target_table: Mapped[str] = mapped_column(String(180), nullable=False)
    fields_json: Mapped[str] = mapped_column(Text, nullable=False)
    filters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class IntegrationJob(Base):
    """Un intento de envio hacia el sistema externo (ledger inmutable)."""

    __tablename__ = "integration_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    map_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    reference_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(60), default="manual", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    last_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
