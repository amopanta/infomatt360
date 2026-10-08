"""Endpoints de seguridad y sesion actual."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import ALL_PERMISSIONS, IDENTITY_USERS_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.auth import PasswordOperationResponse
from app.schemas.security import AdminEmailUpdate, AdminMfaReset, AdminPasswordReset, AdminPasswordResetResponse, AdminUserRead, CurrentUserResponse
from app.services.account_admin_service import account_admin_service
from app.api.permissions import get_project_permissions
from app.schemas.identity import RoleRead
from app.schemas.security import AdminProjectAccessUpdate, AdminProjectRoleCreate, AdminProjectUserCreate, AdminProjectUserCreated
from app.services.project_user_admin_service import project_user_admin_service

router = APIRouter()


@router.get("/me", response_model=CurrentUserResponse, summary="Consultar usuario autenticado")
def read_current_user(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    """Devuelve informacion basica del usuario autenticado.

    Este endpoint sirve para que web, Android y escritorio validen sesion,
    perfil y canales disponibles.
    """
    return CurrentUserResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        status=current_user.status,
        allowed_channels=current_user.allowed_channels.split(",") if current_user.allowed_channels else [],
    )


@router.get("/admin/projects/{project_id}/users", response_model=list[AdminUserRead])
def list_project_users(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[AdminUserRead]:
    require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
    return project_user_admin_service.list_users(db, project_id)


@router.post("/admin/projects/{project_id}/users", response_model=AdminProjectUserCreated, status_code=201)
def admin_create_project_user(project_id: str, payload: AdminProjectUserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> AdminProjectUserCreated:
    require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
    return project_user_admin_service.create_user(db, project_id, payload, current_user)


@router.patch("/admin/projects/{project_id}/users/{user_id}/access", response_model=AdminUserRead)
def admin_update_project_access(project_id: str, user_id: str, payload: AdminProjectAccessUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> AdminUserRead:
    require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
    return project_user_admin_service.update_access(db, project_id, user_id, payload, current_user)


@router.get("/admin/projects/{project_id}/roles", response_model=list[RoleRead])
def admin_list_project_roles(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[RoleRead]:
    require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
    return project_user_admin_service.list_roles(db, project_id, current_user)


@router.get("/admin/projects/{project_id}/grantable-permissions", response_model=list[str])
def admin_grantable_permissions(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[str]:
    require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
    return sorted(get_project_permissions(db, current_user.id, project_id)[1] & ALL_PERMISSIONS)


@router.post("/admin/projects/{project_id}/roles", response_model=RoleRead, status_code=201)
def admin_create_project_role(project_id: str, payload: AdminProjectRoleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RoleRead:
    require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
    return project_user_admin_service.create_role(db, project_id, payload, current_user)


@router.patch("/admin/projects/{project_id}/users/{user_id}/email", response_model=AdminUserRead)
def admin_update_email(project_id: str, user_id: str, payload: AdminEmailUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> AdminUserRead:
    require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
    return account_admin_service.update_email(db, project_id, user_id, payload, current_user)


@router.post("/admin/projects/{project_id}/users/{user_id}/password-reset", response_model=AdminPasswordResetResponse)
def admin_reset_password(project_id: str, user_id: str, payload: AdminPasswordReset, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> AdminPasswordResetResponse:
    require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
    return account_admin_service.reset_password(db, project_id, user_id, payload, current_user)


@router.post("/admin/projects/{project_id}/users/{user_id}/mfa-reset", response_model=PasswordOperationResponse)
def admin_reset_mfa(project_id: str, user_id: str, payload: AdminMfaReset, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> PasswordOperationResponse:
    require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
    account_admin_service.reset_mfa(db, project_id, user_id, payload, current_user)
    return PasswordOperationResponse(message="MFA reiniciado. El usuario puede configurarlo nuevamente.")
