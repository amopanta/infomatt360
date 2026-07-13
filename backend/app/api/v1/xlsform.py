from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import BUILDER_WRITE
from app.db.session import get_db
from app.models.builder import BuilderTemplate
from app.models.identity import User
from app.schemas.xlsform import XlsformImportResult
from app.services.form_import_router import import_form
from app.services.xlsform_export_service import xlsform_export_service

router = APIRouter()


@router.post("/import", response_model=XlsformImportResult, summary="Importar formulario (XLSForm/ODK/KoboToolbox, SurveyMonkey o LimeSurvey)")
async def import_xlsform(
    project_id: str = Form(...),
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> XlsformImportResult:
    require_project_permission(db, current_user.id, project_id, BUILDER_WRITE)
    content = await upload.read()
    return import_form(db, project_id, upload.filename or "formulario.xlsx", content, current_user.id)


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
