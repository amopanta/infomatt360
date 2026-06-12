from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class StorageProfile(Base):
    __tablename__ = "storage_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    provider: Mapped[str] = mapped_column(String(60), default="local", nullable=False)
    base_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    bucket_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    endpoint_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    credentials_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_file_size_mb: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    is_default: Mapped[str] = mapped_column(String(10), default="false", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
