from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE
from app.db.session import get_db
from app.models.identity import Project, User
from app.schemas.assignment import AssignmentCreate, AssignmentRead
from app.services.assignment_service import assignment_service
from app.services.project_user_admin_service import project_user_admin_service
from app.models.assignment import UserProjectAssignment

router = APIRouter()


@router.post("/", response_model=AssignmentRead, summary="Asignar usuario a proyecto")
def create_assignment(
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssignmentRead:
    require_project_permission(db, current_user.id, payload.project_id, IDENTITY_USERS_MANAGE)
    if db.get(User, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if payload.role_id:
        project_user_admin_service._role(db, payload.project_id, payload.role_id, current_user)
    if db.query(UserProjectAssignment).filter_by(user_id=payload.user_id, project_id=payload.project_id).first():
        raise HTTPException(status_code=409, detail="El usuario ya tiene una asignación; modifica su acceso desde Usuarios y permisos")
    return assignment_service.create_assignment(db, payload)


@router.get("/", response_model=list[AssignmentRead], summary="Listar asignaciones")
def list_assignments(
    project_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AssignmentRead]:
    if project_id:
        require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
        return assignment_service.list_assignments(db, project_id)
    result = []
    for project in db.query(Project).all():
        try:
            require_project_permission(db, current_user.id, project.id, IDENTITY_USERS_MANAGE)
        except HTTPException as error:
            if error.status_code in (403, 404):
                continue
            raise
        result.extend(assignment_service.list_assignments(db, project.id))
    return result
