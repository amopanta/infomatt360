from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.api_key_auth import get_api_key_context
from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import INTEGRATIONS_API_KEYS_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.api_key import ApiKeyAuthContext, ApiKeyCheckResponse, ApiKeyCreate, ApiKeyCreateResponse, ApiKeyRead
from app.services.api_key_service import api_key_service
from app.services.assignment_service import assignment_service

router = APIRouter()

MANAGE_PERMISSION = INTEGRATIONS_API_KEYS_MANAGE


@router.post("/", response_model=ApiKeyCreateResponse)
def create_api_key(payload: ApiKeyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ApiKeyCreateResponse:
    require_project_permission(db, current_user.id, payload.project_id, MANAGE_PERMISSION)
    return api_key_service.create_key(db, payload, current_user.id)


@router.get("/{project_id}", response_model=list[ApiKeyRead])
def list_api_keys(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ApiKeyRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return api_key_service.list_keys(db, project_id)


@router.delete("/{project_id}/{key_id}", response_model=ApiKeyRead)
def revoke_api_key(project_id: str, key_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ApiKeyRead:
    require_project_permission(db, current_user.id, project_id, MANAGE_PERMISSION)
    revoked = api_key_service.revoke_key(db, project_id, key_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key no encontrada")
    return revoked


@router.get("/auth/check", response_model=ApiKeyCheckResponse)
def check_api_key(context: ApiKeyAuthContext = Depends(get_api_key_context)) -> ApiKeyCheckResponse:
    return ApiKeyCheckResponse(project_id=context.project_id, key_id=context.key_id, permissions=context.permissions)
