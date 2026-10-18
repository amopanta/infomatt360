from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import get_project_permissions, require_any_permission, require_project_permission
from app.core.permissions import (
    AI_AUDIT_MANAGE, BACKUPS_MANAGE, ERP_MANAGE, IDENTITY_USERS_MANAGE, INTEGRATIONS_API_KEYS_MANAGE,
    INTEGRATIONS_DONOR_SYNC_MANAGE, MIRROR_MANAGE, ORGANIZATIONS_BRANDING_MANAGE, ORGANIZATIONS_MANAGE,
    ORGANIZATIONS_TENANT_CLEAN, STORAGE_MANAGE, SUPPORT_TICKETS_MANAGE,
)
from app.db.session import get_db
from app.models.assignment import UserProjectAssignment
from app.models.identity import Role, User
from app.schemas.assignment import AssignmentCreate, AssignmentRead
from app.services.assignment_service import assignment_service

router = APIRouter()

# Permisos administrativos y de plataforma: solo los entrega quien ya los
# tiene. Los de captura y revisión (records.*, builder.write, reports...) sí
# los asigna un encargado de usuarios a su equipo.
ADMIN_PERMISSIONS = {
    ORGANIZATIONS_MANAGE, ORGANIZATIONS_TENANT_CLEAN, ORGANIZATIONS_BRANDING_MANAGE, BACKUPS_MANAGE, MIRROR_MANAGE,
    STORAGE_MANAGE, ERP_MANAGE, AI_AUDIT_MANAGE, INTEGRATIONS_API_KEYS_MANAGE, INTEGRATIONS_DONOR_SYNC_MANAGE,
    SUPPORT_TICKETS_MANAGE,
}


def _is_platform_admin(db: Session, user_id: str) -> bool:
    """organizations.manage es de plataforma (docs/60): gestiona todos los proyectos."""
    try:
        require_any_permission(db, user_id, {ORGANIZATIONS_MANAGE})
        return True
    except HTTPException:
        return False


@router.post("/", response_model=AssignmentRead, summary="Asignar usuario a proyecto")
def create_assignment(
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssignmentRead:
    # H11: antes bastaba identity.users.manage en CUALQUIER proyecto para
    # asignar a cualquiera (incluso a uno mismo) en cualquier otro proyecto.
    if not _is_platform_admin(db, current_user.id):
        require_project_permission(db, current_user.id, payload.project_id, IDENTITY_USERS_MANAGE)
        # Tampoco se puede entregar un permiso administrativo que uno no tiene allí.
        if payload.role_id:
            role = db.get(Role, payload.role_id)
            if role is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Rol no encontrado")
            granted = {item.strip() for item in role.permissions.split(",") if item.strip()}
            _, own = get_project_permissions(db, current_user.id, payload.project_id)
            if (granted & ADMIN_PERMISSIONS) - own:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puede asignar un rol con permisos administrativos que usted no tiene en el proyecto")
    return assignment_service.create_assignment(db, payload)


@router.get("/", response_model=list[AssignmentRead], summary="Listar asignaciones")
def list_assignments(
    project_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AssignmentRead]:
    require_any_permission(db, current_user.id, {IDENTITY_USERS_MANAGE, ORGANIZATIONS_MANAGE})
    if _is_platform_admin(db, current_user.id):
        return assignment_service.list_assignments(db, project_id)
    if project_id:
        require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
        return assignment_service.list_assignments(db, project_id)
    # Sin proyecto: solo los proyectos que la persona administra.
    managed = [
        row.project_id
        for row in db.query(UserProjectAssignment).filter(UserProjectAssignment.user_id == current_user.id, UserProjectAssignment.status == "active").all()
        if IDENTITY_USERS_MANAGE in get_project_permissions(db, current_user.id, row.project_id)[1]
    ]
    return [item for item in assignment_service.list_assignments(db) if item.project_id in set(managed)]
