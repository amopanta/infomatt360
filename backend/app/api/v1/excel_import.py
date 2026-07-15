from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.excel_import import ExcelImportJobRead, ExcelImportMappingUpdate
from app.services.assignment_service import assignment_service
from app.services.excel_import_service import excel_import_service

router = APIRouter()


@router.post("/upload", response_model=ExcelImportJobRead, summary="Subir Excel y generar previsualizacion")
async def upload_excel_import(
    project_id: str = Form(...),
    entity_type: str = Form(...),
    template_id: str | None = Form(None),
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExcelImportJobRead:
    require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
    content = await upload.read()
    return excel_import_service.upload_and_preview(db, project_id, entity_type, upload.filename or "archivo.xlsx", content, current_user.id, template_id)


@router.patch("/{job_id}/mapping", response_model=ExcelImportJobRead, summary="Confirmar mapeo de columnas")
def confirm_mapping(job_id: str, payload: ExcelImportMappingUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ExcelImportJobRead:
    job = excel_import_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado")
    require_project_permission(db, current_user.id, job.project_id, IDENTITY_USERS_MANAGE)
    return excel_import_service.confirm_mapping(db, job_id, payload.column_mapping)


@router.post("/{job_id}/approve", response_model=ExcelImportJobRead, summary="Aprobar e importar el lote")
def approve_excel_import(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ExcelImportJobRead:
    job = excel_import_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado")
    require_project_permission(db, current_user.id, job.project_id, IDENTITY_USERS_MANAGE)
    return excel_import_service.approve_and_import(db, job_id, current_user.id)


@router.get("/{job_id}", response_model=ExcelImportJobRead, summary="Consultar estado del lote")
def get_excel_import(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ExcelImportJobRead:
    job = excel_import_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado")
    if not assignment_service.user_has_project_access(db, current_user.id, job.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return job


@router.get("/project/{project_id}", response_model=list[ExcelImportJobRead], summary="Listar lotes de carga Excel por proyecto")
def list_excel_imports(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ExcelImportJobRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return excel_import_service.list_jobs(db, project_id)
