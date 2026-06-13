from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.external_data import ExternalDataSourceCreate, ExternalDataSourceRead, FormDataSourceBindingCreate, FormDataSourceBindingRead
from app.services.external_data_service import external_data_service

router = APIRouter()


@router.post("/sources", response_model=ExternalDataSourceRead)
def create_source(payload: ExternalDataSourceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ExternalDataSourceRead:
    return external_data_service.create_data_source(db, payload)


@router.get("/sources/{project_id}", response_model=list[ExternalDataSourceRead])
def list_sources(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ExternalDataSourceRead]:
    return external_data_service.list_data_sources(db, project_id)


@router.post("/bindings", response_model=FormDataSourceBindingRead)
def bind_source(payload: FormDataSourceBindingCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FormDataSourceBindingRead:
    return external_data_service.bind_data_source(db, payload)
