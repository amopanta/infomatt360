from sqlalchemy.orm import Session

from app.models.integrations import IntegrationJob, IntegrationMap, IntegrationSource
from app.schemas.integrations import IntegrationJobCreate, IntegrationJobRead, IntegrationMapCreate, IntegrationMapRead, IntegrationSourceCreate, IntegrationSourceRead


def source_to_read(row: IntegrationSource) -> IntegrationSourceRead:
    return IntegrationSourceRead(id=row.id, project_id=row.project_id, name=row.name, source_type=row.source_type, base_url=row.base_url, config_json=row.config_json, status=row.status)


def map_to_read(row: IntegrationMap) -> IntegrationMapRead:
    return IntegrationMapRead(id=row.id, source_id=row.source_id, name=row.name, target_table=row.target_table, fields_json=row.fields_json, filters_json=row.filters_json, status=row.status)


def job_to_read(row: IntegrationJob) -> IntegrationJobRead:
    return IntegrationJobRead(id=row.id, source_id=row.source_id, map_id=row.map_id, mode=row.mode, status=row.status, last_result=row.last_result)


class IntegrationService:
    def create_source(self, db: Session, payload: IntegrationSourceCreate) -> IntegrationSourceRead:
        row = IntegrationSource(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return source_to_read(row)

    def list_sources(self, db: Session, project_id: str) -> list[IntegrationSourceRead]:
        rows = db.query(IntegrationSource).filter(IntegrationSource.project_id == project_id).order_by(IntegrationSource.created_at.desc()).all()
        return [source_to_read(row) for row in rows]

    def create_map(self, db: Session, payload: IntegrationMapCreate) -> IntegrationMapRead:
        row = IntegrationMap(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return map_to_read(row)

    def create_job(self, db: Session, payload: IntegrationJobCreate) -> IntegrationJobRead:
        row = IntegrationJob(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return job_to_read(row)


integration_service = IntegrationService()
