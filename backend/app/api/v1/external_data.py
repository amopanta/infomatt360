from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.builder_access import require_template_access
from app.db.session import get_db
from app.models.external_data import ExternalDataSource
from app.models.identity import User
from app.schemas.external_data import BulkPublishRead, BulkPublishRequest, ExternalDataSnapshotCreate, ExternalDataSnapshotRead, ExternalDataSourceCreate, ExternalDataSourceRead, FormDataSourceBindingCreate, FormDataSourceBindingRead, PulldataCacheEntry
from app.services.external_data_service import ExternalDataNotFoundError, external_data_service
from app.services.assignment_service import assignment_service

router = APIRouter()


def require_project_access(db: Session, user_id: str, project_id: str) -> None:
    if not assignment_service.user_has_project_access(db, user_id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")


def require_source_access(db: Session, user_id: str, data_source_id: str) -> ExternalDataSource:
    source = db.query(ExternalDataSource).filter(ExternalDataSource.id == data_source_id).first()
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fuente externa no encontrada")
    require_project_access(db, user_id, source.project_id)
    return source


@router.post("/sources", response_model=ExternalDataSourceRead)
def create_source(payload: ExternalDataSourceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ExternalDataSourceRead:
    require_project_access(db, current_user.id, payload.project_id)
    return external_data_service.create_data_source(db, payload)


@router.get("/sources/{project_id}", response_model=list[ExternalDataSourceRead])
def list_sources(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ExternalDataSourceRead]:
    require_project_access(db, current_user.id, project_id)
    return external_data_service.list_data_sources(db, project_id)


@router.post("/bindings", response_model=FormDataSourceBindingRead)
def bind_source(payload: FormDataSourceBindingCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FormDataSourceBindingRead:
    template = require_template_access(db, current_user.id, payload.template_id)
    source = require_source_access(db, current_user.id, payload.data_source_id)
    if source.project_id != template.project_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La fuente y la plantilla pertenecen a proyectos distintos")
    return external_data_service.bind_data_source(db, payload)


@router.post("/sources/{data_source_id}/snapshots", response_model=ExternalDataSnapshotRead, status_code=status.HTTP_201_CREATED)
def create_snapshot(data_source_id: str, payload: ExternalDataSnapshotCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ExternalDataSnapshotRead:
    """Publica una version normalizada en la cache de la fuente."""
    require_source_access(db, current_user.id, data_source_id)
    try:
        return external_data_service.create_snapshot(db, data_source_id, payload)
    except ExternalDataNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Fuente externa no encontrada") from exc


@router.get("/runtime-cache/{template_id}", response_model=dict[str, PulldataCacheEntry])
def get_runtime_cache(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, PulldataCacheEntry]:
    """Retorna el cache pulldata mas reciente de una plantilla."""
    require_template_access(db, current_user.id, template_id)
    return external_data_service.get_runtime_cache(db, template_id)


@router.post("/bulk-publish", response_model=BulkPublishRead, status_code=status.HTTP_202_ACCEPTED)
def bulk_publish(payload: BulkPublishRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BulkPublishRead:
    """Encola una accion de publicacion para varias plantillas."""
    require_project_access(db, current_user.id, payload.project_id)
    for template_id in payload.target_template_ids:
        template = require_template_access(db, current_user.id, template_id)
        if template.project_id != payload.project_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Una plantilla no pertenece al proyecto indicado")
    return external_data_service.bulk_publish(db, payload, current_user.id)
