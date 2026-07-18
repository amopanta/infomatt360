"""Plantillas de actas/documentos PDF de marca blanca.

Dos caminos de renderizado conviven en la misma tabla (ver docs/109,
constructor visual de actas -- docs/96 item #4):

- "Legado": `html_template` no nulo, `layout_json`/`template_id` nulos. El
  coordinador escribe el acta como HTML con marcadores Jinja2 crudo
  (`{{ campo }}`) y el motor la compila con un `data: dict[str, str]`
  arbitrario provisto por el llamador (endpoint `POST /{id}/render`). Nunca
  tuvo UI propia -- sigue existiendo como via de escape para uso avanzado.
- "Constructor visual": `layout_json` no nulo, `template_id` (el
  `BuilderTemplate` para el que fue diseñada) tambien no nulo. El acta se
  arma a partir de bloques estructurados (logo, encabezado, tabla, firma)
  que el constructor visual del frontend edita, y se renderiza siempre a
  partir de un `RuntimeRecord` real de ese `template_id` (endpoint
  `POST /{id}/render-from-record`).

Una fila nunca mezcla ambos caminos -- se valida en el servicio, no en la
base de datos (permitir ambos NULL o ambos NOT NULL simplifica la migracion
de filas legado existentes).

No hay tabla fisica por acta generada: el PDF se transmite en streaming y no
se persiste en el servidor.
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
    html_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
