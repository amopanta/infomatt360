from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.builder import BuilderComponentCreate, BuilderComponentRead, BuilderTemplateCreate, BuilderTemplateRead, BuilderVersionCreate, BuilderVersionRead
from app.services.assignment_service import assignment_service
from app.services.builder_service import builder_service

router = APIRouter()


@router.post("/templates", response_model=BuilderTemplateRead)
def create_template(payload: BuilderTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return builder_service.create_template(db, payload)


@router.get("/templates/{project_id}", response_model=list[BuilderTemplateRead])
def list_templates(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderTemplateRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return builder_service.list_templates(db, project_id)


@router.post("/components", response_model=BuilderComponentRead)
def add_component(payload: BuilderComponentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderComponentRead:
    return builder_service.add_component(db, payload)


@router.post("/versions", response_model=BuilderVersionRead)
def create_version(payload: BuilderVersionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderVersionRead:
    return builder_service.create_version(db, payload)
