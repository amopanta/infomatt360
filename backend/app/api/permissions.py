from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, Role


def get_project_permissions(db: Session, user_id: str, project_id: str) -> tuple[UserProjectAssignment | None, set[str]]:
    row = (
        db.query(UserProjectAssignment, Role)
        .join(Role, Role.id == UserProjectAssignment.role_id)
        .filter(
            UserProjectAssignment.user_id == user_id,
            UserProjectAssignment.project_id == project_id,
            UserProjectAssignment.status == "active",
        )
        .first()
    )
    permissions = {item.strip() for item in row[1].permissions.split(",") if item.strip()} if row else set()
    return (row[0], permissions) if row else (None, permissions)


def require_project_permission(db: Session, user_id: str, project_id: str, permission: str) -> UserProjectAssignment:
    assignment, permissions = get_project_permissions(db, user_id, project_id)
    if permission not in permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")
    return assignment


def require_any_project_permission(db: Session, user_id: str, project_id: str, permissions: set[str]) -> UserProjectAssignment:
    assignment, current_permissions = get_project_permissions(db, user_id, project_id)
    if not assignment or current_permissions.isdisjoint(permissions):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")
    return assignment


def require_any_permission(db: Session, user_id: str, permissions: set[str]) -> UserProjectAssignment:
    row = (
        db.query(UserProjectAssignment, Role)
        .join(Role, Role.id == UserProjectAssignment.role_id)
        .filter(
            UserProjectAssignment.user_id == user_id,
            UserProjectAssignment.status == "active",
        )
        .all()
    )
    for assignment, role in row:
        current_permissions = {item.strip() for item in role.permissions.split(",") if item.strip()}
        if not current_permissions.isdisjoint(permissions):
            return assignment
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")


def require_permission_in_organization(db: Session, user_id: str, organization_id: str, permission: str) -> UserProjectAssignment:
    """Verifica que el permiso este concedido a traves de un proyecto que pertenezca a `organization_id`.

    A diferencia de `require_any_permission` (que acepta el permiso concedido en
    cualquier proyecto/organizacion), esta funcion evita que un permiso obtenido
    en la Organizacion A autorice acciones sobre la Organizacion B solo porque el
    usuario tambien tiene alguna asignacion (con cualquier permiso) ahi.
    """
    row = (
        db.query(UserProjectAssignment, Role)
        .join(Role, Role.id == UserProjectAssignment.role_id)
        .join(Project, Project.id == UserProjectAssignment.project_id)
        .filter(
            UserProjectAssignment.user_id == user_id,
            UserProjectAssignment.status == "active",
            Project.organization_id == organization_id,
        )
        .all()
    )
    for assignment, role in row:
        current_permissions = {item.strip() for item in role.permissions.split(",") if item.strip()}
        if permission in current_permissions:
            return assignment
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente en esta organizacion")


def get_user_organization_ids(db: Session, user_id: str) -> list[str]:
    """Organizaciones a las que el usuario tiene acceso, resueltas via sus proyectos asignados."""
    rows = (
        db.query(Project.organization_id)
        .join(UserProjectAssignment, UserProjectAssignment.project_id == Project.id)
        .filter(
            UserProjectAssignment.user_id == user_id,
            UserProjectAssignment.status == "active",
            Project.organization_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return [row[0] for row in rows]
