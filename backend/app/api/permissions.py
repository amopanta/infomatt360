from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignment import UserOrganizationAssignment, UserProjectAssignment
from app.models.identity import Project, Role


def get_organization_permissions(db: Session, user_id: str, organization_id: str) -> set[str]:
    """Permisos concedidos a un usuario a nivel de una Organizacion completa.

    Distinto de get_project_permissions: no depende de ningun proyecto en
    particular. Usado para el rol de "Administrador nacional" (ver docs/101).
    """
    row = (
        db.query(UserOrganizationAssignment, Role)
        .join(Role, Role.id == UserOrganizationAssignment.role_id)
        .filter(
            UserOrganizationAssignment.user_id == user_id,
            UserOrganizationAssignment.organization_id == organization_id,
            UserOrganizationAssignment.status == "active",
        )
        .first()
    )
    return {item.strip() for item in row[1].permissions.split(",") if item.strip()} if row else set()


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
    assignment = row[0] if row else None

    # Rol de "Administrador nacional" (ver docs/101): union de los permisos
    # otorgados por una asignacion a nivel de la organizacion dueña del
    # proyecto, ademas de los otorgados directamente sobre este proyecto.
    project = db.query(Project).filter(Project.id == project_id).first()
    if project and project.organization_id:
        permissions |= get_organization_permissions(db, user_id, project.organization_id)

    return (assignment, permissions)


def require_project_permission(db: Session, user_id: str, project_id: str, permission: str) -> UserProjectAssignment:
    assignment, permissions = get_project_permissions(db, user_id, project_id)
    if permission not in permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")
    return assignment


def require_any_project_permission(db: Session, user_id: str, project_id: str, permissions: set[str]) -> UserProjectAssignment:
    assignment, current_permissions = get_project_permissions(db, user_id, project_id)
    if current_permissions.isdisjoint(permissions):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")
    return assignment


def require_any_permission(db: Session, user_id: str, permissions: set[str]) -> UserProjectAssignment | None:
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

    # Rol de "Administrador nacional" (ver docs/101): tambien cuentan los
    # permisos otorgados via cualquier asignacion a nivel de organizacion.
    org_row = (
        db.query(UserOrganizationAssignment, Role)
        .join(Role, Role.id == UserOrganizationAssignment.role_id)
        .filter(
            UserOrganizationAssignment.user_id == user_id,
            UserOrganizationAssignment.status == "active",
        )
        .all()
    )
    for _org_assignment, role in org_row:
        current_permissions = {item.strip() for item in role.permissions.split(",") if item.strip()}
        if not current_permissions.isdisjoint(permissions):
            return None

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")


def require_permission_in_organization(db: Session, user_id: str, organization_id: str, permission: str) -> UserProjectAssignment | None:
    """Verifica que el permiso este concedido a traves de un proyecto que pertenezca a `organization_id`,
    o directamente a traves de una asignacion a nivel de esa organizacion ("Administrador nacional",
    ver docs/101).

    A diferencia de `require_any_permission` (que acepta el permiso concedido en
    cualquier proyecto/organizacion), esta funcion evita que un permiso obtenido
    en la Organizacion A autorice acciones sobre la Organizacion B solo porque el
    usuario tambien tiene alguna asignacion (con cualquier permiso) ahi.
    """
    if permission in get_organization_permissions(db, user_id, organization_id):
        return None

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
    """Organizaciones a las que el usuario tiene acceso, via sus proyectos asignados o via una
    asignacion directa a nivel organizacion ("Administrador nacional", ver docs/101)."""
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
    org_ids = {row[0] for row in rows}

    org_rows = (
        db.query(UserOrganizationAssignment.organization_id)
        .filter(
            UserOrganizationAssignment.user_id == user_id,
            UserOrganizationAssignment.status == "active",
        )
        .distinct()
        .all()
    )
    org_ids.update(row[0] for row in org_rows)

    return list(org_ids)
