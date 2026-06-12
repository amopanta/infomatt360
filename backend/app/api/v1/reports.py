from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.reports import ReportCreate, ReportLinkCreate, ReportLinkRead, ReportRead
from app.services.assignment_service import assignment_service
from app.services.report_service import report_service

router = APIRouter()


@router.post("/", response_model=ReportRead)
def create_report(payload: ReportCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReportRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return report_service.create_report(db, payload)


@router.get("/project/{project_id}", response_model=list[ReportRead])
def list_reports(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ReportRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return report_service.list_reports(db, project_id)


@router.post("/links", response_model=ReportLinkRead)
def create_report_link(payload: ReportLinkCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReportLinkRead:
    return report_service.create_link(db, payload)
