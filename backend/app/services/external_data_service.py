"""
Proyecto: InfoMatt360
Modulo: External Data Service
Responsabilidad: Gestionar fuentes externas, vinculos con formularios y trabajos masivos.
"""

import json
from sqlalchemy.orm import Session

from app.models.external_data import BulkPublishJob, ExternalDataSource, FormDataSourceBinding
from app.schemas.external_data import BulkPublishRead, BulkPublishRequest, ExternalDataSourceCreate, ExternalDataSourceRead, FormDataSourceBindingCreate, FormDataSourceBindingRead


def data_source_to_read(row: ExternalDataSource) -> ExternalDataSourceRead:
    return ExternalDataSourceRead(id=row.id, project_id=row.project_id, name=row.name, source_type=row.source_type, source_url=row.source_url, key_field=row.key_field, sync_mode=row.sync_mode, status=row.status)


def binding_to_read(row: FormDataSourceBinding) -> FormDataSourceBindingRead:
    return FormDataSourceBindingRead(id=row.id, template_id=row.template_id, data_source_id=row.data_source_id, alias=row.alias, filter_json=row.filter_json)


def job_to_read(row: BulkPublishJob) -> BulkPublishRead:
    return BulkPublishRead(id=row.id, project_id=row.project_id, action=row.action, target_template_ids_json=row.target_template_ids_json, status=row.status, result_json=row.result_json)


class ExternalDataService:
    """Reglas de negocio para fuentes externas y acciones masivas."""

    def create_data_source(self, db: Session, payload: ExternalDataSourceCreate) -> ExternalDataSourceRead:
        row = ExternalDataSource(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return data_source_to_read(row)

    def list_data_sources(self, db: Session, project_id: str) -> list[ExternalDataSourceRead]:
        rows = db.query(ExternalDataSource).filter(ExternalDataSource.project_id == project_id).order_by(ExternalDataSource.created_at.desc()).all()
        return [data_source_to_read(row) for row in rows]

    def bind_data_source(self, db: Session, payload: FormDataSourceBindingCreate) -> FormDataSourceBindingRead:
        row = FormDataSourceBinding(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return binding_to_read(row)

    def bulk_publish(self, db: Session, payload: BulkPublishRequest, user_id: str | None) -> BulkPublishRead:
        row = BulkPublishJob(project_id=payload.project_id, action=payload.action, target_template_ids_json=json.dumps(payload.target_template_ids), status="queued", created_by=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return job_to_read(row)


external_data_service = ExternalDataService()
