from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.db.session import get_db
from app.models.approval_flow import ApprovalFlow, ApprovalFlowStep
from app.models.identity import User
from app.schemas.approval_flow import (
    ApprovalFlowCreate,
    ApprovalFlowDetail,
    ApprovalFlowRead,
    ApprovalFlowStepCreate,
    ApprovalFlowStepRead,
    ApprovalFlowStepUpdate,
    ApprovalFlowUpdate,
)
from app.services.approval_flow_service import approval_flow_service
from app.services.assignment_service import assignment_service

router = APIRouter()


@router.post("/", response_model=ApprovalFlowRead)
def create_approval_flow(payload: ApprovalFlowCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ApprovalFlowRead:
    require_project_permission(db, current_user.id, payload.project_id, "records.approve")
    return approval_flow_service.create_flow(db, payload)


@router.get("/{project_id}", response_model=list[ApprovalFlowRead])
def list_approval_flows(project_id: str, template_id: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ApprovalFlowRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return approval_flow_service.list_flows(db, project_id, template_id)


@router.get("/detail/{flow_id}", response_model=ApprovalFlowDetail)
def get_approval_flow(flow_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ApprovalFlowDetail:
    flow = db.get(ApprovalFlow, flow_id)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flujo no encontrado")
    if not assignment_service.user_has_project_access(db, current_user.id, flow.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    detail = approval_flow_service.detail(db, flow_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flujo no encontrado")
    return detail


@router.patch("/{flow_id}", response_model=ApprovalFlowRead)
def update_approval_flow(flow_id: str, payload: ApprovalFlowUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ApprovalFlowRead:
    flow = db.get(ApprovalFlow, flow_id)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flujo no encontrado")
    require_project_permission(db, current_user.id, flow.project_id, "records.approve")
    return approval_flow_service.update_flow(db, flow, payload)


@router.post("/steps", response_model=ApprovalFlowStepRead)
def add_approval_flow_step(payload: ApprovalFlowStepCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ApprovalFlowStepRead:
    flow = db.get(ApprovalFlow, payload.flow_id)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flujo no encontrado")
    require_project_permission(db, current_user.id, flow.project_id, "records.approve")
    return approval_flow_service.add_step(db, payload)


@router.patch("/steps/{step_id}", response_model=ApprovalFlowStepRead)
def update_approval_flow_step(step_id: str, payload: ApprovalFlowStepUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ApprovalFlowStepRead:
    step = db.get(ApprovalFlowStep, step_id)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paso no encontrado")
    flow = db.get(ApprovalFlow, step.flow_id)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flujo no encontrado")
    require_project_permission(db, current_user.id, flow.project_id, "records.approve")
    return approval_flow_service.update_step(db, step, payload)
