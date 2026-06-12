"""Servicio temporal de identidad y proyectos.

Este servicio usa almacenamiento en memoria solo para validar contratos de API.
Sera reemplazado por persistencia PostgreSQL/Alembic en el siguiente bloque.
"""

from uuid import uuid4

from app.schemas.identity import ProjectCreate, ProjectRead, RoleCreate, RoleRead, UserCreate, UserRead


class IdentityService:
    """Servicio de aplicacion para usuarios, proyectos y roles.

    Centralizar esta logica evita que los routers contengan reglas de negocio.
    """

    def __init__(self) -> None:
        self._users: dict[str, UserRead] = {}
        self._projects: dict[str, ProjectRead] = {}
        self._roles: dict[str, RoleRead] = {}

    def create_user(self, payload: UserCreate) -> UserRead:
        user = UserRead(id=str(uuid4()), **payload.model_dump())
        self._users[user.id] = user
        return user

    def list_users(self) -> list[UserRead]:
        return list(self._users.values())

    def create_project(self, payload: ProjectCreate) -> ProjectRead:
        project = ProjectRead(id=str(uuid4()), **payload.model_dump())
        self._projects[project.id] = project
        return project

    def list_projects(self) -> list[ProjectRead]:
        return list(self._projects.values())

    def create_role(self, payload: RoleCreate) -> RoleRead:
        role = RoleRead(id=str(uuid4()), **payload.model_dump())
        self._roles[role.id] = role
        return role

    def list_roles(self) -> list[RoleRead]:
        return list(self._roles.values())


identity_service = IdentityService()
