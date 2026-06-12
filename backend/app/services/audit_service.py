from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.schemas.audit import AuditCreate, AuditRead


def to_read(row: AuditLog) -> AuditRead:
    return AuditRead(
        id=row.id,
        project_id=row.project_id,
        user_id=row.user_id,
        module=row.module,
        action=row.action,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        before_json=row.before_json,
        after_json=row.after_json,
        ip_address=row.ip_address,
        device_info=row.device_info,
    )


class AuditService:
    def write(self, db: Session, payload: AuditCreate, user_id: str | None = None) -> AuditRead:
        row = AuditLog(**payload.model_dump(), user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return to_read(row)

    def list_logs(self, db: Session, project_id: str | None = None, module: str | None = None) -> list[AuditRead]:
        query = db.query(AuditLog)
        if project_id:
            query = query.filter(AuditLog.project_id == project_id)
        if module:
            query = query.filter(AuditLog.module == module)
        rows = query.order_by(AuditLog.created_at.desc()).limit(200).all()
        return [to_read(row) for row in rows]


audit_service = AuditService()
