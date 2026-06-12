from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.etl import EtlPipelineCreate, EtlPipelineRead, EtlRuleCreate, EtlRuleRead
from app.services.assignment_service import assignment_service
from app.services.etl_service import etl_service

router = APIRouter()


@router.post("/rules", response_model=EtlRuleRead)
def create_rule(payload: EtlRuleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> EtlRuleRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return etl_service.create_rule(db, payload)


@router.get("/rules/{project_id}", response_model=list[EtlRuleRead])
def list_rules(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[EtlRuleRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return etl_service.list_rules(db, project_id)


@router.post("/pipelines", response_model=EtlPipelineRead)
def create_pipeline(payload: EtlPipelineCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> EtlPipelineRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return etl_service.create_pipeline(db, payload)


@router.get("/pipelines/{project_id}", response_model=list[EtlPipelineRead])
def list_pipelines(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[EtlPipelineRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return etl_service.list_pipelines(db, project_id)
