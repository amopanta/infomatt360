from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import BUILDER_WRITE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.report_board import ReportBoardLayout, ReportBoardRead, ReportBoardUpdate
from app.schemas.reports import ReportCreate, ReportLinkCreate, ReportLinkRead, ReportProjectSummary, ReportRead
from app.services.assignment_service import assignment_service
from app.services.report_service import DEFAULT_WIDGETS, report_service

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


@router.get("/project/{project_id}/board", response_model=ReportBoardRead)
def get_report_board(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReportBoardRead:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    row = report_service.get_board_row(db, project_id)
    widgets = ReportBoardLayout.model_validate_json(row.widgets_json).widgets if row else DEFAULT_WIDGETS
    return report_service.resolve_board(db, project_id, widgets)


@router.put("/project/{project_id}/board", response_model=ReportBoardRead)
def update_report_board(project_id: str, payload: ReportBoardUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReportBoardRead:
    require_project_permission(db, current_user.id, project_id, BUILDER_WRITE)
    if payload.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="project_id inconsistente")
    row = report_service.update_board(db, payload)
    widgets = ReportBoardLayout.model_validate_json(row.widgets_json).widgets
    return report_service.resolve_board(db, project_id, widgets)


@router.post("/links", response_model=ReportLinkRead)
def create_report_link(payload: ReportLinkCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReportLinkRead:
    return report_service.create_link(db, payload)
