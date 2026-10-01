"""Form access and participant assignments."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_current_user
from app.api.permissions import allowed_form_participant_ids, participant_visible, require_any_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE, PARTICIPANTS_CREATE, RECORDS_WRITE
from app.core.time import utc_now
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.builder import BuilderTemplate
from app.models.form_assignment import ParticipantFormAssignment
from app.models.identity import User
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord
from app.services.assignment_service import assignment_service
from app.services.form_assignment_service import upsert_assignment, visible_assignment
from app.services.participant_source_service import configured_source, eligible_participants

router = APIRouter()


class AssignmentWrite(BaseModel):
    participant_id: str
    responsible_user_id: str


class AssignmentRead(BaseModel):
    id: str
    template_id: str
    participant_id: str
    participant_name: str
    responsible_user_id: str
    responsible_name: str
    status: str
    created_at: datetime


class OpenParticipantCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=220)
    document_id: str | None = Field(default=None, max_length=80)
    external_code: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    municipality: str | None = Field(default=None, max_length=120)


def _template(db: Session, user: User, template_id: str) -> BuilderTemplate:
    template = db.get(BuilderTemplate, template_id)
    if not template or not assignment_service.user_has_project_access(db, user.id, template.project_id):
        raise HTTPException(status_code=404, detail="Formulario no encontrado")
    return template


def _read(db: Session, row: ParticipantFormAssignment) -> AssignmentRead:
    participant = db.get(Participant, row.participant_id)
    responsible = db.get(User, row.responsible_user_id)
    return AssignmentRead(id=row.id, template_id=row.template_id, participant_id=row.participant_id,
                          participant_name=participant.full_name if participant else "Participante eliminado",
                          responsible_user_id=row.responsible_user_id,
                          responsible_name=responsible.full_name if responsible else "Usuario eliminado",
                          status=row.status, created_at=row.created_at)


@router.get("/templates/{template_id}", response_model=list[AssignmentRead])
def list_assignments(template_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[AssignmentRead]:
    template = _template(db, user, template_id)
    allowed = allowed_form_participant_ids(db, user.id, template)
    query = db.query(ParticipantFormAssignment).filter_by(template_id=template_id)
    if allowed is not None:
        query = query.filter(ParticipantFormAssignment.participant_id.in_(allowed))
    return [_read(db, row) for row in query.order_by(ParticipantFormAssignment.created_at).all()]


@router.get("/templates/{template_id}/candidates")
def assignment_candidates(template_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict[str, str | None]]:
    template = _template(db, user, template_id)
    require_any_project_permission(db, user.id, template.project_id, {IDENTITY_USERS_MANAGE})
    return [{"id": row.id, "full_name": row.full_name, "document_id": row.document_id,
             "external_code": row.external_code} for row in eligible_participants(db, template, enforce_assignments=False)]


@router.post("/templates/{template_id}", response_model=AssignmentRead)
def assign_participant(template_id: str, payload: AssignmentWrite, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> AssignmentRead:
    template = _template(db, user, template_id)
    require_any_project_permission(db, user.id, template.project_id, {IDENTITY_USERS_MANAGE})
    if configured_source(template).access_mode == "legacy":
        raise HTTPException(status_code=422, detail="Selecciona primero el modo abierto o cerrado del formulario")
    if payload.participant_id not in {person.id for person in eligible_participants(db, template, enforce_assignments=False)}:
        raise HTTPException(status_code=422, detail="El participante no cumple la fuente configurada")
    participant = db.get(Participant, payload.participant_id)
    if not participant_visible(db, payload.responsible_user_id, participant):
        raise HTTPException(status_code=422, detail="El responsable no puede acceder al territorio del participante")
    row = upsert_assignment(db, template, payload.participant_id, payload.responsible_user_id, user.id)
    db.add(AuditLog(project_id=template.project_id, user_id=user.id, module="participants", action="assign_form",
                    entity_type="participant_form_assignment", entity_id=row.id,
                    after_json=json.dumps({"template_id": template_id, "participant_id": payload.participant_id,
                                           "responsible_user_id": payload.responsible_user_id})))
    db.commit()
    db.refresh(row)
    return _read(db, row)


@router.delete("/templates/{template_id}/{participant_id}")
def remove_assignment(template_id: str, participant_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, bool]:
    template = _template(db, user, template_id)
    require_any_project_permission(db, user.id, template.project_id, {IDENTITY_USERS_MANAGE})
    row = db.query(ParticipantFormAssignment).filter_by(template_id=template_id, participant_id=participant_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    if db.query(RuntimeRecord.id).filter_by(template_id=template_id, participant_id=participant_id).first():
        raise HTTPException(status_code=409, detail="La actividad tiene respuestas; reasígnala o ciérrala en lugar de eliminarla")
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.post("/templates/{template_id}/{participant_id}/start", response_model=AssignmentRead)
def start_assignment(template_id: str, participant_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> AssignmentRead:
    template = _template(db, user, template_id)
    require_any_project_permission(db, user.id, template.project_id, {RECORDS_WRITE})
    row = visible_assignment(db, template, participant_id, user.id)
    if row.responsible_user_id != user.id or row.status not in {"assigned", "in_progress"}:
        raise HTTPException(status_code=403, detail="Actividad no disponible para este responsable")
    if db.query(RuntimeRecord.id).filter(RuntimeRecord.template_id == template_id,
        RuntimeRecord.participant_id == participant_id,
        RuntimeRecord.status.notin_(["voided", "cancelled"])).first():
        raise HTTPException(status_code=409, detail="Ya existe una respuesta; abre el registro para consultarlo o corregirlo")
    if row.status == "assigned":
        row.status = "in_progress"
        row.updated_at = utc_now()
        db.commit()
    return _read(db, row)


@router.post("/templates/{template_id}/participants", response_model=AssignmentRead)
def create_participant_in_open_form(template_id: str, payload: OpenParticipantCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> AssignmentRead:
    template = _template(db, user, template_id)
    require_any_project_permission(db, user.id, template.project_id, {RECORDS_WRITE})
    require_any_project_permission(db, user.id, template.project_id, {PARTICIPANTS_CREATE, IDENTITY_USERS_MANAGE})
    source = configured_source(template)
    if source.access_mode != "open":
        raise HTTPException(status_code=403, detail="Este formulario no permite participantes nuevos")
    key = payload.document_id if source.participant_key_field == "document_id" else payload.external_code
    if not key or not key.strip():
        raise HTTPException(status_code=422, detail="Ingresa la llave configurada para este formulario")
    existing = db.query(Participant).filter(Participant.project_id == template.project_id,
        func.lower(getattr(Participant, source.participant_key_field)) == key.strip().lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe un participante con esa llave")
    metadata = {"department": (payload.department or "").strip(), "municipality": (payload.municipality or "").strip()}
    participant = Participant(project_id=template.project_id, full_name=payload.full_name.strip(),
        document_id=(payload.document_id or "").strip() or None,
        external_code=(payload.external_code or "").strip() or None,
        metadata_json=json.dumps(metadata, ensure_ascii=False))
    if not participant_visible(db, user.id, participant):
        raise HTTPException(status_code=403, detail="Fuera del territorio asignado")
    db.add(participant)
    db.flush()
    row = ParticipantFormAssignment(project_id=template.project_id, template_id=template.id,
        participant_id=participant.id, responsible_user_id=user.id, status="assigned", assigned_by=user.id)
    db.add(row)
    db.add(AuditLog(project_id=template.project_id, user_id=user.id, module="participants", action="create_in_form",
                    entity_type="participant", entity_id=participant.id,
                    after_json=json.dumps({"template_id": template_id, "participant_id": participant.id})))
    db.commit()
    db.refresh(row)
    return _read(db, row)
