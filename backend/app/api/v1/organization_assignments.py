"""Asignacion de roles a nivel de Organizacion completa (ver docs/101).

Un rol asignado aqui aplica a todos los proyectos de la organizacion, sin
necesitar una asignacion individual por proyecto -- es como se representa el
rol de "Administrador nacional" del Documento Maestro de Requerimientos §21.
Protegido con `organizations.manage`, el mismo permiso que ya protege la
creacion de roles (`POST /identity/roles`).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_any_permission
from app.core.permissions import ORGANIZATIONS_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.assignment import OrganizationAssignmentCreate, OrganizationAssignmentRead
from app.services.assignment_service import assignment_service

router = APIRouter()


@router.post("/", response_model=OrganizationAssignmentRead, summary="Asignar usuario a organizacion")
def create_organization_assignment(
    payload: OrganizationAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationAssignmentRead:
    require_any_permission(db, current_user.id, {ORGANIZATIONS_MANAGE})
    return assignment_service.create_organization_assignment(db, payload)


@router.get("/", response_model=list[OrganizationAssignmentRead], summary="Listar asignaciones de organizacion")
def list_organization_assignments(
    organization_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OrganizationAssignmentRead]:
    require_any_permission(db, current_user.id, {ORGANIZATIONS_MANAGE})
    return assignment_service.list_organization_assignments(db, organization_id)
