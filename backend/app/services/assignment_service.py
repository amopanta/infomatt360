from sqlalchemy.orm import Session

from app.models.assignment import UserProjectAssignment
from app.schemas.assignment import AssignmentCreate, AssignmentRead


def _to_read(row: UserProjectAssignment) -> AssignmentRead:
    return AssignmentRead(
        id=row.id,
        user_id=row.user_id,
        project_id=row.project_id,
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

    def user_has_project_access(self, db: Session, user_id: str, project_id: str) -> bool:
        return db.query(UserProjectAssignment).filter(
            UserProjectAssignment.user_id == user_id,
            UserProjectAssignment.project_id == project_id,
            UserProjectAssignment.status == "active",
        ).first() is not None


assignment_service = AssignmentService()
