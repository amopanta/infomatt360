from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.dashboard import DashboardSummary
from app.services.assignment_service import assignment_service
from app.services.dashboard_service import dashboard_service

router = APIRouter()


@router.get("/projects/{project_id}/summary", response_model=DashboardSummary)
def project_summary(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> DashboardSummary:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return dashboard_service.summary(db, project_id)
