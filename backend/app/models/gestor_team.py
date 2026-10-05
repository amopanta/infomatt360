"""Operational teams, separate from participant import cohorts."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


class GestorTeam(Base):
    __tablename__ = "gestor_teams"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_gestor_team_project_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class GestorTeamUser(Base):
    __tablename__ = "gestor_team_users"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_gestor_team_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    team_id: Mapped[str] = mapped_column(String(36), ForeignKey("gestor_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)


class GestorTeamParticipant(Base):
    __tablename__ = "gestor_team_participants"
    __table_args__ = (UniqueConstraint("team_id", "participant_id", name="uq_gestor_team_participant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    team_id: Mapped[str] = mapped_column(String(36), ForeignKey("gestor_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    participant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
