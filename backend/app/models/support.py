"""Mesa de ayuda no-code: tickets de soporte con auto-respuesta semantica.

El motor de reglas (ver `support_service.py`) clasifica la descripcion del
problema por palabras clave: si reconoce un patron conocido responde con un
tutorial sin intervencion humana; si detecta senales de daño fisico del
dispositivo, o no reconoce el patron, escala el ticket a soporte humano.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True)
    resolution_channel: Mapped[str] = mapped_column(String(20), default="human", nullable=False)
    matched_rule: Mapped[str | None] = mapped_column(String(60), nullable=True)
    auto_response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
