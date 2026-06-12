from fastapi import APIRouter, Depends

from app.api.project_access import require_project_access
from app.models.identity import User
from app.schemas.project_context import ProjectAccessResponse

router = APIRouter()


@router.get("/{project_id}/access", response_model=ProjectAccessResponse, summary="Validar acceso al proyecto")
def validate_project_access(project_id: str, current_user: User = Depends(require_project_access)) -> ProjectAccessResponse:
    return ProjectAccessResponse(project_id=project_id, user_id=current_user.id, has_access=True)
