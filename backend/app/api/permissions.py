import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignment import UserOrganizationAssignment, UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.form_assignment import ParticipantFormAssignment
from app.models.identity import Project, Role
from app.models.case_management import UserTerritory
from app.models.participants import Participant
from app.models.records import Record
from app.models.runtime_record import RuntimeRecord
from app.core.permissions import IDENTITY_USERS_MANAGE, RECORDS_APPROVE, RECORDS_COORDINATE, RECORDS_REVIEW, RECORDS_VOID
from app.services.permission_cache_service import CachedProjectAssignment, get_permission_cache


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


def get_project_permissions(db: Session, user_id: str, project_id: str) -> tuple[UserProjectAssignment | CachedProjectAssignment | None, set[str]]:
    # Cache de permisos efectivos (ver E-004, docs/108): esta funcion se
    # llama en casi cada endpoint de escritura y hacia hasta 3 queries por
    # chequeo sin ningun cache. `approval_flow_service.user_can_execute_step`
    # es el unico llamador que usa el `assignment` devuelto (solo lee
    # `.role_id`), asi que en un hit de cache se reconstruye un sustituto
    # liviano con ese campo en vez de devolver la fila ORM real (que no
    # sobrevive fuera de la sesion que la cargo).
    cache = get_permission_cache()
    cached = cache.get(user_id, project_id)
    if cached is not None:
        cached_role_id, cached_permissions = cached
        cached_assignment = CachedProjectAssignment(role_id=cached_role_id) if cached_role_id is not None else None
        return (cached_assignment, set(cached_permissions))

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

    cache.set(user_id, project_id, assignment.role_id if assignment else None, frozenset(permissions))
    return (assignment, permissions)


def _matches_territory(participant: Participant, territories: list[UserTerritory]) -> bool:
    try:
        metadata = json.loads(participant.metadata_json or "{}")
        if not isinstance(metadata, dict):
            return False
    except ValueError:
        return False
    department = str(metadata.get("department") or metadata.get("departamento") or "").strip().casefold()
    municipality = str(metadata.get("municipality") or metadata.get("municipio") or "").strip().casefold()
    return any(t.department.casefold() == department and (not t.municipality or t.municipality.casefold() == municipality) for t in territories)


def participant_visible(db: Session, user_id: str, participant: Participant) -> bool:
    _, permissions = get_project_permissions(db, user_id, participant.project_id)
    if IDENTITY_USERS_MANAGE in permissions:
        return True
    territories = db.query(UserTerritory).filter(
        UserTerritory.project_id == participant.project_id, UserTerritory.user_id == user_id,
    ).all()
    return not territories or _matches_territory(participant, territories)


def allowed_participant_ids(db: Session, user_id: str, project_id: str) -> list[str] | None:
    """None: sin restriccion territorial; []: ningun participante visible."""
    _, permissions = get_project_permissions(db, user_id, project_id)
    if IDENTITY_USERS_MANAGE in permissions:
        return None
    territories = db.query(UserTerritory).filter(UserTerritory.user_id == user_id, UserTerritory.project_id == project_id).all()
    if not territories:
        return None
    return [row.id for row in db.query(Participant).filter(Participant.project_id == project_id).all()
            if _matches_territory(row, territories)]


def form_access_mode(template: BuilderTemplate | None) -> str:
    """Old forms remain operational until an administrator selects a mode."""
    if not template or not template.participant_source_json:
        return "legacy"
    try:
        return str(json.loads(template.participant_source_json).get("access_mode") or "legacy")
    except (ValueError, AttributeError):
        return "legacy"


def allowed_form_participant_ids(db: Session, user_id: str, template: BuilderTemplate, *, review: bool = False) -> list[str] | None:
    territorial = allowed_participant_ids(db, user_id, template.project_id)
    if form_access_mode(template) == "legacy":
        return territorial
    _, permissions = get_project_permissions(db, user_id, template.project_id)
    if IDENTITY_USERS_MANAGE in permissions or (review and permissions.intersection({RECORDS_REVIEW, RECORDS_APPROVE, RECORDS_COORDINATE, RECORDS_VOID})):
        return territorial
    assigned = {row[0] for row in db.query(ParticipantFormAssignment.participant_id).filter(
        ParticipantFormAssignment.template_id == template.id,
        ParticipantFormAssignment.responsible_user_id == user_id,
    ).all()}
    return sorted(assigned if territorial is None else assigned.intersection(territorial))


def require_form_participant_access(db: Session, user_id: str, template_id: str, participant_id: str | None, *, review: bool = False) -> None:
    template = db.get(BuilderTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")
    allowed = allowed_form_participant_ids(db, user_id, template, review=review)
    if allowed is not None and participant_id not in allowed:
        raise HTTPException(status_code=404, detail="Registro no encontrado")


def require_record_territory(db: Session, user_id: str, project_id: str, participant_id: str | None) -> None:
    allowed = allowed_participant_ids(db, user_id, project_id)
    if allowed is not None and participant_id not in allowed:
        raise HTTPException(status_code=404, detail="Registro no encontrado")


def require_record_id_territory(db: Session, user_id: str, record_id: str) -> None:
    record = db.get(RuntimeRecord, record_id) or db.get(Record, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    require_record_territory(db, user_id, record.project_id, record.participant_id)
    if isinstance(record, RuntimeRecord):
        require_form_participant_access(db, user_id, record.template_id, record.participant_id, review=True)


def require_unrestricted_territory(db: Session, user_id: str, project_id: str) -> None:
    """Fail closed for project-wide views that cannot yet filter by participant."""
    if allowed_participant_ids(db, user_id, project_id) is not None:
        raise HTTPException(status_code=403, detail="Esta vista general no admite todavía el filtro territorial")


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
