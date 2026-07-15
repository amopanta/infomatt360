from sqlalchemy.orm import Session

from app.models.assignment import UserOrganizationAssignment, UserProjectAssignment
from app.models.identity import Project
from app.schemas.assignment import AssignmentCreate, AssignmentRead, OrganizationAssignmentCreate, OrganizationAssignmentRead


def _to_read(row: UserProjectAssignment) -> AssignmentRead:
    return AssignmentRead(
        id=row.id,
        user_id=row.user_id,
        project_id=row.project_id,
        role_id=row.role_id,
        status=row.status,
    )


def _org_to_read(row: UserOrganizationAssignment) -> OrganizationAssignmentRead:
    return OrganizationAssignmentRead(
        id=row.id,
        user_id=row.user_id,
        organization_id=row.organization_id,
        role_id=row.role_id,
        status=row.status,
    )


class AssignmentService:
    def create_assignment(self, db: Session, payload: AssignmentCreate) -> AssignmentRead:
        row = UserProjectAssignment(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def list_assignments(self, db: Session, project_id: str | None = None) -> list[AssignmentRead]:
        query = db.query(UserProjectAssignment)
        if project_id:
            query = query.filter(UserProjectAssignment.project_id == project_id)
        return [_to_read(row) for row in query.order_by(UserProjectAssignment.created_at.desc()).all()]

    def create_organization_assignment(self, db: Session, payload: OrganizationAssignmentCreate) -> OrganizationAssignmentRead:
        row = UserOrganizationAssignment(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return _org_to_read(row)

    def list_organization_assignments(self, db: Session, organization_id: str | None = None) -> list[OrganizationAssignmentRead]:
        query = db.query(UserOrganizationAssignment)
        if organization_id:
            query = query.filter(UserOrganizationAssignment.organization_id == organization_id)
        return [_org_to_read(row) for row in query.order_by(UserOrganizationAssignment.created_at.desc()).all()]

    def user_has_project_access(self, db: Session, user_id: str, project_id: str) -> bool:
        if db.query(UserProjectAssignment).filter(
            UserProjectAssignment.user_id == user_id,
            UserProjectAssignment.project_id == project_id,
            UserProjectAssignment.status == "active",
        ).first() is not None:
            return True

        # Rol de "Administrador nacional" (ver docs/101): acceso a todo
        # proyecto de la organizacion via una asignacion a nivel organizacion,
        # sin necesitar una fila individual por proyecto.
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or not project.organization_id:
            return False
        return db.query(UserOrganizationAssignment).filter(
            UserOrganizationAssignment.user_id == user_id,
            UserOrganizationAssignment.organization_id == project.organization_id,
            UserOrganizationAssignment.status == "active",
        ).first() is not None


assignment_service = AssignmentService()
