"""
Proyecto: InfoMatt360
Modulo: Offline Backup
Responsabilidad: Registrar backups provenientes de tablets o escritorio y reconciliar envios faltantes.
Notas: Permite validar que informacion offline ya llego al servidor y reenviar solo lo pendiente.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class OfflineBackupImport(Base):
    """Cabecera de una importacion de backup offline."""

    __tablename__ = "offline_backup_imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(220), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="uploaded")
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class OfflineBackupRecordCheck(Base):
    """Resultado de comparar un registro offline contra el servidor."""

    __tablename__ = "offline_backup_record_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    backup_import_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    local_record_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    server_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    template_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
