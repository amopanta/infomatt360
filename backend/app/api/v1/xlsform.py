import hashlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import BUILDER_WRITE
from app.db.session import get_db
from app.models.builder import BuilderTemplate, BuilderVersion
from app.models.identity import User
from app.schemas.xlsform import FormVersionSummary, XlsformImportResult, XlsformPreview
from app.services.form_import_router import import_form
from app.services.xlsform_export_service import xlsform_export_service
from app.services.form_import_common import restore_template_version
from app.schemas.runtime import RuntimeTemplate
from app.services.form_import_router import detect_format
from app.services.xlsform_preview_service import preview_xlsform, template_fingerprint

router = APIRouter()


@router.post("/preview", response_model=XlsformPreview)
async def preview_import(
    project_id: str = Form(...), upload: UploadFile = File(...), replace_template_id: str | None = Form(default=None),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
) -> XlsformPreview:
    require_project_permission(db, current_user.id, project_id, BUILDER_WRITE)
    content = await upload.read(10_000_001)
    if len(content) > 10_000_000:
        raise HTTPException(status_code=413, detail="El XLSForm supera 10 MB")
    if detect_format(content) != "xlsform":
        raise HTTPException(status_code=422, detail="La comparación previa está disponible para XLSForm/ODK/KoBo con hoja survey")
    return preview_xlsform(db, project_id, upload.filename or "formulario.xlsx", content, replace_template_id)


@router.get("/versions/{template_id}", response_model=list[FormVersionSummary])
def list_form_versions(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FormVersionSummary]:
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    rows = db.query(BuilderVersion).filter(BuilderVersion.template_id == template_id).order_by(BuilderVersion.version_number.desc()).all()
    result = []
    for row in rows:
        snapshot = RuntimeTemplate.model_validate_json(row.schema_json)
        count = sum(len(column.components) for page in snapshot.pages for section in page.sections for item in section.rows for column in item.columns)
        result.append(FormVersionSummary(id=row.id, version_number=row.version_number, status=row.status, created_at=row.created_at, question_count=count))
    return result


@router.post("/versions/{template_id}/{version_id}/restore", response_model=FormVersionSummary)
def restore_form_version(template_id: str, version_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FormVersionSummary:
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    restore_template_version(db, template_id, version_id)
    version = db.query(BuilderVersion).filter(BuilderVersion.id == version_id).first()
    snapshot = RuntimeTemplate.model_validate_json(version.schema_json)
    count = sum(len(column.components) for page in snapshot.pages for section in page.sections for item in section.rows for column in item.columns)
    return FormVersionSummary(id=version.id, version_number=version.version_number, status=version.status, created_at=version.created_at, question_count=count)


@router.post("/import", response_model=XlsformImportResult, summary="Importar formulario (XLSForm/ODK/KoboToolbox, SurveyMonkey o LimeSurvey), o reemplazar una plantilla existente en el mismo lugar")
async def import_xlsform(
    project_id: str = Form(...),
    upload: UploadFile = File(...),
    replace_template_id: str | None = Form(default=None),
    expected_file_sha256: str | None = Form(default=None),
    expected_target_sha256: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> XlsformImportResult:
    require_project_permission(db, current_user.id, project_id, BUILDER_WRITE)
    content = await upload.read()
    if expected_file_sha256 and hashlib.sha256(content).hexdigest() != expected_file_sha256:
        raise HTTPException(status_code=409, detail="El archivo cambió desde la validación previa")
    if replace_template_id and expected_target_sha256 and template_fingerprint(db, replace_template_id) != expected_target_sha256:
        raise HTTPException(status_code=409, detail="El formulario cambió desde la validación previa; vuelve a comparar")
    if detect_format(content) == "xlsform":
        preview = preview_xlsform(db, project_id, upload.filename or "formulario.xlsx", content, replace_template_id)
        if preview.errors:
            raise HTTPException(status_code=422, detail={"errors": preview.errors})
    return import_form(db, project_id, upload.filename or "formulario.xlsx", content, current_user.id, replace_template_id)


@router.get("/export/{template_id}", summary="Exportar plantilla a XLSForm (.xlsx)")
def export_xlsform(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    content = xlsform_export_service.export_xlsform(db, template_id)
    safe_name = "".join(character if character.isascii() and (character.isalnum() or character in "-_") else "_" for character in template.name).strip("_") or "formulario"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.xlsx"'},
    )


@router.get("/master-template", summary="Descargar plantilla maestra XLSForm con todos los tipos de campo soportados")
def download_master_template(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    require_project_permission(db, current_user.id, project_id, BUILDER_WRITE)
    content = xlsform_export_service.build_master_template()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="plantilla_maestra_infomatt360.xlsx"'},
    )
