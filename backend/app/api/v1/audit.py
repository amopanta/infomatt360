from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.audit import AuditCreate, AuditRead
from app.services.assignment_service import assignment_service
from app.services.audit_service import audit_service

router = APIRouter()


@router.post("/", response_model=AuditRead)
def create_audit(payload: AuditCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> AuditRead:
    if payload.project_id and not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return audit_service.write(db, payload, current_user.id)


@router.get("/", response_model=list[AuditRead])
def list_audit(
    project_id: str | None = None,
    module: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuditRead]:
    if project_id and not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return audit_service.list_logs(db, project_id, module, current_user.id, limit)
