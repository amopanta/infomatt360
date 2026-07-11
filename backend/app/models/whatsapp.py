"""Ledger de notificaciones enviadas por WhatsApp via WAHA.

Alcance minimo: un canal mas de notificacion (junto a `InternalMessage` y
`MailProfile`), disparado solo en rechazo/devolucion de un registro (ver
`app.services.review_service`). No incluye recibos de lectura/entrega
(eso requeriria configurar un webhook de WAHA de vuelta hacia el backend,
fuera de este alcance) ni plantillas de mensaje configurables.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class WhatsAppNotification(Base):
    """Un intento de envio de WhatsApp, exitoso o fallido.

    Fila inmutable: un reintento manual crea una fila nueva, no actualiza
    esta (mismo patron que `ErpInventoryMovement`).
    """

    __tablename__ = "whatsapp_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recipient_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    recipient_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reference_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
