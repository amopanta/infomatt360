from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class GisLayer(Base):
    __tablename__ = "gis_layers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    layer_type: Mapped[str] = mapped_column(String(60), nullable=False)
    style_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class GisFeature(Base):
    __tablename__ = "gis_features"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    layer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    participant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    feature_type: Mapped[str] = mapped_column(String(60), nullable=False)
    latitude: Mapped[str | None] = mapped_column(String(60), nullable=True)
    longitude: Mapped[str | None] = mapped_column(String(60), nullable=True)
    geometry_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    properties_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
