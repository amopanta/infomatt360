from sqlalchemy.orm import Session

from app.models.reports import Report, ReportLink
from app.schemas.reports import ReportCreate, ReportLinkCreate, ReportLinkRead, ReportRead


def report_to_read(row: Report) -> ReportRead:
    return ReportRead(id=row.id, project_id=row.project_id, name=row.name, report_type=row.report_type, query_json=row.query_json, layout_json=row.layout_json, status=row.status)


def link_to_read(row: ReportLink) -> ReportLinkRead:
    return ReportLinkRead(id=row.id, report_id=row.report_id, token=row.token, access_mode=row.access_mode, allow_download=row.allow_download == "true", status=row.status)


class ReportService:
    def create_report(self, db: Session, payload: ReportCreate) -> ReportRead:
        row = Report(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return report_to_read(row)

    def list_reports(self, db: Session, project_id: str) -> list[ReportRead]:
        rows = db.query(Report).filter(Report.project_id == project_id).order_by(Report.created_at.desc()).all()
        return [report_to_read(row) for row in rows]

    def create_link(self, db: Session, payload: ReportLinkCreate) -> ReportLinkRead:
        row = ReportLink(
            report_id=payload.report_id,
            token=payload.token,
            access_mode=payload.access_mode,
            allow_download="true" if payload.allow_download else "false",
            status=payload.status,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return link_to_read(row)


report_service = ReportService()
