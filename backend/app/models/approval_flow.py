from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class ApprovalFlow(Base):
    __tablename__ = "approval_flows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    template_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    flow_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class ApprovalFlowStep(Base):
    __tablename__ = "approval_flow_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    flow_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    action_label: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    status_after: Mapped[str] = mapped_column(String(60), nullable=False)
    required_permission: Mapped[str] = mapped_column(String(120), nullable=False)
    approver_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    approver_role_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    require_all: Mapped[str] = mapped_column(String(10), default="false", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
