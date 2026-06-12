"""Rutas iniciales de identidad y proyectos.

Estas rutas permiten validar los contratos de usuario unico, proyectos y roles.
La seguridad real con JWT se agregara en el modulo de autenticacion.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.identity import ProjectCreate, ProjectRead, RoleCreate, RoleRead, UserCreate, UserRead
from app.services.identity_service import identity_service

router = APIRouter()


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Crear usuario")
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    """Crea un usuario unico para web, Android y escritorio."""
    return identity_service.create_user(db, payload)


@router.get("/users", response_model=list[UserRead], summary="Listar usuarios")
def list_users(db: Session = Depends(get_db)) -> list[UserRead]:
    return identity_service.list_users(db)


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, summary="Crear proyecto")
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectRead:
    """Crea un proyecto operativo independiente."""
    return identity_service.create_project(db, payload)


@router.get("/projects", response_model=list[ProjectRead], summary="Listar proyectos")
def list_projects(db: Session = Depends(get_db)) -> list[ProjectRead]:
    return identity_service.list_projects(db)


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED, summary="Crear rol")
def create_role(payload: RoleCreate, db: Session = Depends(get_db)) -> RoleRead:
    return identity_service.create_role(db, payload)


@router.get("/roles", response_model=list[RoleRead], summary="Listar roles")
def list_roles(db: Session = Depends(get_db)) -> list[RoleRead]:
    return identity_service.list_roles(db)
