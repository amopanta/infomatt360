from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_any_permission
from app.core.permissions import IDENTITY_USERS_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.assignment import AssignmentCreate, AssignmentRead
from app.services.assignment_service import assignment_service

router = APIRouter()


@router.post("/", response_model=AssignmentRead, summary="Asignar usuario a proyecto")
def create_assignment(
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssignmentRead:
    require_any_permission(db, current_user.id, {IDENTITY_USERS_MANAGE})
    return assignment_service.create_assignment(db, payload)


@router.get("/", response_model=list[AssignmentRead], summary="Listar asignaciones")
def list_assignments(
    project_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AssignmentRead]:
    require_any_permission(db, current_user.id, {IDENTITY_USERS_MANAGE})
    return assignment_service.list_assignments(db, project_id)
