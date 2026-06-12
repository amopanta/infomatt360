from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class MailProfile(Base):
    __tablename__ = "mail_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    provider: Mapped[str] = mapped_column(String(60), default="smtp", nullable=False)
    sender_email: Mapped[str] = mapped_column(String(180), nullable=False)
    server_host: Mapped[str | None] = mapped_column(String(180), nullable=True)
    server_port: Mapped[str | None] = mapped_column(String(20), nullable=True)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[str] = mapped_column(String(10), default="false", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class InternalMessage(Base):
    __tablename__ = "internal_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sender_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    recipient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="unread", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
