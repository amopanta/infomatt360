"""
Proyecto: InfoMatt360
Modulo: Runtime API
Responsabilidad: Exponer endpoints para renderizar, guardar y consultar formularios Runtime.
Dependencias: FastAPI, servicios Runtime y RuntimeRecord.
Notas: Este modulo cierra el flujo MVP Builder -> Runtime -> Guardar -> Consultar.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.api_key_auth import require_api_key_permission
from app.api.deps import get_current_user
from app.api.permissions import require_any_project_permission, require_project_permission
from app.core.permissions import BULK_ADMIN_PERMISSIONS, RECORDS_WRITE
from app.db.session import get_db
from app.models.builder import BuilderTemplate
from app.models.identity import User
from app.schemas.api_key import ApiKeyAuthContext
from app.schemas.runtime import RuntimeTemplate
from app.schemas.runtime_record import RuntimeBulkJobDetail, RuntimeBulkJobRead, RuntimeBulkJobSummary, RuntimeBulkSaveRequest, RuntimeBulkSaveResponse, RuntimeRecordCreate, RuntimeRecordFieldCorrection, RuntimeRecordPage, RuntimeRecordRead
from app.services.runtime_record_service import runtime_record_service
from app.services.runtime_service import runtime_service
from app.services.assignment_service import assignment_service

router = APIRouter()


def require_template_access(db: Session, user_id: str, template_id: str) -> BuilderTemplate:
    """Valida existencia de plantilla y acceso del usuario a su proyecto."""
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    if not assignment_service.user_has_project_access(db, user_id, template.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return template


@router.get("/template/{template_id}", response_model=RuntimeTemplate)
def get_template_runtime(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RuntimeTemplate:
    """Entrega el JSON runtime de una plantilla del Builder.

    Este endpoint permite que el frontend renderice un formulario sin conocer
    las tablas internas del constructor.
    """
    require_template_access(db, current_user.id, template_id)
    return runtime_service.build_template_runtime(db, template_id)


@router.post("/save", response_model=RuntimeRecordRead)
def save_runtime_record(payload: RuntimeRecordCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RuntimeRecordRead:
    """Guarda una respuesta capturada desde el formulario Runtime."""
    template = require_template_access(db, current_user.id, payload.template_id)
    if template.project_id != payload.project_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La plantilla no pertenece al proyecto indicado")
    try:
        return runtime_record_service.save_record(db, payload, current_user.id)
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "no existe" in lowered:
            code = status.HTTP_404_NOT_FOUND
        elif "otro proyecto" in lowered:
            code = status.HTTP_403_FORBIDDEN
        else:
            code = status.HTTP_422_UNPROCESSABLE_CONTENT
        raise HTTPException(status_code=code, detail=detail) from exc


@router.post("/bulk/save", response_model=RuntimeBulkSaveResponse)
def save_runtime_records_bulk(
    payload: RuntimeBulkSaveRequest,
    db: Session = Depends(get_db),
    api_key: ApiKeyAuthContext = Depends(require_api_key_permission(RECORDS_WRITE)),
) -> RuntimeBulkSaveResponse:
    """Guarda registros por lotes usando API key.

    Este endpoint reduce millones de llamadas unitarias a cargas por paquetes.
    """
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == payload.template_id).first()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    if payload.project_id != api_key.project_id or template.project_id != api_key.project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key sin acceso al proyecto indicado")
    try:
        return runtime_record_service.save_records_bulk(db, payload, None)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/bulk/jobs", response_model=list[RuntimeBulkJobRead])
def list_runtime_bulk_jobs(
    template_id: str | None = Query(default=None, max_length=36),
    status_filter: str | None = Query(default=None, alias="status", max_length=40),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    api_key: ApiKeyAuthContext = Depends(require_api_key_permission(RECORDS_WRITE)),
) -> list[RuntimeBulkJobRead]:
    """Lista lotes masivos procesados para seguimiento de integraciones."""
    return runtime_record_service.list_bulk_jobs(db, api_key.project_id, template_id=template_id, status=status_filter, limit=limit, offset=offset)


@router.get("/bulk/jobs/{job_id}", response_model=RuntimeBulkJobDetail)
def get_runtime_bulk_job(
    job_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKeyAuthContext = Depends(require_api_key_permission(RECORDS_WRITE)),
) -> RuntimeBulkJobDetail:
    """Consulta el resultado de un lote masivo por su identificador."""
    job = runtime_record_service.get_bulk_job(db, api_key.project_id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado")
    return job


@router.post("/bulk/jobs/{job_id}/process", response_model=RuntimeBulkJobDetail)
def process_runtime_bulk_job(
    job_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKeyAuthContext = Depends(require_api_key_permission(RECORDS_WRITE)),
) -> RuntimeBulkJobDetail:
    """Procesa un lote encolado y devuelve su resultado consolidado."""
    try:
        job = runtime_record_service.process_bulk_job(db, api_key.project_id, job_id, None)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado")
    return job


@router.get("/bulk/admin/{project_id}/jobs", response_model=list[RuntimeBulkJobRead])
def list_runtime_bulk_jobs_admin(
    project_id: str,
    template_id: str | None = Query(default=None, max_length=36),
    status_filter: str | None = Query(default=None, alias="status", max_length=40),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RuntimeBulkJobRead]:
    """Lista lotes masivos desde el panel administrativo del proyecto."""
    require_any_project_permission(db, current_user.id, project_id, BULK_ADMIN_PERMISSIONS)
    return runtime_record_service.list_bulk_jobs(db, project_id, template_id=template_id, status=status_filter, limit=limit, offset=offset)


@router.get("/bulk/admin/{project_id}/summary", response_model=RuntimeBulkJobSummary)
def summarize_runtime_bulk_jobs_admin(
    project_id: str,
    template_id: str | None = Query(default=None, max_length=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RuntimeBulkJobSummary:
    """Resume estado y volumen de lotes masivos del proyecto."""
    require_any_project_permission(db, current_user.id, project_id, BULK_ADMIN_PERMISSIONS)
    return runtime_record_service.summarize_bulk_jobs(db, project_id, template_id=template_id)


@router.get("/bulk/admin/{project_id}/jobs/{job_id}", response_model=RuntimeBulkJobDetail)
def get_runtime_bulk_job_admin(
    project_id: str,
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RuntimeBulkJobDetail:
    """Consulta detalle de lote masivo desde el panel administrativo."""
    require_any_project_permission(db, current_user.id, project_id, BULK_ADMIN_PERMISSIONS)
    job = runtime_record_service.get_bulk_job(db, project_id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado")
    return job


@router.post("/bulk/admin/{project_id}/jobs/{job_id}/process", response_model=RuntimeBulkJobDetail)
def process_runtime_bulk_job_admin(
    project_id: str,
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RuntimeBulkJobDetail:
    """Procesa un lote encolado desde el panel administrativo."""
    require_any_project_permission(db, current_user.id, project_id, BULK_ADMIN_PERMISSIONS)
    try:
        job = runtime_record_service.process_bulk_job(db, project_id, job_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado")
    return job


@router.get("/bulk/admin/{project_id}/jobs/{job_id}/errors.csv")
def export_runtime_bulk_job_errors_admin(
    project_id: str,
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Exporta errores de un lote masivo en CSV para depuracion operativa."""
    require_any_project_permission(db, current_user.id, project_id, BULK_ADMIN_PERMISSIONS)
    content = runtime_record_service.export_bulk_job_errors_csv(db, project_id, job_id)
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado")
    safe_job_id = "".join(character if character.isascii() and (character.isalnum() or character in "-_") else "_" for character in job_id)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="bulk_errors_{safe_job_id}.csv"'},
    )


@router.get("/record/{record_id}", response_model=RuntimeRecordRead)
def get_runtime_record(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RuntimeRecordRead:
    """Consulta una respuesta Runtime por identificador."""
    record = runtime_record_service.get_record(db, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    if not assignment_service.user_has_project_access(db, current_user.id, record.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return record


@router.get("/record/{record_id}/children/{field_name}", response_model=list[RuntimeRecordRead])
def list_runtime_record_children(record_id: str, field_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[RuntimeRecordRead]:
    """Lista las filas hijas reales de un campo LINKED_SUBFORM (ver docs/97).

    Distinto de un REPEAT embebido: cada hijo es un `RuntimeRecord` propio,
    capturado con su propia plantilla hija.
    """
    parent = runtime_record_service.get_record(db, record_id)
    if parent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    if not assignment_service.user_has_project_access(db, current_user.id, parent.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return runtime_record_service.list_child_records(db, record_id, field_name)


@router.patch("/record/{record_id}/correction", response_model=RuntimeRecordRead)
def correct_runtime_record_field(record_id: str, payload: RuntimeRecordFieldCorrection, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RuntimeRecordRead:
    """Corrige el valor de un campo de un registro devuelto (enlace magico).

    Requiere el mismo permiso que capturar registros (`records.write`): es
    la accion que hoy falta para que un gestor realmente pueda arreglar el
    campo senalado por un revisor, en vez de solo poder marcar
    "corregido" sin cambiar ningun valor.
    """
    record = runtime_record_service.get_record(db, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    require_project_permission(db, current_user.id, record.project_id, RECORDS_WRITE)
    try:
        return runtime_record_service.correct_field(db, record_id, payload, current_user.id)
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "no encontrado" in lowered:
            code = status.HTTP_404_NOT_FOUND
        elif "modificado por otro usuario" in lowered:
            code = status.HTTP_409_CONFLICT
        else:
            code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=detail) from exc


@router.get("/template/{template_id}/records", response_model=list[RuntimeRecordRead])
def list_runtime_records(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[RuntimeRecordRead]:
    """Lista respuestas guardadas para una plantilla Runtime."""
    require_template_access(db, current_user.id, template_id)
    return runtime_record_service.list_template_records(db, template_id)


@router.get("/template/{template_id}/records/search", response_model=RuntimeRecordPage)
def search_runtime_records(
    template_id: str,
    search: str | None = Query(default=None, max_length=120),
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RuntimeRecordPage:
    """Consulta registros Runtime con busqueda, filtro de estado y paginacion."""
    require_template_access(db, current_user.id, template_id)
    return runtime_record_service.search_template_records(db, template_id, search=search, status=status_filter, limit=limit, offset=offset)


@router.get("/template/{template_id}/records/export.csv")
def export_runtime_records(
    template_id: str,
    search: str | None = Query(default=None, max_length=120),
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    template = require_template_access(db, current_user.id, template_id)
    content = runtime_record_service.export_template_csv(db, template_id, search=search, status=status_filter)
    safe_name = "".join(character if character.isascii() and (character.isalnum() or character in "-_") else "_" for character in template.name).strip("_") or "registros"
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.csv"'},
    )
