from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class FileAsset(Base):
    __tablename__ = "file_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    participant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    asset_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(250), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(60), default="local", nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
