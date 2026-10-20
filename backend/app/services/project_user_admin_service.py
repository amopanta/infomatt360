"""Project-scoped user management; roles never exceed the actor's permissions."""

import json

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.permissions import get_organization_permissions, get_project_permissions
from app.core.permissions import ALL_PERMISSIONS
from app.core.security import hash_password
from app.models.assignment import UserOrganizationAssignment, UserProjectAssignment
from app.models.audit import AuditLog
from app.models.identity import Project, Role, User
from app.schemas.identity import RoleRead
from app.schemas.security import AdminProjectAccessUpdate, AdminProjectRoleCreate, AdminProjectUserCreate, AdminProjectUserCreated, AdminUserRead
from app.services.account_admin_service import account_admin_service
from app.services.permission_cache_service import invalidate_permissions_for_user


def _permissions(role: Role) -> set[str]:
    return {value.strip() for value in role.permissions.split(",") if value.strip()}


def _inherited(db: Session, project_id: str, user_id: str) -> set[str]:
    project = db.get(Project, project_id)
    return get_organization_permissions(db, user_id, project.organization_id) if project and project.organization_id else set()


def user_to_admin_read(db: Session, user: User, assignment: UserProjectAssignment) -> AdminUserRead:
    role = db.get(Role, assignment.role_id) if assignment.role_id else None
    inherited = _inherited(db, assignment.project_id, user.id)
    permissions = (_permissions(role) if role and assignment.status == "active" else set()) | inherited
    return AdminUserRead(
        id=user.id, full_name=user.full_name, email=user.email, status=user.status,
        must_change_password=user.must_change_password, mfa_enabled=user.mfa_enabled,
        role_id=assignment.role_id, role_name=role.name if role else None,
        assignment_status=assignment.status, permissions=sorted(permissions),
        inherited_permissions=sorted(inherited),
    )


class ProjectUserAdminService:
    def list_users(self, db: Session, project_id: str) -> list[AdminUserRead]:
        rows = db.query(User, UserProjectAssignment).join(
            UserProjectAssignment, UserProjectAssignment.user_id == User.id,
        ).filter(UserProjectAssignment.project_id == project_id).order_by(User.full_name.asc()).all()
        return [user_to_admin_read(db, user, assignment) for user, assignment in rows]

    def list_roles(self, db: Session, project_id: str, admin: User) -> list[RoleRead]:
        _, grantable = get_project_permissions(db, admin.id, project_id)
        return [RoleRead(id=role.id, name=role.name, description=role.description, permissions=sorted(_permissions(role)))
                for role in db.query(Role).order_by(Role.name.asc()).all()
                if _permissions(role).issubset(grantable)]

    def _role(self, db: Session, project_id: str, role_id: str, admin: User) -> Role:
        role = db.get(Role, role_id)
        if role is None:
            raise HTTPException(status_code=404, detail="Rol no encontrado")
        _, grantable = get_project_permissions(db, admin.id, project_id)
        if not _permissions(role).issubset(grantable):
            raise HTTPException(status_code=403, detail="No puedes conceder permisos que no tienes en este proyecto")
        return role

    def _audit(self, db: Session, project_id: str, admin: User, action: str, entity_id: str,
               before: dict | None, after: dict, entity_type: str = "user") -> None:
        db.add(AuditLog(project_id=project_id, user_id=admin.id, module="identity", action=action,
                        entity_type=entity_type, entity_id=entity_id,
                        before_json=json.dumps(before) if before else None, after_json=json.dumps(after)))

    def create_user(self, db: Session, project_id: str, payload: AdminProjectUserCreate, admin: User) -> AdminProjectUserCreated:
        account_admin_service._reauthenticate(admin, payload.admin_password)
        self._role(db, project_id, payload.role_id, admin)
        if db.get(Project, project_id) is None:
            raise HTTPException(status_code=404, detail="Proyecto no encontrado")
        email = str(payload.email).strip().lower()
        document = payload.document_id.strip()
        if len(document) < 5 or len(payload.full_name.strip()) < 3:
            raise HTTPException(status_code=422, detail="Nombre o documento inválido")
        if db.query(User).filter(or_(func.lower(User.email) == email, User.document_id == document)).first():
            raise HTTPException(status_code=409, detail="El correo o documento ya está registrado")
        temporary = account_admin_service._generate_temporary_password()
        user = User(full_name=payload.full_name.strip(), document_id=document, email=email,
                    phone=payload.phone, status=payload.status.value,
                    allowed_channels=",".join(channel.value for channel in payload.allowed_channels),
                    password_hash=hash_password(temporary), must_change_password=True)
        try:
            db.add(user)
            db.flush()
            assignment = UserProjectAssignment(user_id=user.id, project_id=project_id, role_id=payload.role_id, status="active")
            db.add(assignment)
            db.flush()
            self._audit(db, project_id, admin, "project_user_created", user.id, None,
                        {"role_id": payload.role_id, "assignment_status": "active", "must_change_password": True})
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="El correo o documento ya está registrado") from None
        invalidate_permissions_for_user(user.id)
        return AdminProjectUserCreated(user=user_to_admin_read(db, user, assignment), temporary_password=temporary)

    def update_access(self, db: Session, project_id: str, user_id: str, payload: AdminProjectAccessUpdate, admin: User) -> AdminUserRead:
        account_admin_service._reauthenticate(admin, payload.admin_password)
        if user_id == admin.id:
            raise HTTPException(status_code=409, detail="Otro administrador debe modificar tu propio acceso")
        assignments = db.query(UserProjectAssignment).filter(
            UserProjectAssignment.project_id == project_id, UserProjectAssignment.user_id == user_id,
        ).with_for_update().all()
        user = db.get(User, user_id)
        if not assignments or user is None:
            raise HTTPException(status_code=404, detail="Usuario no asignado al proyecto")
        if len(assignments) != 1:
            raise HTTPException(status_code=409, detail="Hay asignaciones duplicadas; deben revisarse antes de cambiar permisos")
        assignment = assignments[0]
        self._role(db, project_id, payload.role_id, admin)
        _, actor_permissions = get_project_permissions(db, admin.id, project_id)
        _, target_permissions = get_project_permissions(db, user_id, project_id)
        if not target_permissions.issubset(actor_permissions):
            raise HTTPException(status_code=403, detail="No puedes modificar una cuenta con permisos superiores a los tuyos")
        project = db.get(Project, project_id)
        organization_access = project and project.organization_id and db.query(UserOrganizationAssignment).filter(
            UserOrganizationAssignment.user_id == user_id,
            UserOrganizationAssignment.organization_id == project.organization_id,
            UserOrganizationAssignment.status == "active",
        ).first()
        if payload.assignment_status != "active" and organization_access:
            raise HTTPException(status_code=409, detail="El usuario conserva acceso por organización; revisa su asignación de organización")
        before = {"role_id": assignment.role_id, "assignment_status": assignment.status}
        assignment.role_id, assignment.status = payload.role_id, payload.assignment_status
        self._audit(db, project_id, admin, "project_user_access_updated", user_id, before,
                    {"role_id": assignment.role_id, "assignment_status": assignment.status})
        db.commit()
        invalidate_permissions_for_user(user_id)
        return user_to_admin_read(db, user, assignment)

    def create_role(self, db: Session, project_id: str, payload: AdminProjectRoleCreate, admin: User) -> RoleRead:
        account_admin_service._reauthenticate(admin, payload.admin_password)
        _, grantable = get_project_permissions(db, admin.id, project_id)
        requested = set(payload.permissions)
        if not requested.issubset(ALL_PERMISSIONS) or not requested.issubset(grantable):
            raise HTTPException(status_code=403, detail="El rol contiene permisos desconocidos o que no puedes conceder")
        name = payload.name.strip()
        if len(name) < 3:
            raise HTTPException(status_code=422, detail="El nombre del rol debe tener al menos tres caracteres")
        if db.query(Role).filter(func.lower(Role.name) == name.lower()).first():
            raise HTTPException(status_code=409, detail="Ya existe un rol con ese nombre")
        role = Role(name=name, permissions=",".join(sorted(requested)))
        db.add(role)
        db.flush()
        self._audit(db, project_id, admin, "project_role_created", role.id, None,
                    {"name": name, "permissions": sorted(requested)}, "role")
        db.commit()
        return RoleRead(id=role.id, name=role.name, permissions=sorted(requested))


project_user_admin_service = ProjectUserAdminService()
