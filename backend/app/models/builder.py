from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.time import utc_now


def new_uuid() -> str:
    """Genera identificadores UUID portables entre motores SQL."""
    return str(uuid4())


class BuilderTemplate(Base):
    """Plantilla principal del constructor visual.

    Representa un formulario editable dentro de un proyecto. La estructura
    visual se completa con paginas, secciones, filas, columnas y componentes.
    """

    __tablename__ = "builder_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    theme_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class BuilderVersion(Base):
    """Version publicada o borrador de una plantilla.

    Guarda una fotografia JSON del formulario para que los registros antiguos
    sigan interpretandose con la version exacta usada al capturar.
    """

    __tablename__ = "builder_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    schema_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class BuilderComponent(Base):
    """Campo o componente visual del formulario.

    column_id es opcional para mantener compatibilidad con componentes creados
    antes del Layout Engine, pero el Runtime MVP lo usa para renderizar el
    campo dentro de la columna correcta.
    """

    __tablename__ = "builder_components"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    column_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    component_type: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str] = mapped_column(String(220), nullable=False)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
