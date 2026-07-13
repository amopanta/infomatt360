"""Modelo de organizacion (tenant logico).

Una organizacion agrupa proyectos bajo un mismo cliente/marca. El
aislamiento es logico -filtrando por organization_id a traves de
project_id- y no un schema fisico de base de datos separado por tenant.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    public_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class OrganizationBranding(Base):
    """Marca blanca configurable por organizacion.

    Una fila por organizacion. El logo se referencia por URL (puede apuntar a
    un archivo ya subido via el modulo de files) para no acoplar branding a
    un proyecto especifico.
    """

    __tablename__ = "organization_brandings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    accent_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    background_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    slogan: Mapped[str | None] = mapped_column(String(220), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
