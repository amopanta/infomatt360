"""Participant-to-form assignments and capture access rules."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.permissions import allowed_form_participant_ids, form_access_mode, get_project_permissions
from app.core.permissions import IDENTITY_USERS_MANAGE
from app.core.time import utc_now
from app.models.builder import BuilderTemplate
from app.models.form_assignment import ParticipantFormAssignment
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord
from app.services.assignment_service import assignment_service


def require_capture_assignment(db: Session, template: BuilderTemplate, participant_id: str | None, user_id: str | None) -> ParticipantFormAssignment | None:
    if form_access_mode(template) == "legacy":
        return None
    if not participant_id:
        raise ValueError("Selecciona un participante asignado a este formulario")
    row = db.query(ParticipantFormAssignment).filter_by(template_id=template.id, participant_id=participant_id).first()
    if row is None:
        raise ValueError("El participante no está asignado a este formulario")
    if row.status in {"completed", "closed"}:
        raise ValueError("Esta actividad ya tiene una respuesta enviada o aprobada")
    existing = db.query(RuntimeRecord.id).filter(RuntimeRecord.template_id == template.id,
        RuntimeRecord.participant_id == participant_id,
        RuntimeRecord.status.notin_(["voided", "cancelled"])).first()
    if existing:
        raise ValueError("Ya existe una respuesta para esta actividad. Corrige el registro existente si fue devuelto")
    if user_id is None:
        raise ValueError("Esta captura requiere un responsable autenticado")
    _, permissions = get_project_permissions(db, user_id, template.project_id)
    if row.responsible_user_id != user_id and IDENTITY_USERS_MANAGE not in permissions:
        raise ValueError("Este participante está asignado a otro responsable")
    return row


def upsert_assignment(db: Session, template: BuilderTemplate, participant_id: str, user_id: str, actor_id: str) -> ParticipantFormAssignment:
    participant = db.get(Participant, participant_id)
    if not participant or participant.project_id != template.project_id or participant.status != "active":
        raise HTTPException(status_code=422, detail="Participante no activo en este proyecto")
    if not assignment_service.user_has_project_access(db, user_id, template.project_id):
        raise HTTPException(status_code=422, detail="El responsable no tiene acceso al proyecto")
    row = db.query(ParticipantFormAssignment).filter_by(template_id=template.id, participant_id=participant_id).first()
    if row is None:
        row = ParticipantFormAssignment(project_id=template.project_id, template_id=template.id, participant_id=participant_id,
                                        responsible_user_id=user_id, status="assigned", assigned_by=actor_id)
        db.add(row)
    else:
        row.responsible_user_id = user_id
        row.updated_at = utc_now()
    db.flush()
    return row


def visible_assignment(db: Session, template: BuilderTemplate, participant_id: str, user_id: str) -> ParticipantFormAssignment:
    allowed = allowed_form_participant_ids(db, user_id, template)
    if allowed is not None and participant_id not in allowed:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    row = db.query(ParticipantFormAssignment).filter_by(template_id=template.id, participant_id=participant_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    return row


def set_assignment_status(db: Session, template_id: str, participant_id: str | None, status: str) -> None:
    if not participant_id:
        return
    row = db.query(ParticipantFormAssignment).filter_by(template_id=template_id, participant_id=participant_id).first()
    if row:
        row.status = status
        row.updated_at = utc_now()
