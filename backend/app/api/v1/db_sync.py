"""Importación desde bases de datos externas (docs/146)."""

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.builder import BuilderTemplate
from app.models.db_import import DbImport, DbImportRun
from app.models.identity import User
from app.services import db_import_service as svc
from app.services.assignment_service import assignment_service

router = APIRouter()


class ImportWrite(BaseModel):
    source_id: str
    name: str = Field(min_length=3, max_length=180)
    entity: Literal["participants", "records", "assignments"]
    source_table: str = Field(min_length=1, max_length=180)
    template_id: str | None = None
    mapping: dict[str, str] = Field(min_length=1)
    key_column: str = Field(min_length=1, max_length=180)
    cursor_column: str | None = Field(default=None, max_length=180)
    record_status: Literal["draft", "submitted", "approved"] = "submitted"


class ImportStatus(BaseModel):
    status: Literal["active", "paused"]


def _access(db: Session, user: User, project_id: str, entity: str) -> None:
    if not assignment_service.user_has_project_access(db, user.id, project_id):
        raise HTTPException(status_code=403, detail="Sin acceso al proyecto")
    svc.require_permissions(db, user.id, project_id, entity)


def _read(job: DbImport) -> dict:
    return {"id": job.id, "project_id": job.project_id, "source_id": job.source_id, "name": job.name, "entity": job.entity,
            "source_table": job.source_table, "template_id": job.template_id, "mapping": json.loads(job.mapping_json),
            "key_column": job.key_column, "cursor_column": job.cursor_column, "last_cursor": job.last_cursor,
            "record_status": job.record_status, "status": job.status, "last_result": job.last_result, "updated_at": job.updated_at}


def _job(db: Session, user: User, import_id: str) -> DbImport:
    job = db.get(DbImport, import_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Importación no encontrada")
    _access(db, user, job.project_id, job.entity)
    return job


@router.get("/{project_id}/sources/{source_id}/describe")
def describe(project_id: str, source_id: str, entity: Literal["participants", "records", "assignments"] = "participants",
             source_table: str | None = None, template_id: str | None = None,
             db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    _access(db, user, project_id, entity)
    result = svc.describe_source(db, project_id, source_id, entity, source_table, template_id)
    result["target_fields"] = svc.target_fields(db, entity, template_id) if entity != "records" or template_id else []
    return result


@router.get("/{project_id}/imports")
def list_imports(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    if not assignment_service.user_has_project_access(db, user.id, project_id):
        raise HTTPException(status_code=403, detail="Sin acceso al proyecto")
    rows = db.query(DbImport).filter(DbImport.project_id == project_id).order_by(DbImport.created_at.desc()).all()
    visible = []
    for row in rows:
        try:
            svc.require_permissions(db, user.id, project_id, row.entity)
            visible.append(_read(row))
        except HTTPException:
            continue
    return visible


@router.post("/{project_id}/imports", status_code=201)
def create_import(project_id: str, payload: ImportWrite, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    _access(db, user, project_id, payload.entity)
    if payload.entity in {"records", "assignments"}:
        template = db.get(BuilderTemplate, payload.template_id) if payload.template_id else None
        if template is None or template.project_id != project_id:
            raise HTTPException(status_code=422, detail="Elige un formulario del proyecto")
    described = svc.describe_source(db, project_id, payload.source_id, payload.entity, payload.source_table, payload.template_id)
    columns = set(described["columns"])
    allowed_fields = set(svc.target_fields(db, payload.entity, payload.template_id))
    unknown_fields = sorted(set(payload.mapping) - allowed_fields)
    unknown_columns = sorted({c for c in payload.mapping.values() if c not in columns} | ({payload.key_column} - columns)
                             | ({payload.cursor_column} - columns if payload.cursor_column else set()))
    if unknown_fields:
        raise HTTPException(status_code=422, detail=f"Campos de destino no válidos: {', '.join(unknown_fields)}")
    if unknown_columns:
        raise HTTPException(status_code=422, detail=f"Columnas que no existen en el origen: {', '.join(unknown_columns)}")
    job = DbImport(project_id=project_id, source_id=payload.source_id, name=payload.name.strip(), entity=payload.entity,
                   source_table=payload.source_table, template_id=payload.template_id,
                   mapping_json=json.dumps(payload.mapping, ensure_ascii=False), key_column=payload.key_column,
                   cursor_column=payload.cursor_column or None, record_status=payload.record_status, created_by=user.id)
    db.add(job)
    db.commit()
    return _read(job)


@router.patch("/imports/{import_id}")
def set_status(import_id: str, payload: ImportStatus, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    job = _job(db, user, import_id)
    job.status = payload.status
    db.commit()
    return _read(job)


@router.post("/imports/{import_id}/preview")
def preview(import_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """Primeras filas con lo que pasaría (crear, actualizar, sin cambios, error), sin escribir nada."""
    return svc.execute(db, _job(db, user, import_id), triggered_by=f"user:{user.id}", dry_run=True)


@router.post("/imports/{import_id}/run")
def run(import_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    job = _job(db, user, import_id)
    if job.status != "active":
        raise HTTPException(status_code=409, detail="La importación está en pausa")
    return svc.execute(db, job, triggered_by=f"user:{user.id}")


@router.get("/imports/{import_id}/runs")
def runs(import_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    job = _job(db, user, import_id)
    return [{"id": r.id, "status": r.status, "rows_read": r.rows_read, "created": r.created, "updated": r.updated, "unchanged": r.unchanged,
             "failed": r.failed, "errors": json.loads(r.errors_json) if r.errors_json else [], "triggered_by": r.triggered_by,
             "started_at": r.started_at, "finished_at": r.finished_at}
            for r in db.query(DbImportRun).filter(DbImportRun.import_id == job.id).order_by(DbImportRun.started_at.desc()).limit(50).all()]
