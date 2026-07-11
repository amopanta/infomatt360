"""Carga masiva desde Excel: subir+previsualizar, confirmar mapeo, aprobar.

No reutiliza el worker de `bulk_import.py` (ese es para sincronizar
respuestas de formulario ya estructuradas via API/dispositivo). Este motor
importa filas crudas de un archivo .xlsx hacia participantes o usuarios,
validando y dejando reporte de errores antes de decidir importar.
"""

import json
from io import BytesIO

from fastapi import HTTPException, status
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.excel_import import ExcelImportJob
from app.schemas.excel_import import ExcelImportJobRead
from app.schemas.identity import UserCreate
from app.schemas.participants import ParticipantCreate
from app.services.identity_service import identity_service
from app.services.participant_service import participant_service

PREVIEW_ROW_LIMIT = 20

ENTITY_ALIASES: dict[str, dict[str, str]] = {
    "participants": {
        "documento": "document_id",
        "cedula": "document_id",
        "identificacion": "document_id",
        "nombre": "full_name",
        "nombre completo": "full_name",
        "codigo": "external_code",
        "codigo externo": "external_code",
        "tipo": "participant_type",
    },
    "users": {
        "documento": "document_id",
        "cedula": "document_id",
        "nombre": "full_name",
        "nombre completo": "full_name",
        "correo": "email",
        "email": "email",
        "correo electronico": "email",
        "telefono": "phone",
        "celular": "phone",
    },
}

PARTICIPANT_TARGET_FIELDS = {"document_id", "full_name", "external_code", "participant_type"}
USER_TARGET_FIELDS = {"document_id", "full_name", "email", "phone"}

REQUIRED_FIELDS = {
    "participants": {"full_name"},
    "users": {"full_name", "document_id", "email"},
}


def _to_read(row: ExcelImportJob) -> ExcelImportJobRead:
    return ExcelImportJobRead(
        id=row.id,
        project_id=row.project_id,
        entity_type=row.entity_type,
        source_filename=row.source_filename,
        status=row.status,
        column_mapping=json.loads(row.column_mapping_json) if row.column_mapping_json else None,
        preview=json.loads(row.preview_json) if row.preview_json else None,
        total_rows=row.total_rows,
        imported_rows=row.imported_rows,
        failed_rows=row.failed_rows,
        error_report=json.loads(row.error_report_json) if row.error_report_json else None,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


class ExcelImportService:
    def upload_and_preview(self, db: Session, project_id: str, entity_type: str, filename: str, content: bytes, user_id: str) -> ExcelImportJobRead:
        if entity_type not in ENTITY_ALIASES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Tipo de entidad no soportado para carga Excel")
        try:
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
            sheet = workbook.active
            rows_iter = sheet.iter_rows(values_only=True)
            first_row = next(rows_iter, [])
            headers = [str(cell).strip() if cell is not None else "" for cell in first_row]
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"No fue posible leer el archivo Excel: {exc}") from exc

        data_rows: list[dict[str, object]] = []
        for values in rows_iter:
            if values is None or all(value is None for value in values):
                continue
            data_rows.append({headers[i]: values[i] for i in range(len(headers)) if i < len(values)})

        auto_mapping = self._auto_detect_mapping(headers, entity_type)

        row = ExcelImportJob(
            project_id=project_id,
            entity_type=entity_type,
            source_filename=filename,
            status="uploaded",
            column_mapping_json=json.dumps(auto_mapping),
            preview_json=json.dumps({"headers": headers, "sample_rows": data_rows[:PREVIEW_ROW_LIMIT]}),
            rows_json=json.dumps(data_rows),
            total_rows=len(data_rows),
            created_by=user_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def confirm_mapping(self, db: Session, job_id: str, column_mapping: dict[str, str]) -> ExcelImportJobRead:
        row = self._get_or_404(db, job_id)
        if row.status not in {"uploaded", "mapped"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El lote ya fue procesado")
        row.column_mapping_json = json.dumps(column_mapping)
        row.status = "mapped"
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def approve_and_import(self, db: Session, job_id: str, approved_by: str) -> ExcelImportJobRead:
        row = self._get_or_404(db, job_id)
        if row.status != "mapped":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El lote debe estar mapeado antes de aprobarse")

        mapping = json.loads(row.column_mapping_json) if row.column_mapping_json else {}
        data_rows = json.loads(row.rows_json) if row.rows_json else []
        required = REQUIRED_FIELDS.get(row.entity_type, set())
        target_fields = PARTICIPANT_TARGET_FIELDS if row.entity_type == "participants" else USER_TARGET_FIELDS

        errors: list[dict[str, object]] = []
        imported = 0
        for index, data_row in enumerate(data_rows):
            mapped_raw = {target_field: data_row.get(source_header) for source_header, target_field in mapping.items() if target_field in target_fields}
            mapped = {key: (str(value).strip() if value is not None else None) for key, value in mapped_raw.items()}
            missing = [field for field in required if not mapped.get(field)]
            if missing:
                errors.append({"row": index + 2, "error": f"Campos obligatorios faltantes: {', '.join(missing)}"})
                continue
            try:
                if row.entity_type == "participants":
                    participant_service.create_participant(db, ParticipantCreate(project_id=row.project_id, **mapped))
                else:
                    identity_service.create_user(db, UserCreate(**mapped))
                imported += 1
            except HTTPException as exc:
                db.rollback()
                errors.append({"row": index + 2, "error": str(exc.detail)})
            except Exception as exc:
                db.rollback()
                errors.append({"row": index + 2, "error": str(exc)})

        row.status = "completed"
        row.imported_rows = imported
        row.failed_rows = len(errors)
        row.error_report_json = json.dumps(errors) if errors else None
        row.approved_by = approved_by
        row.approved_at = utc_now()
        row.completed_at = utc_now()
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def get_job(self, db: Session, job_id: str) -> ExcelImportJobRead | None:
        row = db.query(ExcelImportJob).filter(ExcelImportJob.id == job_id).first()
        return _to_read(row) if row else None

    def list_jobs(self, db: Session, project_id: str) -> list[ExcelImportJobRead]:
        rows = db.query(ExcelImportJob).filter(ExcelImportJob.project_id == project_id).order_by(ExcelImportJob.created_at.desc()).all()
        return [_to_read(row) for row in rows]

    def _auto_detect_mapping(self, headers: list[str], entity_type: str) -> dict[str, str]:
        aliases = ENTITY_ALIASES[entity_type]
        mapping: dict[str, str] = {}
        for header in headers:
            target = aliases.get(header.strip().lower())
            if target:
                mapping[header] = target
        return mapping

    def _get_or_404(self, db: Session, job_id: str) -> ExcelImportJob:
        row = db.query(ExcelImportJob).filter(ExcelImportJob.id == job_id).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote de carga Excel no encontrado")
        return row


excel_import_service = ExcelImportService()
