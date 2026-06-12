from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.mirror import MirrorPlanCreate, MirrorPlanRead, MirrorTargetCreate, MirrorTargetRead
from app.services.assignment_service import assignment_service
from app.services.mirror_service import mirror_service

router = APIRouter()


@router.post("/targets", response_model=MirrorTargetRead)
def create_target(payload: MirrorTargetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> MirrorTargetRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return mirror_service.create_target(db, payload)


@router.get("/targets/{project_id}", response_model=list[MirrorTargetRead])
def list_targets(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[MirrorTargetRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return mirror_service.list_targets(db, project_id)


@router.post("/plans", response_model=MirrorPlanRead)
def create_plan(payload: MirrorPlanCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> MirrorPlanRead:
    return mirror_service.create_plan(db, payload)


@router.get("/plans/{target_id}", response_model=list[MirrorPlanRead])
def list_plans(target_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[MirrorPlanRead]:
    return mirror_service.list_plans(db, target_id)
