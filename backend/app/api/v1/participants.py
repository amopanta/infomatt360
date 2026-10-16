import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import allowed_form_participant_ids, allowed_participant_ids, form_access_mode, get_project_permissions, participant_visible
from app.api.permissions import require_any_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE, PARTICIPANTS_CREATE, RECORDS_APPROVE, RECORDS_LINK_PARTICIPANT, RECORDS_REVIEW
from app.db.session import get_db
from app.models.identity import User
from app.models.participants import Participant
from app.models.builder import BuilderTemplate
from app.models.form_assignment import ParticipantFormAssignment
from app.models.runtime_record import RuntimeRecord
from app.schemas.participants import ParticipantCreate, ParticipantGroupStatusUpdate, ParticipantGroupUpdate, ParticipantHistoryItem, ParticipantPromoteRequest, ParticipantRead
from app.services.assignment_service import assignment_service
from app.services.participant_service import participant_service
from pydantic import BaseModel

router = APIRouter()


@router.delete("/project/{project_id}/groups/{group_name}", summary="Quitar un grupo sin borrar participantes")
def delete_participant_group(project_id: str, group_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, int]:
    require_any_project_permission(db, current_user.id, project_id, {IDENTITY_USERS_MANAGE})
    return {"updated": participant_service.delete_group(db, project_id, group_name)}


@router.patch("/project/{project_id}/groups/{group_name}/status", summary="Cambiar estado de un grupo de participantes")
def change_participant_group_status(project_id: str, group_name: str, payload: ParticipantGroupStatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, int]:
    require_any_project_permission(db, current_user.id, project_id, {IDENTITY_USERS_MANAGE})
    return {"updated": participant_service.set_group_status(db, project_id, group_name, payload.status)}


@router.post("/", response_model=ParticipantRead, summary="Crear participante")
def create_participant(payload: ParticipantCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ParticipantRead:
    require_any_project_permission(db, current_user.id, payload.project_id, {PARTICIPANTS_CREATE, IDENTITY_USERS_MANAGE})
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    candidate = Participant(project_id=payload.project_id, full_name=payload.full_name,
                            metadata_json=json.dumps({"department": payload.department, "municipality": payload.municipality}))
    if not participant_visible(db, current_user.id, candidate):
        raise HTTPException(status_code=403, detail="Fuera del territorio asignado")
    return participant_service.create_participant(db, payload)


@router.get("/project/{project_id}", response_model=list[ParticipantRead], summary="Listar participantes por proyecto")
def list_project_participants(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ParticipantRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    allowed = allowed_participant_ids(db, current_user.id, project_id)
    rows = participant_service.list_participants(db, project_id)
    if allowed is None:
        return rows
    allowed_set = set(allowed)
    return [row for row in rows if row.id in allowed_set]


def _require_participant(db: Session, current_user: User, participant_id: str) -> ParticipantRead:
    """Resuelve un participante validando acceso al proyecto sin filtrar por
    project_id en la consulta (evita revelar si el id existe en otro
    proyecto vs. si simplemente no existe -- ambos casos dan 404)."""
    participant = participant_service.get_participant(db, participant_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante no encontrado")
    if not assignment_service.user_has_project_access(db, current_user.id, participant.project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante no encontrado")
    if not participant_visible(db, current_user.id, db.get(Participant, participant_id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante no encontrado")
    return participant


@router.get("/{participant_id}", response_model=ParticipantRead, summary="Consultar un participante")
def get_participant(participant_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ParticipantRead:
    return _require_participant(db, current_user, participant_id)


@router.patch("/{participant_id}/group", response_model=ParticipantRead, summary="Asignar grupo a un participante")
def set_participant_group(participant_id: str, payload: ParticipantGroupUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ParticipantRead:
    participant = _require_participant(db, current_user, participant_id)
    require_any_project_permission(db, current_user.id, participant.project_id, {IDENTITY_USERS_MANAGE})
    return participant_service.set_group(db, participant_id, payload.group_name)


@router.get("/{participant_id}/history", response_model=list[ParticipantHistoryItem], summary="Historial unificado del participante entre plantillas y canales")
def get_participant_history(participant_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ParticipantHistoryItem]:
    _require_participant(db, current_user, participant_id)
    return [item for item in participant_service.get_participant_history(db, participant_id)
            if (template := db.get(BuilderTemplate, item.template_id)) is not None
            and ((allowed := allowed_form_participant_ids(db, current_user.id, template, review=True)) is None or participant_id in allowed)]


class ParticipantActivity(BaseModel):
    template_id: str
    template_name: str
    assignment_status: str
    responsible_user_id: str | None = None
    responsible_name: str | None = None
    record_id: str | None = None
    record_status: str | None = None


@router.get("/{participant_id}/activities", response_model=list[ParticipantActivity])
def participant_activities(participant_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ParticipantActivity]:
    participant = _require_participant(db, current_user, participant_id)
    _, permissions = get_project_permissions(db, current_user.id, participant.project_id)
    manager = IDENTITY_USERS_MANAGE in permissions
    query = db.query(ParticipantFormAssignment).filter_by(participant_id=participant_id)
    if not manager:
        query = query.filter_by(responsible_user_id=current_user.id)
    rows = query.all()
    activities = []
    assigned_templates = set()
    for row in rows:
        template = db.get(BuilderTemplate, row.template_id)
        if not template:
            continue
        assigned_templates.add(row.template_id)
        latest = db.query(RuntimeRecord).filter_by(template_id=row.template_id, participant_id=participant_id).order_by(RuntimeRecord.created_at.desc()).first()
        responsible = db.get(User, row.responsible_user_id)
        activities.append(ParticipantActivity(template_id=row.template_id, template_name=template.name,
            assignment_status=row.status, responsible_user_id=row.responsible_user_id,
            responsible_name=responsible.full_name if responsible else None,
            record_id=latest.id if latest else None, record_status=latest.status if latest else None))
    for item in participant_service.get_participant_history(db, participant_id):
        if item.template_id in assigned_templates:
            continue
        template = db.get(BuilderTemplate, item.template_id)
        if not template or form_access_mode(template) != "legacy":
            continue
        allowed = allowed_form_participant_ids(db, current_user.id, template, review=True)
        if allowed is not None and participant_id not in allowed:
            continue
        activities.append(ParticipantActivity(template_id=template.id, template_name=template.name,
            assignment_status="completed", record_id=item.record_id, record_status=item.status))
        assigned_templates.add(item.template_id)
    return sorted(activities, key=lambda item: item.template_name.casefold())


@router.post("/promote", response_model=ParticipantRead, summary="Base abierta -> base cerrada: enlaza o crea un participante a partir de un registro (ver docs/99)")
def promote_record_to_participant(payload: ParticipantPromoteRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ParticipantRead:
    record = db.query(RuntimeRecord).filter(RuntimeRecord.id == payload.record_id).first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    require_any_project_permission(db, current_user.id, record.project_id, {RECORDS_LINK_PARTICIPANT, RECORDS_REVIEW, RECORDS_APPROVE})
    if not payload.participant_id:
        require_any_project_permission(db, current_user.id, record.project_id, {PARTICIPANTS_CREATE, IDENTITY_USERS_MANAGE})
    return participant_service.promote_record_to_participant(db, record, payload)
