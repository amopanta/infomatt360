"""Importación desde una base de datos externa hacia InfoMatt360 (docs/146).

Flujo: conexión (destino de la base espejo) → tabla o vista → mapeo de
columnas (con sugerencia automática) → vista previa sin escribir → ejecución
manual o programada → historial con conteos y errores por fila.

Reglas:
- solo se leen tablas o vistas que existen en el origen (sin SQL libre);
- cada fila se identifica por `key_column`: repetir la importación no
  duplica y una fila sin cambios no se vuelve a escribir (hash);
- escribe con los servicios y permisos de InfoMatt360, en nombre de quien
  creó la importación, y respeta su territorio;
- un registro aprobado no se modifica (docs/141).
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.orm import Session

from app.api.permissions import get_project_permissions, participant_visible
from app.core.permissions import IDENTITY_USERS_MANAGE, MIRROR_MANAGE, PARTICIPANTS_CREATE, RECORDS_WRITE
from app.core.time import utc_now
from app.models.audit import AuditLog
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.db_import import DbImport, DbImportKey, DbImportRun
from app.models.identity import User
from app.models.mirror import MirrorTarget
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.services.project_export_service import slug

ENTITIES = {"participants", "records", "assignments"}
MAX_ROWS = 50_000
PREVIEW_ROWS = 20
PARTICIPANT_FIELDS = ["document_id", "external_code", "full_name", "participant_type", "department", "municipality", "group_name"]
ASSIGNMENT_FIELDS = ["participant_key", "responsible_email"]
RECORD_META_FIELDS = ["participant_key"]
ENTITY_PERMISSIONS = {"participants": {PARTICIPANTS_CREATE, IDENTITY_USERS_MANAGE}, "records": {RECORDS_WRITE},
                      "assignments": {IDENTITY_USERS_MANAGE}}


def require_permissions(db: Session, user_id: str, project_id: str, entity: str) -> None:
    _, permissions = get_project_permissions(db, user_id, project_id)
    if MIRROR_MANAGE not in permissions:
        raise HTTPException(status_code=403, detail="Se requiere mirror.manage para conectar bases externas")
    if not permissions & ENTITY_PERMISSIONS[entity]:
        raise HTTPException(status_code=403, detail="No tienes permiso para crear este tipo de información en el proyecto")


def _engine(db: Session, source_id: str, project_id: str):
    from app.services.mirror_service import mirror_service
    target = db.get(MirrorTarget, source_id)
    if target is None or target.project_id != project_id:
        raise HTTPException(status_code=404, detail="Conexión no encontrada en el proyecto")
    return mirror_service._engine_for_target(target)


def target_fields(db: Session, entity: str, template_id: str | None) -> list[str]:
    if entity == "participants":
        return PARTICIPANT_FIELDS
    if entity == "assignments":
        return ASSIGNMENT_FIELDS
    names = [row[0] for row in db.query(BuilderComponent.name).filter(BuilderComponent.template_id == template_id).all()]
    return RECORD_META_FIELDS + sorted(set(names), key=names.index)


def describe_source(db: Session, project_id: str, source_id: str, entity: str, source_table: str | None, template_id: str | None) -> dict:
    """Tablas y vistas del origen; con una tabla, sus columnas y el mapeo sugerido."""
    engine = _engine(db, source_id, project_id)
    try:
        inspector = inspect(engine)
        tables = sorted(inspector.get_table_names() + inspector.get_view_names())
        result: dict = {"tables": [t for t in tables if not t.startswith("im360_")], "columns": [], "suggested_mapping": {}}
        if source_table:
            if source_table not in tables:
                raise HTTPException(status_code=422, detail="La tabla o vista no existe en el origen")
            columns = [c["name"] for c in inspector.get_columns(source_table)]
            by_slug = {slug(c, 80): c for c in columns}
            aliases = {"document_id": ["documento", "cedula", "numero_documento", "document"], "external_code": ["codigo", "code", "codigo_externo"],
                       "full_name": ["nombre", "nombre_completo", "name"], "department": ["departamento"], "municipality": ["municipio"],
                       "group_name": ["grupo"], "participant_type": ["tipo"], "participant_key": ["documento", "cedula", "codigo"],
                       "responsible_email": ["correo", "email", "correo_responsable", "responsable"]}
            suggested = {}
            for field in target_fields(db, entity, template_id):
                for candidate in [slug(field, 80), *aliases.get(field, [])]:
                    if candidate in by_slug:
                        suggested[field] = by_slug[candidate]
                        break
            result.update({"columns": columns, "suggested_mapping": suggested})
        return result
    finally:
        engine.dispose()


def _plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def _read_rows(db: Session, job: DbImport, limit: int) -> tuple[list[dict], str | None]:
    engine = _engine(db, job.source_id, job.project_id)
    try:
        inspector = inspect(engine)
        if job.source_table not in inspector.get_table_names() + inspector.get_view_names():
            raise HTTPException(status_code=422, detail="La tabla o vista ya no existe en el origen")
        table = Table(job.source_table, MetaData(), autoload_with=engine)
        query = select(table)
        if job.cursor_column:
            column = table.c[job.cursor_column]
            if job.last_cursor is not None:
                query = query.where(column > job.last_cursor)
            query = query.order_by(column)
        with engine.connect() as conn:
            rows = [{key: _plain(value) for key, value in row._mapping.items()} for row in conn.execute(query.limit(limit))]
        cursor = str(rows[-1][job.cursor_column]) if job.cursor_column and rows else job.last_cursor
        return rows, cursor
    finally:
        engine.dispose()


def _row_hash(mapped: dict) -> str:
    return hashlib.sha256(json.dumps(mapped, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")).hexdigest()


def _find_participant(db: Session, project_id: str, key: str) -> Participant | None:
    key = key.strip()
    if not key:
        return None
    return (db.query(Participant).filter(Participant.project_id == project_id, Participant.document_id == key).first()
            or db.query(Participant).filter(Participant.project_id == project_id, Participant.external_code == key).first())


class RowResult(Exception):
    def __init__(self, outcome: str, message: str = ""):
        super().__init__(message)
        self.outcome, self.message = outcome, message


def _apply_participant(db: Session, job: DbImport, actor: User, mapped: dict, dry_run: bool) -> str:
    key_field = "document_id" if mapped.get("document_id") else "external_code"
    key = str(mapped.get(key_field) or "").strip()
    if not key:
        raise RowResult("failed", "Falta el documento o el código del participante")
    if not str(mapped.get("full_name") or "").strip():
        raise RowResult("failed", "Falta el nombre completo")
    existing = db.query(Participant).filter(Participant.project_id == job.project_id, getattr(Participant, key_field) == key).first()
    meta_updates = {k: str(mapped[k]).strip() for k in ("department", "municipality", "group_name") if mapped.get(k)}
    probe = existing or Participant(project_id=job.project_id, full_name=str(mapped["full_name"]), metadata_json=json.dumps(meta_updates))
    if existing is not None:
        meta = json.loads(existing.metadata_json or "{}") if existing.metadata_json else {}
        probe_meta = {**meta, **meta_updates}
        probe = Participant(project_id=job.project_id, full_name=existing.full_name, metadata_json=json.dumps(probe_meta))
    if not participant_visible(db, actor.id, probe):
        raise RowResult("failed", "Participante fuera de tu territorio autorizado")
    if dry_run:
        return "updated" if existing else "created"
    if existing is None:
        db.add(Participant(project_id=job.project_id, full_name=str(mapped["full_name"]).strip(),
                           document_id=str(mapped.get("document_id") or "").strip() or None,
                           external_code=str(mapped.get("external_code") or "").strip() or None,
                           participant_type=str(mapped.get("participant_type") or "person").strip(),
                           metadata_json=json.dumps(meta_updates, ensure_ascii=False) if meta_updates else None))
        return "created"
    meta = json.loads(existing.metadata_json or "{}") if existing.metadata_json else {}
    existing.full_name = str(mapped["full_name"]).strip()
    for field in ("document_id", "external_code", "participant_type"):
        if mapped.get(field):
            setattr(existing, field, str(mapped[field]).strip())
    existing.metadata_json = json.dumps({**meta, **meta_updates}, ensure_ascii=False)
    return "updated"


def _apply_record(db: Session, job: DbImport, actor: User, mapped: dict, source_key: str, previous: DbImportKey | None, dry_run: bool) -> tuple[str, str | None]:
    from app.api.permissions import allowed_form_participant_ids
    from app.schemas.runtime_record import RuntimeRecordCreate, RuntimeValueCreate
    from app.services.runtime_record_service import runtime_record_service
    template = db.get(BuilderTemplate, job.template_id)
    participant = _find_participant(db, job.project_id, str(mapped.get("participant_key") or "")) if mapped.get("participant_key") else None
    if mapped.get("participant_key") and participant is None:
        raise RowResult("failed", "No existe un participante con ese documento o código")
    allowed = allowed_form_participant_ids(db, actor.id, template)
    if participant is not None and allowed is not None and participant.id not in allowed:
        raise RowResult("failed", "Participante fuera de tu territorio o sin asignación en este formulario")
    values = [RuntimeValueCreate(field_name=name, field_value_json=json.dumps(value, ensure_ascii=False, default=str))
              for name, value in mapped.items() if name != "participant_key" and value is not None]
    if not values:
        raise RowResult("failed", "La fila no trae respuestas")
    if previous is not None:
        record = db.get(RuntimeRecord, previous.entity_id)
        if record is not None:
            if record.status in {"approved", "synced"}:
                raise RowResult("unchanged", "Registro aprobado: no se modifica")
            if dry_run:
                return "updated", record.id
            before = {v.field_name: v.field_value_json for v in db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id == record.id).all()}
            db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id == record.id).delete()
            for value in values:
                db.add(RuntimeRecordValue(record_id=record.id, field_name=value.field_name, field_value_json=value.field_value_json))
            record.lock_version += 1
            record.updated_at = utc_now()
            db.add(AuditLog(project_id=job.project_id, user_id=actor.id, module="integrations", action="db_import_record_updated",
                            entity_type="runtime_record", entity_id=record.id, before_json=json.dumps(before, ensure_ascii=False),
                            after_json=json.dumps({"import_id": job.id, "source_key": source_key}, ensure_ascii=False)))
            return "updated", record.id
    if dry_run:
        return "created", None
    saved = runtime_record_service.save_record(db, RuntimeRecordCreate(project_id=job.project_id, template_id=job.template_id,
                                                                        status=job.record_status, participant_id=participant.id if participant else None,
                                                                        values=values), actor.id)
    return "created", saved.id


def _apply_assignment(db: Session, job: DbImport, actor: User, mapped: dict, dry_run: bool) -> str:
    from app.services.form_assignment_service import upsert_assignment
    participant = _find_participant(db, job.project_id, str(mapped.get("participant_key") or ""))
    if participant is None:
        raise RowResult("failed", "No existe un participante con ese documento o código")
    email = str(mapped.get("responsible_email") or "").strip().lower()
    responsible = db.query(User).filter(User.email == email).first() if email else None
    if responsible is None or responsible.status != "active":
        raise RowResult("failed", "El responsable no existe o está inactivo")
    if not participant_visible(db, responsible.id, participant):
        raise RowResult("failed", "El responsable no puede acceder al territorio del participante")
    template = db.get(BuilderTemplate, job.template_id)
    if dry_run:
        return "created"
    from app.models.form_assignment import ParticipantFormAssignment
    existing = db.query(ParticipantFormAssignment).filter_by(template_id=template.id, participant_id=participant.id).first()
    if existing is not None and existing.responsible_user_id == responsible.id:
        return "unchanged"
    upsert_assignment(db, template, participant.id, responsible.id, actor.id)
    return "updated" if existing else "created"


def execute(db: Session, job: DbImport, triggered_by: str, dry_run: bool = False) -> dict:
    actor = db.get(User, job.created_by)
    if actor is None or actor.status != "active":
        raise HTTPException(status_code=403, detail="Quien creó la importación ya no está activo; vuelve a crearla")
    require_permissions(db, actor.id, job.project_id, job.entity)
    mapping = json.loads(job.mapping_json)
    rows, cursor = _read_rows(db, job, PREVIEW_ROWS if dry_run else MAX_ROWS)
    counts = {"rows_read": len(rows), "created": 0, "updated": 0, "unchanged": 0, "failed": 0}
    errors: list[dict] = []
    preview: list[dict] = []
    run = None
    if not dry_run:
        run = DbImportRun(import_id=job.id, triggered_by=triggered_by)
        db.add(run)
        db.commit()  # el historial queda aunque una fila falle y se revierta
        run_id = run.id
    for index, row in enumerate(rows, start=1):
        source_key = str(row.get(job.key_column) if row.get(job.key_column) is not None else "").strip()
        mapped = {field: row.get(column) for field, column in mapping.items() if column in row}
        try:
            if not source_key:
                raise RowResult("failed", f"La columna clave «{job.key_column}» está vacía")
            row_hash = _row_hash(mapped)
            previous = db.query(DbImportKey).filter_by(import_id=job.id, source_key=source_key[:200]).first()
            if previous is not None and previous.row_hash == row_hash:
                raise RowResult("unchanged", "Sin cambios desde la última importación")
            if job.entity == "participants":
                outcome, entity_id = _apply_participant(db, job, actor, mapped, dry_run), None
            elif job.entity == "records":
                outcome, entity_id = _apply_record(db, job, actor, mapped, source_key, previous, dry_run)
            else:
                outcome, entity_id = _apply_assignment(db, job, actor, mapped, dry_run), None
            if not dry_run:
                db.flush()
                if entity_id is None and job.entity == "participants":
                    key_field = "document_id" if mapped.get("document_id") else "external_code"
                    found = db.query(Participant).filter(Participant.project_id == job.project_id,
                                                         getattr(Participant, key_field) == str(mapped[key_field]).strip()).first()
                    entity_id = found.id if found else ""
                if previous is None:
                    db.add(DbImportKey(import_id=job.id, source_key=source_key[:200], entity_id=entity_id or "", row_hash=row_hash))
                else:
                    previous.row_hash, previous.updated_at = row_hash, utc_now()
                    previous.entity_id = entity_id or previous.entity_id
                db.commit()
            counts[outcome] += 1
            if dry_run:
                preview.append({"row": index, "key": source_key, "outcome": outcome, "values": mapped})
        except RowResult as result:
            if not dry_run:
                db.rollback()
            counts[result.outcome] += 1
            if result.outcome == "failed" and len(errors) < 200:
                errors.append({"row": index, "key": source_key, "error": result.message})
            if dry_run:
                preview.append({"row": index, "key": source_key, "outcome": result.outcome, "message": result.message, "values": mapped})
        except HTTPException as exc:
            if not dry_run:
                db.rollback()
            counts["failed"] += 1
            if len(errors) < 200:
                errors.append({"row": index, "key": source_key, "error": str(exc.detail)})
    if dry_run:
        return {**counts, "preview": preview, "errors": errors}
    run = db.get(DbImportRun, run_id)
    run.rows_read, run.created, run.updated, run.unchanged, run.failed = (counts["rows_read"], counts["created"], counts["updated"],
                                                                          counts["unchanged"], counts["failed"])
    run.errors_json = json.dumps(errors, ensure_ascii=False) if errors else None
    run.status = "completed" if not counts["failed"] else "completed_with_errors"
    run.finished_at = utc_now()
    job = db.get(DbImport, job.id)
    if counts["failed"] == 0 or job.cursor_column is None:
        job.last_cursor = cursor
    job.last_result = (f"{run.status}: {counts['rows_read']} leídas, {counts['created']} creadas, {counts['updated']} actualizadas, "
                       f"{counts['unchanged']} sin cambios, {counts['failed']} con error")
    job.updated_at = utc_now()
    db.add(AuditLog(project_id=job.project_id, user_id=actor.id, module="integrations", action="db_import_run", entity_type="db_import",
                    entity_id=job.id, after_json=json.dumps({**counts, "triggered_by": triggered_by}, ensure_ascii=False)))
    db.commit()
    return {**counts, "run_id": run.id, "status": run.status, "errors": errors}
