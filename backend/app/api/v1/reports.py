from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.reports import ReportCreate, ReportLinkCreate, ReportLinkRead, ReportProjectSummary, ReportRead
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


@router.get("/project/{project_id}/summary", response_model=ReportProjectSummary)
def project_report_summary(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReportProjectSummary:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return report_service.project_summary(db, project_id)


@router.get("/project/{project_id}/summary.xlsx")
def export_project_report_summary(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    content = report_service.export_project_summary_xlsx(db, project_id)
    safe_name = "".join(character if character.isascii() and (character.isalnum() or character in "-_") else "_" for character in project_id).strip("_") or "proyecto"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="reporte_{safe_name}.xlsx"'},
    )


@router.post("/links", response_model=ReportLinkRead)
def create_report_link(payload: ReportLinkCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReportLinkRead:
    return report_service.create_link(db, payload)
