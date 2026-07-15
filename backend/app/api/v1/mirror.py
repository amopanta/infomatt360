from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import MIRROR_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.mirror import (
    MirrorPlanCreate,
    MirrorPlanRead,
    MirrorRunRead,
    MirrorTargetConnect,
    MirrorTargetRead,
    MirrorTargetTestConnectionResult,
)
from app.services.mirror_service import mirror_service

router = APIRouter()


def _require_target_access(db: Session, user_id: str, target_id: str) -> str:
    """Resuelve el project_id del target y exige mirror.manage sobre el. Devuelve el project_id."""
    target = mirror_service.get_target(db, target_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destino de espejo no encontrado")
    require_project_permission(db, user_id, target.project_id, MIRROR_MANAGE)
    return target.project_id


def _require_plan_access(db: Session, user_id: str, plan_id: str) -> str:
    """Resuelve el project_id del plan (via su target) y exige mirror.manage sobre el."""
    plan = mirror_service.get_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan de espejo no encontrado")
    return _require_target_access(db, user_id, plan.target_id)


@router.post("/targets", response_model=MirrorTargetRead)
def create_target(payload: MirrorTargetConnect, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> MirrorTargetRead:
    require_project_permission(db, current_user.id, payload.project_id, MIRROR_MANAGE)
    return mirror_service.connect_target(db, payload)


@router.get("/targets/{project_id}", response_model=list[MirrorTargetRead])
def list_targets(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[MirrorTargetRead]:
    require_project_permission(db, current_user.id, project_id, MIRROR_MANAGE)
    return mirror_service.list_targets(db, project_id)


@router.post("/targets/{target_id}/test-connection", response_model=MirrorTargetTestConnectionResult)
def test_connection(target_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> MirrorTargetTestConnectionResult:
    _require_target_access(db, current_user.id, target_id)
    result = mirror_service.test_connection(db, target_id)
    if not result.success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.message)
    return result


@router.post("/plans", response_model=MirrorPlanRead)
def create_plan(payload: MirrorPlanCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> MirrorPlanRead:
    _require_target_access(db, current_user.id, payload.target_id)
    return mirror_service.create_plan(db, payload)


@router.get("/plans/{target_id}", response_model=list[MirrorPlanRead])
def list_plans(target_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[MirrorPlanRead]:
    _require_target_access(db, current_user.id, target_id)
    return mirror_service.list_plans(db, target_id)


@router.post("/plans/{plan_id}/run", response_model=MirrorRunRead)
def run_plan(plan_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> MirrorRunRead:
    _require_plan_access(db, current_user.id, plan_id)
    return mirror_service.run_plan(db, plan_id, current_user.id)


@router.get("/plans/{plan_id}/runs", response_model=list[MirrorRunRead])
def list_runs(plan_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[MirrorRunRead]:
    _require_plan_access(db, current_user.id, plan_id)
    return mirror_service.list_runs(db, plan_id)
