"""Plantillas de actas/documentos PDF de marca blanca.

El coordinador diseña el acta como HTML con marcadores Jinja2 (`{{ campo }}`)
y el motor la compila con datos reales al momento de generar el PDF. No hay
tabla fisica por acta generada: el PDF se transmite en streaming y no se
persiste en el servidor.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class ActaTemplate(Base):
    __tablename__ = "acta_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    html_template: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
