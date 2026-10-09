"""Seguimiento longitudinal de participantes y remisiones entre usuarios."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import participant_visible, require_any_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE, RECORDS_READ, RECORDS_WRITE
from app.db.session import get_db
from app.models.case_management import CaseEvent, ParticipantCase
from app.models.assignment import UserProjectAssignment
from app.models.identity import User
from app.models.messages import InternalMessage
from app.models.participants import Participant
from app.models.scheduler import ScheduledTask
from app.schemas.case_management import CaseCreate, CaseEventRead, CaseRead, CaseUpdate
from app.services.assignment_service import assignment_service

router = APIRouter()


def _participant(db: Session, user: User, participant_id: str, *, write: bool = False) -> Participant:
    row = db.get(Participant, participant_id)
    if not row or not assignment_service.user_has_project_access(db, user.id, row.project_id) or not participant_visible(db, user.id, row):
        raise HTTPException(status_code=404, detail="Participante no encontrado")
    require_any_project_permission(db, user.id, row.project_id, {RECORDS_WRITE} if write else {RECORDS_READ, RECORDS_WRITE, IDENTITY_USERS_MANAGE})
    return row


def _case(db: Session, user: User, case_id: str, *, write: bool = False) -> ParticipantCase:
    row = db.get(ParticipantCase, case_id)
    if not row:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    _participant(db, user, row.participant_id, write=write)
    return row


def _read(row: ParticipantCase) -> CaseRead:
    return CaseRead(id=row.id, project_id=row.project_id, participant_id=row.participant_id,
                    case_type=row.case_type, parent_case_id=row.parent_case_id,
                    title=row.title, status=row.status, assigned_user_id=row.assigned_user_id,
                    due_at=row.due_at, properties=json.loads(row.properties_json),
                    created_by=row.created_by, created_at=row.created_at, updated_at=row.updated_at)


def _check_assignee(db: Session, project_id: str, user_id: str | None, participant: Participant) -> None:
    if user_id and (not db.get(User, user_id) or not assignment_service.user_has_project_access(db, user_id, project_id)):
        raise HTTPException(status_code=422, detail="El responsable debe tener acceso al proyecto")
    if user_id and not participant_visible(db, user_id, participant):
        raise HTTPException(status_code=422, detail="El responsable no tiene acceso al territorio del participante")


def _schedule_reminder(db: Session, row: ParticipantCase) -> None:
    db.query(ScheduledTask).filter(ScheduledTask.task_type == "case_reminder", ScheduledTask.target_id == row.id,
                                    ScheduledTask.status == "active").delete()
    if row.due_at and row.assigned_user_id and row.status != "closed":
        db.add(ScheduledTask(project_id=row.project_id, name=f"Seguimiento: {row.title}", task_type="case_reminder",
                             target_id=row.id, frequency="once", next_run_at=row.due_at))


@router.get("/project/{project_id}/assignees")
def case_assignees(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_any_project_permission(db, user.id, project_id, {RECORDS_READ, RECORDS_WRITE, IDENTITY_USERS_MANAGE})
    rows = db.query(User).join(UserProjectAssignment, UserProjectAssignment.user_id == User.id).filter(
        UserProjectAssignment.project_id == project_id, UserProjectAssignment.status == "active", User.status == "active").distinct().order_by(User.full_name).all()
    return [{"id": item.id, "full_name": item.full_name} for item in rows]


@router.get("/participant/{participant_id}", response_model=list[CaseRead])
def list_cases(participant_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _participant(db, user, participant_id)
    rows = db.query(ParticipantCase).filter(ParticipantCase.participant_id == participant_id).order_by(ParticipantCase.created_at.desc()).all()
    return [_read(row) for row in rows]


@router.post("/", response_model=CaseRead)
def create_case(payload: CaseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    participant = _participant(db, user, payload.participant_id, write=True)
    if not payload.case_type.strip():
        raise HTTPException(status_code=422, detail="El tipo de caso es obligatorio")
    parent = _case(db, user, payload.parent_case_id) if payload.parent_case_id else None
    if parent and parent.project_id != participant.project_id:
        raise HTTPException(status_code=422, detail="El caso padre pertenece a otro proyecto")
    _check_assignee(db, participant.project_id, payload.assigned_user_id, participant)
    now = datetime.utcnow()
    row = ParticipantCase(project_id=participant.project_id, participant_id=participant.id,
                          case_type=payload.case_type.strip(), parent_case_id=parent.id if parent else None,
                          title=payload.title.strip(),
                          assigned_user_id=payload.assigned_user_id, due_at=payload.due_at,
                          properties_json=json.dumps({**{key: value for key, value in payload.properties.items() if not key.startswith("_")}, "_reminder_channels": list(dict.fromkeys(payload.reminder_channels))}, ensure_ascii=False), created_by=user.id,
                          created_at=now, updated_at=now)
    db.add(row)
    db.flush()
    db.add(CaseEvent(case_id=row.id, event_type="created", from_user_id=user.id))
    _schedule_reminder(db, row)
    db.commit()
    db.refresh(row)
    return _read(row)


@router.get("/{case_id}/children", response_model=list[CaseRead])
def case_children(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    parent = _case(db, user, case_id)
    rows = db.query(ParticipantCase).filter(ParticipantCase.parent_case_id == parent.id).order_by(ParticipantCase.created_at).all()
    return [_read(row) for row in rows if participant_visible(db, user.id, db.get(Participant, row.participant_id))]


@router.patch("/{case_id}", response_model=CaseRead)
def update_case(case_id: str, payload: CaseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _case(db, user, case_id, write=True)
    data = payload.model_dump(exclude_unset=True)
    if "assigned_user_id" in data:
        _check_assignee(db, row.project_id, data["assigned_user_id"], db.get(Participant, row.participant_id))
        if data["assigned_user_id"] and data["assigned_user_id"] != row.assigned_user_id:
            db.add(InternalMessage(project_id=row.project_id, sender_id=user.id, recipient_id=data["assigned_user_id"],
                                   subject=f"Remisión de caso: {row.title}", body=payload.note or "Se te asignó un caso para seguimiento."))
    if "properties" in data or "reminder_channels" in data:
        properties = json.loads(row.properties_json or "{}")
        if "properties" in data:
            properties.update({key: value for key, value in (data.pop("properties") or {}).items() if not key.startswith("_")})
        if "reminder_channels" in data:
            properties["_reminder_channels"] = list(dict.fromkeys(data.pop("reminder_channels") or []))
        row.properties_json = json.dumps(properties, ensure_ascii=False)
    for key in ("status", "assigned_user_id", "due_at"):
        if key in data:
            setattr(row, key, data[key])
    row.updated_at = datetime.utcnow()
    event_type = "referred" if "assigned_user_id" in data else "updated"
    db.add(CaseEvent(case_id=row.id, event_type=event_type, note=payload.note, from_user_id=user.id,
                     to_user_id=row.assigned_user_id if event_type == "referred" else None))
    _schedule_reminder(db, row)
    db.commit()
    db.refresh(row)
    return _read(row)


@router.get("/{case_id}/events", response_model=list[CaseEventRead])
def case_events(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _case(db, user, case_id)
    return db.query(CaseEvent).filter(CaseEvent.case_id == case_id).order_by(CaseEvent.created_at).all()
