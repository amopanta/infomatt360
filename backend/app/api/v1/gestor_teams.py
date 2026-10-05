"""Gestor teams are organizational membership, not form access grants."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_any_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.gestor_team import GestorTeam, GestorTeamParticipant, GestorTeamUser
from app.models.identity import User
from app.models.participants import Participant
from app.services.assignment_service import assignment_service

router = APIRouter()


class TeamWrite(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class TeamMembersWrite(BaseModel):
    user_ids: list[str] = Field(default_factory=list)
    participant_ids: list[str] = Field(default_factory=list)


def _manage(db: Session, actor: User, project_id: str) -> None:
    if not assignment_service.user_has_project_access(db, actor.id, project_id):
        raise HTTPException(status_code=403, detail="Sin acceso al proyecto")
    require_any_project_permission(db, actor.id, project_id, {IDENTITY_USERS_MANAGE})


def _team(db: Session, actor: User, team_id: str) -> GestorTeam:
    team = db.get(GestorTeam, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    _manage(db, actor, team.project_id)
    return team


def _read(db: Session, team: GestorTeam) -> dict:
    users = db.query(GestorTeamUser.user_id).filter_by(team_id=team.id).all()
    participants = db.query(GestorTeamParticipant.participant_id).filter_by(team_id=team.id).all()
    return {"id": team.id, "project_id": team.project_id, "name": team.name,
            "user_ids": [row[0] for row in users], "participant_ids": [row[0] for row in participants]}


@router.get("/project/{project_id}")
def list_teams(project_id: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> list[dict]:
    _manage(db, actor, project_id)
    return [_read(db, team) for team in db.query(GestorTeam).filter_by(project_id=project_id).order_by(GestorTeam.name).all()]


@router.post("/project/{project_id}", status_code=201)
def create_team(project_id: str, payload: TeamWrite, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> dict:
    _manage(db, actor, project_id)
    name = payload.name.strip()
    if db.query(GestorTeam.id).filter(GestorTeam.project_id == project_id, func.lower(GestorTeam.name) == name.lower()).first():
        raise HTTPException(status_code=409, detail="Ya existe un equipo con ese nombre")
    team = GestorTeam(project_id=project_id, name=name, created_by=actor.id)
    db.add(team)
    db.flush()
    db.add(AuditLog(project_id=project_id, user_id=actor.id, module="participants", action="create_gestor_team",
                    entity_type="gestor_team", entity_id=team.id, after_json=json.dumps({"name": name})))
    db.commit()
    return _read(db, team)


@router.patch("/{team_id}")
def rename_team(team_id: str, payload: TeamWrite, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> dict:
    team = _team(db, actor, team_id)
    name = payload.name.strip()
    if db.query(GestorTeam.id).filter(GestorTeam.project_id == team.project_id, GestorTeam.id != team.id,
                                       func.lower(GestorTeam.name) == name.lower()).first():
        raise HTTPException(status_code=409, detail="Ya existe un equipo con ese nombre")
    before = team.name
    team.name = name
    db.add(AuditLog(project_id=team.project_id, user_id=actor.id, module="participants", action="rename_gestor_team",
                    entity_type="gestor_team", entity_id=team.id, before_json=json.dumps({"name": before}),
                    after_json=json.dumps({"name": name})))
    db.commit()
    return _read(db, team)


@router.put("/{team_id}/members")
def set_members(team_id: str, payload: TeamMembersWrite, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> dict:
    team = _team(db, actor, team_id)
    user_ids, participant_ids = set(payload.user_ids), set(payload.participant_ids)
    if len(user_ids) > 100 or len(participant_ids) > 10000:
        raise HTTPException(status_code=422, detail="Demasiados integrantes para un equipo")
    invalid_users = [uid for uid in user_ids if not db.get(User, uid) or not assignment_service.user_has_project_access(db, uid, team.project_id)]
    valid_participants = {row[0] for row in db.query(Participant.id).filter(Participant.project_id == team.project_id,
                                                                             Participant.status == "active", Participant.id.in_(participant_ids)).all()}
    if invalid_users or valid_participants != participant_ids:
        raise HTTPException(status_code=422, detail="Usuarios o participantes fuera del proyecto o inactivos")
    before = _read(db, team)
    db.query(GestorTeamUser).filter_by(team_id=team.id).delete(synchronize_session=False)
    db.query(GestorTeamParticipant).filter_by(team_id=team.id).delete(synchronize_session=False)
    db.add_all(GestorTeamUser(team_id=team.id, user_id=uid) for uid in user_ids)
    db.add_all(GestorTeamParticipant(team_id=team.id, participant_id=pid) for pid in participant_ids)
    db.flush()
    after = _read(db, team)
    db.add(AuditLog(project_id=team.project_id, user_id=actor.id, module="participants", action="set_gestor_team_members",
                    entity_type="gestor_team", entity_id=team.id, before_json=json.dumps(before), after_json=json.dumps(after)))
    db.commit()
    return after


@router.delete("/{team_id}")
def delete_team(team_id: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> dict[str, bool]:
    team = _team(db, actor, team_id)
    before = _read(db, team)
    db.query(GestorTeamUser).filter_by(team_id=team.id).delete(synchronize_session=False)
    db.query(GestorTeamParticipant).filter_by(team_id=team.id).delete(synchronize_session=False)
    db.add(AuditLog(project_id=team.project_id, user_id=actor.id, module="participants", action="delete_gestor_team",
                    entity_type="gestor_team", entity_id=team.id, before_json=json.dumps(before)))
    db.delete(team)
    db.commit()
    return {"deleted": True}
