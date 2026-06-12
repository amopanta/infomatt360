"""Rutas iniciales de identidad y proyectos.

Estas rutas permiten validar los contratos de usuario unico, proyectos y roles.
La seguridad real con JWT se agregara en el modulo de autenticacion.
"""

from fastapi import APIRouter, status

from app.schemas.identity import ProjectCreate, ProjectRead, RoleCreate, RoleRead, UserCreate, UserRead
from app.services.identity_service import identity_service

router = APIRouter()


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Crear usuario")
def create_user(payload: UserCreate) -> UserRead:
    """Crea un usuario unico para web, Android y escritorio."""
    return identity_service.create_user(payload)


@router.get("/users", response_model=list[UserRead], summary="Listar usuarios")
def list_users() -> list[UserRead]:
    return identity_service.list_users()


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, summary="Crear proyecto")
def create_project(payload: ProjectCreate) -> ProjectRead:
    """Crea un proyecto operativo independiente."""
    return identity_service.create_project(payload)


@router.get("/projects", response_model=list[ProjectRead], summary="Listar proyectos")
def list_projects() -> list[ProjectRead]:
    return identity_service.list_projects()


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED, summary="Crear rol")
def create_role(payload: RoleCreate) -> RoleRead:
    return identity_service.create_role(payload)


@router.get("/roles", response_model=list[RoleRead], summary="Listar roles")
def list_roles() -> list[RoleRead]:
    return identity_service.list_roles()
