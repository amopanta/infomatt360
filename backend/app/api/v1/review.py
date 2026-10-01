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

router = APIRouter()


@router.post("/records/{record_id}/reopen", response_model=ReviewActionRead)
def reopen_approved_record(record_id: str, payload: ReopenApprovedRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReviewActionRead:
    project_id = review_service.get_record_project_id(db, record_id)
    if not project_id or not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    require_any_project_permission(db, current_user.id, project_id, {IDENTITY_USERS_MANAGE})
    require_record_id_territory(db, current_user.id, record_id)
    try:
        return review_service.reopen_approved(db, record_id, current_user.id, payload.reason)
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
