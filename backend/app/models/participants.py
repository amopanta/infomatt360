from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    external_code: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    document_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(220), nullable=False, index=True)
    participant_type: Mapped[str] = mapped_column(String(80), default="person", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    duplicate_flag: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
