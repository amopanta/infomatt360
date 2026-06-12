from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class BuilderPage(Base):
    __tablename__ = "builder_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visible: Mapped[str] = mapped_column(String(10), default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class BuilderSection(Base):
    __tablename__ = "builder_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    page_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    collapsible: Mapped[str] = mapped_column(String(10), default="false", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visible: Mapped[str] = mapped_column(String(10), default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class BuilderRow(Base):
    __tablename__ = "builder_rows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    section_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    responsive: Mapped[str] = mapped_column(String(10), default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class BuilderColumn(Base):
    __tablename__ = "builder_columns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    row_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    desktop_width: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    tablet_width: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    mobile_width: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
