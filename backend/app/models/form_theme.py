"""
Proyecto: InfoMatt360
Modulo: Form Theme
Responsabilidad: Personalizar apariencia de formularios por programa o plantilla.
Notas: Permite colores, nombre del programa, icono y CSS controlado sin tocar codigo.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class FormTheme(Base):
    """Tema visual aplicable a uno o varios formularios Runtime."""

    __tablename__ = "form_themes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    program_name: Mapped[str] = mapped_column(String(180), nullable=False)
    icon_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#0066CC")
    secondary_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#00C2FF")
    background_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#F5F8FB")
    custom_css: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TemplateThemeBinding(Base):
    """Relaciona una plantilla del Builder con un tema visual."""

    __tablename__ = "template_theme_bindings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    theme_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
