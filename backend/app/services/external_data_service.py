"""
Proyecto: InfoMatt360
Modulo: External Data Service
Responsabilidad: Gestionar fuentes externas, vinculos con formularios y trabajos masivos.
"""

import json
from sqlalchemy.orm import Session

from app.models.external_data import BulkPublishJob, ExternalDataSnapshot, ExternalDataSource, FormDataSourceBinding
from app.schemas.external_data import BulkPublishRead, BulkPublishRequest, ExternalDataSnapshotCreate, ExternalDataSnapshotRead, ExternalDataSourceCreate, ExternalDataSourceRead, FormDataSourceBindingCreate, FormDataSourceBindingRead, PulldataCacheEntry
from app.core.time import utc_now


class ExternalDataNotFoundError(Exception):
    """La fuente externa solicitada no existe."""


def data_source_to_read(row: ExternalDataSource) -> ExternalDataSourceRead:
    return ExternalDataSourceRead(id=row.id, project_id=row.project_id, name=row.name, source_type=row.source_type, source_url=row.source_url, key_field=row.key_field, sync_mode=row.sync_mode, status=row.status)


def binding_to_read(row: FormDataSourceBinding) -> FormDataSourceBindingRead:
    return FormDataSourceBindingRead(id=row.id, template_id=row.template_id, data_source_id=row.data_source_id, alias=row.alias, filter_json=row.filter_json)


def job_to_read(row: BulkPublishJob) -> BulkPublishRead:
    return BulkPublishRead(id=row.id, project_id=row.project_id, action=row.action, target_template_ids_json=row.target_template_ids_json, status=row.status, result_json=row.result_json)


def snapshot_to_read(row: ExternalDataSnapshot) -> ExternalDataSnapshotRead:
    return ExternalDataSnapshotRead(
        id=row.id,
        data_source_id=row.data_source_id,
        version=row.version,
        rows=json.loads(row.rows_json),
        row_count=row.row_count,
    )


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

    def create_snapshot(self, db: Session, data_source_id: str, payload: ExternalDataSnapshotCreate) -> ExternalDataSnapshotRead:
        source = db.query(ExternalDataSource).filter(ExternalDataSource.id == data_source_id).first()
        if source is None:
            raise ExternalDataNotFoundError(data_source_id)

        row = ExternalDataSnapshot(
            data_source_id=data_source_id,
            version=payload.version,
            rows_json=json.dumps(payload.rows),
            row_count=len(payload.rows),
        )
        source.last_sync_at = utc_now()
        db.add(row)
        db.commit()
        db.refresh(row)
        return snapshot_to_read(row)

    def get_runtime_cache(self, db: Session, template_id: str) -> dict[str, PulldataCacheEntry]:
        """Entrega la version mas reciente de cada fuente vinculada."""
        bindings = db.query(FormDataSourceBinding).filter(FormDataSourceBinding.template_id == template_id).all()
        result: dict[str, PulldataCacheEntry] = {}
        for binding in bindings:
            snapshot = (
                db.query(ExternalDataSnapshot)
                .filter(ExternalDataSnapshot.data_source_id == binding.data_source_id)
                .order_by(ExternalDataSnapshot.created_at.desc(), ExternalDataSnapshot.id.desc())
                .first()
            )
            if snapshot is not None:
                result[binding.alias] = PulldataCacheEntry(version=snapshot.version, rows=json.loads(snapshot.rows_json))
        return result

    def bulk_publish(self, db: Session, payload: BulkPublishRequest, user_id: str | None) -> BulkPublishRead:
        row = BulkPublishJob(project_id=payload.project_id, action=payload.action, target_template_ids_json=json.dumps(payload.target_template_ids), status="queued", created_by=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return job_to_read(row)


external_data_service = ExternalDataService()
