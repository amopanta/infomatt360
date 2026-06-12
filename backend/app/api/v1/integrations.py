from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.integrations import IntegrationJobCreate, IntegrationJobRead, IntegrationMapCreate, IntegrationMapRead, IntegrationSourceCreate, IntegrationSourceRead
from app.services.assignment_service import assignment_service
from app.services.integration_service import integration_service

router = APIRouter()


@router.post("/sources", response_model=IntegrationSourceRead)
def create_source(payload: IntegrationSourceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> IntegrationSourceRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return integration_service.create_source(db, payload)


@router.get("/sources/{project_id}", response_model=list[IntegrationSourceRead])
def list_sources(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[IntegrationSourceRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return integration_service.list_sources(db, project_id)


@router.post("/maps", response_model=IntegrationMapRead)
def create_map(payload: IntegrationMapCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> IntegrationMapRead:
    return integration_service.create_map(db, payload)


@router.post("/jobs", response_model=IntegrationJobRead)
def create_job(payload: IntegrationJobCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> IntegrationJobRead:
    return integration_service.create_job(db, payload)
