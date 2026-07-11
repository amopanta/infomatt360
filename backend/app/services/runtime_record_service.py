"""
Proyecto: InfoMatt360
Modulo: Runtime Record Service
Responsabilidad: Aplicar reglas de negocio para guardar y consultar capturas Runtime.
Dependencias: SQLAlchemy Session, modelos RuntimeRecord y RuntimeRecordValue.
Notas: El servicio no contiene logica HTTP; los routers solo exponen la API.
"""

import csv
import hashlib
import json
import logging
from datetime import timedelta
from io import StringIO
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models.files import FileAsset
from app.models.bulk_import import BulkImportJob
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.schemas.runtime_record import RuntimeBulkJobDetail, RuntimeBulkJobRead, RuntimeBulkJobSummary, RuntimeBulkSaveItemResult, RuntimeBulkSaveRequest, RuntimeBulkSaveResponse, RuntimeRecordCreate, RuntimeRecordPage, RuntimeRecordRead, RuntimeValueRead
from app.services.ai_audit_service import ai_audit_service
from app.services.approval_flow_service import approval_flow_service
from app.services.metrics_service import metrics_service

logger = logging.getLogger(__name__)


def value_to_read(row: RuntimeRecordValue) -> RuntimeValueRead:
    """Convierte un valor ORM en contrato de salida API."""
    return RuntimeValueRead(
        id=row.id,
        record_id=row.record_id,
        component_id=row.component_id,
        field_name=row.field_name,
        field_value_json=row.field_value_json,
    )


def record_to_read(db: Session, row: RuntimeRecord) -> RuntimeRecordRead:
    """Convierte la cabecera y sus valores en una respuesta consolidada."""
    values = db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id == row.id).all()
    return RuntimeRecordRead(
        id=row.id,
        project_id=row.project_id,
        template_id=row.template_id,
        version_id=row.version_id,
        approval_flow_id=row.approval_flow_id,
        approval_flow_version=row.approval_flow_version,
        status=row.status,
        submitted_by=row.submitted_by,
        device_id=row.device_id,
        ip_address=row.ip_address,
        duplicate_flag=row.duplicate_flag,
        created_at=row.created_at,
        updated_at=row.updated_at,
        values=[value_to_read(item) for item in values],
    )


def _compute_content_hash(project_id: str, template_id: str, values) -> str:
    """Hash estable de los valores capturados, para detectar reenvios identicos.

    No identifica que campo es "cedula" o "telefono" (el formulario es libre);
    en su lugar hashea todo el contenido, que es lo que el PDF de
    especificacion original describe como "hash de formulario".
    """
    canonical = sorted((item.field_name, item.field_value_json) for item in values)
    raw = json.dumps({"project_id": project_id, "template_id": template_id, "values": canonical}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RuntimeRecordService:
    """Reglas de negocio de persistencia Runtime."""

    def save_record(self, db: Session, payload: RuntimeRecordCreate, user_id: str | None) -> RuntimeRecordRead:
        """Guarda una captura Runtime completa en una unica transaccion logica.

        Crea primero la cabecera y luego cada valor capturado. El diseno es
        flexible para soportar campos simples y complejos sin migraciones por formulario.
        """
        approval_flow_id, approval_flow_version, approval_flow_snapshot_json = approval_flow_service.snapshot_for_record(db, payload.project_id, payload.template_id)
        content_hash = _compute_content_hash(payload.project_id, payload.template_id, payload.values)
        duplicate_window_start = utc_now() - timedelta(days=max(settings.duplicate_check_window_days, 0))
        has_recent_match = db.query(RuntimeRecord).filter(
            RuntimeRecord.project_id == payload.project_id,
            RuntimeRecord.template_id == payload.template_id,
            RuntimeRecord.content_hash == content_hash,
            RuntimeRecord.created_at >= duplicate_window_start,
        ).first() is not None
        record = RuntimeRecord(
            project_id=payload.project_id,
            template_id=payload.template_id,
            version_id=payload.version_id,
            approval_flow_id=approval_flow_id,
            approval_flow_version=approval_flow_version,
            approval_flow_snapshot_json=approval_flow_snapshot_json,
            status=payload.status,
            submitted_by=user_id,
            device_id=payload.device_id,
            ip_address=payload.ip_address,
            content_hash=content_hash,
            duplicate_flag="possible" if has_recent_match else "none",
        )
        try:
            db.add(record)
            # flush asigna el id sin confirmar la cabecera por separado.
            db.flush()
            for item in payload.values:
                db.add(
                    RuntimeRecordValue(
                        record_id=record.id,
                        component_id=item.component_id,
                        field_name=item.field_name,
                        field_value_json=item.field_value_json,
                    )
                )
                parsed_value = json.loads(item.field_value_json)
                for file_id in self._file_asset_ids(parsed_value):
                    asset = db.query(FileAsset).filter(FileAsset.id == file_id, FileAsset.project_id == payload.project_id).first()
                    if asset is None:
                        raise ValueError(f"Evidencia inexistente o fuera del proyecto: {file_id}")
                    if asset.record_id and asset.record_id != record.id:
                        raise ValueError(f"La evidencia ya pertenece a otro registro: {file_id}")
                    asset.record_id = record.id
            db.commit()
        except Exception:
            db.rollback()
            raise

        db.refresh(record)

        # Auditoria semantica con IA (ver docs/88): se ejecuta despues de que
        # el registro ya quedo guardado, nunca antes -- la captura de campo
        # no debe perderse ni demorarse por una llamada a IA lenta o caida.
        # No-op silencioso si la plantilla no tiene AiAuditConfig.
        try:
            ai_audit_service.audit_record(db, record)
        except Exception:
            logger.warning("La auditoria semantica del registro %s fallo de forma inesperada", record.id, exc_info=True)

        return record_to_read(db, record)

    def save_records_bulk(self, db: Session, payload: RuntimeBulkSaveRequest, user_id: str | None) -> RuntimeBulkSaveResponse:
        """Guarda registros por lotes para integraciones de alto volumen.

        En esta version cada registro se confirma de forma independiente para
        permitir continuar cuando un item del lote tiene errores. Si
        continue_on_error es false, se detiene en el primer error.
        """
        if payload.idempotency_key:
            request_hash = self._bulk_request_hash(payload)
            existing = db.query(BulkImportJob).filter(
                BulkImportJob.project_id == payload.project_id,
                BulkImportJob.template_id == payload.template_id,
                BulkImportJob.idempotency_key == payload.idempotency_key,
            ).first()
            if existing:
                if existing.request_hash and existing.request_hash != request_hash:
                    raise ValueError("La idempotency_key ya fue usada con un payload diferente")
                data = json.loads(existing.response_json)
                data["job_id"] = existing.id
                data["job_status"] = existing.status
                data["replayed"] = True
                return RuntimeBulkSaveResponse(**data)

        if payload.processing_mode == "queued":
            if not payload.idempotency_key:
                raise ValueError("processing_mode=queued requiere idempotency_key")
            job_id = str(uuid4())
            response = RuntimeBulkSaveResponse(
                project_id=payload.project_id,
                template_id=payload.template_id,
                job_id=job_id,
                idempotency_key=payload.idempotency_key,
                job_status="queued",
                processing_mode="queued",
                received=len(payload.records),
                created=0,
                failed=0,
                results=[],
            )
            db.add(BulkImportJob(
                id=job_id,
                project_id=payload.project_id,
                template_id=payload.template_id,
                idempotency_key=payload.idempotency_key,
                request_hash=self._bulk_request_hash(payload),
                payload_json=payload.model_dump_json(),
                response_json=response.model_dump_json(),
                status="queued",
            ))
            db.commit()
            return response

        results: list[RuntimeBulkSaveItemResult] = []
        created = 0
        failed = 0
        for index, item in enumerate(payload.records):
            try:
                if item.project_id != payload.project_id or item.template_id != payload.template_id:
                    raise ValueError("El registro no coincide con project_id/template_id del lote")
                saved = self.save_record(db, item, user_id)
                created += 1
                results.append(RuntimeBulkSaveItemResult(index=index, id=saved.id, status="created"))
            except Exception as exc:
                failed += 1
                results.append(RuntimeBulkSaveItemResult(index=index, status="failed", error=str(exc)))
                if not payload.continue_on_error:
                    break
        job_id = str(uuid4()) if payload.idempotency_key else None
        response = RuntimeBulkSaveResponse(
            project_id=payload.project_id,
            template_id=payload.template_id,
            job_id=job_id,
            idempotency_key=payload.idempotency_key,
            job_status="completed",
            processing_mode=payload.processing_mode,
            received=len(payload.records),
            created=created,
            failed=failed,
            results=results,
        )
        if payload.idempotency_key:
            db.add(BulkImportJob(
                id=job_id,
                project_id=payload.project_id,
                template_id=payload.template_id,
                idempotency_key=payload.idempotency_key,
                request_hash=self._bulk_request_hash(payload),
                payload_json=payload.model_dump_json(),
                response_json=response.model_dump_json(),
                status="completed",
                completed_at=utc_now(),
            ))
            db.commit()
        return response

    def process_bulk_job(self, db: Session, project_id: str, job_id: str, user_id: str | None, worker_id: str | None = None) -> RuntimeBulkJobDetail | None:
        job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id, BulkImportJob.project_id == project_id).first()
        if job is None:
            return None
        if job.status == "completed":
            return self.get_bulk_job(db, project_id, job_id)
        if job.status == "failed":
            return self.get_bulk_job(db, project_id, job_id)
        if job.status == "queued":
            claimed = self._claim_bulk_job(db, project_id, job_id, worker_id or user_id or "manual")
            if claimed is None:
                return self.get_bulk_job(db, project_id, job_id)
            job = claimed
        if job.status != "processing":
            raise ValueError(f"El lote no se puede procesar desde estado {job.status}")

        try:
            if not job.payload_json:
                raise ValueError("El lote no conserva payload para procesamiento")
            payload = RuntimeBulkSaveRequest(**json.loads(job.payload_json))
            self._heartbeat_bulk_job(db, project_id, job_id, job.worker_id)
            results, created, failed = self._process_bulk_records(db, payload, user_id, job_id=job_id, worker_id=job.worker_id)
            response = RuntimeBulkSaveResponse(
                project_id=payload.project_id,
                template_id=payload.template_id,
                job_id=job.id,
                idempotency_key=payload.idempotency_key,
                job_status="completed",
                processing_mode="queued",
                received=len(payload.records),
                created=created,
                failed=failed,
                results=results,
            )
            job.status = "completed"
            job.response_json = response.model_dump_json()
            job.completed_at = utc_now()
            job.last_error = None
            db.commit()
            metrics_service.record_bulk_job_completed()
        except Exception as exc:
            db.rollback()
            self._handle_bulk_job_failure(db, project_id, job_id, str(exc))
            raise
        return self.get_bulk_job(db, project_id, job_id)

    def process_queued_bulk_jobs(
        self,
        db: Session,
        *,
        limit: int = 50,
        project_id: str | None = None,
        template_id: str | None = None,
        user_id: str | None = None,
        worker_id: str = "bulk-worker",
    ) -> dict[str, object]:
        """Procesa lotes en cola desde un worker separado del proceso web."""
        safe_limit = max(1, min(limit, 500))
        recovered = self.recover_stale_bulk_jobs(db)
        now = utc_now()
        query = db.query(BulkImportJob).filter(
            BulkImportJob.status == "queued",
            or_(BulkImportJob.next_attempt_at.is_(None), BulkImportJob.next_attempt_at <= now),
        )
        if project_id:
            query = query.filter(BulkImportJob.project_id == project_id)
        if template_id:
            query = query.filter(BulkImportJob.template_id == template_id)
        jobs = query.order_by(BulkImportJob.created_at.asc()).limit(safe_limit).all()

        processed: list[dict[str, object]] = []
        failed: list[dict[str, str]] = []
        for job in jobs:
            try:
                detail = self.process_bulk_job(db, job.project_id, job.id, user_id, worker_id=worker_id)
                if detail:
                    processed.append(
                        {
                            "job_id": detail.id,
                            "project_id": detail.project_id,
                            "template_id": detail.template_id,
                            "status": detail.status,
                            "received": detail.received,
                            "created": detail.created,
                            "failed": detail.failed,
                        }
                    )
            except Exception as exc:
                db.rollback()
                failed.append({"job_id": job.id, "error": str(exc)})

        metrics_service.record_bulk_worker_cycle(
            picked=len(jobs),
            processed=len(processed),
            failed=len(failed),
            recovered_stale=int(recovered["recovered"]),
            failed_stale=int(recovered["failed"]),
        )
        return {
            "requested_limit": safe_limit,
            "recovered_stale": recovered["recovered"],
            "failed_stale": recovered["failed"],
            "picked": len(jobs),
            "processed": len(processed),
            "failed": len(failed),
            "processed_jobs": processed,
            "failed_jobs": failed,
            "recovered_jobs": recovered["recovered_jobs"],
            "failed_stale_jobs": recovered["failed_jobs"],
        }

    def recover_stale_bulk_jobs(self, db: Session) -> dict[str, object]:
        """Libera jobs que quedaron en processing por caida del worker."""
        stale_after = max(settings.bulk_worker_stale_after_seconds, 1)
        cutoff = utc_now() - timedelta(seconds=stale_after)
        stale_jobs = db.query(BulkImportJob).filter(
            BulkImportJob.status == "processing",
            BulkImportJob.locked_at.is_not(None),
            BulkImportJob.locked_at <= cutoff,
        ).order_by(BulkImportJob.locked_at.asc()).all()

        recovered: list[dict[str, str]] = []
        failed: list[dict[str, str]] = []
        for job in stale_jobs:
            job.last_error = "Worker sin heartbeat/timeout durante procesamiento"
            job.worker_id = None
            job.locked_at = None
            if job.attempt_count >= job.max_attempts:
                job.status = "failed"
                job.completed_at = utc_now()
                job.next_attempt_at = None
                failed.append({"job_id": job.id, "project_id": job.project_id})
                metrics_service.record_bulk_job_failed()
            else:
                job.status = "queued"
                job.next_attempt_at = self._next_bulk_retry_at(job.attempt_count)
                recovered.append({"job_id": job.id, "project_id": job.project_id})
                metrics_service.record_bulk_job_retry_scheduled()

        if stale_jobs:
            db.commit()
        return {
            "recovered": len(recovered),
            "failed": len(failed),
            "recovered_jobs": recovered,
            "failed_jobs": failed,
        }

    def _claim_bulk_job(self, db: Session, project_id: str, job_id: str, worker_id: str) -> BulkImportJob | None:
        now = utc_now()
        updated = db.query(BulkImportJob).filter(
            BulkImportJob.id == job_id,
            BulkImportJob.project_id == project_id,
            BulkImportJob.status == "queued",
        ).update(
            {
                BulkImportJob.status: "processing",
                BulkImportJob.worker_id: worker_id,
                BulkImportJob.locked_at: now,
                BulkImportJob.attempt_count: BulkImportJob.attempt_count + 1,
                BulkImportJob.next_attempt_at: None,
                BulkImportJob.last_error: None,
            },
            synchronize_session=False,
        )
        db.commit()
        if updated != 1:
            return None
        return db.query(BulkImportJob).filter(BulkImportJob.id == job_id, BulkImportJob.project_id == project_id).first()

    def _handle_bulk_job_failure(self, db: Session, project_id: str, job_id: str, error: str) -> None:
        job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id, BulkImportJob.project_id == project_id).first()
        if job is None:
            return
        job.last_error = error[:4000]
        job.worker_id = None
        job.locked_at = None
        if job.attempt_count >= job.max_attempts:
            job.status = "failed"
            job.completed_at = utc_now()
            job.next_attempt_at = None
            metrics_service.record_bulk_job_failed()
        else:
            job.status = "queued"
            job.next_attempt_at = self._next_bulk_retry_at(job.attempt_count)
            metrics_service.record_bulk_job_retry_scheduled()
        db.commit()

    def _next_bulk_retry_at(self, attempt_count: int):
        base = max(settings.bulk_worker_retry_backoff_seconds, 1)
        max_backoff = max(settings.bulk_worker_retry_max_backoff_seconds, base)
        delay_seconds = min(base * (2 ** max(attempt_count - 1, 0)), max_backoff)
        return utc_now() + timedelta(seconds=delay_seconds)

    def _heartbeat_bulk_job(self, db: Session, project_id: str, job_id: str, worker_id: str | None) -> None:
        query = db.query(BulkImportJob).filter(
            BulkImportJob.id == job_id,
            BulkImportJob.project_id == project_id,
            BulkImportJob.status == "processing",
        )
        if worker_id:
            query = query.filter(BulkImportJob.worker_id == worker_id)
        updated = query.update({BulkImportJob.locked_at: utc_now()}, synchronize_session=False)
        db.commit()
        if updated != 1:
            raise ValueError("No fue posible renovar el heartbeat del lote bulk")

    def _process_bulk_records(
        self,
        db: Session,
        payload: RuntimeBulkSaveRequest,
        user_id: str | None,
        *,
        job_id: str | None = None,
        worker_id: str | None = None,
    ) -> tuple[list[RuntimeBulkSaveItemResult], int, int]:
        results: list[RuntimeBulkSaveItemResult] = []
        created = 0
        failed = 0
        heartbeat_every = max(settings.bulk_worker_heartbeat_every_records, 1)
        for index, item in enumerate(payload.records):
            try:
                if item.project_id != payload.project_id or item.template_id != payload.template_id:
                    raise ValueError("El registro no coincide con project_id/template_id del lote")
                saved = self.save_record(db, item, user_id)
                created += 1
                results.append(RuntimeBulkSaveItemResult(index=index, id=saved.id, status="created"))
                if job_id and (index + 1) % heartbeat_every == 0:
                    self._heartbeat_bulk_job(db, payload.project_id, job_id, worker_id)
            except Exception as exc:
                failed += 1
                results.append(RuntimeBulkSaveItemResult(index=index, status="failed", error=str(exc)))
                if not payload.continue_on_error:
                    break
        return results, created, failed

    def list_bulk_jobs(self, db: Session, project_id: str, template_id: str | None = None, status: str | None = None, limit: int = 25, offset: int = 0) -> list[RuntimeBulkJobRead]:
        query = db.query(BulkImportJob).filter(BulkImportJob.project_id == project_id)
        if template_id:
            query = query.filter(BulkImportJob.template_id == template_id)
        if status:
            query = query.filter(BulkImportJob.status == status)
        rows = query.order_by(BulkImportJob.created_at.desc()).offset(offset).limit(limit).all()
        return [self._bulk_job_to_read(row) for row in rows]

    def get_bulk_job(self, db: Session, project_id: str, job_id: str) -> RuntimeBulkJobDetail | None:
        row = db.query(BulkImportJob).filter(BulkImportJob.id == job_id, BulkImportJob.project_id == project_id).first()
        if row is None:
            return None
        summary = self._bulk_job_to_read(row)
        response = self._bulk_job_response(row)
        return RuntimeBulkJobDetail(**summary.model_dump(), response=response)

    def summarize_bulk_jobs(self, db: Session, project_id: str, template_id: str | None = None) -> RuntimeBulkJobSummary:
        query = db.query(BulkImportJob).filter(BulkImportJob.project_id == project_id)
        if template_id:
            query = query.filter(BulkImportJob.template_id == template_id)
        rows = query.all()
        summary = RuntimeBulkJobSummary(project_id=project_id)
        for row in rows:
            summary.total_jobs += 1
            if row.status == "queued":
                summary.queued_jobs += 1
            elif row.status == "processing":
                summary.processing_jobs += 1
            elif row.status == "completed":
                summary.completed_jobs += 1
            elif row.status == "failed":
                summary.failed_jobs += 1

            response = self._bulk_job_response(row)
            if response:
                summary.total_received += response.received
                summary.total_created += response.created
                summary.total_failed += response.failed
        total_finished_items = summary.total_created + summary.total_failed
        summary.success_rate = round((summary.total_created / total_finished_items) * 100, 2) if total_finished_items else 0
        return summary

    def export_bulk_job_errors_csv(self, db: Session, project_id: str, job_id: str) -> str | None:
        row = db.query(BulkImportJob).filter(BulkImportJob.id == job_id, BulkImportJob.project_id == project_id).first()
        if row is None:
            return None
        response = self._bulk_job_response(row)
        failed_results = [item for item in response.results if item.status == "failed"] if response else []
        output = StringIO()
        output.write("\ufeff")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["job_id", "idempotency_key", "template_id", "index", "status", "error"])
        for item in failed_results:
            writer.writerow([
                row.id,
                self._safe_csv_cell(row.idempotency_key),
                self._safe_csv_cell(row.template_id),
                item.index,
                item.status,
                self._safe_csv_cell(item.error or ""),
            ])
        return output.getvalue()

    def _bulk_job_to_read(self, row: BulkImportJob) -> RuntimeBulkJobRead:
        response = self._bulk_job_response(row)
        return RuntimeBulkJobRead(
            id=row.id,
            project_id=row.project_id,
            template_id=row.template_id,
            idempotency_key=row.idempotency_key,
            status=row.status,
            created_at=row.created_at,
            completed_at=row.completed_at,
            worker_id=row.worker_id,
            locked_at=row.locked_at,
            attempt_count=row.attempt_count,
            max_attempts=row.max_attempts,
            next_attempt_at=row.next_attempt_at,
            last_error=row.last_error,
            received=response.received if response else 0,
            created=response.created if response else 0,
            failed=response.failed if response else 0,
        )

    def _bulk_job_response(self, row: BulkImportJob) -> RuntimeBulkSaveResponse | None:
        try:
            data = json.loads(row.response_json)
        except json.JSONDecodeError:
            return None
        data["job_id"] = row.id
        return RuntimeBulkSaveResponse(**data)

    def _bulk_request_hash(self, payload: RuntimeBulkSaveRequest) -> str:
        raw = payload.model_dump_json(exclude={"idempotency_key"})
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _file_asset_ids(self, value: object) -> set[str]:
        if isinstance(value, dict):
            own_id = value.get("file_asset_id")
            nested = {item for child in value.values() for item in self._file_asset_ids(child)}
            return nested | ({own_id} if isinstance(own_id, str) and own_id else set())
        if isinstance(value, list):
            return {item for child in value for item in self._file_asset_ids(child)}
        return set()

    def get_record(self, db: Session, record_id: str) -> RuntimeRecordRead | None:
        """Consulta una captura por identificador."""
        row = db.query(RuntimeRecord).filter(RuntimeRecord.id == record_id).first()
        return record_to_read(db, row) if row else None

    def list_template_records(self, db: Session, template_id: str) -> list[RuntimeRecordRead]:
        """Lista capturas asociadas a una plantilla Runtime."""
        rows = db.query(RuntimeRecord).filter(RuntimeRecord.template_id == template_id).order_by(RuntimeRecord.created_at.desc()).all()
        return [record_to_read(db, row) for row in rows]

    def search_template_records(self, db: Session, template_id: str, search: str | None = None, status: str | None = None, limit: int = 25, offset: int = 0) -> RuntimeRecordPage:
        """Consulta paginada de registros Runtime con filtros seguros para uso operativo."""
        query = self._filtered_records_query(db, template_id, search, status)
        total = query.count()
        rows = query.order_by(RuntimeRecord.created_at.desc()).offset(offset).limit(limit).all()
        return RuntimeRecordPage(items=[record_to_read(db, row) for row in rows], total=total, limit=limit, offset=offset)

    def export_template_csv(self, db: Session, template_id: str, search: str | None = None, status: str | None = None) -> str:
        records = self._filtered_records_query(db, template_id, search, status).order_by(RuntimeRecord.created_at.desc()).all()
        record_ids = [record.id for record in records]
        values = db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id.in_(record_ids)).all() if record_ids else []
        field_names = sorted({value.field_name for value in values})
        by_record: dict[str, dict[str, str]] = {}
        for value in values:
            by_record.setdefault(value.record_id, {})[value.field_name] = self._csv_value(value.field_value_json)

        output = StringIO()
        output.write("\ufeff")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["record_id", "fecha", "estado", "capturado_por", *[self._safe_csv_cell(name) for name in field_names]])
        for record in records:
            row_values = by_record.get(record.id, {})
            writer.writerow([
                record.id,
                record.created_at.isoformat(),
                record.status,
                record.submitted_by or "",
                *[self._safe_csv_cell(row_values.get(name, "")) for name in field_names],
            ])
        return output.getvalue()

    def _csv_value(self, raw: str) -> str:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return self._safe_csv_cell(raw)
        if value is None:
            return ""
        if isinstance(value, bool):
            return "Si" if value else "No"
        if isinstance(value, (dict, list)):
            return self._safe_csv_cell(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
        return self._safe_csv_cell(str(value))

    def _safe_csv_cell(self, value: str) -> str:
        return f"'{value}" if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value

    def _filtered_records_query(self, db: Session, template_id: str, search: str | None = None, status: str | None = None):
        query = db.query(RuntimeRecord).filter(RuntimeRecord.template_id == template_id)
        if status:
            query = query.filter(RuntimeRecord.status == status)
        normalized_search = search.strip() if search else ""
        if normalized_search:
            needle = f"%{normalized_search}%"
            matching_record_ids = db.query(RuntimeRecordValue.record_id).filter(
                or_(RuntimeRecordValue.field_name.ilike(needle), RuntimeRecordValue.field_value_json.ilike(needle))
            )
            query = query.filter(
                or_(
                    RuntimeRecord.id.ilike(needle),
                    RuntimeRecord.submitted_by.ilike(needle),
                    RuntimeRecord.status.ilike(needle),
                    RuntimeRecord.id.in_(matching_record_ids),
                )
            )
        return query


runtime_record_service = RuntimeRecordService()
