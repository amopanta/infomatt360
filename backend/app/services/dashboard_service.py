from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.files import FileAsset
from app.models.runtime_record import RuntimeRecord
from app.schemas.dashboard import DashboardRecentRecord, DashboardSummary


class DashboardService:
    def summary(self, db: Session, project_id: str) -> DashboardSummary:
        templates_total = db.query(func.count(BuilderTemplate.id)).filter(BuilderTemplate.project_id == project_id).scalar() or 0
        published_templates = db.query(func.count(BuilderTemplate.id)).filter(BuilderTemplate.project_id == project_id, BuilderTemplate.status == "published").scalar() or 0
        records_total = db.query(func.count(RuntimeRecord.id)).filter(RuntimeRecord.project_id == project_id).scalar() or 0
        users_total = db.query(func.count(func.distinct(UserProjectAssignment.user_id))).filter(UserProjectAssignment.project_id == project_id, UserProjectAssignment.status == "active").scalar() or 0
        files_total, storage_bytes = db.query(func.count(FileAsset.id), func.coalesce(func.sum(FileAsset.size_bytes), 0)).filter(FileAsset.project_id == project_id).one()
        status_rows = db.query(RuntimeRecord.status, func.count(RuntimeRecord.id)).filter(RuntimeRecord.project_id == project_id).group_by(RuntimeRecord.status).all()
        recent_rows = (
            db.query(RuntimeRecord, BuilderTemplate.name)
            .join(BuilderTemplate, BuilderTemplate.id == RuntimeRecord.template_id)
            .filter(RuntimeRecord.project_id == project_id)
            .order_by(RuntimeRecord.created_at.desc())
            .limit(8)
            .all()
        )
        return DashboardSummary(
            project_id=project_id,
            templates_total=int(templates_total),
            published_templates=int(published_templates),
            records_total=int(records_total),
            users_total=int(users_total),
            files_total=int(files_total),
            storage_bytes=int(storage_bytes),
            records_by_status={status: int(count) for status, count in status_rows},
            recent_records=[DashboardRecentRecord(id=row.id, template_id=row.template_id, template_name=name, status=row.status, submitted_by=row.submitted_by, created_at=row.created_at) for row, name in recent_rows],
        )


dashboard_service = DashboardService()
