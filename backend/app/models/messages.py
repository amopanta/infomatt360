from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
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
    last_imap_uid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ExternalMailMessage(Base):
    __tablename__ = "external_mail_messages"
    __table_args__ = (UniqueConstraint("mail_profile_id", "uid", name="uq_external_mail_messages_profile_uid"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    mail_profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    uid: Mapped[int] = mapped_column(Integer, nullable=False)
    from_address: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="unread", nullable=False)


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
