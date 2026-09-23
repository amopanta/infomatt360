from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.builder_access import require_column_access, require_template_access, template_id_for_column
from app.api.permissions import require_project_permission
from app.core.permissions import BUILDER_WRITE
from app.db.session import get_db
from app.models.identity import User
from app.models.builder import BuilderComponent
from app.schemas.builder import BuilderComponentCreate, BuilderComponentPropertiesUpdate, BuilderComponentRead, BuilderTemplateCreate, BuilderTemplatePropertiesUpdate, BuilderTemplateRead, BuilderTemplateScheduleUpdate, BuilderTemplateStatusUpdate, BuilderVersionCreate, BuilderVersionRead, ParticipantSourceUpdate
from app.services.participant_source_service import eligible_participants
from app.schemas.participants import ParticipantRead
from app.services.assignment_service import assignment_service
from app.services.builder_service import builder_service

router = APIRouter()


@router.post("/templates", response_model=BuilderTemplateRead)
def create_template(payload: BuilderTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    """Crea una plantilla visual dentro de un proyecto autorizado."""
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    require_project_permission(db, current_user.id, payload.project_id, BUILDER_WRITE)
    return builder_service.create_template(db, payload, current_user.id)


@router.get("/templates/{project_id}", response_model=list[BuilderTemplateRead])
def list_templates(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderTemplateRead]:
    """Lista las plantillas visuales de un proyecto autorizado."""
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return builder_service.list_templates(db, project_id)


@router.get("/templates/detail/{template_id}", response_model=BuilderTemplateRead)
def get_template_detail(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    require_template_access(db, current_user.id, template_id)
    return builder_service.get_template(db, template_id)


@router.patch("/templates/detail/{template_id}/status", response_model=BuilderTemplateRead)
def update_template_status(template_id: str, payload: BuilderTemplateStatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    template = require_template_access(db, current_user.id, template_id)
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    return builder_service.set_template_status(db, template_id, payload.status)


@router.patch("/templates/detail/{template_id}/properties", response_model=BuilderTemplateRead)
def update_template_properties(template_id: str, payload: BuilderTemplatePropertiesUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    template = require_template_access(db, current_user.id, template_id)
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    return builder_service.set_template_properties(db, template_id, payload)


@router.patch("/templates/detail/{template_id}/schedule", response_model=BuilderTemplateRead)
def update_template_schedule(template_id: str, payload: BuilderTemplateScheduleUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    template = require_template_access(db, current_user.id, template_id)
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    return builder_service.set_template_schedule(db, template_id, payload.starts_at, payload.ends_at)


@router.patch("/templates/detail/{template_id}/participant-source", response_model=BuilderTemplateRead)
def update_participant_source(template_id: str, payload: ParticipantSourceUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    template = require_template_access(db, current_user.id, template_id)
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    return builder_service.set_participant_source(db, template_id, payload.source)


@router.get("/templates/detail/{template_id}/eligible-participants", response_model=list[ParticipantRead])
def get_eligible_participants(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ParticipantRead]:
    template = require_template_access(db, current_user.id, template_id)
    return [ParticipantRead.model_validate(item, from_attributes=True) for item in eligible_participants(db, template)]


@router.post("/components", response_model=BuilderComponentRead)
def add_component(payload: BuilderComponentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderComponentRead:
    """Agrega un componente o campo a una plantilla.

    El campo puede quedar asociado a una columna para que el Runtime lo ubique
    correctamente dentro del layout responsive.
    """
    require_template_access(db, current_user.id, payload.template_id)
    if payload.column_id:
        column = require_column_access(db, current_user.id, payload.column_id)
        if template_id_for_column(db, column) != payload.template_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La columna no pertenece a la plantilla")
    return builder_service.add_component(db, payload)


@router.get("/components/{template_id}", response_model=list[BuilderComponentRead])
def list_components(template_id: str, column_id: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderComponentRead]:
    """Lista componentes de una plantilla, opcionalmente por columna."""
    require_template_access(db, current_user.id, template_id)
    if column_id:
        column = require_column_access(db, current_user.id, column_id)
        if template_id_for_column(db, column) != template_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La columna no pertenece a la plantilla")
    return builder_service.list_components(db, template_id, column_id)


@router.patch("/components/detail/{component_id}", response_model=BuilderComponentRead)
def update_component_properties(component_id: str, payload: BuilderComponentPropertiesUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderComponentRead:
    component = db.get(BuilderComponent, component_id)
    if component is None:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")
    template = require_template_access(db, current_user.id, component.template_id)
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    return builder_service.set_component_properties(db, component_id, payload)


@router.post("/versions", response_model=BuilderVersionRead)
def create_version(payload: BuilderVersionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderVersionRead:
    """Guarda una version JSON de una plantilla."""
    require_template_access(db, current_user.id, payload.template_id)
    return builder_service.create_version(db, payload)
