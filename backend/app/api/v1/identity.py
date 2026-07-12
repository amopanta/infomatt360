"""Rutas de identidad, proyectos y roles.

Requieren sesion autenticada y el permiso administrativo correspondiente:
gestion de usuarios se protege con `identity.users.manage`, y la gestion de
proyectos/roles (que define que permisos existen) con `organizations.manage`.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_any_permission
from app.core.permissions import IDENTITY_USERS_MANAGE, ORGANIZATIONS_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.identity import ProjectCreate, ProjectRead, RoleCreate, RoleRead, UserCreate, UserRead
from app.services.identity_service import identity_service

router = APIRouter()


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Crear usuario")
def create_user(payload: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> UserRead:
    """Crea un usuario unico para web, Android y escritorio."""
    require_any_permission(db, current_user.id, {IDENTITY_USERS_MANAGE})
    return identity_service.create_user(db, payload)


@router.get("/users", response_model=list[UserRead], summary="Listar usuarios")
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[UserRead]:
    require_any_permission(db, current_user.id, {IDENTITY_USERS_MANAGE})
    return identity_service.list_users(db)


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, summary="Crear proyecto")
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ProjectRead:
    """Crea un proyecto operativo independiente."""
    require_any_permission(db, current_user.id, {ORGANIZATIONS_MANAGE})
    return identity_service.create_project(db, payload)


@router.get("/projects", response_model=list[ProjectRead], summary="Listar proyectos")
def list_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ProjectRead]:
    require_any_permission(db, current_user.id, {ORGANIZATIONS_MANAGE})
    return identity_service.list_projects(db)


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED, summary="Crear rol")
def create_role(payload: RoleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RoleRead:
    require_any_permission(db, current_user.id, {ORGANIZATIONS_MANAGE})
    return identity_service.create_role(db, payload)


@router.get("/roles", response_model=list[RoleRead], summary="Listar roles")
def list_roles(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[RoleRead]:
    require_any_permission(db, current_user.id, {ORGANIZATIONS_MANAGE})
    return identity_service.list_roles(db)
