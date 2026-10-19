from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_any_project_permission, require_form_participant_access, require_record_id_territory
from app.db.session import get_db
from app.models.identity import User
from app.schemas.approval_flow import ReviewApprovalProgress, ReviewFlowComparison, ReviewNextAction
from app.schemas.review import ReopenApprovedRequest, ReviewActionCreate, ReviewActionRead
from app.core.permissions import IDENTITY_USERS_MANAGE, RECORDS_WRITE
from app.models.runtime_record import RuntimeRecord
from app.services.approval_flow_service import approval_flow_service
from app.services.assignment_service import assignment_service
from app.services.review_service import review_service
from app.models.files import FileAsset
from app.models.review import ReviewObservation
from app.models.runtime_record import RuntimeRecordValue
from app.schemas.review import ObservationUpdate, ReturnRecordRequest
from app.services.correction_service import (
    correction_package, correction_recipient, observation_to_dict, return_record, update_observation,
)
from app.core.permissions import RECORDS_APPROVE, RECORDS_REVIEW

router = APIRouter()


@router.post("/records/{record_id}/reopen", response_model=ReviewActionRead)
def reopen_approved_record(record_id: str, payload: ReopenApprovedRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReviewActionRead:
    project_id = review_service.get_record_project_id(db, record_id)
    if not project_id or not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    require_any_project_permission(db, current_user.id, project_id, {IDENTITY_USERS_MANAGE})
    require_record_id_territory(db, current_user.id, record_id)
    try:
        return review_service.reopen_approved(db, record_id, current_user.id, payload.reason, payload.assignee_user_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

REVIEW_STATUS_PERMISSIONS: dict[str, set[str]] = {
    "under_review": {"records.review", "records.approve"},
    "tech_approved": {"records.review", "records.approve"},
    "coordinator_approved": {"records.coordinate", "records.approve"},
    "returned": {"records.review", "records.approve"},
    "approved": {"records.approve"},
    "rejected": {"records.approve"},
    "archived": {"records.approve"},
    "synced": {"records.approve"},
    "voided": {"records.void"},
}


@router.post("/actions", response_model=ReviewActionRead)
def apply_review_action(payload: ReviewActionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReviewActionRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    require_record_id_territory(db, current_user.id, payload.record_id)
    context = review_service.get_record_review_context(db, payload.record_id)
    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    _project_id, template_id, _current_status, snapshot_json = context
    if payload.to_status in {"corrected", "submitted"} and _current_status in {"returned", "corrected"}:
        require_any_project_permission(db, current_user.id, payload.project_id, {RECORDS_WRITE})
        record = db.get(RuntimeRecord, payload.record_id)
        if record:
            require_form_participant_access(db, current_user.id, record.template_id, record.participant_id)
            # docs/141: el reenvío lo hace solo quien debía corregir
            if current_user.id != correction_recipient(record):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo la persona designada para corregir puede reenviar este registro")
    configured_step = approval_flow_service.find_step_for_status(db, payload.project_id, template_id, payload.to_status, snapshot_json)
    if configured_step:
        if not approval_flow_service.user_can_execute_step(db, current_user.id, payload.project_id, configured_step):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente para el paso configurado")
    else:
        required_permissions = REVIEW_STATUS_PERMISSIONS.get(payload.to_status)
        if required_permissions:
            require_any_project_permission(db, current_user.id, payload.project_id, required_permissions)
    try:
        return review_service.apply_action(db, payload, current_user.id, configured_step)
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_404_NOT_FOUND if "no encontrado" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=detail) from exc


@router.get("/records/{record_id}/actions", response_model=list[ReviewActionRead])
def list_review_actions(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ReviewActionRead]:
    project_id = review_service.get_record_project_id(db, record_id)
    if not project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    require_record_id_territory(db, current_user.id, record_id)
    return review_service.list_actions(db, record_id)


@router.get("/records/{record_id}/next-actions", response_model=list[ReviewNextAction])
def review_next_actions(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ReviewNextAction]:
    context = review_service.get_record_review_context(db, record_id)
    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    project_id, template_id, current_status, snapshot_json = context
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    require_record_id_territory(db, current_user.id, record_id)
    return approval_flow_service.next_actions(db, project_id, template_id, current_status, snapshot_json)


@router.get("/records/{record_id}/approval-progress", response_model=list[ReviewApprovalProgress])
def review_approval_progress(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ReviewApprovalProgress]:
    context = review_service.get_record_review_context(db, record_id)
    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    project_id, template_id, current_status, snapshot_json = context
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    require_record_id_territory(db, current_user.id, record_id)
    return approval_flow_service.approval_progress(db, project_id, template_id, current_status, record_id, snapshot_json)


@router.get("/records/{record_id}/flow-comparison", response_model=ReviewFlowComparison)
def review_flow_comparison(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReviewFlowComparison:
    context = review_service.get_record_review_context(db, record_id)
    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    project_id, template_id, _current_status, snapshot_json = context
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    require_record_id_territory(db, current_user.id, record_id)
    return approval_flow_service.flow_comparison(db, project_id, template_id, snapshot_json)


# -- Devoluciones con destinatario y observaciones (docs/141) --

REVIEWER_PERMISSIONS = {RECORDS_REVIEW, RECORDS_APPROVE}


def _runtime_record_for_review(db: Session, user: User, record_id: str) -> RuntimeRecord:
    record = db.get(RuntimeRecord, record_id)
    if record is None or not assignment_service.user_has_project_access(db, user.id, record.project_id):
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    require_record_id_territory(db, user.id, record_id)
    return record


@router.post("/records/{record_id}/return")
def return_record_with_observations(record_id: str, payload: ReturnRecordRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Devuelve al autor o reasigna la corrección a otro gestor, con
    observaciones por pregunta o integrante de un REPEAT."""
    record = _runtime_record_for_review(db, current_user, record_id)
    require_any_project_permission(db, current_user.id, record.project_id, REVIEWER_PERMISSIONS)
    try:
        action, observations = return_record(db, record, current_user.id, payload.notes.strip(), payload.assignee_user_id,
                                             [o.model_dump() for o in payload.observations], review_service.apply_action)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record = db.get(RuntimeRecord, record_id)
    return {"action": action, "correction_user_id": correction_recipient(record), "observations": [observation_to_dict(o) for o in observations]}


@router.get("/records/{record_id}/observations")
def list_record_observations(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    record = _runtime_record_for_review(db, current_user, record_id)
    require_form_participant_access(db, current_user.id, record.template_id, record.participant_id, review=True)
    rows = db.query(ReviewObservation).filter(ReviewObservation.record_id == record_id).order_by(ReviewObservation.created_at).all()
    return [observation_to_dict(row) for row in rows]


@router.patch("/observations/{observation_id}")
def change_observation(observation_id: str, payload: ObservationUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    observation = db.get(ReviewObservation, observation_id)
    if observation is None:
        raise HTTPException(status_code=404, detail="Observación no encontrada")
    _runtime_record_for_review(db, current_user, observation.record_id)
    from app.api.permissions import get_project_permissions
    _, permissions = get_project_permissions(db, current_user.id, observation.project_id)
    try:
        row = update_observation(db, observation, current_user.id, payload.status, payload.note,
                                 is_reviewer=not permissions.isdisjoint(REVIEWER_PERMISSIONS))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return observation_to_dict(row)


@router.get("/my-corrections/{project_id}")
def my_corrections(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Registros devueltos que debe corregir el usuario (autor sin reasignar,
    o destinatario designado). La app los baja para corregir sin red."""
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    rows = db.query(RuntimeRecord).filter(RuntimeRecord.project_id == project_id, RuntimeRecord.status.in_(["returned", "corrected"])).all()
    result = []
    for record in rows:
        if correction_recipient(record) != current_user.id:
            continue
        pending = db.query(ReviewObservation).filter(ReviewObservation.record_id == record.id,
                                                     ReviewObservation.status.in_(["pending", "in_correction"])).count()
        result.append({"record_id": record.id, "template_id": record.template_id, "participant_id": record.participant_id,
                       "status": record.status, "lock_version": record.lock_version, "content_hash": record.content_hash,
                       "returned_at": record.returned_at, "author_id": record.submitted_by, "pending_observations": pending})
    return result


@router.get("/records/{record_id}/correction-package")
def record_correction_package(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Respuestas, versión, observaciones y manifiesto de adjuntos del registro
    que el usuario debe corregir (docs/141 §7)."""
    record = _runtime_record_for_review(db, current_user, record_id)
    if record.status not in {"returned", "corrected"} or correction_recipient(record) != current_user.id:
        raise HTTPException(status_code=404, detail="No tiene una corrección asignada para este registro")
    values = db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id == record_id).all()
    files = db.query(FileAsset).filter(FileAsset.record_id == record_id).all()
    return correction_package(db, record, values, files)
