from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import INTEGRATIONS_DONOR_SYNC_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.integrations import (
    IntegrationJobCreate,
    IntegrationJobRead,
    IntegrationMapCreate,
    IntegrationMapRead,
    IntegrationSourceCreate,
    IntegrationSourceRead,
)
from app.services.integration_service import integration_service

router = APIRouter()


def _source_project_id(db: Session, source_id: str) -> str:
    source = integration_service.get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fuente de integracion no encontrada")
    return source.project_id


@router.post("/sources", response_model=IntegrationSourceRead)
def create_source(payload: IntegrationSourceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> IntegrationSourceRead:
    require_project_permission(db, current_user.id, payload.project_id, INTEGRATIONS_DONOR_SYNC_MANAGE)
    return integration_service.create_source(db, payload)


@router.get("/sources/{project_id}", response_model=list[IntegrationSourceRead])
def list_sources(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[IntegrationSourceRead]:
    require_project_permission(db, current_user.id, project_id, INTEGRATIONS_DONOR_SYNC_MANAGE)
    return integration_service.list_sources(db, project_id)


@router.post("/maps", response_model=IntegrationMapRead)
def create_map(payload: IntegrationMapCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> IntegrationMapRead:
    project_id = _source_project_id(db, payload.source_id)
    require_project_permission(db, current_user.id, project_id, INTEGRATIONS_DONOR_SYNC_MANAGE)
    return integration_service.create_map(db, payload)


@router.get("/maps/{source_id}", response_model=list[IntegrationMapRead])
def list_maps(source_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[IntegrationMapRead]:
    project_id = _source_project_id(db, source_id)
    require_project_permission(db, current_user.id, project_id, INTEGRATIONS_DONOR_SYNC_MANAGE)
    return integration_service.list_maps(db, source_id)


@router.post("/jobs", response_model=IntegrationJobRead)
def create_job(payload: IntegrationJobCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> IntegrationJobRead:
    project_id = _source_project_id(db, payload.source_id)
    require_project_permission(db, current_user.id, project_id, INTEGRATIONS_DONOR_SYNC_MANAGE)
    return integration_service.create_job(db, payload)


@router.get("/jobs/{source_id}", response_model=list[IntegrationJobRead])
def list_jobs(source_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[IntegrationJobRead]:
    project_id = _source_project_id(db, source_id)
    require_project_permission(db, current_user.id, project_id, INTEGRATIONS_DONOR_SYNC_MANAGE)
    return integration_service.list_jobs(db, source_id)
