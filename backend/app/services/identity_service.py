"""Servicio persistente de identidad y proyectos.

Este servicio centraliza la logica de usuarios, proyectos y roles usando
SQLAlchemy. Los routers solo deben recibir solicitudes y delegar reglas.
"""

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.identity import Project, Role, User
from app.schemas.identity import ProjectCreate, ProjectRead, RoleCreate, RoleRead, UserCreate, UserRead


def _channels_to_text(channels: list) -> str:
    """Convierte canales permitidos a texto almacenado en base de datos."""
    return ",".join(str(channel.value) for channel in channels)


def _permissions_to_text(permissions: list[str]) -> str:
    """Convierte permisos a texto simple mientras llega el modelo avanzado."""
    return ",".join(permissions)


def _user_to_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        full_name=user.full_name,
        document_id=user.document_id,
        email=user.email,
        phone=user.phone,
        status=user.status,
        allowed_channels=user.allowed_channels.split(",") if user.allowed_channels else [],
    )


def _project_to_read(project: Project) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
    )


def _role_to_read(role: Role) -> RoleRead:
    return RoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role.permissions.split(",") if role.permissions else [],
    )


class IdentityService:
    """Servicio de aplicacion para usuarios, proyectos y roles."""

    def create_user(self, db: Session, payload: UserCreate) -> UserRead:
        user = User(
            full_name=payload.full_name,
            document_id=payload.document_id,
            email=str(payload.email),
            password_hash=hash_password("ChangeMe123"),
            phone=payload.phone,
            status=payload.status.value,
            allowed_channels=_channels_to_text(payload.allowed_channels),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return _user_to_read(user)

    def list_users(self, db: Session) -> list[UserRead]:
        return [_user_to_read(user) for user in db.query(User).order_by(User.created_at.desc()).all()]

    def get_user_by_email(self, db: Session, email: str) -> User | None:
        return db.query(User).filter(User.email == email).first()

    def create_project(self, db: Session, payload: ProjectCreate) -> ProjectRead:
        project = Project(
            name=payload.name,
            description=payload.description,
            status=payload.status.value,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return _project_to_read(project)

    def list_projects(self, db: Session) -> list[ProjectRead]:
        return [_project_to_read(project) for project in db.query(Project).order_by(Project.created_at.desc()).all()]

    def create_role(self, db: Session, payload: RoleCreate) -> RoleRead:
        role = Role(
            name=payload.name,
            description=payload.description,
            permissions=_permissions_to_text(payload.permissions),
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        return _role_to_read(role)

    def list_roles(self, db: Session) -> list[RoleRead]:
        return [_role_to_read(role) for role in db.query(Role).order_by(Role.created_at.desc()).all()]


identity_service = IdentityService()
