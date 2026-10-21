from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import get_project_permissions, require_any_permission, require_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE, ORGANIZATIONS_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.assignment import AssignmentCreate, AssignmentRead
from app.services.assignment_service import assignment_service
from app.services.project_user_admin_service import project_user_admin_service
from app.models.assignment import UserProjectAssignment

router = APIRouter()

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
    # PR #46: además, nadie entrega un rol con permisos que no tiene allí.
    if not _is_platform_admin(db, current_user.id):
        require_project_permission(db, current_user.id, payload.project_id, IDENTITY_USERS_MANAGE)
        if payload.role_id:
            project_user_admin_service._role(db, payload.project_id, payload.role_id, current_user)
    if db.get(User, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if db.query(UserProjectAssignment).filter_by(user_id=payload.user_id, project_id=payload.project_id).first():
        raise HTTPException(status_code=409, detail="El usuario ya tiene una asignación; modifica su acceso desde Usuarios y permisos")
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
